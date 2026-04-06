from __future__ import annotations
import os
import uuid
from typing import Optional
from gtts import gTTS


def text_to_speech(text: str, output_dir: str = "temp") -> Optional[str]:
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
