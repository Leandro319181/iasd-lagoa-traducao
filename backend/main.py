from __future__ import annotations
import asyncio
import os
import time
import queue as sync_queue
import json
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
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
clients: list = []       # uma asyncio.Queue por cliente SSE conectado
audio_files: dict = {}   # audio_id -> timestamp de criação


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup e shutdown do servidor."""
    print("Iniciando servidor de tradução IASD...")
    load_model(WHISPER_MODEL)
    start_capture(audio_queue, AUDIO_DEVICE_INDEX)
    process_task = asyncio.create_task(process_loop())
    cleanup_task = asyncio.create_task(cleanup_loop())
    yield
    process_task.cancel()
    cleanup_task.cancel()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve arquivos do frontend se a pasta existir
_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/static", StaticFiles(directory=_frontend_dir), name="static")


async def process_loop():
    """Lê chunks da fila, processa com Whisper + gTTS, notifica clientes SSE."""
    while True:
        try:
            wav_path = audio_queue.get_nowait()
        except sync_queue.Empty:
            await asyncio.sleep(0.1)
            continue

        text = await asyncio.to_thread(transcribe_and_translate, wav_path)
        if not text:
            continue

        audio_id = await asyncio.to_thread(text_to_speech, text)
        if audio_id:
            audio_files[audio_id] = time.time()

        event_data = json.dumps({"text": text, "audio_id": audio_id})
        print(f"[TRADUÇÃO] {text[:60]}...")

        for client_queue in list(clients):
            await client_queue.put(event_data)


async def cleanup_loop():
    """Remove arquivos .mp3 com mais de 60 segundos."""
    while True:
        await asyncio.sleep(30)
        now = time.time()
        to_delete = [aid for aid, ts in audio_files.items() if now - ts > 60]
        for audio_id in to_delete:
            filepath = os.path.join("temp", f"{audio_id}.mp3")
            if os.path.exists(filepath):
                os.remove(filepath)
            audio_files.pop(audio_id, None)


@app.get("/")
async def root():
    """Serve a página principal do app."""
    index_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({"message": "Frontend não encontrado. Verifique a pasta frontend/"})


@app.get("/events")
async def events():
    """SSE: envia texto traduzido + audio_id para todos os clientes conectados."""
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


@app.get("/audio/{audio_id}")
async def get_audio(audio_id: str):
    """Serve o arquivo .mp3 gerado pelo gTTS."""
    if "/" in audio_id or "\\" in audio_id or ".." in audio_id:
        return JSONResponse({"error": "ID de áudio inválido"})

    filepath = os.path.join("temp", f"{audio_id}.mp3")
    if not os.path.exists(filepath):
        return JSONResponse({"error": "Arquivo de áudio não encontrado"})

    return FileResponse(filepath, media_type="audio/mpeg")
