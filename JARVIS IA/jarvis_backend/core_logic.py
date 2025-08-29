# core_logic.py
import json
import asyncio
from jose import jwt, JWTError
import requests
from typing import Optional

# Módulos e conexões do projeto
from config import openai_client, supabase, SERPER_API_KEY, SECRET_KEY, ALGORITHM
from context_cache import file_contexts

# ==========================================================
# === FUNÇÕES DE LÓGICA DO PROJETO
# ==========================================================

# core_logic.py
import json
import asyncio
from jose import jwt, JWTError
import requests

# Módulos e conexões do projeto
from utils import detectar_idioma_com_ia
from config import openai_client, supabase, SERPER_API_KEY, SECRET_KEY, ALGORITHM
from context_cache import file_contexts

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
    """Usa a IA para determinar se uma pergunta requer uma busca na web,
    com uma verificação prioritária para uma lista expandida de palavras-chave."""
    
    pergunta_lower = pergunta.lower()
    
    # --- LISTA DE PALAVRAS-CHAVE EXPANDIDA ---
    palavras_chave_busca = [
        # Tempo e Data
        "hora", "horas", "horário", "que horas são", "data de hoje",
        # Notícias
        "notícia", "notícias", "últimas sobre", "manchetes de hoje", "resumo de notícias",
        # Clima
        "previsão do tempo", "temperatura em", "clima em", "vai chover",
        # Esportes
        "resultado do jogo", "placar do jogo", "quem ganhou", "próxima partida",
        # Finanças
        "cotação do dólar", "preço das ações", "valor do euro", "bolsa de valores"
    ]

    # Verifica se alguma das palavras-chave está na pergunta
    triggered_keyword = next((palavra for palavra in palavras_chave_busca if palavra in pergunta_lower), None)
    if triggered_keyword:
        print(f"[DEBUG Web Search] Palavra-chave '{triggered_keyword}' detectada. Forçando busca na web.")
        return True
    # --- FIM DA VERIFICAÇÃO POR PALAVRAS-CHAVE ---

    # Se não for uma pergunta com palavra-chave, continua com a verificação da IA como um fallback
    try:
        prompt = f"""
        A pergunta a seguir precisa de informações da internet em tempo real (eventos atuais, política, etc)?
        Responda apenas com uma única palavra: SIM ou NAO.

        Pergunta: "{pergunta}"
        """
        response = openai_client.chat.completions.create(
            model='gpt-4o-mini', messages=[{"role": "user", "content": prompt}], max_tokens=3, temperature=0
        )
        decisao = response.choices[0].message.content.strip().upper()
        
        print(f"[DEBUG Web Search] Decisão da IA para buscar na web: '{decisao}'")
        
        return "SIM" in decisao
    except Exception as e:
        print(f"[ERRO Web Search] Falha ao decidir sobre a busca na web: {e}")
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
                snippet = item.get('snippet', 'N/A')
                snippet_limpo = snippet.replace('\n', ' ')
                contexto += f"* [{item.get('title', 'N/A')}]({item.get('link', '#')}) - {snippet_limpo}\n"
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

# <--- MODIFICADO: A função agora aceita 'context_id' --->
async def stream_chat_generator(message: str, history_json: str, token: str, context_id: str = None):
    """
    Função geradora final que busca preferências, contexto de arquivos e gera a resposta da IA.
    """
    print("\n--- INICIANDO NOVO PEDIDO DE CHAT ---") # <<< DEBUG >>>
    try:
        user_email = get_user_email_from_token(token)
        print(f"[DEBUG] Token decodificado com sucesso. E-mail do utilizador: {user_email}") # <<< DEBUG >>>

        # === NOVO: DETECÇÃO DE IDIOMA NO INÍCIO ===
        idioma_usuario = detectar_idioma_com_ia(message)
        print(f"[DEBUG] Idioma do utilizador detetado: {idioma_usuario}")
        # ==========================================
        
        # === LÓGICA DE PRIORIZAÇÃO DE CONTEXTO ===
        # PASSO 1: Sempre verifica e prioriza o contexto do arquivo, se houver.
        if context_id and context_id in file_contexts:
            print(f"[DEBUG] Contexto de arquivo encontrado para o ID: {context_id}. A usar o arquivo.") # <<< DEBUG >>>
            contexto_arquivo = file_contexts[context_id]
            
            LIMITE_CARACTERES = 20000 * 4
            if len(contexto_arquivo) > LIMITE_CARACTERES:
                contexto_final_para_ia = contexto_arquivo[:LIMITE_CARACTERES]
            else:
                contexto_final_para_ia = contexto_arquivo

            prompt_sistema = (
                f"Você é Jarvis, um assistente prestável e amigável. Responda na língua do utilizador (código: {idioma_usuario}). "
                "Você deve basear sua resposta *primariamente* no conteúdo dos seguintes arquivos fornecidos pelo usuário:\n\n"
                f"--- CONTEÚDO DO ARQUIVO ---\n{contexto_final_para_ia}\n--- FIM DO CONTEÚDO ---\n"
            )
            mensagens_para_api = [{"role": "system", "content": prompt_sistema}]

        # PASSO 2: Se não houver contexto de arquivo, então decide se precisa de busca na web.
        elif precisa_buscar_na_web(message):
            print("[DEBUG] Decisão: Busca na web é necessária. Nenhum arquivo fornecido.") # <<< DEBUG >>>
            contexto_da_web = buscar_na_internet(message)
            prompt_sistema = f"""
            Você é Jarvis, um assistente de IA que resume notícias da web.
            INSTRUÇÕES CRÍTICAS: Responda na língua do utilizador (código: {idioma_usuario}).
            Os resultados da pesquisa já estão no formato de link Markdown `* [Título](URL) - Resumo`. A sua resposta final DEVE manter este formato de link.
            RESULTADOS DA PESQUISA:
            {contexto_da_web}
            """
            mensagens_para_api = [{"role": "system", "content": prompt_sistema}]
            
            # --- NOVO: LÓGICA PARA AJUSTAR A LINGUA DA BUSCA ---
            # Para buscas na web em outras línguas, você precisará modificar a função 'buscar_na_internet'
            # para aceitar 'hl' (host language) e 'gl' (geography language) como parâmetros.
            # No momento, a sua função 'buscar_na_internet' tem esses valores fixos como 'pt-br'
            # e 'br', o que limitaria a busca a resultados em português do Brasil.
            # Isso pode ser uma melhoria futura.
            
        # PASSO 3: Se não houver arquivo nem necessidade de busca na web, usa as preferências do usuário.
        else:
            print("[DEBUG] Decisão: Não é necessária busca na web. A processar com personalização.") # <<< DEBUG >>>
            preferencias = carregar_preferencias_do_usuario(user_email)
            prompt_sistema = f"Você é Jarvis, um assistente prestável e amigável. Responda na língua do utilizador (código: {idioma_usuario})."
            if preferencias:
                print("[DEBUG] Preferências encontradas. A injetar contexto no prompt do sistema.") # <<< DEBUG >>>
                nome_usuario = preferencias.get('nome', 'utilizador')
                prompt_sistema += f"\n\nContexto sobre o utilizador ({nome_usuario.capitalize()}): {json.dumps(preferencias, ensure_ascii=False)}. Use essas informações para personalizar as suas respostas sempre que for relevante."
            else:
                print("[DEBUG] Nenhuma preferência encontrada para este utilizador. A usar prompt padrão.") # <<< DEBUG >>>
            
            mensagens_para_api = [{"role": "system", "content": prompt_sistema}]

        # === FIM DA LÓGICA DE PRIORIZAÇÃO ===

        history = json.loads(history_json)
        mensagens_para_api.extend(history)
        mensagens_para_api.append({"role": "user", "content": message})

        print(f"[DEBUG] Prompt final do sistema enviado para a OpenAI:\n---\n{prompt_sistema}\n---") # <<< DEBUG >>>

        stream = openai_client.chat.completions.create(
            model="gpt-4o-mini", messages=mensagens_para_api, stream=True
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:                
                yield f"data: {json.dumps({'text': content, 'lang': idioma_usuario})}\n\n"
                await asyncio.sleep(0.01)
                
    except Exception as e:
        print(f"[DEBUG CRÍTICO] Ocorreu uma exceção no stream_chat_generator: {e}") # <<< DEBUG >>>
        yield f"data: {json.dumps({'text': f'❌ ERRO INTERNO: Ocorreu um erro no servidor: {e}. Por favor, tente novamente mais tarde.'})}\n\n"