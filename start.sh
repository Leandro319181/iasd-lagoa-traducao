#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

echo ""
echo "================================================="
echo "  Servidor de Tradução IASD — A verificar updates..."
echo "================================================="

# --- Auto-update do Git ---
if command -v git &>/dev/null && [ -d ".git" ]; then
    echo "🔄 A verificar atualizações no GitHub..."
    git fetch origin --quiet 2>/dev/null
    BEHIND=$(git rev-list HEAD..origin/main --count 2>/dev/null || echo "0")
    if [ "$BEHIND" -gt 0 ]; then
        echo "📥 $BEHIND atualização(ões) encontrada(s). A aplicar..."
        git pull origin main --quiet
        echo "✅ Código atualizado com sucesso!"

        # Instala dependências novas (caso requirements.txt tenha mudado)
        if [ -d ".venv" ]; then
            source ".venv/bin/activate"
        elif [ -d "venv" ]; then
            source "venv/bin/activate"
        fi
        echo "📦 A verificar dependências..."
        pip install -r backend/requirements.txt --quiet 2>/dev/null
        echo "✅ Dependências atualizadas!"
    else
        echo "✅ Já está na versão mais recente."
    fi
else
    echo "⚠️  Git não disponível — a iniciar sem verificar atualizações."
fi

# --- Ativa o venv e inicia ---
if [ -d ".venv" ]; then
    source ".venv/bin/activate"
elif [ -d "venv" ]; then
    source "venv/bin/activate"
fi

cd "$SCRIPT_DIR/backend"
echo ""
echo "================================================="
echo "  Servidor de Tradução IASD — A iniciar..."
echo "================================================="
python -m uvicorn main:app --host 0.0.0.0 --port 8000 2>&1 | tee "$LOG_DIR/app.log"
