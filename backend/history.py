"""
Histórico de blocos traduzidos em SQLite (arquivo único, sem servidor).
Uso diagnóstico: ver transcrições/traduções e onde o app falha.
"""
import sqlite3
import threading
import time
from typing import Optional

_db_path: str = "logs/historico.db"
_lock = threading.Lock()


def init_db(path: str = "logs/historico.db"):
    """Cria o arquivo e a tabela se não existirem. Chamar no startup."""
    global _db_path
    _db_path = path
    import os as _os
    _os.makedirs(_os.path.dirname(_db_path), exist_ok=True)
    with _lock:
        with sqlite3.connect(_db_path, timeout=5) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS blocks (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    seq        INTEGER,
                    created_at TEXT NOT NULL,
                    pt_text    TEXT,
                    en_text    TEXT,
                    status     TEXT NOT NULL,
                    has_audio  INTEGER
                )
            """)
    print(f"[HISTÓRICO] SQLite pronto em '{_db_path}'.")


def log_block(seq: Optional[int], pt_text: Optional[str],
              en_text: Optional[str], status: str):
    """Grava um bloco. status: 'ok' | 'hallucination' | 'translation_failed'."""
    created_at = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with _lock:
            with sqlite3.connect(_db_path, timeout=5) as conn:
                conn.execute(
                    "INSERT INTO blocks (seq, created_at, pt_text, en_text, status, has_audio) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (seq, created_at, pt_text, en_text, status, None),
                )
    except Exception as e:
        print(f"[HISTÓRICO] ❌ Falha ao gravar bloco: {e}")


def mark_audio(seq: int, ok: bool):
    """Marca se o áudio (TTS) do bloco foi gerado. Atualiza pela seq."""
    try:
        with _lock:
            with sqlite3.connect(_db_path, timeout=5) as conn:
                conn.execute(
                    "UPDATE blocks SET has_audio = ? WHERE seq = ?",
                    (1 if ok else 0, seq),
                )
    except Exception as e:
        print(f"[HISTÓRICO] ❌ Falha ao marcar áudio: {e}")
