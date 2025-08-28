document.addEventListener("DOMContentLoaded", () => {
    // ==========================================================
    // === SELETORES DE ELEMENTOS
    // ==========================================================
    const chatForm = document.getElementById("chat-form");
    const messageInput = document.getElementById("message-input");
    const chatMessages = document.getElementById("chat-messages");
    const chatHistoryList = document.getElementById("chat-history");
    const newChatBtn = document.getElementById("new-chat-btn");
    const chatTitleElement = document.getElementById("chat-title");
    const sidebar = document.getElementById("sidebar");
    const sidebarToggleOpen = document.getElementById("sidebar-toggle-open");
    const themeToggle = document.getElementById("theme-toggle");
    const ttsToggle = document.getElementById("tts-toggle");
    const logoutBtn = document.getElementById("logout-btn");
    // ==========================================================
    // === CONFIGURAÇÃO E ESTADO
    // ==========================================================
    const BACKEND_URL = "https://jarvis-ia-backend.onrender.com"; 

    const streamApiUrl = `${BACKEND_URL}/chat/stream`;
    const titleApiUrl = `${BACKEND_URL}/chat/generate-title`;
    const codeGenApiUrl = `${BACKEND_URL}/code/generate-web-page`;
    let state = { chats: {}, currentChatId: null };
    
    // ==========================================================
    // === [NOVO] LÓGICA DE AUTENTICAÇÃO E CONTROLE DE ACESSO
    // ==========================================================
    const token = localStorage.getItem('jwtToken');
    if (!token) {
        window.location.href = 'login.html'; // Redireciona se não estiver logado
        return; // Para a execução do script para evitar erros
    }

    // Função para decodificar o payload do JWT (não verifica a assinatura)
    function decodeJwtPayload(token) {
        try {
            const base64Url = token.split('.')[1];
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            return JSON.parse(atob(base64));
        } catch (e) {
            console.error("Erro ao decodificar o token:", e);
            localStorage.removeItem('jwtToken'); // Limpa token inválido
            window.location.href = 'login.html';
            return null;
        }
    }

    const userData = decodeJwtPayload(token);
    const userRole = userData ? userData.role : null;

    if (userRole === 'admin') {
        const adminPanelLink = document.createElement('a');
        adminPanelLink.href = 'admin.html';
        adminPanelLink.textContent = 'Painel do Administrador';
        adminPanelLink.className = 'admin-panel-link';
        const sidebarFooter = document.querySelector('.sidebar-footer');
        if (sidebarFooter) {
            sidebarFooter.prepend(adminPanelLink);
        }
    }

    // ==========================================================
    // === LÓGICA DE SÍNTESE DE VOZ (ATUALIZADA)
    // ==========================================================
    function cleanTextForSpeech(text) {
        let cleanText = text.replace(/###|##|#|\*\*|\*|`/g, '');
        cleanText = cleanText.replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1');
        return cleanText;
    }

    function getVoices() {
        return new Promise((resolve) => {
            let voices = speechSynthesis.getVoices();
            if (voices.length) {
                resolve(voices);
                return;
            }
            speechSynthesis.onvoiceschanged = () => {
                voices = speechSynthesis.getVoices();
                resolve(voices);
            };
        });
    }

    async function speak(text, lang = "pt-BR") {
        if (speechSynthesis.speaking) {
            speechSynthesis.cancel();
        }
        
        const utterance = new SpeechSynthesisUtterance(cleanTextForSpeech(text));
        utterance.lang = lang;
        utterance.rate = 1.0;

        const allVoices = await getVoices();
        const voicesForLang = allVoices.filter(v => v.lang.startsWith(lang));
        let desiredVoice = null;

        if (voicesForLang.length > 0) {
            desiredVoice = voicesForLang.find(v => v.name.includes("Francisca")) || 
                           voicesForLang.find(v => v.name.includes("(Natural)")) || 
                           voicesForLang.find(v => ['Female', 'Feminino', 'Femme', 'Mujer'].some(m => v.name.includes(m)));
            
            if (desiredVoice) {
                utterance.voice = desiredVoice;
            }
        }
        
        speechSynthesis.speak(utterance);
    }

    // ==========================================================
    // === GERENCIAMENTO DE ESTADO (STATE)
    // ==========================================================
    function saveState() { localStorage.setItem("jarvisAppState", JSON.stringify(state)); }
    function loadState() { const savedState = localStorage.getItem("jarvisAppState"); if (savedState) { state = JSON.parse(savedState); } else { createNewChat(); } }
    function renderSidebar() { chatHistoryList.innerHTML = ''; Object.values(state.chats).sort((a, b) => b.createdAt - a.createdAt).forEach(chat => { const li = document.createElement("li"); li.className = `chat-history-item ${chat.id === state.currentChatId ? "active" : ""}`; li.dataset.chatId = chat.id; li.innerHTML = ` <span class="history-item-title">${chat.title}</span> <div class="history-item-buttons"> <button class="icon-button edit-btn"><i class="ph ph-pencil-simple"></i></button> <button class="icon-button delete-btn"><i class="ph ph-trash"></i></button> </div>`; chatHistoryList.appendChild(li); }); addSidebarEventListeners(); }
    function renderMessages() { chatMessages.innerHTML = ""; const currentChat = state.chats[state.currentChatId]; if (!currentChat) return; chatTitleElement.textContent = currentChat.title; currentChat.messages.forEach(msg => { addMessageToUI(msg.role, msg.content); }); }
    function addMessageToUI(sender, text = "") { const messageElement = document.createElement("div"); const role = sender; messageElement.classList.add("message", `${role === "user" ? "user-message" : "jarvis-message"}`); if (role === "assistant" && typeof marked !== "undefined") { messageElement.innerHTML = marked.parse(text); } else { messageElement.textContent = text; } chatMessages.appendChild(messageElement); chatMessages.scrollTop = chatMessages.scrollHeight; return messageElement; }
    function createNewChat() { const newChatId = `chat-${Date.now()}`; state.chats[newChatId] = { id: newChatId, title: "Novo Chat", messages: [{ role: "assistant", content: "Olá! Como posso ajudar hoje?" }], createdAt: Date.now(), }; state.currentChatId = newChatId; saveState(); render(); }
    function switchChat(chatId) { if (state.currentChatId === chatId) return; state.currentChatId = chatId; saveState(); render(); }
    function deleteChat(chatId) { if (confirm(`Tem certeza que deseja apagar o chat "${state.chats[chatId].title}"?`)) { delete state.chats[chatId]; if (state.currentChatId === chatId) { const remainingChats = Object.values(state.chats).sort((a, b) => b.createdAt - a.createdAt); state.currentChatId = remainingChats.length > 0 ? remainingChats[0].id : null; } if (!state.currentChatId) { createNewChat(); } else { saveState(); render(); } } }
    function editChatTitle(chatId) { const newTitle = prompt("Digite o novo título do chat:", state.chats[chatId].title); if (newTitle && newTitle.trim() !== "") { state.chats[chatId].title = newTitle.trim(); saveState(); render(); } }
    async function generateAndSetTitle(chatId) { const chat = state.chats[chatId]; if (chat.title === "Novo Chat" && chat.messages.length === 2) { try { 
        const response = await fetch(titleApiUrl, { method: "POST", headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` }, body: JSON.stringify({ history: chat.messages }) }); 
        const data = await response.json(); if (data.title) { chat.title = data.title; saveState(); renderSidebar(); } } catch (error) { console.error("Falha ao gerar título:", error); } } }
    
    // ==========================================================
    // === EVENT LISTENERS E INICIALIZAÇÃO
    // ==========================================================
    chatForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const userMessage = messageInput.value.trim();
        if (!userMessage) return;
        speechSynthesis.cancel();
        const currentChat = state.chats[state.currentChatId];
        currentChat.messages.push({ role: "user", content: userMessage });
        addMessageToUI("user", userMessage);
        messageInput.value = "";
        const isCodeRequest = userMessage.toLowerCase().includes("crie uma página") || userMessage.toLowerCase().includes("código html");
        if (isCodeRequest) {
             const jarvisMessageElement = addMessageToUI("assistant", "Gerando o código para você, um momento...");
            try {
                const response = await fetch(codeGenApiUrl, { method: "POST", headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` }, body: JSON.stringify({ prompt: userMessage }) });
                const data = await response.json();
                jarvisMessageElement.innerHTML = marked.parse(data.structured_content);
                const fullReply = data.structured_content;
                currentChat.messages.push({ role: "assistant", content: fullReply });
                saveState();
                if (ttsToggle.checked && fullReply) { speak("Código gerado. Aqui estão os detalhes.", "pt-BR"); }
            } catch (error) {
                console.error("Erro ao gerar código:", error);
                jarvisMessageElement.textContent = "Desculpe, ocorreu um erro ao gerar o código.";
            }
        } else {
            generateAndSetTitle(state.currentChatId);
            const jarvisMessageElement = addMessageToUI("assistant");
            let fullReply = "";
            let responseLang = "pt-BR";
            const url = new URL(streamApiUrl);
            url.searchParams.append('message', userMessage);
            url.searchParams.append('history', JSON.stringify(currentChat.messages));            
            url.searchParams.append('token', token);
            const eventSource = new EventSource(url);
            eventSource.addEventListener('metadata', (event) => {
                const data = JSON.parse(event.data);
                if (data.lang) { responseLang = data.lang; }
            });
            eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.text) {
                    fullReply += data.text;
                    jarvisMessageElement.innerHTML = marked.parse(fullReply);
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                }
            };
            eventSource.onerror = () => {
                eventSource.close();
                currentChat.messages.push({ role: "assistant", content: fullReply });
                saveState();
                if (ttsToggle.checked && fullReply) {
                    speak(fullReply, responseLang);
                }
            };
        }
    });

    function addSidebarEventListeners() { document.querySelectorAll(".chat-history-item").forEach((item) => { const chatId = item.dataset.chatId; item.querySelector(".history-item-title").addEventListener("click", () => switchChat(chatId)); item.querySelector(".edit-btn").addEventListener("click", (e) => { e.stopPropagation(); editChatTitle(chatId); }); item.querySelector(".delete-btn").addEventListener("click", (e) => { e.stopPropagation(); deleteChat(chatId); }); }); }
    
    newChatBtn.addEventListener("click", createNewChat);
    sidebarToggleOpen.addEventListener("click", (event) => { 
    event.stopPropagation(); // Impede que o clique "vaze" para o fundo
    sidebar.classList.toggle("collapsed"); 
});
    
    const chatContainer = document.querySelector(".chat-container");
    chatContainer.addEventListener("click", () => {
        if (window.innerWidth <= 768 && !sidebar.classList.contains("collapsed")) {
            sidebar.classList.add("collapsed");
        }
    });

    themeToggle.addEventListener("change", () => { document.body.classList.toggle("dark-theme"); localStorage.setItem("theme", document.body.classList.contains("dark-theme") ? "dark" : "light"); });
    ttsToggle.addEventListener('change', () => { if (!ttsToggle.checked) { speechSynthesis.cancel(); } });

    // --- [NOVO] LÓGICA DE LOGOUT ---
    logoutBtn.addEventListener('click', () => {
        if (confirm("Tem certeza que deseja sair?")) {
            localStorage.removeItem('jwtToken');
            localStorage.removeItem('jarvisAppState');
            window.location.href = 'login.html';
        }
    });
    
    function render() { renderSidebar(); renderMessages(); }

    // A inicialização agora acontece após a verificação do token
    loadState();
    render();
});