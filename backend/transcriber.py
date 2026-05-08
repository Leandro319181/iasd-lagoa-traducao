"""
Transcrição PT com Whisper + filtros anti-alucinação.
Separado da tradução para permitir uso de LLM externo de qualidade.
"""
from typing import Optional, Tuple
import os
import re
import whisper

_model: Optional[object] = None

# Frases que o Whisper alucina (treinado em legendas de YouTube/etc)
HALLUCINATION_PHRASES = {
    "obrigado por assistir",
    "obrigado por assistir!",
    "obrigado pela atenção",
    "legendas pela comunidade amara.org",
    "legendado pela comunidade amara.org",
    "legendas: amara.org",
    "subtitles by the amara.org community",
    "thanks for watching",
    "thank you for watching",
    "please subscribe",
    "like and subscribe",
    "se inscreva no canal",
    "deixe seu like",
    "...",
    ".",
    "♪",
    "[música]",
    "[music]",
    "[applause]",
    "[aplausos]",
}

# Limite de probabilidade de "não-fala" — acima disso, descarta
NO_SPEECH_THRESHOLD = 0.6
# Limite máximo de caracteres não-latinos antes de considerar alucinação
NON_LATIN_RATIO_THRESHOLD = 0.3
# Mínimo de caracteres para considerar tradução válida
MIN_TEXT_LENGTH = 3


def load_model(model_name: str = "small"):
    """Carrega o modelo Whisper. Chamar UMA VEZ no startup."""
    global _model
    print(f"Carregando modelo Whisper '{model_name}'...")
    _model = whisper.load_model(model_name)
    print(f"Modelo '{model_name}' carregado com sucesso!")


def _is_non_latin_heavy(text: str) -> bool:
    """Detecta texto majoritariamente em chinês/japonês/coreano/árabe/cirílico."""
    if not text:
        return False
    non_latin_count = sum(
        1 for c in text
        if c.isalpha() and not (
            ('a' <= c.lower() <= 'z') or c in 'áàâãäéèêëíìîïóòôõöúùûüçñ'
        )
    )
    total_alpha = sum(1 for c in text if c.isalpha())
    if total_alpha == 0:
        return False
    return (non_latin_count / total_alpha) > NON_LATIN_RATIO_THRESHOLD


def _is_repetitive_loop(text: str) -> bool:
    """Detecta loops do tipo 'amém amém amém amém amém'."""
    words = text.lower().split()
    if len(words) < 5:
        return False
    # Se a mesma palavra aparece >50% das vezes, é loop
    from collections import Counter
    counts = Counter(words)
    most_common_word, count = counts.most_common(1)[0]
    if count / len(words) > 0.5 and len(most_common_word) > 2:
        return True
    # Detecta padrões repetidos do tipo "X Y X Y X Y"
    if len(words) >= 6:
        pattern = " ".join(words[:2])
        repeated = " ".join(words).count(pattern)
        if repeated >= 3:
            return True
    return False


def _is_hallucination(text: str, no_speech_prob: float) -> Tuple[bool, str]:
    """
    Retorna (é_alucinação, motivo).
    Aplica todos os filtros de alucinação conhecidos.
    """
    if not text or len(text.strip()) < MIN_TEXT_LENGTH:
        return True, "texto vazio ou muito curto"

    if no_speech_prob > NO_SPEECH_THRESHOLD:
        return True, f"no_speech_prob alto ({no_speech_prob:.2f})"

    text_lower = text.lower().strip().rstrip(".,!?")
    if text_lower in HALLUCINATION_PHRASES:
        return True, f"frase alucinada conhecida: '{text[:40]}'"

    if _is_non_latin_heavy(text):
        return True, f"texto não-latino (provável chinês/japonês alucinado)"

    if _is_repetitive_loop(text):
        return True, f"loop repetitivo detectado"

    return False, ""


def transcribe_audio(wav_path: str) -> Optional[str]:
    """
    Transcreve áudio PT com Whisper. Retorna texto PT ou None se for alucinação.
    NÃO deleta o .wav (caller decide, para permitir fallback de tradução).
    """
    if _model is None:
        raise RuntimeError("Modelo Whisper não carregado. Chame load_model() antes.")

    if not os.path.exists(wav_path):
        return None

    # Whisper retorna mais info quando pegamos result completo
    result = _model.transcribe(
        wav_path,
        task="transcribe",
        language="pt",
        no_speech_threshold=0.6,
        condition_on_previous_text=False,  # evita propagar alucinações entre chunks
    )
    text = result["text"].strip()

    # Calcula no_speech_prob médio dos segmentos
    segments = result.get("segments", [])
    if segments:
        no_speech_prob = sum(s.get("no_speech_prob", 0) for s in segments) / len(segments)
    else:
        no_speech_prob = 0.0

    is_halluc, reason = _is_hallucination(text, no_speech_prob)
    if is_halluc:
        print(f"[ANTI-ALUCINAÇÃO] Descartado: {reason} | texto: '{text[:60]}'")
        return None

    return text


def whisper_translate_fallback(wav_path: str) -> Optional[str]:
    """
    FALLBACK: Whisper traduz direto PT->EN. Usar só se Groq falhar.
    Aplica os mesmos filtros anti-alucinação.
    """
    if _model is None:
        raise RuntimeError("Modelo Whisper não carregado.")

    if not os.path.exists(wav_path):
        return None

    result = _model.transcribe(
        wav_path,
        task="translate",
        language="pt",
        no_speech_threshold=0.6,
        condition_on_previous_text=False,
    )
    text = result["text"].strip()

    segments = result.get("segments", [])
    if segments:
        no_speech_prob = sum(s.get("no_speech_prob", 0) for s in segments) / len(segments)
    else:
        no_speech_prob = 0.0

    is_halluc, reason = _is_hallucination(text, no_speech_prob)
    if is_halluc:
        print(f"[ANTI-ALUCINAÇÃO/FALLBACK] Descartado: {reason}")
        return None

    return text


def cleanup_wav(wav_path: str):
    """Deleta o .wav após uso. Chamar quando terminar todo o processamento."""
    if os.path.exists(wav_path):
        os.remove(wav_path)
