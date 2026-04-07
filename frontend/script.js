const transcriptEl = document.getElementById('transcript');
const statusEl     = document.getElementById('status');

let eventSource = null;

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

        if (data.status === 'connected') {
            console.log('[SSE] Handshake de conexão recebido.');
            return;
        }

        if (data.text) {
            transcriptEl.textContent = data.text;
        }

        if (data.audio_id) {
            playAudio(data.audio_id);
        }
    };

    eventSource.onerror = function () {
        statusEl.textContent = '⚫ OFFLINE';
        statusEl.className   = 'status offline';
        transcriptEl.textContent = 'Connection lost. Reconnecting...';
        eventSource.close();
        console.log('[SSE] Desconectado. Tentando reconectar em 3s...');
        setTimeout(connect, 3000);
    };
}

function playAudio(audioId) {
    const audio = new Audio('/audio/' + audioId);
    audio.play().catch(function (error) {
        // Auto-play bloqueado pelo browser na primeira vez — usuário precisa tocar na tela
        console.warn('[Audio] Auto-play bloqueado:', error.message);
        transcriptEl.textContent += '\n\n[Tap the screen to enable audio]';
    });
}

connect();
