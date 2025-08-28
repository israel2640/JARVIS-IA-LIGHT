# main.py

import uvicorn
import json
import asyncio
import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
from typing import Optional
from dotenv import load_dotenv

# Segurança e Autenticação
from passlib.context import CryptContext
from jose import jwt, JWTError

# Conexão com Supabase
from supabase import create_client, Client

# Importa as funções dos outros módulos
from config import openai_client
import core_logic
# import data_analysis # Removido se não estiver em uso para simplificar
import utils

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# ==========================================================
# === CONFIGURAÇÃO DE SERVIÇOS EXTERNOS
# ==========================================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "sua-chave-secreta-padrao")
ALGORITHM = "HS256"
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
    
class ChatInput(BaseModel):
    message: str
    history: list = []

# ==========================================================
# === INICIALIZAÇÃO DA APLICAÇÃO
# ==========================================================
app = FastAPI(title="Jarvis IA Backend")

# Lista de origens permitidas
origins = [
    "https://jarvis-ia-frontend.onrender.com",
    "http://127.0.0.1:5500",
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
    try:
        response = supabase.table('usuarios').select("email, senha_hash, role").eq('email', form_data.email).execute()
        if not response.data:
            raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")
        user = response.data[0]
        if not verify_password(form_data.password, user["senha_hash"]):
            raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")
        access_token = create_access_token(data={"sub": user["email"], "role": user["role"]})
        return {"accessToken": access_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================================
# === ENDPOINTS DE ADMINISTRAÇÃO
# ==========================================================
@app.get("/api/admin/users")
async def get_all_users(admin_user: dict = Depends(get_current_admin_user)):
    try:
        response = supabase.table('usuarios').select("nome, email, role, data_expiracao").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/users")
async def create_user_subscription(user: UserCreate, admin_user: dict = Depends(get_current_admin_user)):
    hashed_password = pwd_context.hash(user.password)
    if user.acesso_vitalicio:
        expiracao = datetime(9999, 12, 31)
    else:
        expiracao = datetime.now(timezone.utc) + timedelta(days=user.dias_duracao)
    try:
        response = supabase.table('usuarios').insert({"nome": user.name, "email": user.email, "senha_hash": hashed_password, "role": "user", "data_expiracao": expiracao.isoformat()}).execute()
        if not response.data:
            raise HTTPException(status_code=400, detail="E-mail já pode estar em uso ou outro erro ocorreu.")
    except Exception as e:
        if "unique constraint" in str(e):
             raise HTTPException(status_code=400, detail="E-mail já registrado.")
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": f"Usuário {user.name} criado com sucesso."}

@app.put("/api/admin/users/{email}")
async def update_user(email: str, user_update: UserUpdate, admin_user: dict = Depends(get_current_admin_user)):
    try:
        update_data = user_update.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="Nenhum dado fornecido para atualização.")
        response = supabase.table('usuarios').update(update_data).eq('email', email).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        return {"message": f"Usuário {email} atualizado com sucesso."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/users/{email}")
async def delete_user(email: str, admin_user: dict = Depends(get_current_admin_user)):
    try:
        response = supabase.table('usuarios').delete().eq('email', email).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        return {"message": f"Usuário {email} excluído com sucesso."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
# ==========================================================
# === ENDPOINTS DE PREFERÊNCIAS
# ==========================================================
@app.get("/api/preferences")
async def get_user_preferences(user_email: str = Depends(get_current_user_email)):
    try:
        response = supabase.table('preferencias').select('id, topico, valor').eq('user_email', user_email).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/preferences")
async def create_user_preference(preferencia: PreferenciaCreate, user_email: str = Depends(get_current_user_email)):
    try:
        response = supabase.table('preferencias').insert({"user_email": user_email, "topico": preferencia.topico.strip().lower(), "valor": preferencia.valor.strip()}).execute()
        return response.data[0]
    except Exception as e:
        if "unique constraint" in str(e):
            raise HTTPException(status_code=400, detail="Este tópico de preferência já existe.")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/preferences/{pref_id}")
async def update_user_preference(pref_id: int, preferencia: PreferenciaUpdate, user_email: str = Depends(get_current_user_email)):
    try:
        response = supabase.table('preferencias').update({"valor": preferencia.valor}).eq('id', pref_id).eq('user_email', user_email).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Preferência não encontrada ou não pertence ao usuário.")
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/preferences/{pref_id}")
async def delete_user_preference(pref_id: int, user_email: str = Depends(get_current_user_email)):
    try:
        response = supabase.table('preferencias').delete().eq('id', pref_id).eq('user_email', user_email).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Preferência não encontrada ou não pertence ao usuário.")
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================================
# === ENDPOINTS PRINCIPAIS DA APLICAÇÃO (IA)
# ==========================================================
async def stream_chat_generator(message: str, history_json: str):
    try:
        if core_logic.precisa_buscar_na_web(message):
            contexto_da_web = core_logic.buscar_na_internet(message)
            prompt_sistema = f"""
            Você é Jarvis, um assistente de IA que resume notícias da web.
            INSTRUÇÕES CRÍTICAS: Responda em português. Comece com uma introdução.
            Os resultados já estão no formato Markdown `* [Título](URL)`. Sua resposta DEVE manter este formato de link.
            RESULTADOS DA PESQUISA:
            {contexto_da_web}
            """
            mensagens_para_api = [{"role": "system", "content": prompt_sistema}]
        else:
            history = json.loads(history_json)
            prompt_sistema = "Você é Jarvis, um assistente prestativo."
            mensagens_para_api = [{"role": "system", "content": prompt_sistema}]
            mensagens_para_api.extend(history)
            mensagens_para_api.append({"role": "user", "content": message})

        stream = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=mensagens_para_api,
            stream=True,
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield f"data: {json.dumps({'text': content})}\n\n"
                await asyncio.sleep(0.01)
    except Exception as e:
        error_message = json.dumps({"error": f"Ocorreu um erro no servidor: {e}"})
        yield f"data: {error_message}\n\n"

@app.get("/chat/stream")
async def handle_chat_stream(message: str, history: str):
    return StreamingResponse(
        stream_chat_generator(message, history),
        media_type="text/event-stream"
    )

@app.post("/chat/generate-title", response_model=TitleGenerationOutput)
async def handle_generate_title(payload: TitleGenerationInput):
    try:
        titulo = core_logic.gerar_titulo_conversa(payload.history)
        return TitleGenerationOutput(title=titulo)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao gerar o título: {e}")

# ==========================================================
# === Bloco para iniciar o servidor ---
# ==========================================================
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)