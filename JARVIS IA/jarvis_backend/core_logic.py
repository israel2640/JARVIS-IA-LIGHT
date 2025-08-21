# core_logic.py
import json
import requests
import base64
from config import openai_client, SERPER_API_KEY
from utils import detectar_idioma_com_ia, chamar_openai_com_retries
# Importe outras funções do utils se precisar, como carregar_preferencias

# NOTA: As funções `carregar_modelo_embedding` e `inicializar_memoria_dinamica`
# deverão ser chamadas uma vez quando o servidor iniciar (em main.py) e o
# modelo e vetores passados como argumentos para as funções que os usam.

def analisar_metadados_prompt(prompt_usuario):
    # ... (código da função copiado de app.py, usando openai_client) ...
    pass

def responder_com_inteligencia(pergunta_usuario, historico_chat, memoria, preferencias, ultima_emocao):
    # Esta função é a fusão da sua `responder_com_inteligencia` e `processar_entrada_usuario`.
    # Ela não deve ter nenhuma chamada a `st.` (streamlit).
    
    idioma_da_pergunta = detectar_idioma_com_ia(pergunta_usuario)
    # ... (toda a sua lógica de construção de prompt, busca na memória local, etc.) ...

    # A função deve apenas CONSTRUIR o prompt e chamar a IA.
    # A decisão de salvar o chat, etc., fica no endpoint da API em main.py.
    prompt_sistema = "..." # Construa seu prompt aqui
    mensagens_para_api = [{"role": "system", "content": prompt_sistema}]
    mensagens_para_api.extend(historico_chat)

    resposta_modelo = chamar_openai_com_retries(mensagens_para_api)
    
    if resposta_modelo:
        return resposta_modelo.choices[0].message.content
    return "Desculpe, não consegui obter uma resposta no momento."

def gerar_imagem_com_dalle(prompt_para_imagem):
    try:
        response = openai_client.images.generate(
            model="dall-e-3", prompt=prompt_para_imagem, size="1024x1024", n=1
        )
        image_url = response.data[0].url
        image_response = requests.get(image_url)
        image_response.raise_for_status()
        image_base64 = base64.b64encode(image_response.content).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"
    except Exception as e:
        print(f"Erro ao gerar imagem com DALL-E: {e}")
        return None

def buscar_na_internet(pergunta_usuario):
    # ... (código da função copiado de app.py, usando SERPER_API_KEY) ...
    pass

# ==========================================================
# === NOVA FUNÇÃO ADICIONADA CIRURGICAMENTE
# ==========================================================
def gerar_titulo_conversa(historico: list):
    """
    Usa a IA para criar um título curto para a conversa com base nas primeiras mensagens.
    """
    if not historico:
        return "Novo Chat"

    # Pega as 4 primeiras mensagens para ter contexto suficiente
    conversa_inicial = "\n".join(
        [f"{msg['role']}: {msg['content']}" for msg in historico[:4]]
    )

    prompt = f"""
    Abaixo está o início de uma conversa entre um usuário e um assistente de IA.
    Sua tarefa é criar um título curto e conciso em português (máximo de 5 palavras) que resuma o tópico principal.
    Responda APENAS com o título, sem aspas, nenhuma outra palavra ou pontuação.

    CONVERSA:
    {conversa_inicial}

    TÍTULO CURTO:
    """
    try:
        # Usamos um modelo rápido e barato para esta tarefa simples
        resposta_modelo = openai_client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{"role": "user", "content": prompt}],
            max_tokens=15,
        )
        titulo = resposta_modelo.choices[0].message.content.strip().replace('"', '')
        return titulo if titulo else "Chat"
    except Exception as e:
        print(f"Erro ao gerar título: {e}")
        return "Chat"

# ==========================================================

def gerar_pagina_web_completa(descricao_usuario: str):
    """
    Usa a IA com um prompt detalhado para gerar uma página web completa (HTML/CSS/JS)
    com uma estrutura de resposta bem definida em Markdown.
    """
    print(f"Gerando página web completa para: '{descricao_usuario}'")

    # ESTE É O PROMPT QUE FAZ A MÁGICA
    prompt_detalhado = f"""
    Você é um assistente especialista em desenvolvimento web full-stack. Sua tarefa é gerar um exemplo de código completo e funcional com base na solicitação do usuário.

    Você DEVE ESTRITURAR sua resposta OBRIGATORIAMENTE no seguinte formato Markdown, sem nenhuma variação:

    1.  **Introdução:** Comece com uma única frase amigável que descreva o que o código faz.
    2.  **Estrutura de Arquivos:** Forneça uma seção `### Estrutura de Arquivos` mostrando a disposição dos arquivos em um bloco de código.
    3.  **Código-Fonte:** Para cada arquivo (ex: `index.html`, `styles.css`, `script.js`), crie uma seção separada com um cabeçalho numerado (ex: `### 1. `index.html``). Dentro de cada seção, coloque o código completo dentro de um bloco de código Markdown com a linguagem apropriada (ex: ```html ... ```).
    4.  **Como Usar:** Termine com uma seção `### Como Usar` explicando em 2 ou 3 passos simples como executar o projeto.

    NÃO inclua nenhuma outra conversa, explicação ou texto fora desta estrutura.

    ---
    SOLICITAÇÃO DO USUÁRIO: "{descricao_usuario}"
    ---
    """

    try:
        # Usamos um modelo mais capaz para garantir a qualidade da estrutura e do código
        resposta_modelo = openai_client.chat.completions.create(
            model='gpt-4o', # Recomendo um modelo mais forte como gpt-4o para esta tarefa
            messages=[{"role": "user", "content": prompt_detalhado}]
        )
        conteudo_estruturado = resposta_modelo.choices[0].message.content
        return conteudo_estruturado
    except Exception as e:
        print(f"Erro ao gerar página web completa: {e}")
        return "Desculpe, ocorreu um erro ao tentar gerar o código. Por favor, tente novamente."