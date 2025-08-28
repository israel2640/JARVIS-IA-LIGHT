# core_logic.py
import json
import asyncio
from jose import jwt, JWTError
import requests

# Módulos e conexões do projeto
from config import openai_client, supabase, SERPER_API_KEY, SECRET_KEY, ALGORITHM

# ==========================================================
# === FUNÇÕES DE LÓGICA DO PROJETO
# ==========================================================

def get_user_email_from_token(token: str):
    """Descodifica o token JWT para extrair o e-mail do utilizador de forma segura."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise ValueError("Token inválido: e-mail não encontrado.")
        return email
    except JWTError as e:
        raise ValueError(f"Token inválido ou expirado: {e}")

def carregar_preferencias_do_usuario(email: str):
    """Busca as preferências de um utilizador no Supabase."""
    try:
        response = supabase.table('preferencias').select('topico, valor').eq('user_email', email).execute()
        if response.data:
            return {item['topico']: item['valor'] for item in response.data}
    except Exception as e:
        print(f"Erro ao carregar preferências: {e}")
    return {}

def adicionar_ou_atualizar_preferencia_manual(email_usuario: str, topico: str, valor: str):
    """
    Adiciona ou atualiza uma preferência para um utilizador manualmente.
    Retorna (True, "Mensagem de sucesso") ou (False, "Mensagem de erro").
    """
    if not email_usuario or not topico or not valor:
        return (False, "E-mail, tópico e valor são obrigatórios.")
    try:
        dados_para_upsert = {
            "user_email": email_usuario,
            "topico": topico.strip().lower(),
            "valor": valor.strip()
        }
        response = supabase.table('preferencias').upsert(
            dados_para_upsert, on_conflict='user_email, topico'
        ).execute()
        if response.data:
            mensagem = f"Preferência '{topico}' guardada com sucesso para {email_usuario}."
            return (True, mensagem)
        else:
            return (False, "Falha ao guardar preferência no Supabase.")
    except Exception as e:
        return (False, f"Erro inesperado ao guardar preferência: {e}")

def precisa_buscar_na_web(pergunta: str):
    """Usa a IA para determinar se uma pergunta requer uma busca na web."""
    try:
        prompt = f"""
        Analise a pergunta do utilizador. A resposta exige conhecimento sobre eventos ou informações muito recentes (ocorridos hoje ou nos últimos dias)?
        Perguntas sobre notícias, resultados desportivos, cotações de moedas, previsão do tempo ou eventos atuais exigem uma busca na web.
        Responda APENAS com 'SIM' ou 'NÃO'.
        Pergunta: "{pergunta}"
        """
        response = openai_client.chat.completions.create(
            model='gpt-4o-mini', messages=[{"role": "user", "content": prompt}], max_tokens=3, temperature=0
        )
        decisao = response.choices[0].message.content.strip().upper()
        return "SIM" in decisao
    except Exception:
        return False

def buscar_na_internet(query: str):
    """Busca na internet usando a API da Serper."""
    if not SERPER_API_KEY: return "ERRO: A chave SERPER_API_KEY não está configurada."
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query, "gl": "br", "hl": "pt-br"})
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        results = response.json()
        contexto = ""
        if "organic" in results:
            for item in results["organic"][:5]:
                contexto += f"* [{item.get('title', 'N/A')}]({item.get('link', '#')}) - {item.get('snippet', 'N/A').replace('\n', ' ')}\n"
        return contexto if contexto else "Nenhum resultado relevante encontrado."
    except Exception as e:
        return f"Ocorreu um erro ao tentar buscar na web: {e}"

def gerar_titulo_conversa(historico: list):
    """Usa a IA para criar um título curto para a conversa."""
    if not historico or len(historico) < 2: return "Novo Chat"
    conversa_inicial = "\n".join([f"{msg['role']}: {msg['content']}" for msg in historico[:4]])
    prompt = f"""Crie um título curto e conciso em português (máximo 5 palavras) para a seguinte conversa. Responda APENAS com o título.\nCONVERSA:\n{conversa_inicial}\nTÍTULO:"""
    try:
        resposta_modelo = openai_client.chat.completions.create(
            model='gpt-4o-mini', messages=[{"role": "user", "content": prompt}], max_tokens=15
        )
        return resposta_modelo.choices[0].message.content.strip().replace('"', '')
    except Exception:
        return "Chat"

async def stream_chat_generator(message: str, history_json: str, token: str):
    """
    Função geradora final que busca preferências e gera a resposta da IA.
    """
    try:
        user_email = get_user_email_from_token(token)
        preferencias = carregar_preferencias_do_usuario(user_email)

        if precisa_buscar_na_web(message):
            contexto_da_web = buscar_na_internet(message)
            prompt_sistema = f"""
            Você é Jarvis, um assistente de IA que resume notícias da web.
            INSTRUÇÕES CRÍTICAS: Responda em português. Comece com uma introdução.
            Os resultados da pesquisa já estão no formato de link Markdown `* [Título](URL) - Resumo`. A sua resposta final DEVE manter este formato de link.
            RESULTADOS DA PESQUISA:
            {contexto_da_web}
            """
            mensagens_para_api = [{"role": "system", "content": prompt_sistema}]
        else:
            history = json.loads(history_json)
            prompt_sistema = "Você é Jarvis, um assistente prestável e amigável."
            if preferencias:
                nome_usuario = preferencias.get('nome', 'utilizador')
                prompt_sistema += f"\n\nContexto sobre o utilizador ({nome_usuario.capitalize()}): {json.dumps(preferencias, ensure_ascii=False)}. Use essas informações para personalizar as suas respostas sempre que for relevante."
            
            mensagens_para_api = [{"role": "system", "content": prompt_sistema}]
            mensagens_para_api.extend(history)
            mensagens_para_api.append({"role": "user", "content": message})

        stream = openai_client.chat.completions.create(
            model="gpt-4o", messages=mensagens_para_api, stream=True
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield f"data: {json.dumps({'text': content})}\n\n"
                await asyncio.sleep(0.01)
                
    except Exception as e:
        print(f"Erro no stream: {e}")
        yield f"data: {json.dumps({'error': 'Ocorreu um erro no servidor.'})}\n\n"
