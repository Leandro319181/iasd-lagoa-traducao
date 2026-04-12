# App de Tradução de Áudio IASD — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar um app Python que capta áudio em português da mesa de som, transcreve e traduz para inglês com Whisper, sintetiza voz com gTTS, e transmite legenda + áudio para ~8 pessoas via navegador mobile em tempo real.

**Architecture:** PyAudio captura chunks de 5 segundos em uma thread separada, coloca em uma fila síncrona (`queue.Queue`). FastAPI consome essa fila em loop assíncrono, chama Whisper (transcrição + tradução PT→EN) e gTTS (síntese de voz), depois envia resultado via SSE para todos os clientes conectados.

**Tech Stack:** Python 3.10+, FastAPI, Uvicorn, OpenAI Whisper (`small`), gTTS, PyAudio, pytest, HTML5/CSS/JS vanilla, qrcode, Windows 11.

---

## Mapa de Arquivos

```
projeto-traducao-iasd/
├── backend/
│   ├── main.py              # FastAPI: endpoints SSE, /audio, /, startup
│   ├── audio_capture.py     # PyAudio: captura em thread, fila síncrona
│   ├── transcriber.py       # Whisper: load_model(), transcribe_and_translate()
│   ├── tts.py               # gTTS: text_to_speech() → audio_id
│   ├── requirements.txt     # Dependências Python
│   └── .env                 # Configurações (device, modelo, porta)
├── frontend/
│   ├── index.html           # Página única responsiva
│   ├── style.css            # Tela escura, fonte grande
│   └── script.js            # SSE client, auto-play, reconexão
├── tests/
│   ├── test_transcriber.py
│   ├── test_tts.py
│   └── test_main.py
├── temp/                    # .wav e .mp3 temporários (criado automaticamente)
├── generate_qr.py           # Detecta IP e gera qrcode.png
└── qrcode.png               # Gerado pelo script acima
```

---

## Task 1: Estrutura do projeto e ambiente virtual

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env`

- [ ] **Step 1: Criar as pastas do projeto**

Abra o terminal (PowerShell ou CMD) e rode:

```powershell
mkdir projeto-traducao-iasd
cd projeto-traducao-iasd
mkdir backend frontend tests temp
```

- [ ] **Step 2: Criar e ativar o ambiente virtual Python**

```powershell
python -m venv venv
venv\Scripts\activate
```

Você vai ver `(venv)` no início da linha do terminal — isso confirma que está dentro do ambiente virtual.

- [ ] **Step 3: Criar `backend/requirements.txt`**

```
fastapi==0.104.1
uvicorn[standard]==0.24.0
openai-whisper==20231117
gtts==2.5.1
pydub==0.25.1
python-dotenv==1.0.0
qrcode[pil]==7.4.2
pillow==10.1.0
httpx==0.25.2
pytest==7.4.3
pytest-asyncio==0.21.1
```

> **Nota sobre PyAudio no Windows:** O PyAudio tem um passo especial de instalação. Faça separado:
> ```powershell
> pip install pipwin
> pipwin install pyaudio
> ```
> Se der erro, baixe o `.whl` manualmente em: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
> Escolha o arquivo `PyAudio‑0.2.14‑cp310‑cp310‑win_amd64.whl` e instale com:
> `pip install PyAudio‑0.2.14‑cp310‑cp310‑win_amd64.whl`

- [ ] **Step 4: Instalar as dependências**

```powershell
pip install -r backend/requirements.txt
```

> **Atenção:** O Whisper requer o `ffmpeg` instalado no Windows.
> Baixe em https://ffmpeg.org/download.html → Windows builds → Extraia e adicione a pasta `bin` ao PATH do Windows.
> Para verificar: `ffmpeg -version` (deve mostrar a versão).

- [ ] **Step 5: Criar `backend/.env`**

```env
AUDIO_DEVICE_INDEX=0
WHISPER_MODEL=small
PORT=8000
CHUNK_SECONDS=5
```

> `AUDIO_DEVICE_INDEX=0` usa o microfone padrão. Mais tarde veremos como trocar para a entrada P2/USB.

- [ ] **Step 6: Commit**

```powershell
git init
git add backend/requirements.txt backend/.env
git commit -m "chore: project structure and dependencies"
```

---

## Task 2: transcriber.py — Whisper (transcrição + tradução)

**Files:**
- Create: `backend/transcriber.py`
- Create: `tests/test_transcriber.py`

- [ ] **Step 1: Escrever o teste antes do código**

Crie `tests/test_transcriber.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
import os


def test_load_model_chama_whisper_load_model():
    """Garante que load_model chama whisper.load_model com o nome correto."""
    with patch("transcriber.whisper") as mock_whisper:
        import transcriber
        transcriber._model = None  # reseta para forçar o carregamento
        transcriber.load_model("tiny")
        mock_whisper.load_model.assert_called_once_with("tiny")


def test_transcribe_retorna_texto_traduzido(tmp_path):
    """Garante que transcribe_and_translate chama o modelo e retorna o texto."""
    # Cria um .wav fake só para o arquivo existir
    wav_file = tmp_path / "audio.wav"
    wav_file.write_bytes(b"fake_wav_data")

    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "  Hello world  "}

    with patch("transcriber._model", mock_model):
        import transcriber
        result = transcriber.transcribe_and_translate(str(wav_file))

    assert result == "Hello world"
    mock_model.transcribe.assert_called_once_with(str(wav_file), task="translate")


def test_transcribe_deleta_wav_apos_processar(tmp_path):
    """Garante que o .wav temporário é deletado após transcrição."""
    wav_file = tmp_path / "audio.wav"
    wav_file.write_bytes(b"fake_wav_data")

    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "Test"}

    with patch("transcriber._model", mock_model):
        import transcriber
        transcriber.transcribe_and_translate(str(wav_file))

    assert not wav_file.exists()


def test_transcribe_sem_modelo_lanca_erro(tmp_path):
    """Garante que erro claro é lançado se load_model não foi chamado."""
    wav_file = tmp_path / "audio.wav"
    wav_file.write_bytes(b"fake")

    with patch("transcriber._model", None):
        import transcriber
        with pytest.raises(RuntimeError, match="load_model"):
            transcriber.transcribe_and_translate(str(wav_file))
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

```powershell
cd backend
python -m pytest ../tests/test_transcriber.py -v
```

Esperado: `ModuleNotFoundError: No module named 'transcriber'`

- [ ] **Step 3: Criar `backend/transcriber.py`**

```python
import os
import whisper

# Variável global que guarda o modelo carregado
# (carregamos só uma vez para não gastar tempo toda vez)
_model = None


def load_model(model_name: str = "small"):
    """
    Carrega o modelo Whisper na memória.
    Chame isso UMA VEZ quando o servidor iniciar.
    
    model_name: "tiny" (rápido, menos preciso) ou "small" (recomendado)
    """
    global _model
    print(f"Carregando modelo Whisper '{model_name}'... (pode demorar 1-2 minutos na primeira vez)")
    _model = whisper.load_model(model_name)
    print(f"Modelo '{model_name}' carregado com sucesso!")


def transcribe_and_translate(wav_path: str) -> str:
    """
    Recebe o caminho de um arquivo .wav em português.
    Retorna o texto traduzido para inglês.
    Deleta o .wav após processar.
    
    Exemplo:
        texto = transcribe_and_translate("temp/audio123.wav")
        # texto = "Good morning, brothers and sisters"
    """
    if _model is None:
        raise RuntimeError(
            "Modelo Whisper não carregado. Chame load_model() antes de transcrever."
        )

    # task="translate" faz o Whisper transcrever E traduzir para inglês diretamente
    result = _model.transcribe(wav_path, task="translate")
    text = result["text"].strip()

    # Deleta o .wav temporário para não encher o disco
    if os.path.exists(wav_path):
        os.remove(wav_path)

    return text
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

```powershell
python -m pytest ../tests/test_transcriber.py -v
```

Esperado:
```
PASSED tests/test_transcriber.py::test_load_model_chama_whisper_load_model
PASSED tests/test_transcriber.py::test_transcribe_retorna_texto_traduzido
PASSED tests/test_transcriber.py::test_transcribe_deleta_wav_apos_processar
PASSED tests/test_transcriber.py::test_transcribe_sem_modelo_lanca_erro
4 passed
```

- [ ] **Step 5: Commit**

```powershell
git add backend/transcriber.py tests/test_transcriber.py
git commit -m "feat: add Whisper transcriber with translate task"
```

---

## Task 3: tts.py — gTTS (síntese de voz)

**Files:**
- Create: `backend/tts.py`
- Create: `tests/test_tts.py`

- [ ] **Step 1: Escrever o teste antes do código**

Crie `tests/test_tts.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
import os


def test_text_to_speech_cria_arquivo_mp3(tmp_path):
    """Garante que um arquivo .mp3 é criado no diretório correto."""
    mock_gtts = MagicMock()

    with patch("tts.gTTS", return_value=mock_gtts):
        import tts
        audio_id = tts.text_to_speech("Hello world", output_dir=str(tmp_path))

    assert audio_id is not None
    mp3_path = tmp_path / f"{audio_id}.mp3"
    mock_gtts.save.assert_called_once_with(str(mp3_path))


def test_text_to_speech_texto_vazio_retorna_none(tmp_path):
    """Garante que texto vazio não gera arquivo e retorna None."""
    import tts
    result = tts.text_to_speech("", output_dir=str(tmp_path))
    assert result is None


def test_text_to_speech_usa_idioma_ingles(tmp_path):
    """Garante que gTTS é chamado com lang='en'."""
    mock_gtts_class = MagicMock()

    with patch("tts.gTTS", mock_gtts_class):
        import tts
        tts.text_to_speech("Hello", output_dir=str(tmp_path))

    call_kwargs = mock_gtts_class.call_args[1]
    assert call_kwargs["lang"] == "en"
    assert call_kwargs["text"] == "Hello"
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

```powershell
python -m pytest ../tests/test_tts.py -v
```

Esperado: `ModuleNotFoundError: No module named 'tts'`

- [ ] **Step 3: Criar `backend/tts.py`**

```python
import os
import uuid
from gtts import gTTS


def text_to_speech(text: str, output_dir: str = "temp") -> str | None:
    """
    Converte texto em inglês para um arquivo de áudio .mp3.
    Retorna o ID único do arquivo (sem extensão) ou None se o texto for vazio.
    
    Exemplo:
        audio_id = text_to_speech("Good morning everyone")
        # audio_id = "a3f2c1d4-..." (UUID)
        # Arquivo salvo em: temp/a3f2c1d4-....mp3
    """
    # Texto vazio não gera áudio
    if not text:
        return None

    # Garante que a pasta temp existe
    os.makedirs(output_dir, exist_ok=True)

    # Gera um ID único para este arquivo de áudio
    audio_id = str(uuid.uuid4())
    filepath = os.path.join(output_dir, f"{audio_id}.mp3")

    # Cria o áudio em inglês e salva no disco
    tts = gTTS(text=text, lang="en")
    tts.save(filepath)

    return audio_id
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

```powershell
python -m pytest ../tests/test_tts.py -v
```

Esperado:
```
PASSED tests/test_tts.py::test_text_to_speech_cria_arquivo_mp3
PASSED tests/test_tts.py::test_text_to_speech_texto_vazio_retorna_none
PASSED tests/test_tts.py::test_text_to_speech_usa_idioma_ingles
3 passed
```

- [ ] **Step 5: Commit**

```powershell
git add backend/tts.py tests/test_tts.py
git commit -m "feat: add gTTS text-to-speech synthesis"
```

---

## Task 4: audio_capture.py — PyAudio (captura de áudio)

**Files:**
- Create: `backend/audio_capture.py`

> **Nota:** O PyAudio requer hardware real para testes completos. Vamos testar com mocks.

- [ ] **Step 1: Criar `backend/audio_capture.py`**

```python
import pyaudio
import wave
import os
import uuid
import queue
import threading

# Configurações de áudio
RATE = 16000        # Taxa de amostragem: 16kHz (adequado para voz)
CHANNELS = 1        # Mono (um canal — mais simples e suficiente para voz)
FORMAT = pyaudio.paInt16   # Formato de 16 bits
CHUNK = 1024        # Tamanho de cada pedaço lido do microfone
RECORD_SECONDS = 5  # Duração de cada chunk gravado


def list_audio_devices():
    """
    Lista todos os dispositivos de áudio disponíveis no PC.
    Use isso para descobrir o índice do seu cabo P2/USB.
    
    Como usar:
        python -c "from audio_capture import list_audio_devices; list_audio_devices()"
    """
    p = pyaudio.PyAudio()
    print("\nDispositivos de áudio disponíveis:")
    print("-" * 50)
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:  # Só mostra entradas (microfones/linhas)
            print(f"  Índice {i}: {info['name']}")
    print("-" * 50)
    p.terminate()


def _capture_loop(output_queue: queue.Queue, device_index: int | None, stop_event: threading.Event):
    """
    Loop de captura que roda em uma thread separada.
    Captura chunks de RECORD_SECONDS segundos e coloca na fila.
    Para quando stop_event é ativado.
    """
    p = pyaudio.PyAudio()

    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        input_device_index=device_index,  # None = dispositivo padrão
        frames_per_buffer=CHUNK,
    )

    print(f"Capturando áudio... (chunks de {RECORD_SECONDS}s)")

    try:
        while not stop_event.is_set():
            frames = []

            # Lê RECORD_SECONDS segundos de áudio
            for _ in range(int(RATE / CHUNK * RECORD_SECONDS)):
                if stop_event.is_set():
                    break
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)

            if frames:
                wav_path = _save_wav(frames, p)
                output_queue.put(wav_path)

    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        print("Captura de áudio encerrada.")


def _save_wav(frames: list, p: pyaudio.PyAudio) -> str:
    """Salva os frames capturados como arquivo .wav temporário."""
    os.makedirs("temp", exist_ok=True)
    wav_path = f"temp/{uuid.uuid4()}.wav"

    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))

    return wav_path


def start_capture(output_queue: queue.Queue, device_index: int | None = None) -> threading.Event:
    """
    Inicia a captura de áudio em uma thread de fundo.
    Retorna um stop_event — chame stop_event.set() para parar a captura.
    
    Exemplo:
        q = queue.Queue()
        stop = start_capture(q, device_index=0)
        # ... mais tarde:
        stop.set()  # para a captura
    """
    stop_event = threading.Event()
    thread = threading.Thread(
        target=_capture_loop,
        args=(output_queue, device_index, stop_event),
        daemon=True,  # Thread para automaticamente quando o programa principal para
    )
    thread.start()
    return stop_event
```

- [ ] **Step 2: Testar a listagem de dispositivos de áudio**

```powershell
cd backend
python -c "from audio_capture import list_audio_devices; list_audio_devices()"
```

Esperado (exemplo):
```
Dispositivos de áudio disponíveis:
--------------------------------------------------
  Índice 0: Microphone (Realtek Audio)
  Índice 1: Line In (USB Audio Device)
--------------------------------------------------
```

> Se você ver o cabo P2/USB na lista (ex: "Line In" ou "USB Audio"), anote o índice e coloque no `.env` como `AUDIO_DEVICE_INDEX=1`.

- [ ] **Step 3: Commit**

```powershell
git add backend/audio_capture.py
git commit -m "feat: add PyAudio capture with thread-based loop"
```

---

## Task 5: main.py — FastAPI com SSE e endpoints

**Files:**
- Create: `backend/main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Escrever os testes antes do código**

Crie `tests/test_main.py`:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import queue
import json


@pytest.fixture
def client():
    """Cria um cliente de teste com todas as dependências externas mockadas."""
    with patch("main.load_model"), \
         patch("main.start_capture", return_value=MagicMock()):
        from main import app
        with TestClient(app) as c:
            yield c


def test_raiz_retorna_html(client):
    """GET / deve retornar o arquivo index.html."""
    response = client.get("/")
    # Como o frontend pode não existir nos testes, aceitamos 200 ou 404
    assert response.status_code in [200, 404]


def test_audio_inexistente_retorna_erro(client):
    """GET /audio/id-inexistente deve retornar erro."""
    response = client.get("/audio/id-que-nao-existe-99999")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data


def test_events_conecta_e_recebe_status(client):
    """GET /events deve retornar text/event-stream e status inicial."""
    with client.stream("GET", "/events") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        # Lê apenas o primeiro evento (status: connected)
        first_line = next(response.iter_lines())
        assert "connected" in first_line
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

```powershell
python -m pytest ../tests/test_main.py -v
```

Esperado: `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Criar `backend/main.py`**

```python
import asyncio
import os
import time
import queue as sync_queue
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from transcriber import load_model, transcribe_and_translate
from tts import text_to_speech
from audio_capture import start_capture

# --- Configurações do .env ---
AUDIO_DEVICE_INDEX = os.getenv("AUDIO_DEVICE_INDEX")
AUDIO_DEVICE_INDEX = int(AUDIO_DEVICE_INDEX) if AUDIO_DEVICE_INDEX else None
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
PORT = int(os.getenv("PORT", 8000))

# --- Filas e estado compartilhado ---
audio_queue = sync_queue.Queue()   # Thread de captura → loop de processamento
clients: list[asyncio.Queue] = []  # Uma fila por cliente SSE conectado
audio_files: dict[str, float] = {} # audio_id → timestamp de criação


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialização e encerramento do servidor."""
    # Startup: carrega Whisper e inicia captura de áudio
    print("Iniciando servidor de tradução IASD...")
    load_model(WHISPER_MODEL)
    start_capture(audio_queue, AUDIO_DEVICE_INDEX)

    # Inicia loops assíncronos em background
    process_task = asyncio.create_task(process_loop())
    cleanup_task = asyncio.create_task(cleanup_loop())

    yield  # Servidor rodando

    # Shutdown: cancela as tasks
    process_task.cancel()
    cleanup_task.cancel()


app = FastAPI(lifespan=lifespan)

# Permite que os celulares da Igreja acessem o servidor
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve os arquivos do frontend (HTML, CSS, JS)
if os.path.exists("../frontend"):
    app.mount("/static", StaticFiles(directory="../frontend"), name="static")


async def process_loop():
    """
    Loop principal: lê chunks da fila de captura,
    processa com Whisper + gTTS, e notifica todos os clientes SSE.
    """
    while True:
        # Verifica a fila sem bloquear o event loop
        try:
            wav_path = audio_queue.get_nowait()
        except sync_queue.Empty:
            await asyncio.sleep(0.1)
            continue

        # Transcreve e traduz (pode levar 2-4 segundos)
        text = await asyncio.to_thread(transcribe_and_translate, wav_path)

        if not text:
            continue  # Silêncio ou ruído — descarta

        # Gera o áudio em inglês
        audio_id = await asyncio.to_thread(text_to_speech, text)

        if audio_id:
            audio_files[audio_id] = time.time()

        # Monta o evento e envia para todos os clientes conectados
        event_data = json.dumps({"text": text, "audio_id": audio_id})
        print(f"[TRADUÇÃO] {text[:60]}...")

        for client_queue in clients.copy():
            await client_queue.put(event_data)


async def cleanup_loop():
    """Remove arquivos .mp3 com mais de 60 segundos para não encher o disco."""
    while True:
        await asyncio.sleep(30)
        now = time.time()
        to_delete = [aid for aid, ts in audio_files.items() if now - ts > 60]

        for audio_id in to_delete:
            filepath = f"temp/{audio_id}.mp3"
            if os.path.exists(filepath):
                os.remove(filepath)
            audio_files.pop(audio_id, None)


# --- Endpoints ---

@app.get("/")
async def root():
    """Serve a página principal do app."""
    index_path = "../frontend/index.html"
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend não encontrado. Verifique a pasta frontend/"}


@app.get("/events")
async def events():
    """
    SSE (Server-Sent Events): cada cliente conectado recebe eventos
    com o texto traduzido e o ID do áudio em tempo real.
    """
    client_queue: asyncio.Queue = asyncio.Queue()
    clients.append(client_queue)

    async def event_generator():
        try:
            # Evento inicial confirma a conexão
            yield 'data: {"status": "connected"}\n\n'
            while True:
                data = await client_queue.get()
                yield f"data: {data}\n\n"
        finally:
            # Remove o cliente quando ele desconectar
            if client_queue in clients:
                clients.remove(client_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/audio/{audio_id}")
async def get_audio(audio_id: str):
    """Serve o arquivo .mp3 gerado pelo gTTS."""
    # Validação simples para evitar path traversal
    if "/" in audio_id or "\\" in audio_id or ".." in audio_id:
        return {"error": "ID de áudio inválido"}

    filepath = f"temp/{audio_id}.mp3"
    if not os.path.exists(filepath):
        return {"error": "Arquivo de áudio não encontrado"}

    return FileResponse(filepath, media_type="audio/mpeg")
```

- [ ] **Step 4: Rodar os testes**

```powershell
python -m pytest ../tests/test_main.py -v
```

Esperado:
```
PASSED tests/test_main.py::test_raiz_retorna_html
PASSED tests/test_main.py::test_audio_inexistente_retorna_erro
PASSED tests/test_main.py::test_events_conecta_e_recebe_status
3 passed
```

- [ ] **Step 5: Commit**

```powershell
git add backend/main.py tests/test_main.py
git commit -m "feat: add FastAPI server with SSE and audio endpoints"
```

---

## Task 6: Frontend — HTML + CSS + JavaScript

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/style.css`
- Create: `frontend/script.js`

- [ ] **Step 1: Criar `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>IASD Live Translation</title>
    <link rel="stylesheet" href="/static/style.css" />
</head>
<body>
    <div class="container">

        <header class="header">
            <h1>IASD Live Translation</h1>
            <span id="status" class="status offline">&#9899; OFFLINE</span>
        </header>

        <main class="transcript-box">
            <p id="transcript">Waiting for translation...</p>
        </main>

        <footer class="footer">
            <p>Sabbath Service &mdash; Portuguese to English</p>
        </footer>

    </div>
    <script src="/static/script.js"></script>
</body>
</html>
```

- [ ] **Step 2: Criar `frontend/style.css`**

```css
/* Reset básico */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    background-color: #0a0a0a;
    color: #ffffff;
    font-family: Arial, Helvetica, sans-serif;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
}

.container {
    width: 92%;
    max-width: 680px;
    padding: 24px 0;
}

/* Cabeçalho */
.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
}

.header h1 {
    font-size: 1rem;
    color: #888888;
    font-weight: normal;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

/* Indicador de status */
.status {
    font-size: 0.75rem;
    font-weight: bold;
    padding: 5px 14px;
    border-radius: 20px;
    letter-spacing: 0.08em;
}

.status.live {
    background-color: #cc0000;
    color: #ffffff;
    animation: pulse 1.4s ease-in-out infinite;
}

.status.offline {
    background-color: #2a2a2a;
    color: #666666;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.5; }
}

/* Caixa de legenda */
.transcript-box {
    background-color: #111111;
    border-radius: 16px;
    padding: 36px 28px;
    min-height: 220px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid #222222;
}

#transcript {
    font-size: 2rem;
    line-height: 1.5;
    color: #ffffff;
    text-align: center;
    word-break: break-word;
}

/* Rodapé */
.footer {
    margin-top: 20px;
    text-align: center;
    color: #444444;
    font-size: 0.75rem;
}

/* Telas menores (celular) */
@media (max-width: 480px) {
    #transcript {
        font-size: 1.5rem;
    }
}
```

- [ ] **Step 3: Criar `frontend/script.js`**

```javascript
// Elementos da página
const transcriptEl = document.getElementById('transcript');
const statusEl     = document.getElementById('status');

// Guarda a conexão SSE atual
let eventSource = null;

/**
 * Conecta ao servidor via SSE.
 * Se a conexão cair, tenta reconectar automaticamente a cada 3 segundos.
 */
function connect() {
    // Fecha conexão anterior se existir
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource('/events');

    // Conexão estabelecida com sucesso
    eventSource.onopen = function () {
        statusEl.textContent = '🔴 LIVE';
        statusEl.className   = 'status live';
        console.log('[SSE] Conectado ao servidor.');
    };

    // Novo evento recebido (texto + áudio)
    eventSource.onmessage = function (event) {
        let data;
        try {
            data = JSON.parse(event.data);
        } catch (e) {
            console.error('[SSE] Erro ao parsear evento:', event.data);
            return;
        }

        // Evento inicial de conexão — ignora
        if (data.status === 'connected') {
            console.log('[SSE] Handshake de conexão recebido.');
            return;
        }

        // Atualiza a legenda na tela
        if (data.text) {
            transcriptEl.textContent = data.text;
        }

        // Toca o áudio automaticamente
        if (data.audio_id) {
            playAudio(data.audio_id);
        }
    };

    // Erro ou desconexão
    eventSource.onerror = function () {
        statusEl.textContent = '⚫ OFFLINE';
        statusEl.className   = 'status offline';
        transcriptEl.textContent = 'Connection lost. Reconnecting...';
        eventSource.close();
        console.log('[SSE] Desconectado. Tentando reconectar em 3s...');
        setTimeout(connect, 3000);
    };
}

/**
 * Cria um elemento <audio> invisível e toca o .mp3 recebido.
 * O browser exige interação do usuário antes de tocar — o primeiro toque
 * na página desbloqueia o auto-play.
 */
function playAudio(audioId) {
    const audio = new Audio(`/audio/${audioId}`);
    audio.play().catch(function (error) {
        // Auto-play bloqueado pelo browser (normal na primeira vez)
        console.warn('[Audio] Auto-play bloqueado:', error.message);
        // Mostra aviso na tela para o usuário tocar uma vez
        transcriptEl.textContent += '\n\n[Tap the screen to enable audio]';
    });
}

// Inicia a conexão quando a página carrega
connect();
```

- [ ] **Step 4: Testar visualmente abrindo o arquivo no browser**

Primeiro inicie o servidor:
```powershell
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Abra no browser: `http://localhost:8000`

Você deve ver:
- Fundo preto com "IASD Live Translation"
- Indicador "⚫ OFFLINE" que vira "🔴 LIVE" em alguns segundos
- Texto "Waiting for translation..."

- [ ] **Step 5: Commit**

```powershell
git add frontend/index.html frontend/style.css frontend/script.js
git commit -m "feat: add responsive frontend with SSE client and auto-play"
```

---

## Task 7: generate_qr.py — QR Code com IP local

**Files:**
- Create: `generate_qr.py` (na raiz do projeto)

- [ ] **Step 1: Criar `generate_qr.py`**

```python
"""
Detecta o IP do PC na rede local e gera um QR Code com a URL do app.
Rode este script DEPOIS de iniciar o servidor (uvicorn).

Como usar:
    python generate_qr.py
"""
import socket
import qrcode
import os


def get_local_ip() -> str:
    """
    Descobre o IP do PC na rede WiFi local.
    Abre uma conexão fake para um servidor externo só para descobrir
    qual interface de rede está sendo usada — não envia dados.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def generate_qr(port: int = 8000):
    ip = get_local_ip()
    url = f"http://{ip}:{port}"

    print("\n" + "=" * 50)
    print(f"  URL do App: {url}")
    print(f"  Compartilhe esse link no WhatsApp!")
    print("=" * 50 + "\n")

    # Gera o QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    output_path = "qrcode.png"
    img.save(output_path)

    print(f"QR Code salvo em: {os.path.abspath(output_path)}")
    print("Imprima ou mostre na tela para os membros escanearem.\n")


if __name__ == "__main__":
    generate_qr()
```

- [ ] **Step 2: Testar a geração do QR Code**

```powershell
python generate_qr.py
```

Esperado:
```
==================================================
  URL do App: http://192.168.1.10:8000
  Compartilhe esse link no WhatsApp!
==================================================

QR Code salvo em: C:\...\projeto-traducao-iasd\qrcode.png
Imprima ou mostre na tela para os membros escanearem.
```

Abra `qrcode.png` e escaneie com o celular — deve abrir o app.

- [ ] **Step 3: Commit**

```powershell
git add generate_qr.py
git commit -m "feat: add QR code generator with local IP detection"
```

---

## Task 8: Teste de integração e ajuste do dispositivo de áudio

**Files:**
- Modify: `backend/.env`

- [ ] **Step 1: Rodar todos os testes unitários**

```powershell
cd backend
python -m pytest ../tests/ -v
```

Esperado: todos os testes passando (verde).

- [ ] **Step 2: Listar os dispositivos de áudio disponíveis**

```powershell
python -c "from audio_capture import list_audio_devices; list_audio_devices()"
```

Identifique o índice do cabo P2/USB (ex: `Índice 1: Line In (USB Audio)`)

- [ ] **Step 3: Atualizar `.env` com o dispositivo correto**

```env
AUDIO_DEVICE_INDEX=1
WHISPER_MODEL=small
PORT=8000
CHUNK_SECONDS=5
```

> Substitua `1` pelo índice real que você encontrou no passo anterior.

- [ ] **Step 4: Iniciar o servidor e testar ao vivo**

Abra dois terminais:

**Terminal 1 — Servidor:**
```powershell
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

Aguarde:
```
Carregando modelo Whisper 'small'... (pode demorar 1-2 minutos na primeira vez)
Modelo 'small' carregado com sucesso!
Capturando áudio...
INFO:     Application startup complete.
```

**Terminal 2 — QR Code:**
```powershell
python generate_qr.py
```

Abra `http://localhost:8000` no browser. Em outro dispositivo na mesma rede WiFi, escaneie o QR Code ou use o link do WhatsApp.

- [ ] **Step 5: Teste com voz**

Fale perto do microfone/entrada em português. Após ~8-11 segundos você deve ver:
- Legenda em inglês aparecendo na tela
- Áudio em inglês tocando no browser

Verifique o terminal do servidor — cada tradução aparece como:
```
[TRADUÇÃO] Good morning brothers and sisters...
```

- [ ] **Step 6: Commit final**

```powershell
git add backend/.env
git commit -m "chore: configure audio device for production use"
```

---

## Checklist Final de Validação

Antes de usar no sábado, verifique:

- [ ] `python -m pytest tests/ -v` — todos os testes passando
- [ ] Servidor inicia sem erros
- [ ] Modelo Whisper carrega (mensagem "carregado com sucesso!")
- [ ] Captura áudio da entrada configurada
- [ ] Transcrição aparece no terminal
- [ ] Legenda aparece no browser
- [ ] Áudio em inglês toca no browser
- [ ] Indicador "🔴 LIVE" aparece nos celulares conectados
- [ ] 8 celulares conseguem acessar simultaneamente via QR Code
- [ ] Se internet cair: legenda continua aparecendo, só o áudio falha
- [ ] Se celular perder WiFi e reconectar: SSE reconecta automaticamente

---

## Como iniciar toda semana (sábado de manhã)

```powershell
# 1. Abra o terminal na pasta do projeto
cd projeto-traducao-iasd

# 2. Ative o ambiente virtual
venv\Scripts\activate

# 3. Inicie o servidor
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000

# 4. Em outro terminal, gere o QR Code
python generate_qr.py

# 5. Compartilhe o link no WhatsApp do grupo
```
