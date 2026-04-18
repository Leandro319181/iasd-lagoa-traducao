#!/bin/bash
# =============================================================
#  IASD LAGOA — Script de instalação para macOS (Apple Silicon)
#  Execute: bash setup_mac.sh
# =============================================================

set -e  # Para se der qualquer erro

# Cores para o terminal
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # sem cor

ok()   { echo -e "${GREEN}✅ $1${NC}"; }
info() { echo -e "${YELLOW}➜  $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; exit 1; }

echo ""
echo "=============================================="
echo "  IASD LAGOA — Instalação do App de Tradução"
echo "=============================================="
echo ""

# --- 1. Homebrew ---
info "Verificando Homebrew..."
if ! command -v brew &>/dev/null; then
    info "Homebrew não encontrado. Instalando..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Adiciona brew ao PATH para Apple Silicon
    eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
    ok "Homebrew instalado."
else
    ok "Homebrew já instalado."
fi

# --- 2. Python 3.11 ---
info "Verificando Python 3.11..."
if ! command -v python3.11 &>/dev/null; then
    info "Instalando Python 3.11..."
    brew install python@3.11
    ok "Python 3.11 instalado."
else
    ok "Python 3.11 já instalado."
fi

# --- 3. ffmpeg (necessário para o Whisper) ---
info "Verificando ffmpeg..."
if ! command -v ffmpeg &>/dev/null; then
    info "Instalando ffmpeg..."
    brew install ffmpeg
    ok "ffmpeg instalado."
else
    ok "ffmpeg já instalado."
fi

# --- 4. PortAudio (necessário para o PyAudio) ---
info "Verificando PortAudio..."
if ! brew list portaudio &>/dev/null; then
    info "Instalando PortAudio..."
    brew install portaudio
    ok "PortAudio instalado."
else
    ok "PortAudio já instalado."
fi

# --- 5. Ambiente virtual Python ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

info "Criando ambiente virtual Python em venv/..."
if [ ! -d "venv" ]; then
    python3.11 -m venv venv
    ok "Ambiente virtual criado."
else
    ok "Ambiente virtual já existe."
fi

# Ativa o venv
source venv/bin/activate
ok "Ambiente virtual ativado."

# --- 6. Dependências Python ---
info "Instalando dependências Python (requirements.txt)..."
pip install --upgrade pip --quiet
pip install -r backend/requirements.txt --quiet
ok "Dependências instaladas."

# --- 7. PyAudio ---
info "Instalando PyAudio..."
pip install pyaudio --quiet
ok "PyAudio instalado."

# --- 8. Verifica instalação ---
echo ""
info "Verificando instalação..."
python3 -c "import fastapi; print('  fastapi ✅')"
python3 -c "import uvicorn; print('  uvicorn ✅')"
python3 -c "import pyaudio; print('  pyaudio ✅')"
python3 -c "import qrcode; print('  qrcode ✅')"
python3 -c "import dotenv; print('  python-dotenv ✅')"

# Whisper é pesado — verifica sem baixar o modelo
python3 -c "import whisper; print('  whisper ✅')" 2>/dev/null || \
    echo "  whisper ⏳ (será baixado na primeira execução)"

echo ""
echo "=============================================="
ok "Instalação concluída!"
echo ""
echo "  Para iniciar o app:"
echo ""
echo "  1. Ative o ambiente virtual:"
echo "     source venv/bin/activate"
echo ""
echo "  2. Inicie o servidor:"
echo "     cd backend"
echo "     uvicorn main:app --host 0.0.0.0 --port 8000"
echo ""
echo "  3. Em outro terminal, gere o QR Code:"
echo "     python3 generate_qr.py"
echo ""
echo "  4. Acesse no celular: http://localhost:8000"
echo "=============================================="
echo ""
