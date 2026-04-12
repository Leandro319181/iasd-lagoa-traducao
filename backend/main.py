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
    await asyncio.sleep(1.0)
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
