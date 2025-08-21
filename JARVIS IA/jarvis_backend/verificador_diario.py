# verificador_diario.py

import os
from datetime import datetime, timezone
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configurações dos Serviços ---

# Conexão com Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Credenciais de E-mail
EMAIL_REMETENTE = os.getenv("GMAIL_USER")
SENHA_APP = os.getenv("GMAIL_APP_PASSWORD")
EMAIL_ADMIN = os.getenv("EMAIL_ADMIN")

def enviar_email(destinatario, assunto, mensagem):
    """Função para enviar e-mails de notificação."""
    if not EMAIL_REMETENTE or not SENHA_APP:
        print("ERRO: Credenciais de e-mail (GMAIL_USER, GMAIL_APP_PASSWORD) não configuradas no .env.")
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = assunto
        msg["From"] = EMAIL_REMETENTE
        msg["To"] = destinatario
        msg.set_content(mensagem)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_REMETENTE, SENHA_APP)
            smtp.send_message(msg)
        print(f"E-mail enviado com sucesso para {destinatario}.")
        return True
    except Exception as e:
        print(f"ERRO ao enviar e-mail para {destinatario}: {e}")
        return False

# --- Lógica Principal do Script ---
def verificar_expiracoes():
    """
    Busca usuários no Supabase, verifica assinaturas expiradas e envia notificações.
    """
    print(f"Iniciando verificação de assinaturas em {datetime.now()}...")
    
    try:
        # Busca todos os usuários que ainda não foram notificados
        response = supabase.table('usuarios').select('*').eq('notificacao_enviada', False).execute()
        if not response.data:
            print("Nenhum usuário pendente de notificação encontrado.")
            print("Verificação concluída.")
            return
            
        usuarios = response.data
    except Exception as e:
        print(f"ERRO: Falha ao buscar usuários no Supabase: {e}")
        return

    agora = datetime.now(timezone.utc)
    usuarios_notificados_admin = []
    
    for user in usuarios:
        expiracao_str = user.get('data_expiracao')
        if not expiracao_str:
            continue # Pula usuários sem data de expiração (ex: vitalícios)

        expiracao = datetime.fromisoformat(expiracao_str)
        
        # Se a assinatura expirou
        if agora >= expiracao:
            print(f"Assinatura de '{user['nome']}' (Email: {user['email']}) expirou.")
            
            # 1. Envia e-mail para o cliente
            assunto_cliente = "🔔 Sua assinatura da Jarvis IA expirou"
            mensagem_cliente = f"Olá {user['nome']},\n\nSua assinatura da Jarvis IA expirou em {expiracao.strftime('%d/%m/%Y')}. Renove para continuar usando os serviços."
            enviar_email(user["email"], assunto_cliente, mensagem_cliente)
            
            # 2. Adiciona à lista de resumo para o admin
            usuarios_notificados_admin.append(f"- {user['nome']} (Email: {user['email']})")

            # 3. Atualiza o status no Supabase para não notificar novamente
            try:
                supabase.table('usuarios').update({'notificacao_enviada': True}).eq('id', user['id']).execute()
                print(f"Status de notificação atualizado para o usuário {user['email']}.")
            except Exception as e:
                print(f"ERRO: Falha ao atualizar status de notificação para {user['email']}: {e}")

    # 4. Envia o e-mail de resumo para o admin, se houver notificações
    if usuarios_notificados_admin and EMAIL_ADMIN:
        corpo_resumo = "As seguintes assinaturas expiraram e os clientes foram notificados hoje:\n\n" + "\n".join(usuarios_notificados_admin)
        enviar_email(EMAIL_ADMIN, "Resumo Diário de Assinaturas Expiradas - Jarvis IA", corpo_resumo)
    else:
        print("Nenhuma nova assinatura expirada para notificar.")

    print("Verificação concluída.")

# Ponto de entrada para executar o script
if __name__ == "__main__":
    verificar_expiracoes()