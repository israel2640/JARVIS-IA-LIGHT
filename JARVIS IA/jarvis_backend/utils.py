# utils.py
import os
import json
import re
import fitz  # PyMuPDF
import docx
import pandas as pd
import requests
import base64
import time
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from openai import RateLimitError
from config import openai_client # Importa o cliente já configurado

# NOTA: As funções de salvar/carregar no GitHub (carregar_dados_do_github, salvar_dados_no_github,
# encrypt_file_content_general, decrypt_file_content_general, salvar_emocoes, carregar_emocoes)
# devem ser movidas para cá do seu arquivo utils.py original.

# --- Funções de Manipulação de Arquivos e Dados ---

def carregar_memoria():
    try:
        with open("memoria_jarvis.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def salvar_memoria(memoria):
    with open("memoria_jarvis.json", "w", encoding="utf-8") as f:
        json.dump(memoria, f, ensure_ascii=False, indent=4)

def extrair_texto_documento(uploaded_file_bytes, filename):
    # Esta função agora recebe os bytes do arquivo e o nome do arquivo
    if filename.endswith(".pdf"):
        texto = ""
        with fitz.open(stream=uploaded_file_bytes, filetype="pdf") as doc:
            for page in doc:
                texto += page.get_text()
        return texto
    # Adicione aqui as outras lógicas para .docx, .txt, etc., adaptando para receber bytes.
    return "Formato de arquivo não suportado."

# --- Funções de Geração (PDF, etc.) ---

def criar_pdf(texto_corpo, titulo_documento):
    pdf = FPDF()
    pdf.add_page()
    script_dir = os.path.dirname(__file__)
    font_path_regular = os.path.join(script_dir, 'assets', 'DejaVuSans.ttf')
    font_path_bold = os.path.join(script_dir, 'assets', 'DejaVuSans-Bold.ttf')
    try:
        pdf.add_font('DejaVu', '', font_path_regular)
        pdf.add_font('DejaVu', 'B', font_path_bold)
        FONT_FAMILY = 'DejaVu'
    except Exception:
        FONT_FAMILY = 'Helvetica'
    pdf.set_font(FONT_FAMILY, 'B', 18)
    pdf.multi_cell(0, 10, titulo_documento, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    pdf.ln(15)
    # ... (resto da sua lógica de formatação do PDF) ...
    return bytes(pdf.output())

# --- Funções Auxiliares de IA ---

def chamar_openai_com_retries(mensagens, modelo="gpt-4o-mini", max_tentativas=3, pausa_segundos=5):
    for tentativa in range(1, max_tentativas + 1):
        try:
            print(f"INFO: Tentativa {tentativa} de chamada à OpenAI com modelo {modelo}")
            resposta = openai_client.chat.completions.create(
                model=modelo,
                messages=mensagens
            )
            return resposta
        except RateLimitError:
            print(f"AVISO: RateLimitError. Tentando novamente em {pausa_segundos}s...")
            time.sleep(pausa_segundos)
        except Exception as e:
            print(f"ERRO: Erro inesperado na chamada da OpenAI: {e}")
            break
    return None

def detectar_idioma_com_ia(texto_usuario):
    if not texto_usuario.strip(): return 'pt'
    try:
        prompt = f"Qual o código de idioma ISO 639-1 do seguinte texto? Responda APENAS com o código de duas letras.\nTexto: \"{texto_usuario}\""
        resposta_modelo = openai_client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5
        )
        idioma = resposta_modelo.choices[0].message.content.strip().lower()
        return idioma if len(idioma) == 2 else 'pt'
    except Exception as e:
        print(f"Erro ao detectar idioma: {e}")
        return 'pt'