"""Alertas por Telegram. Nunca pode afetar a tradução:
tudo corre em segundo plano e todas as falhas são engolidas."""
import os
import socket
import subprocess
import threading
import time

import httpx

_lock = threading.Lock()
_last_sent: dict = {}      # key -> timestamp do último envio
_suppressed: dict = {}     # key -> nº de ocorrências não enviadas
_THROTTLE_SECONDS = 60
_HOST = socket.gethostname()


def _config():
    return os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")


def enabled() -> bool:
    token, chat_id = _config()
    return bool(token and chat_id)


def _post(text: str) -> None:
    token, chat_id = _config()
    if not token or not chat_id:
        return
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text[:3500]},
            timeout=5.0,
        )
        if r.status_code != 200:
            print(f"[ALERTA] Telegram recusou a mensagem (HTTP {r.status_code}): {r.text[:200]}")
    except Exception as e:
        # Só o tipo do erro: a mensagem pode conter o URL com o token
        print(f"[ALERTA] Falha ao enviar para o Telegram: {type(e).__name__}")


def send(text: str, key: str = None, wait: bool = False) -> None:
    """Envia um alerta. Com key, limita a 1 mensagem por minuto por key."""
    try:
        if not enabled():
            return
        if key:
            now = time.time()
            with _lock:
                last = _last_sent.get(key, 0)
                if now - last < _THROTTLE_SECONDS:
                    _suppressed[key] = _suppressed.get(key, 0) + 1
                    return
                extra = _suppressed.pop(key, 0)
                _last_sent[key] = now
            if extra:
                text += f"\n(+{extra} ocorrências iguais no último minuto)"
        msg = f"[{_HOST}] {text}"
        if wait:
            _post(msg)
        else:
            threading.Thread(target=_post, args=(msg,), daemon=True).start()
    except Exception as e:
        print(f"[ALERTA] Erro interno: {e!r}")


def git_version() -> str:
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%h %s"],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or "?"
    except Exception:
        return "?"
