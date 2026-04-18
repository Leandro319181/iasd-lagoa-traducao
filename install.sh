#!/bin/bash
set -e

echo ""
echo "================================================="
echo "  Instalação — App de Tradução IASD"
echo "================================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 1. Verificar Python 3.9+
PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null)
if [ -z "$PYTHON" ]; then
    echo "ERRO: Python 3 não encontrado."
    echo "Instale em: https://www.python.org/downloads/"
    exit 1
fi

VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
MAJOR=$(echo "$VERSION" | cut -d. -f1)
MINOR=$(echo "$VERSION" | cut -d. -f2)

if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 9 ]; }; then
    echo "ERRO: Python $VERSION encontrado. Necessário Python 3.9 ou superior."
    exit 1
fi
echo "✓ Python $VERSION encontrado"

# 2. Criar ambiente virtual
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "A criar ambiente virtual..."
    $PYTHON -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
echo "✓ Ambiente virtual pronto"

# 3. Instalar dependências
echo "A instalar dependências (pode demorar 3-5 min)..."
pip install -q --upgrade pip
pip install -q -r "$SCRIPT_DIR/backend/requirements.txt"
echo "✓ Dependências instaladas"

# 4. Descarregar modelo Kokoro (primeira vez)
echo "A verificar modelo de voz Kokoro (~85MB, só na primeira vez)..."
"$VENV_DIR/bin/python" -c "
from kokoro import KPipeline
import numpy as np, soundfile as sf, tempfile, os
p = KPipeline(lang_code='a')
chunks = []
for _, _, a in p('Ready.', voice='af_heart'):
    chunks.append(a)
with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
    sf.write(f.name, np.concatenate(chunks), 24000)
    os.remove(f.name)
print('OK')
"
echo "✓ Modelo de voz pronto"

# 5. Criar .env se não existir
ENV_FILE="$SCRIPT_DIR/backend/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo ""
    echo "Dispositivos de áudio disponíveis:"
    set +e
    DEVICE_LIST=$($PYTHON -c "
import pyaudio
p = pyaudio.PyAudio()
found = False
for i in range(p.get_device_count()):
    d = p.get_device_info_by_index(i)
    if d['maxInputChannels'] > 0:
        print(f'  [{i}] {d[\"name\"]}')
        found = True
p.terminate()
if not found:
    raise SystemExit(2)
" 2>/dev/null)
    PYAUDIO_EXIT=$?
    set -e
    if [ $PYAUDIO_EXIT -ne 0 ]; then
        echo "  AVISO: Não foi possível listar dispositivos de áudio."
        echo "  (Verifique permissões de microfone em Preferências do Sistema)"
        echo "  Pode editar AUDIO_DEVICE_INDEX manualmente em backend/.env após a instalação."
    else
        echo "$DEVICE_LIST"
    fi
    echo ""
    printf "Índice do microfone/mesa de som [0]: "
    read -r DEV_IDX
    DEV_IDX=${DEV_IDX:-0}

    cat > "$ENV_FILE" << EOF
AUDIO_DEVICE_INDEX=$DEV_IDX
WHISPER_MODEL=small
PORT=8000
CHUNK_SECONDS=5
EOF
    echo "✓ Ficheiro .env criado (dispositivo $DEV_IDX)"
else
    echo "✓ Ficheiro .env já existe"
fi

# 6. Criar pasta temp
mkdir -p "$SCRIPT_DIR/temp"
echo "✓ Pasta temp/ pronta"

# 7. Gerar start.sh
START_SCRIPT="$SCRIPT_DIR/start.sh"
cat > "$START_SCRIPT" << 'STARTEOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/backend"
source "$SCRIPT_DIR/.venv/bin/activate"
echo ""
echo "================================================="
echo "  Servidor de Tradução IASD — A iniciar..."
echo "================================================="
python -m uvicorn main:app --host 0.0.0.0 --port 8000
STARTEOF
chmod +x "$START_SCRIPT"
echo "✓ start.sh criado"

# 8. Mostrar resultado
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "127.0.0.1")
echo ""
echo "================================================="
echo ""
echo "  ✅ Instalação concluída!"
echo ""
echo "  Para iniciar:"
echo "    ./start.sh"
echo ""
echo "  App dos membros:"
echo "    http://$IP:8000"
echo ""
echo "  Painel do operador:"
echo "    http://$IP:8000/operator"
echo ""
echo "================================================="
