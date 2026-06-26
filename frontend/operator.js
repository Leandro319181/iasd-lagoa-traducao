var isPaused    = true;
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
            var btn = document.getElementById('btn-pause');
            if (isPaused) {
                btn.textContent = '▶ Iniciar Tradução';
                btn.className   = 'btn-success';
            } else {
                btn.textContent = '⏸ Pausar Tradução';
                btn.className   = 'btn-primary';
            }
            currentVoice = data.voice;

            // Sincroniza o dropdown de áudio se ainda não estiver definido
            var devSelect = document.getElementById('device-select');
            if (devSelect && data.device_index !== undefined && !devSelect.dataset.manual) {
                devSelect.value = data.device_index;
            }

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
var evtSource = null;
function connect() {
    if (evtSource) { evtSource.close(); }
    evtSource = new EventSource('/operator-events');

    evtSource.onopen = function () {
        serverStatus.textContent = 'SSE conectado';
    };

    evtSource.onmessage = function (event) {
        var data;
        try { data = JSON.parse(event.data); }
        catch (e) { return; }

        if (data.status === 'connected') return;

        if (data.action === 'reload') {
            location.reload(true);
            return;
        }

        // Evento de áudio pronto: marca o item correspondente como tendo áudio
        if (data.audio_id && data.seq && !data.text) {
            var target = subtitleList.querySelector('li[data-seq="' + data.seq + '"]');
            if (target) { target.classList.remove('no-audio'); }
            return;
        }

        // Feedback de membro
        if (data.feedback) {
            var feedbackList = document.getElementById('feedback-list');
            var placeholder = feedbackList.querySelector('li[style]');
            if (placeholder) { feedbackList.removeChild(placeholder); }
            var li = document.createElement('li');
            li.style.cssText = 'padding:0.4rem 0;border-bottom:1px solid #eee;';
            li.innerHTML = '<span style="color:#999;font-size:0.75rem;">' 
                + data.timestamp + '</span> '
                + '<span style="color:#dc3545;font-weight:bold;">⚠ </span>'
                + escapeHtml(data.feedback);
            feedbackList.insertBefore(li, feedbackList.firstChild);
            while (feedbackList.children.length > 10) {
                feedbackList.removeChild(feedbackList.lastChild);
            }
            return;
        }

        if (!data.text) return;

        // Remove placeholder inicial
        var placeholder = subtitleList.querySelector('li[style]');
        if (placeholder) { subtitleList.removeChild(placeholder); }

        var li   = document.createElement('li');
        li.dataset.seq = data.seq;
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
        evtSource.close();
        setTimeout(connect, 3000);
    };
}
connect();

// --- Ações dos Controles ---
function togglePause() {
    var btn = document.getElementById('btn-pause');
    if (isPaused) {
        // Retomar: flush + resume
        fetch('/control/resume', { method: 'POST' })
            .then(function() { pollStatus(); })
            .catch(function(err) { alert('Erro: ' + err.message); });
    } else {
        // Pausar
        fetch('/control/pause', { method: 'POST' })
            .then(function() { pollStatus(); })
            .catch(function(err) { alert('Erro: ' + err.message); });
    }
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

// --- Seleção de Microfone ---
function loadDevices() {
    fetch('/audio-devices')
        .then(function (res) { return res.json(); })
        .then(function (devices) {
            var select = document.getElementById('device-select');
            select.innerHTML = '';
            devices.forEach(function (d) {
                var opt = document.createElement('option');
                opt.value = d.id;
                opt.textContent = d.name;
                select.appendChild(opt);
            });
            // Tenta marcar o atual a partir do primeiro poll
            pollStatus();
        })
        .catch(function (err) { console.error('Erro ao carregar dispositivos:', err); });
}

function changeDevice() {
    var select = document.getElementById('device-select');
    var idx = select.value;
    select.dataset.manual = "true"; // Evita que o polling sobrescreva enquanto instalamos

    fetch('/control/set-device', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ index: idx })
    })
    .then(function (res) { return res.json(); })
    .then(function (data) {
        if (data.status === 'updated') {
            console.log('Microfone alterado com sucesso');
            setTimeout(function() { delete select.dataset.manual; }, 2000);
        }
    })
    .catch(function (err) { alert('Erro ao mudar de microfone: ' + err.message); });
}

loadDevices();

// --- Verificação de Actualizações ---
function checkUpdates() {
    fetch('/update-status')
        .then(function (res) { return res.json(); })
        .then(function (data) {
            var banner = document.getElementById('update-banner');
            if (data.has_update) {
                var msg = data.commits_behind + ' commit(s) disponível(is)';
                if (data.latest_message) { msg += ' · ' + data.latest_message; }
                document.getElementById('update-message').textContent = msg;
                banner.classList.remove('hidden');
            } else {
                banner.classList.add('hidden');
            }
        })
        .catch(function () { /* sem rede — ignorar silenciosamente */ });
}

function applyUpdate() {
    var btn = document.getElementById('btn-apply-update');
    btn.disabled = true;
    btn.textContent = 'A actualizar...';
    fetch('/control/apply-update', { method: 'POST' })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            if (data.success) {
                document.getElementById('update-message').textContent =
                    '✅ Pronto! Fecha o terminal do servidor e abre o start.sh de novo para activar.';
                btn.style.display = 'none';
            } else {
                document.getElementById('update-message').textContent =
                    '❌ Erro: ' + data.error;
                btn.disabled = false;
                btn.textContent = 'Tentar novamente';
            }
        })
        .catch(function (err) {
            document.getElementById('update-message').textContent = '❌ Erro: ' + err.message;
            btn.disabled = false;
            btn.textContent = 'Tentar novamente';
        });
}

setInterval(checkUpdates, 24 * 60 * 60 * 1000);
checkUpdates();

// --- QR Code ---
function downloadQR() {
    var a = document.createElement('a');
    a.href = '/qr';
    a.download = 'qr-iasd-lagoa.png';
    a.click();
}

function printQR() {
    window.print();
}

function escapeHtml(text) {
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(text));
    return d.innerHTML;
}
