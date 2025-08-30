# main.py

import uvicorn
import json
import asyncio
import os
# <--- ADICIONADO: Importações para upload de arquivos --->
from fastapi import UploadFile, File
import uuid
import utils
from context_cache import file_contexts
# <--- FIM DA ADIÇÃO --->
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
from typing import Optional, List 

# Segurança e Autenticação
from passlib.context import CryptContext
from jose import jwt, JWTError
from dotenv import load_dotenv
# Módulos do projeto e conexões
from supabase import create_client, Client
from config import openai_client, supabase, SECRET_KEY, ALGORITHM
import core_logic

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# ==========================================================
# === CONFIGURAÇÃO DE SEGURANÇA
# ==========================================================
ACCESS_TOKEN_EXPIRE_MINUTES = 60
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ==========================================================
# === MODELOS DE DADOS (PYDANTIC)
# ==========================================================
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    dias_duracao: Optional[int] = 30
    acesso_vitalicio: Optional[bool] = False

class UserUpdate(BaseModel):
    nome: Optional[str] = None
    data_expiracao: Optional[datetime] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    accessToken: str
    token_type: str = "bearer"

class PreferenciaCreate(BaseModel):
    topico: str
    valor: str

class PreferenciaUpdate(BaseModel):
    valor: str

class TitleGenerationInput(BaseModel):
    history: list

class TitleGenerationOutput(BaseModel):
    title: str
    
# ==========================================================
# === INICIALIZAÇÃO DA APLICAÇÃO
# ==========================================================
app = FastAPI(title="Jarvis IA Backend")

origins = [
    # URLs para desenvolvimento local
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    
    # URL exata do seu frontend em produção no Render
    "https://jarvis-ia-frontend.onrender.com", 
    
    # Padrão curinga para permitir qualquer subdomínio do serviço no Render    
    "*.onrender.com" 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================
# === FUNÇÕES DE DEPENDÊNCIA E SEGURANÇA
# ==========================================================
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user_email(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Could not validate credentials")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

def get_current_admin_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Acesso negado. Requer privilégios de administrador.")
        return payload
    except JWTError:
        raise HTTPException(status_code=403, detail="Token inválido ou expirado.")

# ==========================================================
# === ENDPOINTS GERAIS E DE AUTENTICAÇÃO
# ==========================================================
@app.get("/")
async def health_check():
    return {"status": "ok"}

@app.post("/api/auth/login", response_model=Token)
async def login_for_access_token(form_data: UserLogin):
    response = supabase.table('usuarios').select("email, senha_hash, role").eq('email', form_data.email).execute()
    if not response.data:
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")
    user = response.data[0]
    if not verify_password(form_data.password, user["senha_hash"]):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")
    access_token = create_access_token(data={"sub": user["email"], "role": user["role"]})
    return {"accessToken": access_token, "token_type": "bearer"}

# ==========================================================
# === ENDPOINTS DE ADMINISTRAÇÃO
# ==========================================================
@app.get("/api/admin/users")
async def get_all_users(admin_user: dict = Depends(get_current_admin_user)):
    response = supabase.table('usuarios').select("nome, email, role, data_expiracao").execute()
    return response.data

@app.post("/api/admin/users")
async def create_user_subscription(user: UserCreate, admin_user: dict = Depends(get_current_admin_user)):
    hashed_password = pwd_context.hash(user.password)
    if user.acesso_vitalicio:
        expiracao = datetime(9999, 12, 31)
    else:
        expiracao = datetime.now(timezone.utc) + timedelta(days=user.dias_duracao)
    
    response = supabase.table('usuarios').insert({
        "nome": user.name, "email": user.email, "senha_hash": hashed_password, 
        "role": "user", "data_expiracao": expiracao.isoformat()
    }).execute()
    
    if "unique constraint" in str(response.data):
         raise HTTPException(status_code=400, detail="E-mail já registrado.")
    if not response.data:
        raise HTTPException(status_code=400, detail="E-mail já pode estar em uso ou outro erro ocorreu.")
    return {"message": f"Usuário {user.name} criado com sucesso."}

@app.put("/api/admin/users/{email}")
async def update_user(email: str, user_update: UserUpdate, admin_user: dict = Depends(get_current_admin_user)):
    update_data = user_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado fornecido para atualização.")
        
    # A conversão da data antes de enviar para o Supabase
    if 'data_expiracao' in update_data and update_data['data_expiracao'] is not None:
        update_data['data_expiracao'] = update_data['data_expiracao'].isoformat()
    # ==========================================

    response = supabase.table('usuarios').update(update_data).eq('email', email).execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return {"message": f"Usuário {email} atualizado com sucesso."}

@app.delete("/api/admin/users/{email}")
async def delete_user(email: str, admin_user: dict = Depends(get_current_admin_user)):
    
    supabase.table('preferencias').delete().eq('user_email', email).execute()

    
    response = supabase.table('usuarios').delete().eq('email', email).execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return {"message": f"Usuário {email} e todas as suas preferências foram excluídos com sucesso."}
        
# ==========================================================
# === ENDPOINTS DE PREFERÊNCIAS
# ==========================================================
@app.get("/api/preferences")
async def get_user_preferences(user_email: str = Depends(get_current_user_email)):
    response = supabase.table('preferencias').select('id, topico, valor').eq('user_email', user_email).execute()
    return response.data

@app.post("/api/preferences")
async def create_user_preference(preferencia: PreferenciaCreate, user_email: str = Depends(get_current_user_email)):
    response = supabase.table('preferencias').insert({
        "user_email": user_email, "topico": preferencia.topico.strip().lower(), "valor": preferencia.valor.strip()
    }).execute()
    if "unique constraint" in str(response.data):
        raise HTTPException(status_code=400, detail="Este tópico de preferência já existe.")
    return response.data[0]

@app.put("/api/preferences/{pref_id}")
async def update_user_preference(pref_id: int, preferencia: PreferenciaUpdate, user_email: str = Depends(get_current_user_email)):
    response = supabase.table('preferencias').update({"valor": preferencia.valor}).eq('id', pref_id).eq('user_email', user_email).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Preferência não encontrada ou não pertence ao usuário.")
    return response.data[0]

@app.delete("/api/preferences/{pref_id}")
async def delete_user_preference(pref_id: int, user_email: str = Depends(get_current_user_email)):
    response = supabase.table('preferencias').delete().eq('id', pref_id).eq('user_email', user_email).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Preferência não encontrada ou não pertence ao usuário.")
    return {"ok": True}

# ==========================================================
# === ENDPOINTS PRINCIPAIS DA APLICAÇÃO (IA)
# ==========================================================

# <--- Novo endpoint para upload de arquivos --->
@app.post("/chat/upload-files")
async def handle_file_upload(files: List[UploadFile] = File(...)):
    conteudo_agregado = []
    nomes_arquivos = []

    for file in files:
        nomes_arquivos.append(file.filename)
        texto_extraido = await utils.extrair_texto_de_upload(file)
        conteudo_agregado.append(
            f"--- INÍCIO DO ARQUIVO: {file.filename} ---\n\n{texto_extraido}\n\n--- FIM DO ARQUIVO: {file.filename} ---"
        )
    
    contexto_final = "\n\n".join(conteudo_agregado)
    context_id = str(uuid.uuid4())
    file_contexts[context_id] = contexto_final # Armazena em memória

    return {"context_id": context_id, "filenames": nomes_arquivos}

@app.get("/chat/stream")
async def handle_chat_stream(message: str, history: str, token: str, context_id: Optional[str] = None):
    return StreamingResponse(
        core_logic.stream_chat_generator(message, history, token, context_id),
        media_type="text/event-stream"
    )

@app.post("/chat/generate-title", response_model=TitleGenerationOutput)
async def handle_generate_title(payload: TitleGenerationInput):
    titulo = core_logic.gerar_titulo_conversa(payload.history)
    return TitleGenerationOutput(title=titulo)

# ==========================================================
# === Bloco para iniciar o servidor
# ==========================================================
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)