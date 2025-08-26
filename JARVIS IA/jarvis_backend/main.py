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
from jose import jwt
from jose import jwt, JWTError
# Conexão com Supabase
from supabase import create_client, Client

# Importa as funções dos outros módulos
from config import openai_client
import core_logic
import data_analysis
import utils

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# ==========================================================
# === CONFIGURAÇÃO DE SERVIÇOS EXTERNOS
# ==========================================================

# --- SUPABASE ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- SEGURANÇA E AUTENTICAÇÃO ---
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ==========================================================
# === MODELOS DE DADOS (PYDANTIC)
# ==========================================================

# --- Modelos para o Chat e IA ---
class ChatInput(BaseModel):
    message: str
    history: list = []

class ImagineInput(BaseModel):
    prompt: str

class ImagineOutput(BaseModel):
    image_base64: str

class TitleGenerationInput(BaseModel):
    history: list

class TitleGenerationOutput(BaseModel):
    title: str

class CodeGenInput(BaseModel):
    prompt: str

class CodeGenOutput(BaseModel):
    structured_content: str

# --- Modelos para Autenticação e Usuários ---
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

# ... (outros modelos de IA como ChatInput, ImagineInput, etc.)

# ==========================================================
# === INICIALIZAÇÃO DA APLICAÇÃO
# ==========================================================
app = FastAPI(title="Jarvis IA Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://jarvis-ia-frontend.onrender.com"],
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
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_admin_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # ...
        return payload
    except JWTError: 
        raise HTTPException(status_code=403, detail="Token inválido ou expirado.")

# ==========================================================
# === ENDPOINTS DE AUTENTICAÇÃO E ADMINISTRAÇÃO
# ==========================================================

@app.post("/api/auth/login", response_model=Token)
async def login_for_access_token(form_data: UserLogin):
    try:
        response = supabase.table('usuarios').select("email, senha_hash, role").eq('email', form_data.email).execute()
        if not response.data:
            raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")
        
        user = response.data[0]
        if not verify_password(form_data.password, user["senha_hash"]):
            raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")
        
        access_token = create_access_token(
            data={"sub": user["email"], "role": user["role"]}
        )
        return {"accessToken": access_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        response = supabase.table('usuarios').insert({
            "nome": user.name,
            "email": user.email,
            "senha_hash": hashed_password,
            "role": "user",
            "data_expiracao": expiracao.isoformat()
        }).execute()
        
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
# === ENDPOINTS PRINCIPAIS DA APLICAÇÃO (IA)
# ==========================================================

# Cole este bloco ANTES da linha 'if __name__ == "__main__":'

# ==========================================================
# === ENDPOINTS PRINCIPAIS DA APLICAÇÃO (IA)
# ==========================================================

async def stream_chat_generator(message: str, history_json: str):
    """
    Função geradora que detecta o idioma, envia como metadado,
    e depois transmite a resposta da IA.
    """
    try:
        idioma_detectado = utils.detectar_idioma_com_ia(message)
        yield f"event: metadata\ndata: {json.dumps({'lang': idioma_detectado})}\n\n"

        history = json.loads(history_json)
        mensagens_para_api = [{"role": "system", "content": "Você é Jarvis, um assistente prestativo."}]
        mensagens_para_api.extend(history)
        mensagens_para_api.append({"role": "user", "content": message})

        stream = openai_client.chat.completions.create(
            model="gpt-5-nano",
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


# --- Bloco para iniciar o servidor ---
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)