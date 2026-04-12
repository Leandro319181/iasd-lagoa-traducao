var isPaused    = false;
var currentVoice = 'female';
var MAX_SUBTITLES = 10;

var subtitleList  = document.getElementById('subtitle-list');
var serverStatus  = document.getElementById('server-status');

// --- Polling de status a cada 2s ---
function pollStatus() {
    fetch('/status')
        .then(function (res) { return res.json(); })
        .then(function (data) {
            document.getElementById('clients-count').textContent = data.clients;
            document.getElementById('chunks-count').textContent  = data.chunks_processed;
            document.getElementById('tts-failures').textContent  = data.tts_failures;
            document.getElementById('capture-status').textContent = '🟢 Ativo';
            serverStatus.textContent = 'Conectado';

            var errBox = document.getElementById('last-error');
            if (data.last_error) {
                errBox.textContent = '⚠ ' + data.last_error;
                errBox.classList.remove('hidden');
            } else {
                errBox.classList.add('hidden');
            }

            isPaused     = data.is_paused;
            currentVoice = data.voice;

            var btnPause = document.getElementById('btn-pause');
            btnPause.textContent  = isPaused ? '▶ Retomar' : '⏸ Pausar';
            btnPause.className    = isPaused ? 'btn-paused' : 'btn-primary';

            document.getElementById('btn-female').className =
                data.voice === 'female' ? 'btn-success' : 'btn-neutral';
            document.getElementById('btn-male').className =
                data.voice === 'male'   ? 'btn-success' : 'btn-neutral';
        })
        .catch(function () {
            document.getElementById('capture-status').textContent = '🔴 Sem resposta';
            serverStatus.textContent = 'Erro — servidor offline?';
        });
}

setInterval(pollStatus, 2000);
pollStatus();

// --- SSE para legendas em tempo real ---
var evtSource = new EventSource('/operator-events');

evtSource.onmessage = function (event) {
    var data;
    try { data = JSON.parse(event.data); }
    catch (e) { return; }

    if (data.status === 'connected') {
        serverStatus.textContent = 'SSE conectado';
        return;
    }

    if (!data.text) return;

    // Remove placeholder inicial
    var placeholder = subtitleList.querySelector('li[style]');
    if (placeholder) { subtitleList.removeChild(placeholder); }

    var li   = document.createElement('li');
    var now  = new Date();
    var time = now.toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    li.innerHTML = '<span class="time">' + time + '</span> ' + data.text;

    if (!data.audio_id) { li.classList.add('no-audio'); }

    subtitleList.insertBefore(li, subtitleList.firstChild);
    while (subtitleList.children.length > MAX_SUBTITLES) {
        subtitleList.removeChild(subtitleList.lastChild);
    }
};

evtSource.onerror = function () {
    serverStatus.textContent = '⚫ SSE desconectado — a reconectar...';
};

// --- Ações dos Controles ---
function togglePause() {
    var endpoint = isPaused ? '/control/resume' : '/control/pause';
    fetch(endpoint, { method: 'POST' })
        .then(function () { pollStatus(); })
        .catch(function (err) { alert('Erro: ' + err.message); });
}

function restartCapture() {
    if (!confirm('Reiniciar a captura de microfone?')) return;
    document.getElementById('capture-status').textContent = '🔄 Reiniciando...';
    fetch('/control/restart-capture', { method: 'POST' })
        .then(function () { setTimeout(pollStatus, 1500); })
        .catch(function (err) { alert('Erro: ' + err.message); });
}

function setVoice(gender) {
    fetch('/set-voice', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gender: gender }),
    })
    .then(function () { pollStatus(); })
    .catch(function (err) { alert('Erro: ' + err.message); });
}

function muteAll() {
    if (!confirm('Mutar o áudio em todos os telemóveis dos membros?')) return;
    fetch('/control/mute-all', { method: 'POST' })
        .then(function (res) { return res.json(); })
        .then(function () { alert('Todos os membros foram mutados.'); })
        .catch(function (err) { alert('Erro: ' + err.message); });
}
