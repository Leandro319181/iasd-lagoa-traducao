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
