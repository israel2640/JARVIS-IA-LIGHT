# config.py
import os
from openai import OpenAI
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env (para o ambiente local)
load_dotenv()

# Prioriza as chaves de ambiente do servidor de produção (nuvem)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

# Validação para garantir que a chave de API da OpenAI foi carregada
if not OPENAI_API_KEY:
    raise ValueError("Chave de API da OpenAI não encontrada! Verifique suas variáveis de ambiente.")

# Inicializa o cliente da OpenAI que será usado em todo o backend
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Você pode adicionar outras inicializações aqui, como o cliente do S3, etc.