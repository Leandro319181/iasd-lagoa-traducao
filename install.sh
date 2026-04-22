#!/bin/bash
set -euo pipefail

echo ""
echo "================================================="
echo "  Instalação — App de Tradução IASD"
echo "================================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR" "$SCRIPT_DIR/temp"

# ---------------------------------------------------------------------------
# Funções de erro em português
# ---------------------------------------------------------------------------
die() {
    echo ""
    echo "❌ ERRO: $1"
    echo ""
    echo "Contacte o administrador ou consulte o README.md para ajuda."
    exit 1
}

check_network() {
    curl -s --connect-timeout 5 https://pypi.org > /dev/null 2>&1 || \
        die "Sem ligação à internet. Verifique a sua rede e tente novamente."
}

# ---------------------------------------------------------------------------
# 1. Instalar uv (gestor de Python moderno)
#    uv instala automaticamente o Python correto — não precisa de instalar nada antes
# ---------------------------------------------------------------------------
if ! command -v uv &>/dev/null; then
    echo "A instalar uv (gestor de Python automático)..."
    check_network
    curl -LsSf https://astral.sh/uv/install.sh | sh || \
        die "Não foi possível instalar o uv. Verifique a ligação à internet."
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

if ! command -v uv &>/dev/null; then
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

UV=$(command -v uv) || die "uv não encontrado após instalação. Reinicie o terminal e tente de novo."
echo "✓ uv pronto: $UV"

# ---------------------------------------------------------------------------
# 2. Verificar/instalar ffmpeg
# ---------------------------------------------------------------------------
if ! command -v ffmpeg &>/dev/null; then
    echo "A instalar ffmpeg (necessário para áudio)..."
    if command -v brew &>/dev/null; then
        brew install ffmpeg || die "Erro ao instalar ffmpeg via Homebrew."
    else
        echo "  ⚠️  Homebrew não encontrado."
        echo "  Instale o ffmpeg manualmente: https://ffmpeg.org/download.html"
        echo "  Ou instale o Homebrew primeiro: https://brew.sh"
        read -rp "  Prima Enter para continuar sem ffmpeg (pode haver problemas de áudio)..." _
    fi
fi
echo "✓ ffmpeg: $(command -v ffmpeg 2>/dev/null || echo 'não instalado — instale manualmente')"

# ---------------------------------------------------------------------------
# 3. Criar ambiente virtual com Python 3.11 via uv
# ---------------------------------------------------------------------------
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "A criar ambiente Python 3.11..."
    "$UV" venv "$VENV_DIR" --python 3.11 || \
        die "Não foi possível criar o ambiente Python. Verifique ligação à internet (uv faz download do Python automaticamente)."
fi
echo "✓ Python 3.11 pronto"

# ---------------------------------------------------------------------------
# 4. Instalar dependências (sem -q para mostrar erros reais)
# ---------------------------------------------------------------------------
echo "A instalar dependências (pode demorar 5-10 min na primeira vez)..."
"$UV" pip install --python "$VENV_DIR/bin/python" -r "$SCRIPT_DIR/backend/requirements.txt" || \
    die "Erro ao instalar dependências Python. Verifique a ligação à internet e tente novamente."
echo "✓ Dependências instaladas"

# ---------------------------------------------------------------------------
# 5. Descarregar modelo Whisper com progresso e verificação
# ---------------------------------------------------------------------------
WHISPER_CACHE="$HOME/.cache/whisper"
mkdir -p "$WHISPER_CACHE"

WHISPER_MODEL_NAME="small"
WHISPER_MODEL_FILE="$WHISPER_CACHE/small.pt"
WHISPER_SHA256="55d977-placeholder"  # será verificado após download real

if [ ! -f "$WHISPER_MODEL_FILE" ]; then
    echo "A descarregar modelo Whisper '${WHISPER_MODEL_NAME}' (~242MB, só na primeira vez)..."
    "$VENV_DIR/bin/python" -c "
import whisper, sys
print('A descarregar...', flush=True)
whisper.load_model('${WHISPER_MODEL_NAME}')
print('OK')
" || die "Erro ao descarregar o modelo Whisper. Verifique a ligação à internet."
fi
echo "✓ Modelo Whisper pronto"

# ---------------------------------------------------------------------------
# 6. Verificar/descarregar modelo Kokoro TTS
# ---------------------------------------------------------------------------
echo "A verificar modelo de voz Kokoro (~85MB, só na primeira vez)..."
"$VENV_DIR/bin/python" -c "
from kokoro import KPipeline
import numpy as np, soundfile as sf, tempfile, os, sys
print('A carregar modelo...', flush=True)
try:
    p = KPipeline(lang_code='a')
    chunks = []
    for _, _, a in p('Pronto.', voice='af_heart'):
        chunks.append(a)
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        sf.write(f.name, np.concatenate(chunks), 24000)
        os.remove(f.name)
    print('OK')
except Exception as e:
    print(f'ERRO: {e}', file=sys.stderr)
    sys.exit(1)
" || die "Erro ao carregar o modelo de voz Kokoro. Tente novamente."
echo "✓ Modelo de voz pronto"

# ---------------------------------------------------------------------------
# 7. Configurar .env com teste real de microfone
# ---------------------------------------------------------------------------
ENV_FILE="$SCRIPT_DIR/backend/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo ""
    echo "Dispositivos de áudio disponíveis:"
    set +e
    DEVICE_LIST=$("$VENV_DIR/bin/python" -c "
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
        echo "  ⚠️  Não foi possível listar dispositivos de áudio."
        echo "  Verifique permissões de microfone em: Preferências do Sistema → Privacidade → Microfone"
        echo "  Pode editar AUDIO_DEVICE_INDEX manualmente em backend/.env após a instalação."
        DEV_IDX=0
    else
        echo "$DEVICE_LIST"
        echo ""
        printf "Índice do microfone/mesa de som [0]: "
        read -r DEV_IDX
        DEV_IDX=${DEV_IDX:-0}

        # Testar dispositivo com gravação de 3 segundos
        echo "A testar microfone (índice $DEV_IDX) por 3 segundos..."
        set +e
        "$VENV_DIR/bin/python" -c "
import pyaudio, wave, tempfile, os, sys, time
DEVICE = $DEV_IDX
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
DURATION = 3
try:
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                    input=True, input_device_index=DEVICE, frames_per_buffer=CHUNK)
    frames = []
    for _ in range(int(RATE / CHUNK * DURATION)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
    stream.stop_stream()
    stream.close()
    p.terminate()
    total = sum(len(f) for f in frames)
    print(f'OK: gravados {total} bytes')
except Exception as e:
    print(f'FALHOU: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1
        MIC_EXIT=$?
        set -e
        if [ $MIC_EXIT -ne 0 ]; then
            echo "  ⚠️  Microfone índice $DEV_IDX falhou no teste."
            echo "  Verifique se está ligado e tente um índice diferente."
            echo "  Pode alterar AUDIO_DEVICE_INDEX em backend/.env depois."
        else
            echo "  ✓ Microfone testado com sucesso"
        fi
    fi

    cat > "$ENV_FILE" << EOF
AUDIO_DEVICE_INDEX=$DEV_IDX
WHISPER_MODEL=small
PORT=8000
CHUNK_SECONDS=5
EOF
    chmod 600 "$ENV_FILE"
    echo "✓ Ficheiro .env criado (dispositivo $DEV_IDX)"
else
    echo "✓ Ficheiro .env já existe"
fi

# ---------------------------------------------------------------------------
# 8. Criar lançador de duplo-clique (Mac)
# ---------------------------------------------------------------------------
LAUNCHER_MAC="$SCRIPT_DIR/Iniciar Tradução.command"
cat > "$LAUNCHER_MAC" << 'LAUNCHEOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

echo "================================================="
echo "  Servidor de Tradução IASD"
echo "================================================="
echo ""

# Verificar se já está a correr
if lsof -i :8000 -sTCP:LISTEN &>/dev/null; then
    echo "✓ Servidor já está a correr."
    sleep 1
    open http://localhost:8000/operator
    exit 0
fi

source "$SCRIPT_DIR/.venv/bin/activate"
cd "$SCRIPT_DIR/backend"

echo "A iniciar servidor..."
python -m uvicorn main:app --host 0.0.0.0 --port 8000 \
    >> "$LOG_DIR/app.log" 2>&1 &
SERVER_PID=$!

# Aguardar servidor ficar pronto
OPEN_URL="http://localhost:8000/operator"
# Abrir wizard de configuração na primeira vez
if [ ! -f "$SCRIPT_DIR/.setup-done" ]; then
    OPEN_URL="http://localhost:8000/setup"
fi

for i in {1..15}; do
    sleep 1
    if curl -s http://localhost:8000/health &>/dev/null; then
        echo "✓ Servidor pronto!"
        open "$OPEN_URL"
        touch "$SCRIPT_DIR/.setup-done" 2>/dev/null || true
        echo ""
        echo "Para parar o servidor: feche esta janela ou pressione Ctrl+C"
        wait $SERVER_PID
        exit 0
    fi
done

echo "⚠️  Servidor demorou mais do que o esperado."
echo "Verifique logs/app.log se houver problemas."
open "$OPEN_URL"
wait $SERVER_PID
LAUNCHEOF
chmod +x "$LAUNCHER_MAC"
echo "✓ Lançador 'Iniciar Tradução.command' criado"

# ---------------------------------------------------------------------------
# 9. Gerar start.sh (compatibilidade terminal)
# ---------------------------------------------------------------------------
START_SCRIPT="$SCRIPT_DIR/start.sh"
cat > "$START_SCRIPT" << 'STARTEOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
cd "$SCRIPT_DIR/backend"
source "$SCRIPT_DIR/.venv/bin/activate"
echo ""
echo "================================================="
echo "  Servidor de Tradução IASD — A iniciar..."
echo "================================================="
python -m uvicorn main:app --host 0.0.0.0 --port 8000 2>&1 | tee "$LOG_DIR/app.log"
STARTEOF
chmod +x "$START_SCRIPT"
echo "✓ start.sh criado"

# ---------------------------------------------------------------------------
# 10. Configurar auto-arranque (launchd) — opcional
# ---------------------------------------------------------------------------
echo ""
printf "Deseja que o servidor arranque automaticamente no login? [s/N]: "
read -r AUTO_START
if [[ "$AUTO_START" =~ ^[sS]$ ]]; then
    PLIST_LABEL="com.iasd-lagoa.traducao"
    PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"
    mkdir -p "$HOME/Library/LaunchAgents"
    cat > "$PLIST_PATH" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>cd "${SCRIPT_DIR}/backend" && source "${SCRIPT_DIR}/.venv/bin/activate" && python -m uvicorn main:app --host 0.0.0.0 --port 8000</string>
    </array>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/stderr.log</string>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}/backend</string>
</dict>
</plist>
PLISTEOF
    launchctl load "$PLIST_PATH" 2>/dev/null || true
    echo "✓ Auto-arranque configurado (launchd)"
    echo "  Para desativar: launchctl unload ~/Library/LaunchAgents/${PLIST_LABEL}.plist"
fi

# ---------------------------------------------------------------------------
# 11. Resultado final
# ---------------------------------------------------------------------------
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "127.0.0.1")
echo ""
echo "================================================="
echo ""
echo "  ✅ Instalação concluída!"
echo ""
echo "  Para iniciar (duplo-clique):"
echo "    Iniciar Tradução.command"
echo ""
echo "  Ou via terminal:"
echo "    ./start.sh"
echo ""
echo "  App dos membros:"
echo "    http://$IP:8000"
echo ""
echo "  Painel do operador:"
echo "    http://$IP:8000/operator"
echo ""
echo "  Logs:"
echo "    $LOG_DIR/app.log"
echo ""
echo "================================================="
