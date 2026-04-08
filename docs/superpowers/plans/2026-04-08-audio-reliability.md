# Audio Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir edge-tts por Kokoro TTS local, corrigir playback de áudio no Chrome mobile com PWA + Wake Lock, e adicionar painel de controlo para o operador.

**Architecture:** Kokoro TTS gera WAV localmente (sem rede), FastAPI serve os ficheiros e novos endpoints de controlo, frontend torna-se PWA com Wake Lock e fila de áudio robusta baseada em elemento HTML `<audio>`, painel `/operator` separado para monitorização e controlo.

**Tech Stack:** Python 3.9+, FastAPI, Kokoro TTS (PyTorch), soundfile, Whisper, PWA (manifest + Service Worker), Wake Lock API, HTML5 Audio element.

---

## File Map

| Ação | Ficheiro | Responsabilidade |
|------|----------|-----------------|
| Modificar | `backend/transcriber.py` | Adicionar `language="pt"` |
| Modificar | `backend/tts.py` | Substituir edge-tts por Kokoro |
| Modificar | `backend/requirements.txt` | Trocar edge-tts por kokoro + soundfile |
| Modificar | `backend/main.py` | Novos endpoints + estado operador + wav |
| Modificar | `frontend/index.html` | Adicionar manifest + theme-color |
| Modificar | `frontend/script.js` | Wake Lock + fila HTML audio + mute-all |
| Criar | `frontend/manifest.json` | PWA manifest |
| Criar | `frontend/sw.js` | Service Worker cache |
| Criar | `frontend/operator.html` | Painel do operador |
| Criar | `frontend/operator.js` | Lógica do painel |
| Criar | `install.sh` | Script de instalação único |
| Modificar | `tests/test_transcriber.py` | Atualizar assert para language="pt" |
| Criar | `tests/test_tts.py` | Testes Kokoro TTS |
| Modificar | `tests/test_main.py` | Testes novos endpoints |

---

## Task 1: Fix Whisper — language="pt"

**Files:**
- Modify: `backend/transcriber.py:39`
- Modify: `tests/test_transcriber.py:28`

- [ ] **Step 1: Atualizar o teste que verifica os argumentos do transcribe**

Editar `tests/test_transcriber.py`, linha 28 — mudar o assert para incluir `language="pt"`:

```python
def test_transcribe_retorna_texto_traduzido(tmp_path):
    """Garante que transcribe_and_translate chama o modelo e retorna o texto."""
    wav_file = tmp_path / "audio.wav"
    wav_file.write_bytes(b"fake_wav_data")

    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "  Hello world  "}

    with patch("transcriber._model", mock_model):
        import transcriber
        result = transcriber.transcribe_and_translate(str(wav_file))

    assert result == "Hello world"
    mock_model.transcribe.assert_called_once_with(
        str(wav_file), task="translate", language="pt"
    )
```

- [ ] **Step 2: Correr o teste — confirmar que falha**

```bash
cd /Users/leandro/Desktop/API-Traducao
python -m pytest tests/test_transcriber.py::test_transcribe_retorna_texto_traduzido -v
```

Esperado: `FAILED — AssertionError: expected call with language="pt"`

- [ ] **Step 3: Adicionar language="pt" ao transcriber.py**

Editar `backend/transcriber.py`, linha 39:

```python
    result = _model.transcribe(wav_path, task="translate", language="pt")
```

- [ ] **Step 4: Correr todos os testes do transcriber — confirmar que passam**

```bash
python -m pytest tests/test_transcriber.py -v
```

Esperado: 5 testes `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/transcriber.py tests/test_transcriber.py
git commit -m "fix: add language=pt hint to Whisper for pt-PT/pt-BR accuracy"
```

---

## Task 2: Substituir edge-tts por Kokoro TTS

**Files:**
- Modify: `backend/requirements.txt`
- Rewrite: `backend/tts.py`
- Create: `tests/test_tts.py`
- Modify: `backend/main.py:94-97` (cleanup .mp3 → .wav)
- Modify: `backend/main.py:129-138` (get_audio .mp3 → .wav)

- [ ] **Step 1: Atualizar requirements.txt**

Substituir o conteúdo de `backend/requirements.txt`:

```
fastapi==0.104.1
uvicorn[standard]==0.24.0
openai-whisper
kokoro>=0.9.2
soundfile>=0.12.1
numpy>=1.24.0
pydub==0.25.1
PyAudio==0.2.14
python-dotenv==1.0.0
qrcode[pil]==7.4.2
pillow==10.1.0
httpx==0.25.2
pytest==7.4.3
pytest-asyncio==0.21.1
```

- [ ] **Step 2: Instalar as novas dependências**

```bash
cd /Users/leandro/Desktop/API-Traducao/backend
pip install kokoro soundfile numpy
```

Esperado: instalação sem erros. O modelo Kokoro (~85MB) é descarregado na primeira utilização.

- [ ] **Step 3: Escrever os testes para o novo tts.py**

Criar `tests/test_tts.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
import numpy as np
import os


def test_texto_vazio_retorna_none(tmp_path):
    """text_to_speech com texto vazio deve retornar None sem criar ficheiro."""
    import tts
    result = tts.text_to_speech("", output_dir=str(tmp_path))
    assert result is None
    assert list(tmp_path.glob("*.wav")) == []


def test_cria_ficheiro_wav_e_retorna_audio_id(tmp_path):
    """text_to_speech deve criar .wav e retornar UUID."""
    fake_audio = np.zeros(24000, dtype=np.float32)
    mock_pipeline = MagicMock(return_value=iter([("g", "p", fake_audio)]))

    import tts
    with patch.object(tts, "_get_pipeline", return_value=mock_pipeline):
        audio_id = tts.text_to_speech("Hello world.", output_dir=str(tmp_path))

    assert audio_id is not None
    assert (tmp_path / f"{audio_id}.wav").exists()
    assert (tmp_path / f"{audio_id}.wav").stat().st_size > 0


def test_voz_masculina_usa_am_michael(tmp_path):
    """Voz 'male' deve chamar pipeline com voice='am_michael'."""
    fake_audio = np.zeros(24000, dtype=np.float32)
    mock_pipeline = MagicMock(return_value=iter([("g", "p", fake_audio)]))

    import tts
    with patch.object(tts, "_get_pipeline", return_value=mock_pipeline):
        tts.text_to_speech("Hello.", voice="male", output_dir=str(tmp_path))

    call_kwargs = mock_pipeline.call_args
    assert call_kwargs[1]["voice"] == "am_michael"


def test_voz_feminina_usa_af_heart(tmp_path):
    """Voz 'female' (padrão) deve chamar pipeline com voice='af_heart'."""
    fake_audio = np.zeros(24000, dtype=np.float32)
    mock_pipeline = MagicMock(return_value=iter([("g", "p", fake_audio)]))

    import tts
    with patch.object(tts, "_get_pipeline", return_value=mock_pipeline):
        tts.text_to_speech("Hello.", voice="female", output_dir=str(tmp_path))

    call_kwargs = mock_pipeline.call_args
    assert call_kwargs[1]["voice"] == "af_heart"


def test_erro_retorna_none_sem_ficheiro_residual(tmp_path):
    """Se Kokoro falhar, retorna None e não deixa ficheiro .wav."""
    import tts
    with patch.object(tts, "_get_pipeline", side_effect=RuntimeError("Kokoro down")):
        result = tts.text_to_speech("Hello.", output_dir=str(tmp_path))

    assert result is None
    assert list(tmp_path.glob("*.wav")) == []
```

- [ ] **Step 4: Correr testes — confirmar que falham (tts.py ainda usa edge-tts)**

```bash
python -m pytest tests/test_tts.py -v
```

Esperado: `FAILED` ou `ImportError` porque `tts._get_pipeline` não existe ainda.

- [ ] **Step 5: Reescrever backend/tts.py com Kokoro**

```python
from __future__ import annotations
import os
import uuid
from typing import Optional

import numpy as np
import soundfile as sf

VOICE_FEMALE = "af_heart"
VOICE_MALE   = "am_michael"
SAMPLE_RATE  = 24000

_pipeline = None


def _get_pipeline():
    """Carrega o pipeline Kokoro uma vez e reutiliza (lazy init)."""
    global _pipeline
    if _pipeline is None:
        from kokoro import KPipeline
        print("[TTS] Carregando Kokoro TTS (pode demorar na 1ª vez)...")
        _pipeline = KPipeline(lang_code="a")  # "a" = American English
        print("[TTS] Kokoro pronto.")
    return _pipeline


def text_to_speech(
    text: str,
    voice: str = "female",
    output_dir: str = "temp",
) -> Optional[str]:
    """
    Converte texto em inglês para .wav usando Kokoro TTS local.
    Retorna audio_id (UUID) ou None em caso de falha.
    """
    if not text:
        return None

    os.makedirs(output_dir, exist_ok=True)
    audio_id = str(uuid.uuid4())
    filepath = os.path.join(output_dir, f"{audio_id}.wav")
    voice_name = VOICE_FEMALE if voice == "female" else VOICE_MALE

    try:
        pipeline = _get_pipeline()
        chunks = []
        for _, _, audio in pipeline(text, voice=voice_name, speed=1.0):
            chunks.append(audio)

        if not chunks:
            raise RuntimeError("Kokoro não gerou áudio")

        audio_data = np.concatenate(chunks)
        sf.write(filepath, audio_data, SAMPLE_RATE)

        if os.path.getsize(filepath) == 0:
            raise RuntimeError("Ficheiro WAV vazio")

        return audio_id

    except Exception as e:
        print(f"[TTS] Erro: {e}")
        if os.path.exists(filepath):
            os.remove(filepath)
        return None
```

- [ ] **Step 6: Correr testes TTS — confirmar que passam**

```bash
python -m pytest tests/test_tts.py -v
```

Esperado: 5 testes `PASSED`

- [ ] **Step 7: Atualizar cleanup_loop e get_audio em main.py (.mp3 → .wav)**

Em `backend/main.py`, substituir o `cleanup_loop`:

```python
async def cleanup_loop():
    """Remove ficheiros .wav com mais de 60 segundos."""
    while True:
        await asyncio.sleep(30)
        now = time.time()
        to_delete = [aid for aid, ts in audio_files.items() if now - ts > 60]
        for audio_id in to_delete:
            filepath = os.path.join("temp", f"{audio_id}.wav")
            if os.path.exists(filepath):
                os.remove(filepath)
            audio_files.pop(audio_id, None)
```

Substituir o endpoint `get_audio`:

```python
@app.get("/audio/{audio_id}")
async def get_audio(audio_id: str):
    """Serve o ficheiro .wav gerado pelo Kokoro TTS."""
    if "/" in audio_id or "\\" in audio_id or ".." in audio_id:
        return JSONResponse({"error": "ID de áudio inválido"})

    filepath = os.path.join("temp", f"{audio_id}.wav")
    if not os.path.exists(filepath):
        return JSONResponse({"error": "Arquivo de áudio não encontrado"})

    return FileResponse(filepath, media_type="audio/wav")
```

- [ ] **Step 8: Correr testes de main — confirmar que passam**

```bash
python -m pytest tests/test_main.py -v
```

Esperado: testes existentes `PASSED` (path traversal e audio inexistente continuam a funcionar com .wav)

- [ ] **Step 9: Testar TTS manualmente**

```bash
cd /Users/leandro/Desktop/API-Traducao/backend
python3 -c "
from tts import text_to_speech
import os
aid = text_to_speech('Good morning brothers and sisters. Welcome to our service.', 'female', '../temp')
print('audio_id:', aid)
path = f'../temp/{aid}.wav'
print('exists:', os.path.exists(path), '| size:', os.path.getsize(path), 'bytes')
"
```

Esperado: `audio_id: <uuid>`, `exists: True`, size > 50000

- [ ] **Step 10: Commit**

```bash
git add backend/tts.py backend/requirements.txt backend/main.py tests/test_tts.py
git commit -m "feat: replace edge-tts with local Kokoro TTS, serve WAV audio"
```

---

## Task 3: Novos endpoints de controlo e estado do operador

**Files:**
- Rewrite: `backend/main.py` (completo — adicionar estado operador + endpoints)
- Modify: `tests/test_main.py` (adicionar testes novos endpoints)

- [ ] **Step 1: Escrever testes para os novos endpoints**

Adicionar ao final de `tests/test_main.py`:

```python
@pytest.fixture
def client_v2():
    """Fixture com estado limpo para testes dos endpoints de controlo."""
    with patch("main.load_model"), \
         patch("main.start_capture", return_value=MagicMock()):
        import main
        main.clients.clear()
        main.operator_clients.clear()
        main.audio_files.clear()
        main.is_paused = False
        main.stats.update({"chunks_processed": 0, "last_text": "", "last_error": "", "tts_failures": 0})
        with TestClient(main.app) as c:
            yield c


def test_status_retorna_json(client_v2):
    """/status deve retornar JSON com campos esperados."""
    res = client_v2.get("/status")
    assert res.status_code == 200
    data = res.json()
    assert "is_paused" in data
    assert "clients" in data
    assert "voice" in data
    assert "chunks_processed" in data


def test_pause_e_resume(client_v2):
    """/control/pause deve pausar e /control/resume deve retomar."""
    import main
    assert main.is_paused is False

    res = client_v2.post("/control/pause")
    assert res.status_code == 200
    assert res.json()["paused"] is True
    assert main.is_paused is True

    res = client_v2.post("/control/resume")
    assert res.status_code == 200
    assert res.json()["paused"] is False
    assert main.is_paused is False


def test_set_voice_invalida_retorna_400(client_v2):
    """/set-voice com gender inválido deve retornar 400."""
    res = client_v2.post(
        "/set-voice",
        json={"gender": "robot"},
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 400
```

- [ ] **Step 2: Correr novos testes — confirmar que falham**

```bash
python -m pytest tests/test_main.py::test_status_retorna_json tests/test_main.py::test_pause_e_resume -v
```

Esperado: `FAILED — AttributeError: module 'main' has no attribute 'is_paused'`

- [ ] **Step 3: Reescrever backend/main.py com todo o estado e endpoints novos**

```python
from __future__ import annotations
import asyncio
import os
import time
import queue as sync_queue
import json
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from transcriber import load_model, transcribe_and_translate
from tts import text_to_speech
from audio_capture import start_capture

# --- Configurações do .env ---
_device_str = os.getenv("AUDIO_DEVICE_INDEX")
AUDIO_DEVICE_INDEX: Optional[int] = int(_device_str) if _device_str else None
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "small")

# --- Estado compartilhado ---
audio_queue: sync_queue.Queue = sync_queue.Queue()
clients: list = []            # asyncio.Queue por cliente SSE membro
operator_clients: list = []   # asyncio.Queue por cliente SSE operador
audio_files: dict = {}        # audio_id -> timestamp
current_voice: str = "female"
is_paused: bool = False
_capture_stop_event = None
stats: dict = {
    "chunks_processed": 0,
    "last_text": "",
    "last_error": "",
    "tts_failures": 0,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _capture_stop_event
    print("Iniciando servidor de tradução IASD...")
    load_model(WHISPER_MODEL)
    _capture_stop_event = start_capture(audio_queue, AUDIO_DEVICE_INDEX)
    process_task = asyncio.create_task(process_loop())
    cleanup_task = asyncio.create_task(cleanup_loop())
    yield
    if _capture_stop_event:
        _capture_stop_event.set()
    process_task.cancel()
    cleanup_task.cancel()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/static", StaticFiles(directory=_frontend_dir), name="static")


async def process_loop():
    """Lê chunks da fila, processa com Whisper + Kokoro, notifica clientes SSE."""
    while True:
        if is_paused:
            await asyncio.sleep(0.5)
            continue

        try:
            wav_path = audio_queue.get_nowait()
        except sync_queue.Empty:
            await asyncio.sleep(0.1)
            continue

        text = await asyncio.to_thread(transcribe_and_translate, wav_path)
        if not text:
            continue

        audio_id = await asyncio.to_thread(text_to_speech, text, current_voice)
        if audio_id:
            audio_files[audio_id] = time.time()
            stats["last_error"] = ""
        else:
            stats["tts_failures"] += 1
            stats["last_error"] = f"TTS falhou: {text[:50]}"

        stats["chunks_processed"] += 1
        stats["last_text"] = text

        member_event = json.dumps({"text": text, "audio_id": audio_id})
        operator_event = json.dumps({
            "text": text,
            "audio_id": audio_id,
            "clients": len(clients),
            "chunks": stats["chunks_processed"],
        })

        print(f"[TRADUÇÃO] {text[:60]}...")

        for q in list(clients):
            await q.put(member_event)
        for q in list(operator_clients):
            await q.put(operator_event)


async def cleanup_loop():
    """Remove ficheiros .wav com mais de 60 segundos."""
    while True:
        await asyncio.sleep(30)
        now = time.time()
        to_delete = [aid for aid, ts in audio_files.items() if now - ts > 60]
        for audio_id in to_delete:
            filepath = os.path.join("temp", f"{audio_id}.wav")
            if os.path.exists(filepath):
                os.remove(filepath)
            audio_files.pop(audio_id, None)


# --- Páginas ---

@app.get("/")
async def root():
    index_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({"message": "Frontend não encontrado."})


@app.get("/operator")
async def operator_page():
    op_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "operator.html")
    if os.path.exists(op_path):
        return FileResponse(op_path)
    return JSONResponse({"error": "Página do operador não encontrada."})


@app.get("/sw.js")
async def service_worker():
    sw_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "sw.js")
    if os.path.exists(sw_path):
        return FileResponse(sw_path, media_type="application/javascript")
    return JSONResponse({"error": "sw.js não encontrado."})


# --- SSE ---

@app.get("/events")
async def events():
    """SSE para clientes membros."""
    client_queue: asyncio.Queue = asyncio.Queue()
    clients.append(client_queue)

    async def event_generator():
        try:
            yield 'data: {"status": "connected"}\n\n'
            while True:
                data = await client_queue.get()
                yield f"data: {data}\n\n"
        finally:
            if client_queue in clients:
                clients.remove(client_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/operator-events")
async def operator_events():
    """SSE para o painel do operador."""
    client_queue: asyncio.Queue = asyncio.Queue()
    operator_clients.append(client_queue)

    async def event_generator():
        try:
            yield 'data: {"status": "connected"}\n\n'
            while True:
                data = await client_queue.get()
                yield f"data: {data}\n\n"
        finally:
            if client_queue in operator_clients:
                operator_clients.remove(client_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# --- Áudio ---

@app.get("/audio/{audio_id}")
async def get_audio(audio_id: str):
    """Serve o ficheiro .wav gerado pelo Kokoro TTS."""
    if "/" in audio_id or "\\" in audio_id or ".." in audio_id:
        return JSONResponse({"error": "ID de áudio inválido"})

    filepath = os.path.join("temp", f"{audio_id}.wav")
    if not os.path.exists(filepath):
        return JSONResponse({"error": "Arquivo de áudio não encontrado"})

    return FileResponse(filepath, media_type="audio/wav")


# --- Estado e Controlo ---

@app.get("/status")
async def status():
    """Estado actual do servidor para o painel do operador."""
    return JSONResponse({
        "is_paused": is_paused,
        "clients": len(clients),
        "voice": current_voice,
        **stats,
    })


@app.post("/set-voice")
async def set_voice(request: Request):
    global current_voice
    body = await request.json()
    gender = body.get("gender", "female")
    if gender not in ("male", "female"):
        return JSONResponse({"error": "Use 'male' ou 'female'"}, status_code=400)
    current_voice = gender
    print(f"[VOZ] Alterada para: {current_voice}")
    return JSONResponse({"voice": current_voice})


@app.post("/control/pause")
async def control_pause():
    global is_paused
    is_paused = True
    print("[CONTROLO] Tradução pausada")
    return JSONResponse({"paused": True})


@app.post("/control/resume")
async def control_resume():
    global is_paused
    is_paused = False
    print("[CONTROLO] Tradução retomada")
    return JSONResponse({"paused": False})


@app.post("/control/restart-capture")
async def control_restart_capture():
    global _capture_stop_event
    if _capture_stop_event:
        _capture_stop_event.set()
    await asyncio.sleep(1.0)  # aguarda thread parar
    _capture_stop_event = start_capture(audio_queue, AUDIO_DEVICE_INDEX)
    print("[CONTROLO] Captura de áudio reiniciada")
    return JSONResponse({"status": "restarted"})


@app.post("/control/mute-all")
async def control_mute_all():
    """Envia evento de mute para todos os clientes membros."""
    mute_event = json.dumps({"action": "mute"})
    for q in list(clients):
        await q.put(mute_event)
    print("[CONTROLO] Todos os clientes mutados")
    return JSONResponse({"status": "muted"})
```

- [ ] **Step 4: Correr todos os testes — confirmar que passam**

```bash
python -m pytest tests/ -v
```

Esperado: todos os testes `PASSED`

- [ ] **Step 5: Testar endpoints manualmente (servidor em background)**

```bash
cd /Users/leandro/Desktop/API-Traducao/backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
sleep 5
curl -s http://localhost:8000/status | python3 -m json.tool
curl -s -X POST http://localhost:8000/control/pause | python3 -m json.tool
curl -s http://localhost:8000/status | python3 -m json.tool  # is_paused deve ser true
curl -s -X POST http://localhost:8000/control/resume | python3 -m json.tool
pkill -f "uvicorn main:app"
```

Esperado: `/status` retorna JSON com `is_paused: false/true`, `/control/pause` retorna `{"paused": true}`

- [ ] **Step 6: Commit**

```bash
git add backend/main.py tests/test_main.py
git commit -m "feat: add operator state, control endpoints, and operator SSE"
```

---

## Task 4: PWA + Wake Lock + fila de áudio robusta

**Files:**
- Create: `frontend/manifest.json`
- Create: `frontend/sw.js`
- Modify: `frontend/index.html`
- Rewrite: `frontend/script.js`

- [ ] **Step 1: Criar frontend/manifest.json**

```json
{
  "name": "IASD Lagoa – Live Translation",
  "short_name": "Tradução IASD",
  "description": "Tradução ao vivo PT → EN para membros anglófonos",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0a0a0a",
  "theme_color": "#cc0000",
  "icons": [
    {
      "src": "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='20' fill='%23cc0000'/><text y='75' x='50' text-anchor='middle' font-size='60'>🎙</text></svg>",
      "sizes": "any",
      "type": "image/svg+xml",
      "purpose": "any maskable"
    }
  ]
}
```

- [ ] **Step 2: Criar frontend/sw.js**

```javascript
var CACHE = 'iasd-v2';
var STATIC = ['/', '/static/style.css', '/static/script.js', '/static/manifest.json'];

self.addEventListener('install', function (e) {
    e.waitUntil(
        caches.open(CACHE).then(function (cache) {
            return cache.addAll(STATIC);
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', function (e) {
    e.waitUntil(
        caches.keys().then(function (keys) {
            return Promise.all(
                keys.filter(function (k) { return k !== CACHE; }).map(function (k) {
                    return caches.delete(k);
                })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', function (e) {
    var url = e.request.url;
    // Nunca cachear SSE, áudio ou status — esses são sempre ao vivo
    if (url.includes('/events') || url.includes('/audio/') || url.includes('/status') || url.includes('/operator')) {
        return;
    }
    e.respondWith(
        caches.match(e.request).then(function (cached) {
            return cached || fetch(e.request);
        })
    );
});
```

- [ ] **Step 3: Atualizar frontend/index.html — adicionar manifest e theme-color**

Substituir o `<head>` de `frontend/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="theme-color" content="#cc0000" />
    <meta name="mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-status-bar-style" content="black" />
    <title>IASD Lagoa – Live Translation</title>
    <link rel="stylesheet" href="/static/style.css" />
    <link rel="manifest" href="/static/manifest.json" />
</head>
<body>
    <div class="container">

        <header class="header">
            <div class="church-info">
                <span class="church-name">IASD LAGOA</span>
                <span class="service-label">Sabbath Service · Live Translation</span>
            </div>
            <span id="status" class="status offline">&#9899; OFFLINE</span>
        </header>

        <main class="transcript-box">
            <p id="transcript" class="waiting">Waiting for the service to begin...</p>
        </main>

        <div class="controls">
            <div class="voice-selector">
                <span class="controls-label">Speaker voice</span>
                <div class="voice-buttons">
                    <button id="btn-female" class="voice-btn active" onclick="setVoice('female')">
                        👩 Female
                    </button>
                    <button id="btn-male" class="voice-btn" onclick="setVoice('male')">
                        👨 Male
                    </button>
                </div>
            </div>

            <button id="audio-toggle" class="audio-btn audio-on" onclick="toggleAudio()">
                🔊 Audio ON
            </button>
        </div>

        <div class="instructions">
            <p>&#9432; Keep this page open · Translation appears automatically</p>
            <p>Tap <strong>Audio ON/OFF</strong> to choose how you follow</p>
        </div>

    </div>
    <script src="/static/script.js"></script>
</body>
</html>
```

- [ ] **Step 4: Reescrever frontend/script.js — Wake Lock + fila robusta + mute-all**

```javascript
var transcriptEl  = document.getElementById('transcript');
var statusEl      = document.getElementById('status');
var audioToggleEl = document.getElementById('audio-toggle');
var btnFemale     = document.getElementById('btn-female');
var btnMale       = document.getElementById('btn-male');

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

// --- Controlo de Voz ---
function setVoice(gender) {
    fetch('/set-voice', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gender: gender }),
    })
    .then(function (res) { return res.json(); })
    .then(function (data) {
        btnFemale.classList.toggle('active', data.voice === 'female');
        btnMale.classList.toggle('active',   data.voice === 'male');
    })
    .catch(function (err) { console.error('[VOZ] Erro:', err); });
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
```

- [ ] **Step 5: Verificar que os ficheiros foram criados**

```bash
ls /Users/leandro/Desktop/API-Traducao/frontend/
```

Esperado: `index.html  manifest.json  operator.html  operator.js  script.js  style.css  sw.js`
(operator.html e operator.js ainda não existem — criam-se na Task 5)

- [ ] **Step 6: Testar PWA no servidor**

```bash
cd /Users/leandro/Desktop/API-Traducao/backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
sleep 3
curl -s http://localhost:8000/static/manifest.json | python3 -m json.tool
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/sw.js
pkill -f "uvicorn main:app"
```

Esperado: manifest.json retorna JSON válido, `/sw.js` retorna `200`

- [ ] **Step 7: Commit**

```bash
git add frontend/manifest.json frontend/sw.js frontend/index.html frontend/script.js
git commit -m "feat: PWA manifest, service worker, Wake Lock, robust audio queue"
```

---

## Task 5: Painel do Operador

**Files:**
- Create: `frontend/operator.html`
- Create: `frontend/operator.js`

- [ ] **Step 1: Criar frontend/operator.html**

```html
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>IASD – Painel do Operador</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #0d0d0d; color: #e0e0e0; font-family: Arial, sans-serif; padding: 20px; }
        h1 { font-size: 1.2rem; color: #fff; margin-bottom: 20px; letter-spacing: 0.05em; }
        h2 { font-size: 0.75rem; color: #555; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 12px; }
        section { background: #1a1a1a; border-radius: 12px; padding: 18px; margin-bottom: 16px; border: 1px solid #2a2a2a; }
        .stat-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
        .stat { background: #111; border-radius: 8px; padding: 12px; }
        .stat label { display: block; font-size: 0.65rem; color: #555; text-transform: uppercase; margin-bottom: 4px; }
        .stat span { font-size: 1.4rem; font-weight: bold; color: #fff; }
        .error-box { background: #3a0a0a; border: 1px solid #cc0000; border-radius: 8px; padding: 10px; margin-top: 12px; font-size: 0.8rem; color: #ff6666; }
        .hidden { display: none; }
        .btn-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
        button { padding: 12px; border-radius: 8px; border: none; font-size: 0.85rem; font-weight: bold; cursor: pointer; transition: opacity 0.2s; }
        button:active { opacity: 0.7; }
        .btn-primary   { background: #1a4a8a; color: #fff; }
        .btn-danger    { background: #8a1a1a; color: #fff; }
        .btn-success   { background: #1a6b1a; color: #fff; }
        .btn-warning   { background: #6b5a1a; color: #fff; }
        .btn-neutral   { background: #2a2a2a; color: #aaa; }
        .btn-paused    { background: #cc0000; color: #fff; }
        #subtitle-list { list-style: none; }
        #subtitle-list li { padding: 8px 0; border-bottom: 1px solid #222; font-size: 0.9rem; line-height: 1.4; }
        #subtitle-list li:last-child { border-bottom: none; }
        #subtitle-list .time { color: #555; font-size: 0.7rem; margin-right: 8px; }
        #subtitle-list li.no-audio { color: #888; }
        #subtitle-list li.no-audio::after { content: " ⚠ sem áudio"; color: #cc4400; font-size: 0.7rem; }
        #server-status { font-size: 0.75rem; color: #555; margin-top: 4px; }
    </style>
</head>
<body>
    <h1>⚙ Painel do Operador — IASD Lagoa</h1>
    <div id="server-status">A conectar...</div>

    <section>
        <h2>Estado</h2>
        <div class="stat-grid">
            <div class="stat">
                <label>Captura de Áudio</label>
                <span id="capture-status">—</span>
            </div>
            <div class="stat">
                <label>Membros Conectados</label>
                <span id="clients-count">—</span>
            </div>
            <div class="stat">
                <label>Chunks Processados</label>
                <span id="chunks-count">—</span>
            </div>
            <div class="stat">
                <label>Falhas TTS</label>
                <span id="tts-failures">—</span>
            </div>
        </div>
        <div id="last-error" class="error-box hidden"></div>
    </section>

    <section>
        <h2>Controles</h2>
        <div class="btn-grid">
            <button id="btn-pause" class="btn-primary" onclick="togglePause()">⏸ Pausar</button>
            <button class="btn-warning" onclick="restartCapture()">🔄 Reiniciar Microfone</button>
            <button id="btn-female" class="btn-neutral" onclick="setVoice('female')">👩 Voz Feminina</button>
            <button id="btn-male"   class="btn-neutral" onclick="setVoice('male')">👨 Voz Masculina</button>
            <button class="btn-danger" onclick="muteAll()" style="grid-column: span 2;">🔇 Mutar Todos os Membros</button>
        </div>
    </section>

    <section>
        <h2>Últimas Legendas</h2>
        <ol id="subtitle-list">
            <li style="color:#444; font-style:italic;">A aguardar traduções...</li>
        </ol>
    </section>

    <script src="/static/operator.js"></script>
</body>
</html>
```

- [ ] **Step 2: Criar frontend/operator.js**

```javascript
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
```

- [ ] **Step 3: Verificar que /operator responde corretamente**

```bash
cd /Users/leandro/Desktop/API-Traducao/backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
sleep 4
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/operator
pkill -f "uvicorn main:app"
```

Esperado: `200`

- [ ] **Step 4: Commit**

```bash
git add frontend/operator.html frontend/operator.js
git commit -m "feat: add operator control panel with real-time status and controls"
```

---

## Task 6: Script de Instalação

**Files:**
- Create: `install.sh`

- [ ] **Step 1: Criar install.sh**

```bash
#!/bin/bash
set -e

echo ""
echo "================================================="
echo "  Instalação — App de Tradução IASD"
echo "================================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 1. Verificar Python 3.9+
PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null)
if [ -z "$PYTHON" ]; then
    echo "ERRO: Python 3 não encontrado."
    echo "Instale em: https://www.python.org/downloads/"
    exit 1
fi

VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
MAJOR=$(echo "$VERSION" | cut -d. -f1)
MINOR=$(echo "$VERSION" | cut -d. -f2)

if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 9 ]; }; then
    echo "ERRO: Python $VERSION encontrado. Necessário Python 3.9 ou superior."
    exit 1
fi
echo "✓ Python $VERSION encontrado"

# 2. Criar ambiente virtual
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "A criar ambiente virtual..."
    $PYTHON -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
echo "✓ Ambiente virtual pronto"

# 3. Instalar dependências
echo "A instalar dependências (pode demorar 3-5 min)..."
pip install -q --upgrade pip
pip install -q -r "$SCRIPT_DIR/backend/requirements.txt"
echo "✓ Dependências instaladas"

# 4. Descarregar modelo Kokoro (primeira vez)
echo "A verificar modelo de voz Kokoro (~85MB, só na primeira vez)..."
$PYTHON -c "
from kokoro import KPipeline
import numpy as np, soundfile as sf, tempfile, os
p = KPipeline(lang_code='a')
chunks = []
for _, _, a in p('Ready.', voice='af_heart'):
    chunks.append(a)
with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
    sf.write(f.name, np.concatenate(chunks), 24000)
    os.remove(f.name)
print('OK')
"
echo "✓ Modelo de voz pronto"

# 5. Criar .env se não existir
ENV_FILE="$SCRIPT_DIR/backend/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo ""
    echo "Dispositivos de áudio disponíveis:"
    $PYTHON -c "
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    d = p.get_device_info_by_index(i)
    if d['maxInputChannels'] > 0:
        print(f'  [{i}] {d[\"name\"]}')
p.terminate()
"
    echo ""
    printf "Índice do microfone/mesa de som [0]: "
    read -r DEV_IDX
    DEV_IDX=${DEV_IDX:-0}

    cat > "$ENV_FILE" << EOF
AUDIO_DEVICE_INDEX=$DEV_IDX
WHISPER_MODEL=small
PORT=8000
CHUNK_SECONDS=5
EOF
    echo "✓ Ficheiro .env criado (dispositivo $DEV_IDX)"
else
    echo "✓ Ficheiro .env já existe"
fi

# 6. Criar pasta temp
mkdir -p "$SCRIPT_DIR/temp"
echo "✓ Pasta temp/ pronta"

# 7. Gerar start.sh
START_SCRIPT="$SCRIPT_DIR/start.sh"
cat > "$START_SCRIPT" << 'STARTEOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/backend"
source "$SCRIPT_DIR/.venv/bin/activate"
echo ""
echo "================================================="
echo "  Servidor de Tradução IASD — A iniciar..."
echo "================================================="
python -m uvicorn main:app --host 0.0.0.0 --port 8000
STARTEOF
chmod +x "$START_SCRIPT"
echo "✓ start.sh criado"

# 8. Mostrar resultado
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "127.0.0.1")
echo ""
echo "================================================="
echo ""
echo "  ✅ Instalação concluída!"
echo ""
echo "  Para iniciar:"
echo "    ./start.sh"
echo ""
echo "  App dos membros:"
echo "    http://$IP:8000"
echo ""
echo "  Painel do operador:"
echo "    http://$IP:8000/operator"
echo ""
echo "================================================="
```

- [ ] **Step 2: Tornar executável e testar sintaxe**

```bash
chmod +x /Users/leandro/Desktop/API-Traducao/install.sh
bash -n /Users/leandro/Desktop/API-Traducao/install.sh && echo "Sintaxe OK"
```

Esperado: `Sintaxe OK`

- [ ] **Step 3: Commit**

```bash
git add install.sh
git commit -m "feat: add one-command install script with audio device detection"
```

---

## Task 7: Teste de sistema completo

- [ ] **Step 1: Correr suite de testes completa**

```bash
cd /Users/leandro/Desktop/API-Traducao
python -m pytest tests/ -v
```

Esperado: todos os testes `PASSED`

- [ ] **Step 2: Iniciar servidor e verificar todas as rotas**

```bash
cd /Users/leandro/Desktop/API-Traducao/backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
sleep 5

echo "--- / (app membros) ---"
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/

echo "--- /operator ---"
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/operator

echo "--- /sw.js ---"
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/sw.js

echo "--- /status ---"
curl -s http://localhost:8000/status | python3 -m json.tool

echo "--- /static/manifest.json ---"
curl -s http://localhost:8000/static/manifest.json | python3 -m json.tool

pkill -f "uvicorn main:app"
```

Esperado: todas as rotas retornam `200`, `/status` e `/static/manifest.json` retornam JSON válido

- [ ] **Step 3: Commit final**

```bash
git add -A
git commit -m "chore: audio reliability improvements complete — Kokoro TTS, PWA, operator panel"
```
