from __future__ import annotations
import os
import subprocess
import time

_REPO_DIR = os.path.join(os.path.dirname(__file__), "..")

# Cache do último check para não fazer git fetch em cada separador aberto
_cache: dict = {}
_cache_ts: float = 0.0
_CACHE_TTL = 82800  # segundos (23 horas)


def check_for_updates() -> dict:
    """
    Verifica se existem commits novos no GitHub.
    Resultado em cache por 4 minutos para não sobrecarregar o GitHub.
    Retorna {"has_update": bool, "commits_behind": int,
             "current_version": str, "latest_message": str, "error": str}
    """
    global _cache, _cache_ts
    if _cache and (time.time() - _cache_ts) < _CACHE_TTL:
        return _cache

    try:
        # Fetch sem aplicar alterações
        fetch_result = subprocess.run(
            ["git", "fetch", "origin", "--quiet"],
            cwd=_REPO_DIR, capture_output=True, timeout=15
        )
        if fetch_result.returncode != 0:
            error_msg = fetch_result.stderr.decode(errors="replace").strip()
            result = {
                "has_update": False,
                "commits_behind": 0,
                "current_version": "",
                "latest_message": "",
                "error": f"git fetch falhou: {error_msg}",
            }
            _cache = result
            _cache_ts = time.time()
            return result

        # Quantos commits atrás está o HEAD local
        rev_result = subprocess.run(
            ["git", "rev-list", "HEAD..origin/main", "--count"],
            cwd=_REPO_DIR, capture_output=True, text=True, timeout=5
        )
        try:
            commits_behind = int(rev_result.stdout.strip() or "0")
        except ValueError:
            commits_behind = 0

        # Versão actual (hash curto)
        current = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_REPO_DIR, capture_output=True, text=True, timeout=5
        ).stdout.strip()

        # Mensagem do commit mais recente no remoto (se houver update)
        latest_msg = ""
        if commits_behind > 0:
            latest_msg = subprocess.run(
                ["git", "log", "origin/main", "-1", "--pretty=%s"],
                cwd=_REPO_DIR, capture_output=True, text=True, timeout=5
            ).stdout.strip()

        result = {
            "has_update": commits_behind > 0,
            "commits_behind": commits_behind,
            "current_version": current,
            "latest_message": latest_msg,
            "error": "",
        }
        _cache = result
        _cache_ts = time.time()
        return result

    except Exception as e:
        return {
            "has_update": False,
            "commits_behind": 0,
            "current_version": "",
            "latest_message": "",
            "error": str(e),
        }


def apply_update() -> dict:
    """
    Aplica as actualizações via git pull.
    Retorna {"success": bool, "output": str, "error": str}
    Após aplicar, invalida o cache para que o próximo check mostre o estado real.
    """
    global _cache, _cache_ts
    try:
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=_REPO_DIR, capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            return {"success": False, "output": "", "error": result.stderr.strip()}
        # Invalida cache
        _cache = {}
        _cache_ts = 0.0
        return {"success": True, "output": result.stdout.strip(), "error": ""}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}
