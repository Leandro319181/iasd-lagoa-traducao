from __future__ import annotations
import asyncio
import os
os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")
import time
import queue as sync_queue
import json
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request as FastAPIRequest
from fastapi.requests import Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from transcriber import set_local_model_name, init_groq_transcriber, transcribe_audio, whisper_translate_fallback, cleanup_wav
import translator
from tts import text_to_speech
from audio_capture import start_capture, get_audio_devices_list
import updater
import history

# --- Configurações do .env ---
_device_str = os.getenv("AUDIO_DEVICE_INDEX")
AUDIO_DEVICE_INDEX: Optional[int] = int(_device_str) if _device_str else None
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "small")
GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# --- Estado compartilhado ---
audio_queue: sync_queue.Queue = sync_queue.Queue()
tts_queue: asyncio.Queue = asyncio.Queue()
_seq_counter = 0
clients: list = []            # asyncio.Queue por cliente SSE membro
operator_clients: list = []   # asyncio.Queue por cliente SSE operador
audio_files: dict = {}        # audio_id -> timestamp
current_voice: str = "female"
is_paused: bool = True   # inicia parado — operador clica "Iniciar" pra começar
_capture_stop_event = None
_restart_lock = asyncio.Lock()
stats: dict = {
    "chunks_processed": 0,
    "last_text": "",
    "last_error": "",
    "tts_failures": 0,
    "translator_failures": 0,
    "translator_active": False,
    "groq_transcription": False,
    "hallucinations_filtered": 0,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _capture_stop_event
    print("Iniciando servidor de tradução IASD...")
    set_local_model_name(WHISPER_MODEL)
    history.init_db("logs/historico.db")
    # Inicializar Groq Whisper para transcrição de alta qualidade
    if GROQ_API_KEY:
        groq_transcription_ok = init_groq_transcriber(GROQ_API_KEY)
        stats["groq_transcription"] = groq_transcription_ok
    translator_ok = translator.init_translator(GROQ_API_KEY, GROQ_MODEL)
    stats["translator_active"] = translator_ok
    _capture_stop_event = start_capture(audio_queue, AUDIO_DEVICE_INDEX)
    process_task = asyncio.create_task(process_loop())
    cleanup_task = asyncio.create_task(cleanup_loop())
    tts_task = asyncio.create_task(tts_loop())
    yield
    if _capture_stop_event:
        _capture_stop_event.set()
    process_task.cancel()
    cleanup_task.cancel()
    tts_task.cancel()


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



def broadcast(queues, event):
    """Envia um evento a todos os clientes sem bloquear.
    Se a fila de um cliente está cheia (lento/morto), descarta para ELE só."""
    for q in list(queues):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


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

        # 1. Transcreve áudio em PT (com filtros anti-alucinação)
        pt_text = await asyncio.to_thread(transcribe_audio, wav_path)
        if pt_text is None:
            # Era alucinação ou silêncio — descarta o .wav e segue
            stats["hallucinations_filtered"] += 1
            await asyncio.to_thread(history.log_block, None, None, None, "hallucination")
            await asyncio.to_thread(cleanup_wav, wav_path)
            continue

        # 2. Tenta traduzir PT -> EN com Groq
        text = await asyncio.to_thread(translator.translate_pt_to_en, pt_text)

        # 3. Fallback: se Groq falhou, usa Whisper como tradutor
        if text is None:
            stats["translator_failures"] += 1
            print(f"[FALLBACK] Groq falhou, usando Whisper para: {pt_text[:50]}")
            text = await asyncio.to_thread(whisper_translate_fallback, wav_path)
            if text is None:
                await asyncio.to_thread(history.log_block, None, pt_text, None, "translation_failed")
                await asyncio.to_thread(cleanup_wav, wav_path)
                continue

        # 4. Limpa o .wav após processamento completo
        await asyncio.to_thread(cleanup_wav, wav_path)

        if not text:
            continue

        # 5. Sequência + broadcast IMEDIATO do texto (sem esperar o TTS)
        global _seq_counter
        _seq_counter += 1
        seq = _seq_counter

        stats["chunks_processed"] += 1
        stats["last_text"] = text

        member_event = json.dumps({"seq": seq, "text": text, "audio_id": None})
        operator_event = json.dumps({
            "seq": seq, "text": text, "audio_id": None,
            "clients": len(clients), "chunks": stats["chunks_processed"],
        })

        print(f"[TRADUÇÃO] {text[:60]}...")

        broadcast(clients, member_event)
        broadcast(operator_clients, operator_event)
        await asyncio.to_thread(history.log_block, seq, pt_text, text, "ok")

        # 6. Enfileira o TTS (processado em ordem pelo tts_loop)
        await tts_queue.put((seq, text, current_voice))


async def tts_loop():
    """Gera o áudio TTS fora do caminho crítico, em ordem, e avisa os clientes."""
    while True:
        seq, text, voice = await tts_queue.get()
        audio_id = await asyncio.to_thread(text_to_speech, text, voice)
        await asyncio.to_thread(history.mark_audio, seq, bool(audio_id))
        if not audio_id:
            stats["tts_failures"] += 1
            stats["last_error"] = f"TTS falhou: {text[:50]}"
            continue
        audio_files[audio_id] = time.time()
        stats["last_error"] = ""

        audio_event = json.dumps({"seq": seq, "audio_id": audio_id})
        broadcast(clients, audio_event)
        broadcast(operator_clients, audio_event)


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


@app.get("/setup")
async def setup_page():
    setup_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "setup.html")
    if os.path.exists(setup_path):
        return FileResponse(setup_path)
    return JSONResponse({"error": "Página de configuração não encontrada."})


@app.get("/operator")
@app.get("/operador")
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
    client_queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    clients.append(client_queue)

    async def event_generator():
        try:
            yield 'data: {"status": "connected"}\n\n'
            while True:
                try:
                    data = await asyncio.wait_for(client_queue.get(), timeout=20)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"   # SSE comment, mantém a conexão viva
        finally:
            if client_queue in clients:
                clients.remove(client_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/operator-events")
async def operator_events():
    """SSE para o painel do operador."""
    client_queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    operator_clients.append(client_queue)

    async def event_generator():
        try:
            yield 'data: {"status": "connected"}\n\n'
            while True:
                try:
                    data = await asyncio.wait_for(client_queue.get(), timeout=20)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"   # SSE comment, mantém a conexão viva
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


@app.get("/audio-devices")
async def audio_devices():
    """Lista todos os microfones/placas de som disponíveis."""
    return JSONResponse(get_audio_devices_list())


# --- Estado e Controlo ---

@app.get("/status")
async def status():
    """Estado actual do servidor para o painel do operador."""
    return JSONResponse({
        "is_paused": is_paused,
        "clients": len(clients),
        "voice": current_voice,
        "device_index": AUDIO_DEVICE_INDEX,
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
    # Esvaziar áudio acumulado durante a pausa
    while not audio_queue.empty():
        try:
            audio_queue.get_nowait()
        except Exception:
            break
    print("[CONTROLO] Tradução retomada — fila de áudio limpa")
    return JSONResponse({"paused": False})


@app.post("/control/flush-queue")
async def control_flush_queue():
    """Esvazia a fila de áudio acumulado (usar antes de retomar)."""
    flushed = 0
    while not audio_queue.empty():
        try:
            audio_queue.get_nowait()
            flushed += 1
        except Exception:
            break
    print(f"[CONTROLO] Fila esvaziada: {flushed} chunks descartados")
    return JSONResponse({"flushed": flushed})


@app.post("/control/restart-capture")
async def control_restart_capture():
    global _capture_stop_event
    async with _restart_lock:
        if _capture_stop_event:
            _capture_stop_event.set()
        await asyncio.sleep(1.0)
        _capture_stop_event = await asyncio.to_thread(
            start_capture, audio_queue, AUDIO_DEVICE_INDEX
        )
    print("[CONTROLO] Captura de áudio reiniciada")
    return JSONResponse({"status": "restarted"})


@app.post("/control/set-device")
async def control_set_device(request: Request):
    """Muda o microfone em tempo real e guarda no .env."""
    global AUDIO_DEVICE_INDEX, _capture_stop_event
    body = await request.json()
    new_index = body.get("index")

    if new_index is None:
        return JSONResponse({"error": "Índice não fornecido"}, status_code=400)

    try:
        new_index = int(new_index)
    except ValueError:
        return JSONResponse({"error": "Índice inválido"}, status_code=400)

    async with _restart_lock:
        AUDIO_DEVICE_INDEX = new_index
        # Persistir no .env
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()

        with open(env_path, "w") as f:
            found = False
            for line in lines:
                if line.startswith("AUDIO_DEVICE_INDEX="):
                    f.write(f"AUDIO_DEVICE_INDEX={new_index}\n")
                    found = True
                else:
                    f.write(line)
            if not found:
                f.write(f"AUDIO_DEVICE_INDEX={new_index}\n")

        # Reiniciar a captura
        if _capture_stop_event:
            _capture_stop_event.set()
        await asyncio.sleep(1.0)
        _capture_stop_event = await asyncio.to_thread(
            start_capture, audio_queue, AUDIO_DEVICE_INDEX
        )

    print(f"[CONTROLO] Dispositivo de áudio alterado para índice: {new_index}")
    return JSONResponse({"status": "updated", "index": new_index})


@app.post("/control/mute-all")
async def control_mute_all():
    """Envia evento de mute para todos os clientes membros."""
    mute_event = json.dumps({"action": "mute"})
    broadcast(clients, mute_event)
    print("[CONTROLO] Todos os clientes mutados")
    return JSONResponse({"status": "muted"})


@app.post("/feedback")
async def member_feedback(request: Request):
    """Recebe feedback de texto de um membro e envia ao operador via SSE."""
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "Texto vazio"}, status_code=400)
    if len(text) > 200:
        text = text[:200]
    import time as _time
    timestamp = _time.strftime("%H:%M")
    event = json.dumps({"feedback": text, "timestamp": timestamp})
    broadcast(operator_clients, event)
    print(f"[FEEDBACK] {timestamp} — {text[:60]}")
    return JSONResponse({"status": "sent"})


@app.get("/update-status")
async def update_status():
    """Verifica se há actualizações no GitHub."""
    result = await asyncio.to_thread(updater.check_for_updates)
    return JSONResponse(result)


@app.post("/control/apply-update")
async def control_apply_update():
    """Aplica as actualizações via git pull e manda recarregar os clientes."""
    result = await asyncio.to_thread(updater.apply_update)
    if result["success"]:
        print("[UPDATE] Actualização aplicada:", result["output"][:80])
        # Avisar todas as páginas (membros + operador) para recarregar
        reload_event = json.dumps({"action": "reload"})
        broadcast(clients, reload_event)
        broadcast(operator_clients, reload_event)
        print("[UPDATE] Sinal de reload enviado aos clientes.")
    else:
        print("[UPDATE] Erro ao aplicar:", result["error"])
    return JSONResponse(result)


@app.get("/qr")
async def qr_code():
    """Gera QR code PNG com o IP real da máquina na rede local."""
    import qrcode
    import io
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    url = f"http://{ip}:8000"
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(content=buf.read(), media_type="image/png")


@app.post("/api/test-mic")
async def api_test_mic(request: Request):
    """Testa um dispositivo de áudio gravando 3 segundos."""
    body = await request.json()
    device_index = body.get("device_index", 0)
    try:
        result = await asyncio.to_thread(_test_mic_sync, int(device_index))
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


def _test_mic_sync(device_index: int) -> dict:
    import pyaudio
    CHUNK = 1024
    RATE = 16000
    DURATION = 3
    try:
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16, channels=1, rate=RATE,
            input=True, input_device_index=device_index, frames_per_buffer=CHUNK
        )
        frames = []
        for _ in range(int(RATE / CHUNK * DURATION)):
            frames.append(stream.read(CHUNK, exception_on_overflow=False))
        stream.stop_stream()
        stream.close()
        p.terminate()
        total_bytes = sum(len(f) for f in frames)
        return {"ok": True, "message": f"{total_bytes // 1024}KB gravados em {DURATION}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/set-language")
async def api_set_language(request: Request):
    """Guarda o idioma de origem no .env para o Whisper."""
    body = await request.json()
    language = body.get("language", "auto")
    allowed = {"auto", "pt", "en", "es", "fr", "de", "it", "zh", "ja", "ko", "ar"}
    if language not in allowed:
        return JSONResponse({"error": "Idioma inválido"}, status_code=400)

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()

    found = False
    with open(env_path, "w") as f:
        for line in lines:
            if line.startswith("WHISPER_LANGUAGE="):
                f.write(f"WHISPER_LANGUAGE={language}\n")
                found = True
            else:
                f.write(line)
        if not found:
            f.write(f"WHISPER_LANGUAGE={language}\n")

    return JSONResponse({"ok": True, "language": language})


@app.get("/health")
async def health():
    """Endpoint de health check para lançadores e CI."""
    return JSONResponse({"status": "ok"})


@app.get("/api/diagnostics")
async def diagnostics():
    """Diagnósticos do sistema para troubleshooting."""
    import platform
    import shutil
    import socket

    checks = {}

    # Python version
    checks["python"] = {
        "version": platform.python_version(),
        "ok": tuple(int(x) for x in platform.python_version().split(".")) >= (3, 9),
    }

    # ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    checks["ffmpeg"] = {"found": bool(ffmpeg_path), "path": ffmpeg_path or "não encontrado"}

    # Modelo Whisper
    try:
        import whisper
        model_path = whisper._download(whisper._MODELS[WHISPER_MODEL], os.path.expanduser("~/.cache/whisper"), False)
        checks["whisper_model"] = {"ok": True, "model": WHISPER_MODEL}
    except Exception as e:
        checks["whisper_model"] = {"ok": False, "error": str(e)}

    # Kokoro
    try:
        from kokoro import KPipeline
        checks["kokoro"] = {"ok": True}
    except Exception as e:
        checks["kokoro"] = {"ok": False, "error": str(e)}

    # Tradutor Groq
    checks["translator"] = {
        "ok": translator.is_available(),
        "model": GROQ_MODEL,
        "configured": bool(GROQ_API_KEY),
    }

    # Transcritor Groq Whisper
    from transcriber import _groq_client as _tc
    checks["groq_transcription"] = {
        "ok": _tc is not None,
        "model": "whisper-large-v3-turbo",
        "configured": bool(GROQ_API_KEY),
    }

    # Dispositivo de áudio
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        devices = [
            p.get_device_info_by_index(i)["name"]
            for i in range(p.get_device_count())
            if p.get_device_info_by_index(i)["maxInputChannels"] > 0
        ]
        p.terminate()
        checks["audio"] = {
            "configured_index": AUDIO_DEVICE_INDEX,
            "available_devices": devices,
            "ok": AUDIO_DEVICE_INDEX is None or AUDIO_DEVICE_INDEX < len(devices),
        }
    except Exception as e:
        checks["audio"] = {"ok": False, "error": str(e)}

    # IP da rede local
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    all_ok = all(v.get("ok", True) for v in checks.values() if isinstance(v, dict))
    return JSONResponse({
        "status": "ok" if all_ok else "degraded",
        "local_ip": local_ip,
        "platform": platform.system(),
        "checks": checks,
    })
