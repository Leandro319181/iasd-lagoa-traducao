var transcriptEl  = document.getElementById('transcript');
var statusEl      = document.getElementById('status');
var audioToggleEl = document.getElementById('audio-toggle');

var eventSource  = null;
var audioEnabled = true;
var wakeLock     = null;

// --- Fila de Áudio (estado: 'idle' | 'playing') ---
var audioState = 'idle';
var audioQueue = [];
var audioEl    = new Audio();

audioEl.addEventListener('ended', function () {
    audioState = 'idle';
    playNext();
});

audioEl.addEventListener('error', function () {
    console.warn('[Audio] Erro no elemento, avançando fila');
    audioState = 'idle';
    playNext();
});

function playAudio(audioId) {
    audioQueue.push(audioId);
    if (audioState === 'idle') {
        playNext();
    }
}

function playNext() {
    if (audioQueue.length === 0) { audioState = 'idle'; return; }
    if (!audioEnabled) { audioQueue = []; audioState = 'idle'; return; }

    audioState = 'playing';
    var id = audioQueue.shift();
    audioEl.src = '/audio/' + id;
    audioEl.play().catch(function (err) {
        console.warn('[Audio] play() bloqueado:', err.message);
        // Guarda na fila — toca no próximo toque do utilizador
        audioQueue.unshift(id);
        audioState = 'idle';
    });
}

// Tenta retomar fila bloqueada no primeiro toque
document.addEventListener('touchstart', function () {
    if (audioState === 'idle' && audioQueue.length > 0) {
        playNext();
    }
}, { passive: true });

// --- Wake Lock (mantém ecrã aceso) ---
function requestWakeLock() {
    if (!('wakeLock' in navigator)) return;
    navigator.wakeLock.request('screen').then(function (lock) {
        wakeLock = lock;
        console.log('[WakeLock] Ecrã bloqueado.');
        lock.addEventListener('release', function () {
            console.log('[WakeLock] Libertado — a renovar...');
            requestWakeLock();
        });
    }).catch(function (err) {
        console.warn('[WakeLock] Não disponível:', err.message);
    });
}

document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') {
        requestWakeLock();
    }
});

requestWakeLock();

// Registar Service Worker (PWA)
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(function (err) {
        console.warn('[SW] Registo falhou:', err);
    });
}

// --- Áudio ON/OFF ---
function toggleAudio() {
    audioEnabled = !audioEnabled;
    if (audioEnabled) {
        audioToggleEl.textContent = '🔊 Audio ON';
        audioToggleEl.className   = 'audio-btn audio-on';
    } else {
        audioToggleEl.textContent = '🔇 Audio OFF';
        audioToggleEl.className   = 'audio-btn audio-off';
        audioQueue = [];
        audioEl.pause();
        audioState = 'idle';
    }
}

// --- Conexão SSE ---
function connect() {
    if (eventSource) { eventSource.close(); }
    eventSource = new EventSource('/events');

    eventSource.onopen = function () {
        statusEl.textContent = '🔴 LIVE';
        statusEl.className   = 'status live';
    };

    eventSource.onmessage = function (event) {
        var data;
        try { data = JSON.parse(event.data); }
        catch (e) { return; }

        if (data.status === 'connected') return;

        // Comando do operador: mutar todos
        if (data.action === 'mute') {
            audioEnabled = false;
            audioToggleEl.textContent = '🔇 Audio OFF';
            audioToggleEl.className   = 'audio-btn audio-off';
            audioQueue = [];
            audioEl.pause();
            audioState = 'idle';
            return;
        }

        if (data.text) {
            transcriptEl.textContent = data.text;
            transcriptEl.classList.remove('waiting');
        }

        if (data.audio_id && audioEnabled) {
            playAudio(data.audio_id);
        }
    };

    eventSource.onerror = function () {
        statusEl.textContent = '⚫ OFFLINE';
        statusEl.className   = 'status offline';
        eventSource.close();
        setTimeout(connect, 3000);
    };
}

connect();
