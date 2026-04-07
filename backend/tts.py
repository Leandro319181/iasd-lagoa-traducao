from __future__ import annotations
import asyncio
import os
import uuid
from typing import Optional

import edge_tts

# Vozes disponíveis (Microsoft Edge TTS — alta qualidade, grátis)
VOICE_MALE   = "en-US-ChristopherNeural"
VOICE_FEMALE = "en-US-JennyNeural"


def text_to_speech(
    text: str,
    voice: str = "female",
    output_dir: str = "temp",
) -> Optional[str]:
    """
    Converte texto em inglês para um arquivo .mp3 usando Edge TTS.

    Parâmetros:
        text       — texto a sintetizar
        voice      — "female" (padrão) ou "male"
        output_dir — pasta onde salvar o .mp3 (padrão: temp/)

    Retorna o audio_id (UUID) ou None em caso de falha.
    """
    if not text:
        return None

    os.makedirs(output_dir, exist_ok=True)

    audio_id = str(uuid.uuid4())
    filepath = os.path.join(output_dir, f"{audio_id}.mp3")

    voice_name = VOICE_FEMALE if voice == "female" else VOICE_MALE

    try:
        # edge-tts é assíncrono; asyncio.run() cria um event loop isolado na thread
        asyncio.run(_synthesize(text, voice_name, filepath))
    except Exception as e:
        print(f"[TTS] Erro ao sintetizar áudio: {e}")
        return None

    return audio_id


async def _synthesize(text: str, voice_name: str, filepath: str) -> None:
    """Chama a API do Edge TTS e salva o .mp3."""
    communicate = edge_tts.Communicate(text, voice_name)
    await communicate.save(filepath)
