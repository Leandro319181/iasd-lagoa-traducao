"""
Transcrição PT com Whisper + filtros anti-alucinação.
Suporta transcrição via Groq API (whisper-large-v3-turbo) como primária,
e Whisper local como fallback.
"""
from __future__ import annotations
from typing import Optional, Tuple
import os
import whisper

_model: Optional[object] = None
_groq_client: Optional[object] = None

# ── Prompt inicial teológico adventista ───────────────────────────────────────
# Orienta o Whisper sobre o vocabulário esperado antes de ouvir o áudio.
# Máximo ~224 tokens — não exceder.
THEOLOGICAL_PROMPT_PT = (
    "Sermão da Igreja Adventista do Sétimo Dia: Sábado, Escola Sabatina, "
    "Espírito de Profecia, Ellen White, Irmã White, Três Mensagens Angélicas, "
    "Juízo Investigativo, Santuário, Grande Conflito, Remanescente, Segunda Vinda, "
    "Estado dos Mortos, Santa Ceia, Lava-pés, Dízimos e Ofertas, Ancião, Diácono, "
    "Diaconisa, Pastor distrital, Espírito Santo, Apocalipse, Gálatas, Efésios, "
    "Romanos, Salmos, Isaías, Daniel, Génesis, Êxodo, Hebreus, Colossenses. "
    "Amém, Aleluia, Glória a Deus, Bênção, Graça, Salvação, Redenção, Justificação, "
    "Santificação, Profecia, Ressurreição, Evangelho eterno."
)

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
# Mínimo de caracteres para considerar transcrição válida
MIN_TEXT_LENGTH = 3


# ── Inicialização ──────────────────────────────────────────────────────────────

def init_groq_transcriber(api_key: str) -> bool:
    """
    Inicializa o cliente Groq para transcrição via whisper-large-v3-turbo.
    Deve ser chamado UMA VEZ no startup se a chave estiver disponível.
    """
    global _groq_client
    try:
        from groq import Groq
        _groq_client = Groq(api_key=api_key)
        print("[TRANSCRITOR] ✅ Groq Whisper inicializado (whisper-large-v3-turbo) — qualidade máxima")
        return True
    except ImportError:
        print("[TRANSCRITOR] ⚠️  Pacote 'groq' não instalado. Usando Whisper local.")
        return False
    except Exception as e:
        print(f"[TRANSCRITOR] ❌ Erro ao inicializar Groq Whisper: {e}")
        return False


def load_model(model_name: str = "medium"):
    """
    Carrega o modelo Whisper local. Usado como fallback se Groq não estiver disponível.
    Recomendado: 'medium' (bom equilíbrio) ou 'large-v3' (máxima qualidade local).
    """
    global _model
    print(f"[TRANSCRITOR] Carregando modelo Whisper local '{model_name}' (fallback)...")
    _model = whisper.load_model(model_name)
    print(f"[TRANSCRITOR] Modelo local '{model_name}' carregado com sucesso!")


# ── Filtros anti-alucinação ────────────────────────────────────────────────────

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
        return True, "texto não-latino (provável chinês/japonês alucinado)"

    if _is_repetitive_loop(text):
        return True, "loop repetitivo detectado"

    return False, ""


# ── Transcrição local (fallback) ───────────────────────────────────────────────

def _transcribe_local(wav_path: str, task: str = "transcribe") -> Tuple[Optional[str], float]:
    """
    Transcreve usando o modelo Whisper local com initial_prompt teológico.
    Retorna (texto, no_speech_prob).
    """
    if _model is None:
        raise RuntimeError("Modelo Whisper não carregado. Chame load_model() antes.")

    result = _model.transcribe(
        wav_path,
        task=task,
        language="pt",
        initial_prompt=THEOLOGICAL_PROMPT_PT,   # ← vocabulário teológico
        no_speech_threshold=0.6,
        condition_on_previous_text=False,        # evita propagar alucinações
    )
    text = result["text"].strip()

    segments = result.get("segments", [])
    if segments:
        no_speech_prob = sum(s.get("no_speech_prob", 0) for s in segments) / len(segments)
    else:
        no_speech_prob = 0.0

    return text, no_speech_prob


# ── Transcrição principal ──────────────────────────────────────────────────────

def transcribe_audio(wav_path: str) -> Optional[str]:
    """
    Transcreve áudio PT. Tenta Groq API (whisper-large-v3-turbo) primeiro;
    fallback para Whisper local se Groq falhar ou não estiver configurado.
    Retorna texto PT, ou None se for alucinação/silêncio.
    NÃO deleta o .wav (caller decide, para permitir fallback de tradução).
    """
    if not os.path.exists(wav_path):
        return None

    # 1. ── Groq Whisper API (qualidade máxima, sem usar RAM local) ──
    if _groq_client is not None:
        try:
            with open(wav_path, "rb") as audio_file:
                transcription = _groq_client.audio.transcriptions.create(
                    file=(os.path.basename(wav_path), audio_file, "audio/wav"),
                    model="whisper-large-v3-turbo",
                    language="pt",
                    prompt=THEOLOGICAL_PROMPT_PT,   # ← vocabulário teológico
                    response_format="text",
                    temperature=0.0,
                )
            # response_format="text" devolve a string diretamente
            text = (transcription if isinstance(transcription, str) else str(transcription)).strip()

            is_halluc, reason = _is_hallucination(text, 0.0)
            if is_halluc:
                print(f"[ANTI-ALUCINAÇÃO/GROQ] Descartado: {reason} | texto: '{text[:60]}'")
                return None

            print(f"[TRANSCRITOR/GROQ] ✅ {text[:70]}...")
            return text

        except Exception as e:
            print(f"[TRANSCRITOR] ⚠️  Falha Groq Whisper, usando local: {e}")

    # 2. ── Fallback: Whisper local ──
    if _model is None:
        print("[TRANSCRITOR] ❌ Nem Groq nem modelo local disponível!")
        return None

    text, no_speech_prob = _transcribe_local(wav_path, task="transcribe")

    is_halluc, reason = _is_hallucination(text, no_speech_prob)
    if is_halluc:
        print(f"[ANTI-ALUCINAÇÃO] Descartado: {reason} | texto: '{text[:60]}'")
        return None

    print(f"[TRANSCRITOR/LOCAL] {text[:70]}...")
    return text


# ── Fallback de tradução via Whisper local ─────────────────────────────────────

def whisper_translate_fallback(wav_path: str) -> Optional[str]:
    """
    FALLBACK: Whisper local traduz direto PT->EN.
    Usar só se tanto Groq Whisper como Groq Tradução falharem.
    Aplica os mesmos filtros anti-alucinação e initial_prompt teológico.
    """
    if _model is None:
        raise RuntimeError("Modelo Whisper não carregado.")

    if not os.path.exists(wav_path):
        return None

    text, no_speech_prob = _transcribe_local(wav_path, task="translate")

    is_halluc, reason = _is_hallucination(text, no_speech_prob)
    if is_halluc:
        print(f"[ANTI-ALUCINAÇÃO/FALLBACK] Descartado: {reason}")
        return None

    return text


# ── Utilitários ────────────────────────────────────────────────────────────────

def cleanup_wav(wav_path: str):
    """Deleta o .wav após uso. Chamar quando terminar todo o processamento."""
    if os.path.exists(wav_path):
        os.remove(wav_path)
