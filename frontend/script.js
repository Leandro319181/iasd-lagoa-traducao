const transcriptEl  = document.getElementById('transcript');
const statusEl      = document.getElementById('status');
const audioToggleEl = document.getElementById('audio-toggle');

let eventSource  = null;
let audioEnabled = true;   // áudio ligado por padrão

// --- Controle de áudio ---

function toggleAudio() {
    audioEnabled = !audioEnabled;
    if (audioEnabled) {
        audioToggleEl.textContent  = '🔊 Audio ON';
        audioToggleEl.className    = 'audio-btn audio-on';
    } else {
        audioToggleEl.textContent  = '🔇 Audio OFF';
        audioToggleEl.className    = 'audio-btn audio-off';
    }
}

// --- Conexão SSE ---

function connect() {
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource('/events');

    eventSource.onopen = function () {
        statusEl.textContent = '🔴 LIVE';
        statusEl.className   = 'status live';
        console.log('[SSE] Conectado ao servidor.');
    };

    eventSource.onmessage = function (event) {
        let data;
        try {
            data = JSON.parse(event.data);
        } catch (e) {
            console.error('[SSE] Erro ao parsear evento:', event.data);
            return;
        }

        // Evento inicial de handshake — ignora
        if (data.status === 'connected') {
            return;
        }

        // Atualiza legenda
        if (data.text) {
            transcriptEl.textContent = data.text;
            transcriptEl.classList.remove('waiting');
        }

        // Toca áudio se habilitado
        if (data.audio_id && audioEnabled) {
            playAudio(data.audio_id);
        }
    };

    eventSource.onerror = function () {
        statusEl.textContent = '⚫ OFFLINE';
        statusEl.className   = 'status offline';
        if (!transcriptEl.classList.contains('waiting')) {
            transcriptEl.textContent = 'Connection lost. Reconnecting...';
        }
        eventSource.close();
        console.log('[SSE] Desconectado. Reconectando em 3s...');
        setTimeout(connect, 3000);
    };
}

// --- Reprodução de áudio ---

function playAudio(audioId) {
    const audio = new Audio('/audio/' + audioId);
    audio.play().catch(function (error) {
        // Browser bloqueou auto-play — avisa o usuário uma vez
        console.warn('[Audio] Auto-play bloqueado:', error.message);
    });
}

// Inicia conexão ao carregar a página
connect();
