from __future__ import annotations
import os
import subprocess


_REPO_DIR = os.path.join(os.path.dirname(__file__), "..")


def check_for_updates() -> dict:
    """
    Verifica se existem commits novos no GitHub.
    Retorna {"has_update": bool, "commits_behind": int,
             "current_version": str, "latest_message": str, "error": str}
    """
    try:
        # Fetch sem aplicar alterações
        subprocess.run(
            ["git", "fetch", "origin", "--quiet"],
            cwd=_REPO_DIR, capture_output=True, timeout=15
        )

        # Quantos commits atrás está o HEAD local
        result = subprocess.run(
            ["git", "rev-list", "HEAD..origin/main", "--count"],
            cwd=_REPO_DIR, capture_output=True, text=True, timeout=5
        )
        commits_behind = int(result.stdout.strip() or "0")

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

        return {
            "has_update": commits_behind > 0,
            "commits_behind": commits_behind,
            "current_version": current,
            "latest_message": latest_msg,
            "error": "",
        }
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
    """
    try:
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=_REPO_DIR, capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            return {"success": False, "output": "", "error": result.stderr.strip()}
        return {"success": True, "output": result.stdout.strip(), "error": ""}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}
