from __future__ import annotations
import pyaudio
import wave
import os
import uuid
import queue
import threading
from typing import Optional

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
    for d in get_audio_devices_list():
        print(f"  Índice {d['id']}: {d['name']}")


def get_audio_devices_list():
    """Retorna uma lista de dicionários com {id, name} das entradas de áudio."""
    p = pyaudio.PyAudio()
    devices = []
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:
            devices.append({
                "id": i,
                "name": info["name"]
            })
    p.terminate()
    return devices


def _get_channels(p: pyaudio.PyAudio, device_index: Optional[int]) -> int:
    """Retorna o número de canais suportados pelo dispositivo (1 ou 2)."""
    try:
        info = p.get_device_info_by_index(
            device_index if device_index is not None else p.get_default_input_device_info()["index"]
        )
        max_ch = int(info["maxInputChannels"])
        return max_ch if max_ch > 0 else 1
    except Exception:
        return 1


def _capture_loop(output_queue: queue.Queue, device_index: Optional[int], stop_event: threading.Event):
    """
    Loop de captura que roda em uma thread separada.
    Captura chunks de RECORD_SECONDS segundos e coloca na fila.
    Para quando stop_event é ativado.
    """
    p = pyaudio.PyAudio()

    max_ch = _get_channels(p, device_index)
    stream = None
    channels = 1
    for ch in sorted(set([1, 2, max_ch])):
        try:
            stream = p.open(
                format=FORMAT,
                channels=ch,
                rate=RATE,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=CHUNK,
            )
            channels = ch
            break
        except Exception:
            continue

    if stream is None:
        p.terminate()
        raise RuntimeError(f"Não foi possível abrir o microfone (device_index={device_index}). Verifique o AUDIO_DEVICE_INDEX no .env")

    print(f"Capturando áudio... (chunks de {RECORD_SECONDS}s, canais={channels})")

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
                wav_path = _save_wav(frames, p, channels)
                output_queue.put(wav_path)

    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        print("Captura de áudio encerrada.")


def _save_wav(frames: list, p: pyaudio.PyAudio, channels: int = 1) -> str:
    """Salva os frames capturados como arquivo .wav temporário."""
    os.makedirs("temp", exist_ok=True)
    wav_path = f"temp/{uuid.uuid4()}.wav"

    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))

    return wav_path


def start_capture(output_queue: queue.Queue, device_index: Optional[int] = None) -> threading.Event:
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
