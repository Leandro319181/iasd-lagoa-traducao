#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/backend"
source "$SCRIPT_DIR/.venv/bin/activate"
echo ""
echo "================================================="
echo "  Servidor de Tradução IASD — A iniciar..."
echo "================================================="
python -m uvicorn main:app --host 0.0.0.0 --port 8000
