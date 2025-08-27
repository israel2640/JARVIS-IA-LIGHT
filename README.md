# Jarvis IA - Assistente Pessoal com IA

![Demonstração do Chat](https://i.imgur.com/Kz3s5oW.png) **Jarvis IA** é uma aplicação web completa que simula um assistente pessoal inteligente, construído com uma arquitetura moderna de backend em Python (FastAPI) e um frontend dinâmico em JavaScript puro. A aplicação é projetada para ser robusta, segura e escalável, pronta para ser comercializada como um serviço de assinatura.

## ✨ Funcionalidades Principais

* **Chat Interativo:** Interface de chat em tempo real com respostas da IA transmitidas palavra por palavra (streaming).
* **Busca na Web:** Capacidade de responder a perguntas sobre eventos atuais, buscando informações em tempo real na internet através da API da Serper.
* **Sistema de Assinaturas:**
    * **Autenticação de Usuários:** Sistema de login seguro com senhas criptografadas.
    * **Controle de Acesso Baseado em Funções (RBAC):** Distinção clara entre usuários comuns e administradores.
    * **Painel de Administração:** Uma interface completa para o administrador criar, listar, editar e excluir contas de usuários, definir durações de assinatura e conceder acesso vitalício.
* **Notificações Automáticas:** Um script agendado (`verificador_diario.py`) roda diariamente para verificar assinaturas expiradas e notificar os clientes por e-mail.
* **Interface Responsiva:** O design se adapta a telas de desktop e dispositivos móveis, com um menu lateral retrátil.
* **Seleção de Modelos de IA:** O backend está preparado para utilizar diferentes modelos da OpenAI, como `gpt-4o-mini`, `gpt-4-turbo` ou futuros modelos como `gpt-5-nano`.

## 🚀 Tecnologias Utilizadas

#### **Backend**
* **Python 3.10+**
* **FastAPI:** Para a criação da API REST.
* **Uvicorn:** Como servidor ASGI.
* **Supabase:** Banco de dados PostgreSQL para gerenciamento de usuários.
* **OpenAI API:** Para a geração de texto e inteligência do chat.
* **Serper API:** Para a funcionalidade de busca na web.
* **Jose & Passlib:** Para manipulação de tokens JWT e segurança de senhas.
* **Dotenv:** Para gerenciamento de variáveis de ambiente.

#### **Frontend**
* **HTML5**
* **CSS3:** Com variáveis para temas claro/escuro e Media Queries para responsividade.
* **JavaScript (Vanilla):** Sem frameworks, com manipulação direta do DOM e chamadas de API com `fetch`.

#### **Deploy**
* **Render:** Plataforma de nuvem para hospedar:
    * O backend como um **Serviço Web**.
    * O frontend como um **Site Estático**.
    * O script de notificação como uma **Tarefa Cron**.
* **Git & GitHub:** Para versionamento e integração contínua (CI/CD).

## 🔧 Configuração e Instalação Local

Para rodar este projeto localmente, siga os passos abaixo.

### **Pré-requisitos**
* Python 3.10 ou superior
* Uma conta na [OpenAI](https://platform.openai.com/)
* Uma conta no [Supabase](https://supabase.com/)
* Uma conta na [Serper](https://serper.dev/)

### **1. Backend (`jarvis_backend`)**

a. **Navegue até a pasta do backend:**
```bash
cd jarvis_backend
```

b. **Crie e configure o arquivo `.env`:**
   Crie um arquivo chamado `.env` nesta pasta e adicione suas chaves:
```env
OPENAI_API_KEY="sk-..."
SUPABASE_URL="https://..."
SUPABASE_SERVICE_KEY="eyJ..."
JWT_SECRET_KEY="sua-frase-secreta-longa-aqui"
SERPER_API_KEY="sua-chave-serper-aqui"
GMAIL_USER="seu-email@gmail.com"
GMAIL_APP_PASSWORD="sua-senha-de-app-de-16-letras"
EMAIL_ADMIN="seu-email-de-admin@gmail.com"
```

c. **Instale as dependências:**
```bash
pip install -r requirements.txt
```

d. **Inicie o servidor:**
```bash
uvicorn main:app --reload
```
O backend estará rodando em `http://localhost:8000`.

### **2. Frontend (`jarvis_frontend`)**

a. **Ajuste a URL da API:**
   Nos arquivos `login.html`, `admin.html` e `script.js`, certifique-se de que a constante `BACKEND_URL` está apontando para o seu servidor local:
   ```javascript
   const BACKEND_URL = "http://localhost:8000";
   ```

b. **Inicie um servidor local para o frontend:**
   Abra um **novo terminal**, navegue até a pasta do frontend e execute:
```bash
cd jarvis_frontend
python -m http.server 5500
```
Acesse a aplicação no seu navegador em `http://localhost:5500`.

