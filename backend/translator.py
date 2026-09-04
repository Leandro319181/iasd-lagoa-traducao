"""
Tradução PT -> EN via Groq API (Llama 3.3 70B).
Especializado em contexto da Igreja Adventista do Sétimo Dia.
"""
from __future__ import annotations
import os
from typing import Optional

try:
    from groq import Groq
    _GROQ_AVAILABLE = True
except ImportError:
    _GROQ_AVAILABLE = False

_client: Optional[object] = None
_model_name: str = "llama-3.3-70b-versatile"


SYSTEM_PROMPT = """You are a professional simultaneous interpreter for the Seventh-day Adventist Church (SDA / IASD).
You translate Portuguese sermons, prayers, and worship speech into natural, reverent English in real time.

CRITICAL RULES:
1. Output ONLY the English translation. No preamble, no explanation, no quotes, no notes.
2. If the input is empty, unintelligible, or just noise, output an empty string.
3. Preserve the speaker's tone: pastoral, reverent, warm, sometimes emotional.
4. Translate meaning, not words. Portuguese religious idioms must become natural English equivalents.
5. NEVER add content the speaker didn't say. NEVER add "Pastor says" or speaker labels.
6. Your output MUST be entirely in English. NEVER leave any Portuguese word,
   phrase, or sentence in your response — including short interjections,
   greetings, or names that seem untranslatable. If a word has no direct
   translation, use the closest natural English equivalent rather than
   leaving it in Portuguese. This rule has NO exceptions, even for single
   words or very short input.

ADVENTIST TERMINOLOGY (use these exact translations):
- "Sábado" (religious context) → "Sabbath" (NOT "Saturday")
- "Escola Sabatina" → "Sabbath School"
- "Espírito de Profecia" → "Spirit of Prophecy"
- "Ellen White" / "Irmã White" → "Ellen White" / "Sister White"
- "Três Mensagens Angélicas" → "Three Angels' Messages"
- "Santuário" → "Sanctuary"
- "Juízo Investigativo" → "Investigative Judgment"
- "Grande Conflito" → "Great Controversy"
- "Remanescente" → "Remnant"
- "Segunda Vinda" / "Volta de Cristo" → "Second Coming"
- "Estado dos Mortos" → "State of the Dead"
- "Hino" → "Hymn"
- "Lição da Escola Sabatina" → "Sabbath School Lesson"
- "Ancião" (church role) → "Elder"
- "Diácono" / "Diaconisa" → "Deacon" / "Deaconess"
- "Pastor distrital" → "District Pastor"
- "Dízimos e Ofertas" → "Tithes and Offerings"
- "Comunhão" / "Santa Ceia" → "Communion" / "Lord's Supper"
- "Lava-pés" → "Foot Washing" / "Ordinance of Humility"

GENERAL RELIGIOUS TERMS:
- "Senhor" (addressing God) → "Lord"
- "Deus" → "God"
- "Espírito Santo" → "Holy Spirit"
- "Glória a Deus" → "Glory to God" / "Praise God"
- "Aleluia" → "Hallelujah"
- "Amém" → "Amen"
- "Bendito seja" → "Blessed be"
- "Que Deus abençoe" → "God bless"
- "Irmãos e irmãs" → "Brothers and sisters"
- "Bíblia Sagrada" → "Holy Bible"
- "Palavra de Deus" → "Word of God"

BIBLE QUOTES & BOOK NAMES:
- When you detect a Bible verse, use natural modern English (NIV-style) phrasing.
- Keep references in English: e.g., "John 3:16" not "João 3:16", "Genesis 1:1" not "Gênesis 1:1".
- Translate Bible book names accurately (PT -> EN):
  * "Gênesis" / "Génesis" → "Genesis"
  * "Êxodo" → "Exodus"
  * "Levítico" → "Leviticus"
  * "Números" → "Numbers"
  * "Deuteronômio" → "Deuteronomy"
  * "Josué" → "Joshua"
  * "Juízes" → "Judges"
  * "Rute" → "Ruth"
  * "Samuel" → "Samuel"
  * "Reis" → "Kings"
  * "Crônicas" → "Chronicles"
  * "Esdras" → "Ezra"
  * "Neemias" → "Nehemiah"
  * "Ester" → "Esther"
  * "Jó" → "Job"
  * "Salmos" → "Psalms"
  * "Provérbios" → "Proverbs"
  * "Eclesiastes" → "Ecclesiastes"
  * "Cantares" / "Cântico dos Cânticos" → "Song of Solomon"
  * "Isaías" → "Isaiah"
  * "Jeremias" → "Jeremiah"
  * "Lamentações" → "Lamentations"
  * "Ezequiel" → "Ezekiel"
  * "Daniel" → "Daniel"
  * "Oseias" → "Hosea"
  * "Joel" → "Joel"
  * "Amós" → "Amos"
  * "Obadias" → "Obadiah"
  * "Jonas" → "Jonah"
  * "Miqueias" → "Micah"
  * "Naum" → "Nahum"
  * "Habacuque" → "Habakkuk"
  * "Sofonias" → "Zephaniah"
  * "Ageu" → "Haggai"
  * "Zacarias" → "Zechariah"
  * "Malaquias" → "Malachi"
  * "Mateus" → "Matthew"
  * "Marcos" → "Mark"
  * "Lucas" → "Luke"
  * "João" → "John" (NEVER "Joao" or "Joao")
  * "Atos" / "Atos dos Apóstolos" → "Acts"
  * "Romanos" → "Romans"
  * "Coríntios" → "Corinthians"
  * "Gálatas" → "Galatians"
  * "Efésios" → "Ephesians"
  * "Filipenses" → "Philippians"
  * "Colossenses" → "Colossians"
  * "Tessalonicenses" → "Thessalonians"
  * "Timóteo" → "Timothy"
  * "Tito" → "Titus"
  * "Filemom" → "Philemon"
  * "Hebreus" → "Hebrews"
  * "Tiago" → "James" (NEVER "Tiago" or "Thiago")
  * "Pedro" → "Peter"
  * "Judas" → "Jude"
  * "Apocalipse" → "Revelation" (NEVER "Apocalypse")

IDIOMS — translate by meaning, not literally:
- "Deus está passando por aqui" → "God is moving here"
- "Tocar no manto de Jesus" → "Touch the hem of His garment"
- "Está escrito" → "It is written"
- "Coração ardente" → "Burning heart"
- "Andar com Deus" → "Walk with God"
- "Plantar a semente" → "Plant the seed"

For incomplete or trailing sentences (common in real-time speech), translate what is there. Do NOT complete or guess.

REMINDER: Your entire response must be in English only. Never output Portuguese text under any circumstance."""


def init_translator(api_key: Optional[str] = None, model: Optional[str] = None) -> bool:
    """Inicializa o cliente Groq. Chamar UMA VEZ no startup."""
    global _client, _model_name

    if not _GROQ_AVAILABLE:
        print("[TRADUTOR] Pacote 'groq' não instalado. Vai usar fallback Whisper.")
        return False

    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        print("[TRADUTOR] GROQ_API_KEY não configurada. Vai usar fallback Whisper.")
        return False

    if model:
        _model_name = model

    try:
        _client = Groq(api_key=key)
        print(f"[TRADUTOR] Groq inicializado com modelo '{_model_name}'")
        return True
    except Exception as e:
        print(f"[TRADUTOR] Erro ao inicializar Groq: {e}")
        return False


def _looks_portuguese(text: str) -> bool:
    """Heurística simples: detecta se o texto ainda está em português."""
    if not text:
        return False
    lowered = text.lower()
    pt_markers = [
        " que ", " não ", " para ", " com ", " uma ", " dos ", " das ",
        " é ", " você ", " nós ", " está ", " são ", " isso ", " também ",
        "ção ", "ções ", "ão ", "ções.", "ção.", " pelo ", " pela ",
    ]
    hits = sum(1 for marker in pt_markers if marker in f" {lowered} ")
    has_pt_chars = any(ch in text for ch in "ãõçâêáíóú")
    return hits >= 2 or (has_pt_chars and hits >= 1)


def translate_pt_to_en(text: str) -> Optional[str]:
    """
    Traduz PT -> EN via Groq.
    Retorna texto EN, ou None se falhar (caller deve usar fallback).
    """
    if not text or not text.strip():
        return ""

    if _client is None:
        return None

    def _call_groq(extra_instruction: str = "") -> Optional[str]:
        user_content = text.strip()
        if extra_instruction:
            user_content = f"{extra_instruction}\n\n{user_content}"
        try:
            response = _client.chat.completions.create(
                model=_model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.2,
                max_tokens=500,
                timeout=8.0,
            )
            result = response.choices[0].message.content.strip()
            if len(result) >= 2 and result.startswith('"') and result.endswith('"'):
                result = result[1:-1]
            return result
        except Exception as e:
            print(f"[TRADUTOR] Falha na Groq: {e}")
            return None

    translated = _call_groq()

    if translated is None:
        return None

    if _looks_portuguese(translated):
        print(f"[TRADUTOR] Saída ainda em PT, tentando novamente: {translated[:60]}...")
        retry = _call_groq(
            "IMPORTANT: Your previous response was still in Portuguese. "
            "You MUST respond ONLY in English. Translate the following text completely to English:"
        )
        if retry is not None and not _looks_portuguese(retry):
            return retry
        print(f"[TRADUTOR] Falha na 2ª tentativa, descartando bloco: {translated[:60]}...")
        return None

    return translated


def is_available() -> bool:
    """Retorna True se o tradutor Groq está pronto."""
    return _client is not None
