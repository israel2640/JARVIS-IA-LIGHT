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
  // <--- ADICIONADO: Seletores para a nova funcionalidade --->
  const attachBtn = document.getElementById("attach-btn");
  const fileInput = document.getElementById("file-input");
  const fileContextArea = document.getElementById("file-context-area");
  // NOVO SELETOR ADICIONADO AQUI
  const micBtn = document.getElementById("mic-btn");

  // ==========================================================
  // === CONFIGURAÇÃO E ESTADO
  // ==========================================================
  const isLocal =
    window.location.hostname === "127.0.0.1" ||
    window.location.hostname === "localhost";
  const BACKEND_URL = isLocal
    ? "http://127.0.0.1:8000"
    : "https://jarvis-ia-backend.onrender.com";

  // Adiciona uma mensagem no console do navegador para saber qual URL está em uso
  console.log(
    `Modo: ${
      isLocal ? "Local" : "Produção"
    }. Conectando ao backend em: ${BACKEND_URL}`
  );

  const streamApiUrl = `${BACKEND_URL}/chat/stream`;
  const titleApiUrl = `${BACKEND_URL}/chat/generate-title`;
  const codeGenApiUrl = `${BACKEND_URL}/code/generate-web-page`;
  let state = { chats: {}, currentChatId: null };
  // <--- ADICIONADO: Variável para guardar o ID do contexto dos arquivos --->
  let currentFileContextId = null;

  // ==========================================================
  // === LÓGICA DE AUTENTICAÇÃO E CONTROLE DE ACESSO
  // ==========================================================
  const token = localStorage.getItem("jwtToken");
  let currentUserEmail = null;
  if (!token) {
    window.location.href = "login.html";
    return;
  }

  function decodeJwtPayload(token) {
    try {
      const base64Url = token.split(".")[1];
      const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
      return JSON.parse(atob(base64));
    } catch (e) {
      console.error("Erro ao decodificar o token:", e);
      localStorage.removeItem("jwtToken");
      window.location.href = "login.html";
      return null;
    }
  }

  const userData = decodeJwtPayload(token);
  const userRole = userData ? userData.role : null;
  currentUserEmail = userData ? userData.sub : null;

  if (userRole === "admin") {
    const adminPanelLink = document.createElement("a");
    adminPanelLink.href = "admin.html";
    adminPanelLink.textContent = "Painel do Administrador";
    adminPanelLink.className = "admin-panel-link";
    const sidebarFooter = document.querySelector(".sidebar-footer");
    if (sidebarFooter) {
      sidebarFooter.prepend(adminPanelLink);
    }
  }

  // ==========================================================
  // === LÓGICA DE SÍNTESE DE VOZ (ATUALIZADA)
  // ==========================================================
  function cleanTextForSpeech(text) {
    let cleanText = text.replace(/###|##|#|\*\*|\*|`/g, "");
    cleanText = cleanText.replace(/\[([^\]]+)\]\([^\)]+\)/g, "$1");

    cleanText = cleanText.replace(
      /([\u2700-\u27BF]|[\uE000-\uF8FF]|||[\u2011-\u26FF]|\uD83C[\uDC00-\uDFFF]|\uD83D[\uDC00-\uDFFF]|\uD83E[\uDD10-\uDDFF])/g,
      ""
    );
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
    const voicesForLang = allVoices.filter((v) => v.lang.startsWith(lang));
    let desiredVoice = null;

    if (voicesForLang.length > 0) {
      desiredVoice =
        voicesForLang.find((v) => v.name.includes("Francisca")) ||
        voicesForLang.find((v) => v.name.includes("(Natural)")) ||
        voicesForLang.find((v) =>
          ["Female", "Feminino", "Femme", "Mujer"].some((m) =>
            v.name.includes(m)
          )
        );

      if (desiredVoice) {
        utterance.voice = desiredVoice;
      }
    }

    speechSynthesis.speak(utterance);
  }

  // ==========================================================
  // === GERENCIAMENTO DE ESTADO (STATE)
  // ==========================================================
  function saveState() {
      if (!currentUserEmail) return; // Não salva nada se não houver um usuário logado
      const userStateKey = `jarvisAppState_${currentUserEmail}`;
      localStorage.setItem(userStateKey, JSON.stringify(state));
  }
  function loadState() {
      if (!currentUserEmail) { // Se não houver usuário, inicia um chat vazio
          createNewChat();
          return;
      }
      const userStateKey = `jarvisAppState_${currentUserEmail}`;
      const savedState = localStorage.getItem(userStateKey);
      if (savedState) {
          state = JSON.parse(savedState);
      } else {
          // Se este usuário nunca salvou um estado, cria um novo chat para ele
          createNewChat();
      }
  }

  function renderSidebar() {
      chatHistoryList.innerHTML = '';
      Object.values(state.chats)
        .sort((a, b) => b.createdAt - a.createdAt)
        .forEach(chat => {
          const li = document.createElement("li");
          li.className = `chat-history-item ${chat.id === state.currentChatId ? "active" : ""}`;
          li.dataset.chatId = chat.id;
          li.innerHTML = ` <span class="history-item-title">${chat.title}</span> <div class="history-item-buttons"> <button class="icon-button edit-btn"><i class="ph ph-pencil-simple"></i></button> <button class="icon-button delete-btn"><i class="ph ph-trash"></i></button> </div>`;
          chatHistoryList.appendChild(li);
        });
      addSidebarEventListeners();
  }
  // Substitua a sua função renderMessages por esta:
  function renderMessages() {
    chatMessages.innerHTML = "";
    const currentChat = state.chats[state.currentChatId];
    if (!currentChat) return;
    chatTitleElement.textContent = currentChat.title;
    // Modificação aqui: passamos o 'index' para o forEach
    currentChat.messages.forEach((msg, index) => {
      addMessageToUI(msg.role, msg.content, index); // Adicionamos o 'index' como argumento
    });
  }

  // Adicione estas duas novas funções em script.js

  /**
   * Lida com a edição de uma mensagem do usuário.
   * @param {number} messageIndex O índice da mensagem a ser editada.
   */
  function handleEditMessage(messageIndex) {
    const currentChat = state.chats[state.currentChatId];
    const originalMessage = currentChat.messages[messageIndex].content;

    const editedMessage = prompt("Edite sua mensagem:", originalMessage);

    // Se o usuário não cancelou e a mensagem mudou
    if (editedMessage && editedMessage.trim() !== originalMessage.trim()) {
      // 1. Remove todas as mensagens APÓS a mensagem editada
      currentChat.messages = currentChat.messages.slice(0, messageIndex + 1);

      // 2. Atualiza o conteúdo da mensagem atual
      currentChat.messages[messageIndex].content = editedMessage.trim();

      // 3. Renderiza novamente para mostrar a alteração e o "corte"
      renderMessages();

      // 4. Reenvia a conversa para a IA a partir do ponto editado
      resubmitChatFrom(messageIndex);
    }
  }

  /**
   * Reenvia a conversa para a IA a partir de um ponto específico.
   * @param {number} startIndex O índice da mensagem do usuário a partir da qual reenviar.
   */
  async function resubmitChatFrom(startIndex) {
    const currentChat = state.chats[state.currentChatId];
    const userMessage = currentChat.messages[startIndex].content;
    const history = currentChat.messages.slice(0, startIndex); // Pega o histórico ANTERIOR

    const jarvisMessageElement = addMessageToUI("assistant", "..."); // Placeholder de "pensando"
    let fullReply = "";

    // Desabilita o input durante o reenvio
    messageInput.disabled = true;

    const url = new URL(streamApiUrl);
    url.searchParams.append("message", userMessage);
    url.searchParams.append("history", JSON.stringify(history));
    url.searchParams.append("token", token);

    if (currentFileContextId) {
      url.searchParams.append("context_id", currentFileContextId);
    }

    let jarvisLanguage = "pt-BR";

    try {
      const response = await fetch(url);
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = JSON.parse(line.substring(6));
            if (data.lang) jarvisLanguage = data.lang;
            if (data.text) {
              fullReply += data.text;
              jarvisMessageElement.innerHTML = marked.parse(fullReply);
              addCopyButtonsToCodeBlocks(jarvisMessageElement); 
              openLinksInNewTab(jarvisMessageElement);
              chatMessages.scrollTop = chatMessages.scrollHeight;
            }
          }
        }
      }
    } catch (error) {
      console.error("Erro na conexão com o servidor:", error);
      jarvisMessageElement.innerHTML = `<span style="color:red;">Erro ao conectar. Tente novamente.</span>`;
    } finally {
      currentChat.messages.push({ role: "assistant", content: fullReply });
      saveState();
      messageInput.disabled = false; // Reabilita o input
      if (ttsToggle.checked && fullReply) {
        speak(fullReply, jarvisLanguage);
      }
    }
  }

  // --- NOVA FUNÇÃO AUXILIAR ---
  function addCopyButtonsToCodeBlocks(messageElement) {
    const codeBlocks = messageElement.querySelectorAll("pre");
    codeBlocks.forEach((block) => {
      const button = document.createElement("button");
      button.className = "copy-code-btn";
      button.textContent = "Copiar";

      const code = block.querySelector("code");
      if (!code) return; // Se não houver tag <code>, não faz nada

      button.addEventListener("click", () => {
        navigator.clipboard
          .writeText(code.textContent)
          .then(() => {
            button.textContent = "Copiado!";
            setTimeout(() => {
              button.textContent = "Copiar";
            }, 2000); // Volta para "Copiar" após 2 segundos
          })
          .catch((err) => {
            console.error("Falha ao copiar o código:", err);
          });
      });

      block.appendChild(button);
    });
  }

  // --- FUNÇÃO MODIFICADA ---
  function addMessageToUI(sender, text = "", index) {
    // Adicionamos 'index' aos parâmetros
    const messageElement = document.createElement("div");
    const role = sender;
    messageElement.classList.add(
      "message",
      `${role === "user" ? "user-message" : "jarvis-message"}`
    );

    if (role === "assistant" && typeof marked !== "undefined") {
      messageElement.innerHTML = marked.parse(text);
      addCopyButtonsToCodeBlocks(messageElement);
      openLinksInNewTab(messageElement);
    } else {
      messageElement.textContent = text;
    }

    // --- NOVA LÓGICA DE EDIÇÃO ---
    if (role === "user") {
      const editBtn = document.createElement("button");
      editBtn.className = "edit-message-btn";
      editBtn.title = "Editar e reenviar";
      editBtn.innerHTML = '<i class="ph ph-pencil-simple"></i>';
      editBtn.onclick = () => handleEditMessage(index); // Chama a nova função de edição
      messageElement.appendChild(editBtn);
    }
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return messageElement;
  }

  function openLinksInNewTab(element) {
      const links = element.querySelectorAll('a');
      links.forEach(link => {
          link.target = '_blank';
          // Adiciona 'rel' por segurança e boas práticas ao usar target="_blank"
          link.rel = 'noopener noreferrer';
      });
  }

  function createNewChat() {
    const newChatId = `chat-${Date.now()}`;
    state.chats[newChatId] = {
      id: newChatId,
      title: "Novo Chat",
      messages: [
        { role: "assistant", content: "Olá! Como posso ajudar hoje?" },
      ],
      createdAt: Date.now(),
    };
    state.currentChatId = newChatId;
    saveState();
    render();
  }
  function switchChat(chatId) {
    if (state.currentChatId === chatId) return;
    state.currentChatId = chatId;
    saveState();
    render();
  }
  function deleteChat(chatId) {
    if (
      confirm(
        `Tem certeza que deseja apagar o chat "${state.chats[chatId].title}"?`
      )
    ) {
      delete state.chats[chatId];
      if (state.currentChatId === chatId) {
        const remainingChats = Object.values(state.chats).sort(
          (a, b) => b.createdAt - a.createdAt
        );
        state.currentChatId =
          remainingChats.length > 0 ? remainingChats[0].id : null;
      }
      if (!state.currentChatId) {
        createNewChat();
      } else {
        saveState();
        render();
      }
    }
  }
  function editChatTitle(chatId) {
    const newTitle = prompt(
      "Digite o novo título do chat:",
      state.chats[chatId].title
    );
    if (newTitle && newTitle.trim() !== "") {
      state.chats[chatId].title = newTitle.trim();
      saveState();
      render();
    }
  }
  async function generateAndSetTitle(chatId) {
    const chat = state.chats[chatId];
    if (chat.title === "Novo Chat" && chat.messages.length >= 2) {
      try {
        const response = await fetch(titleApiUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ history: chat.messages }),
        });
        const data = await response.json();
        if (data.title) {
          chat.title = data.title;
          saveState();
          renderSidebar();
        }
      } catch (error) {
        console.error("Falha ao gerar título:", error);
      }
    }
  }
  // ==========================================================
  // === EVENT LISTENERS E INICIALIZAÇÃO
  // ==========================================================
  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const userMessage = messageInput.value.trim();
    if (!userMessage) return;
    speechSynthesis.cancel();
    const currentChat = state.chats[state.currentChatId];

    // Adiciona a mensagem do usuário ao estado
    currentChat.messages.push({ role: "user", content: userMessage });

    // --- ALTERAÇÃO 1: Passar o índice para a mensagem do usuário ---
    // Pegamos o índice da última mensagem adicionada (a que o usuário acabou de enviar)
    const userMessageIndex = currentChat.messages.length - 1;
    addMessageToUI("user", userMessage, userMessageIndex);
    
    messageInput.value = "";

    generateAndSetTitle(state.currentChatId);
    const jarvisMessageElement = addMessageToUI("assistant");
    let fullReply = "";

    const url = new URL(streamApiUrl);
    url.searchParams.append("message", userMessage);
    url.searchParams.append(
      "history",
      JSON.stringify(currentChat.messages.slice(0, -1))
    );
    url.searchParams.append("token", token);

    if (currentFileContextId) {
      url.searchParams.append("context_id", currentFileContextId);
    }

    let jarvisLanguage = "pt-BR";

    try {
      const response = await fetch(url);
      if (!response.body) {
        throw new Error("Streaming not supported by the browser.");
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = JSON.parse(line.substring(6));
            if (data.lang) {
              jarvisLanguage = data.lang;
            }
            if (data.text) {
              fullReply += data.text;
              jarvisMessageElement.innerHTML = marked.parse(fullReply);
              
              // --- ALTERAÇÃO 2: Adicionar o botão de copiar na resposta da IA ---
              addCopyButtonsToCodeBlocks(jarvisMessageElement);
              openLinksInNewTab(jarvisMessageElement);
              chatMessages.scrollTop = chatMessages.scrollHeight;
            }
          } else if (line.startsWith("event: end")) {
            reader.cancel();
          }
        }
      }
    } catch (error) {
      console.error("Erro na conexão com o servidor:", error);
      jarvisMessageElement.innerHTML = `<span style="color:red;">Erro ao conectar. Tente novamente.</span>`;
    } finally {
      currentChat.messages.push({ role: "assistant", content: fullReply });
      saveState();
      if (ttsToggle.checked && fullReply) {
        speak(fullReply, jarvisLanguage);
      }
    }
  });

  function addSidebarEventListeners() {
    document.querySelectorAll(".chat-history-item").forEach((item) => {
      const chatId = item.dataset.chatId;
      item
        .querySelector(".history-item-title")
        .addEventListener("click", () => switchChat(chatId));
      item.querySelector(".edit-btn").addEventListener("click", (e) => {
        e.stopPropagation();
        editChatTitle(chatId);
      });
      item.querySelector(".delete-btn").addEventListener("click", (e) => {
        e.stopPropagation();
        deleteChat(chatId);
      });
    });
  }

  // <--- A função do newChatBtn limpa o contexto dos arquivos --->
  newChatBtn.addEventListener("click", () => {
    currentFileContextId = null;
    fileContextArea.innerHTML = "";
    createNewChat();
  });

  sidebarToggleOpen.addEventListener("click", (event) => {
    event.stopPropagation();
    sidebar.classList.toggle("collapsed");
  });

  const chatContainer = document.querySelector(".chat-container");
  chatContainer.addEventListener("click", () => {
    if (window.innerWidth <= 768 && !sidebar.classList.contains("collapsed")) {
      sidebar.classList.add("collapsed");
    }
  });

  // <--- Lógica para upload de arquivos --->
  attachBtn.addEventListener("click", () => {
    fileInput.click();
  });

  fileInput.addEventListener("change", async () => {
    if (fileInput.files.length === 0) {
      return;
    }

    const formData = new FormData();
    for (const file of fileInput.files) {
      formData.append("files", file);
    }

    fileContextArea.innerHTML = `<span class="file-tag">Enviando e processando...</span>`;

    try {
      const response = await fetch(`${BACKEND_URL}/chat/upload-files`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Falha ao enviar arquivos.");
      }

      const result = await response.json();
      currentFileContextId = result.context_id;

      fileContextArea.innerHTML = "<span>Arquivos em contexto:</span>";
      result.filenames.forEach((name) => {
        const tag = document.createElement("div");
        tag.className = "file-tag";
        tag.innerHTML = `<span>${name}</span>`;
        fileContextArea.appendChild(tag);
      });
      // Adiciona mensagem de confirmação ao chat
      addMessageToUI(
        "assistant",
        `Arquivos [${result.filenames.join(
          ", "
        )}] carregados com sucesso. Agora você pode fazer perguntas sobre eles.`
      );
    } catch (error) {
      console.error("Erro no upload:", error);
      fileContextArea.innerHTML = `<span style="color: red;">Erro ao carregar arquivos.</span>`;
    } finally {
      fileInput.value = ""; // Limpa o input para permitir o reenvio dos mesmos arquivos
    }
  });

  themeToggle.addEventListener("change", () => {
    document.body.classList.toggle("dark-theme");
    localStorage.setItem(
      "theme",
      document.body.classList.contains("dark-theme") ? "dark" : "light"
    );
  });
  ttsToggle.addEventListener("change", () => {
    if (!ttsToggle.checked) {
      speechSynthesis.cancel();
    }
  });

  // --- LÓGICA DE FALA PARA TEXTO ---
  if ("webkitSpeechRecognition" in window) {
    const SpeechRecognition = window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.lang = "pt-BR";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    // Ouve o resultado da fala
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      // Define o texto reconhecido no campo de entrada
      messageInput.value = transcript;
      // Dispara o formulário automaticamente para enviar a mensagem
      chatForm.dispatchEvent(new Event("submit"));
    };

    // Evento que dispara o reconhecimento ao clicar no botão
    micBtn.addEventListener("click", () => {
      // Cancela a síntese de voz, caso esteja em andamento
      speechSynthesis.cancel();
      recognition.start();
      messageInput.placeholder = "Ouvindo...";
      console.log("Reconhecimento de fala iniciado.");
    });

    // Restaura o placeholder quando o reconhecimento terminar
    recognition.onend = () => {
      messageInput.placeholder = "Converse com Jarvis...";
      console.log("Reconhecimento de fala finalizado.");
    };

    // Trata erros, como microfone não encontrado
    recognition.onerror = (event) => {
      console.error("Erro no reconhecimento de fala:", event.error);
      messageInput.placeholder = "Erro de voz. Tente digitar.";
    };
  } else {
    console.warn("Web Speech API não suportada no seu navegador.");
    micBtn.style.display = "none"; // Esconde o botão se a API não for suportada
  }

  
  // --- LÓGICA DE LOGOUT COM ESCOLHA DO USUÁRIO) ---
  logoutBtn.addEventListener("click", () => {
      // Primeira confirmação: o usuário realmente quer sair?
      if (confirm("Tem certeza que deseja sair?")) {
          
          // CORREÇÃO: Adicionando a chamada 'confirm()' que estava faltando
          const deleteHistory = confirm("Deseja APAGAR o histórico de conversas deste navegador?\n\nClique em 'OK' para apagar ou 'Cancelar' para manter.");

          if (deleteHistory) {
              // Se o usuário clicou em 'OK' (true), então APAGAMOS o histórico.
              const userStateKey = `jarvisAppState_${currentUserEmail}`;
              localStorage.removeItem(userStateKey);
              console.log("Histórico de chat local foi removido.");
          }
          // Se o usuário clicar em 'Cancelar' (false), nada acontece com o histórico.

          // Remove o token de autenticação (sempre)
          localStorage.removeItem("jwtToken");

          // Remove a chave genérica antiga, para limpeza
          localStorage.removeItem('jarvisAppState');

          // Redireciona para a página de login
          window.location.href = "login.html";
      }
  });

  function render() {
    renderSidebar();
    renderMessages();
  }

  // A inicialização agora acontece após a verificação do token
  loadState();
  render();
});
