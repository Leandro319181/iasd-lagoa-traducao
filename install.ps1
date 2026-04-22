# Instalação — App de Tradução IASD (Windows)
# Execute no PowerShell como Administrador: .\install.ps1

param(
    [switch]$SkipAutoStart
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $ScriptDir "logs"
$TempDir = Join-Path $ScriptDir "temp"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
New-Item -ItemType Directory -Force -Path $TempDir | Out-Null

Write-Host ""
Write-Host "================================================="
Write-Host "  Instalação — App de Tradução IASD"
Write-Host "================================================="
Write-Host ""

function Die {
    param([string]$Message)
    Write-Host ""
    Write-Host "ERRO: $Message" -ForegroundColor Red
    Write-Host ""
    Write-Host "Contacte o administrador ou consulte o README.md para ajuda."
    exit 1
}

function Test-NetworkConnectivity {
    try {
        $null = Invoke-WebRequest -Uri "https://pypi.org" -TimeoutSec 5 -UseBasicParsing
        return $true
    } catch {
        return $false
    }
}

# ---------------------------------------------------------------------------
# 1. Instalar uv
# ---------------------------------------------------------------------------
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "A instalar uv (gestor de Python automático)..."
    if (-not (Test-NetworkConnectivity)) {
        Die "Sem ligação à internet. Verifique a sua rede e tente novamente."
    }
    try {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    } catch {
        Die "Não foi possível instalar o uv. Erro: $_"
    }
    $env:Path = "$env:USERPROFILE\.local\bin;$env:USERPROFILE\.cargo\bin;$env:Path"
}

$uvPath = (Get-Command uv -ErrorAction SilentlyContinue)?.Source
if (-not $uvPath) {
    $env:Path = "$env:USERPROFILE\.local\bin;$env:USERPROFILE\.cargo\bin;$env:Path"
    $uvPath = (Get-Command uv -ErrorAction SilentlyContinue)?.Source
}
if (-not $uvPath) {
    Die "uv não encontrado após instalação. Reinicie o PowerShell e tente novamente."
}
Write-Host "✓ uv pronto: $uvPath"

# ---------------------------------------------------------------------------
# 2. Instalar ffmpeg via winget (ou instruções manuais)
# ---------------------------------------------------------------------------
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "A instalar ffmpeg..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        try {
            winget install --id Gyan.FFmpeg -e --silent
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        } catch {
            Write-Host "  Winget falhou. A tentar download manual..." -ForegroundColor Yellow
            $ffmpegUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            $ffmpegZip = Join-Path $TempDir "ffmpeg.zip"
            $ffmpegDir = Join-Path $ScriptDir "ffmpeg"
            Invoke-WebRequest $ffmpegUrl -OutFile $ffmpegZip -UseBasicParsing
            Expand-Archive $ffmpegZip -DestinationPath $ffmpegDir -Force
            $ffmpegBin = (Get-ChildItem "$ffmpegDir\*\bin" -Directory | Select-Object -First 1).FullName
            [System.Environment]::SetEnvironmentVariable("Path", "$env:Path;$ffmpegBin", "User")
            $env:Path = "$env:Path;$ffmpegBin"
        }
    } else {
        Write-Host "  ⚠️  winget não disponível." -ForegroundColor Yellow
        Write-Host "  Descarregue o ffmpeg em: https://www.gyan.dev/ffmpeg/builds/"
        Write-Host "  Extraia e adicione a pasta 'bin' ao PATH do sistema."
        Read-Host "  Prima Enter para continuar sem ffmpeg (pode haver problemas de áudio)"
    }
}
Write-Host "✓ ffmpeg: $(try { (Get-Command ffmpeg).Source } catch { 'não instalado — instale manualmente' })"

# ---------------------------------------------------------------------------
# 3. Criar ambiente virtual com Python 3.11 via uv
# ---------------------------------------------------------------------------
$VenvDir = Join-Path $ScriptDir ".venv"
if (-not (Test-Path $VenvDir)) {
    Write-Host "A criar ambiente Python 3.11..."
    & uv venv $VenvDir --python 3.11
    if ($LASTEXITCODE -ne 0) {
        Die "Não foi possível criar o ambiente Python. Verifique a ligação à internet."
    }
}
Write-Host "✓ Python 3.11 pronto"

$PythonExe = Join-Path $VenvDir "Scripts\python.exe"

# ---------------------------------------------------------------------------
# 4. Instalar dependências
# ---------------------------------------------------------------------------
Write-Host "A instalar dependências (pode demorar 5-10 min na primeira vez)..."
& uv pip install --python $PythonExe -r (Join-Path $ScriptDir "backend\requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Die "Erro ao instalar dependências Python. Verifique a ligação à internet e tente novamente."
}
Write-Host "✓ Dependências instaladas"

# ---------------------------------------------------------------------------
# 5. Descarregar modelos
# ---------------------------------------------------------------------------
Write-Host "A verificar modelo Whisper (~242MB, só na primeira vez)..."
& $PythonExe -c "import whisper; whisper.load_model('small'); print('OK')"
if ($LASTEXITCODE -ne 0) {
    Die "Erro ao descarregar o modelo Whisper. Verifique a ligação à internet."
}
Write-Host "✓ Modelo Whisper pronto"

Write-Host "A verificar modelo de voz Kokoro (~85MB, só na primeira vez)..."
& $PythonExe -c @"
from kokoro import KPipeline
import numpy as np, soundfile as sf, tempfile, os, sys
try:
    p = KPipeline(lang_code='a')
    chunks = [a for _, _, a in p('Pronto.', voice='af_heart')]
    import tempfile
    f = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    sf.write(f.name, np.concatenate(chunks), 24000)
    os.remove(f.name)
    print('OK')
except Exception as e:
    print(f'ERRO: {e}', file=sys.stderr)
    sys.exit(1)
"@
if ($LASTEXITCODE -ne 0) {
    Die "Erro ao carregar o modelo Kokoro. Tente novamente."
}
Write-Host "✓ Modelo de voz pronto"

# ---------------------------------------------------------------------------
# 6. Configurar .env com teste de microfone
# ---------------------------------------------------------------------------
$EnvFile = Join-Path $ScriptDir "backend\.env"
if (-not (Test-Path $EnvFile)) {
    Write-Host ""
    Write-Host "Dispositivos de áudio disponíveis:"
    & $PythonExe -c @"
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    d = p.get_device_info_by_index(i)
    if d['maxInputChannels'] > 0:
        print(f'  [{i}] {d[\"name\"]}')
p.terminate()
"@

    Write-Host ""
    $DevIdx = Read-Host "Índice do microfone/mesa de som [0]"
    if (-not $DevIdx) { $DevIdx = "0" }

    # Testar microfone
    Write-Host "A testar microfone (índice $DevIdx) por 3 segundos..."
    & $PythonExe -c @"
import pyaudio, sys
DEVICE = $DevIdx
CHUNK = 1024
try:
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                    input=True, input_device_index=DEVICE, frames_per_buffer=CHUNK)
    frames = []
    for _ in range(int(16000 / CHUNK * 3)):
        frames.append(stream.read(CHUNK, exception_on_overflow=False))
    stream.stop_stream(); stream.close(); p.terminate()
    print(f'OK: gravados {sum(len(f) for f in frames)} bytes')
except Exception as e:
    print(f'FALHOU: {e}', file=sys.stderr)
    sys.exit(1)
"@
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ⚠️  Microfone índice $DevIdx falhou. Pode alterar em backend\.env depois." -ForegroundColor Yellow
    } else {
        Write-Host "  ✓ Microfone testado com sucesso"
    }

    @"
AUDIO_DEVICE_INDEX=$DevIdx
WHISPER_MODEL=small
PORT=8000
CHUNK_SECONDS=5
"@ | Set-Content $EnvFile -Encoding UTF8

    # Restringir permissões do ficheiro .env
    $acl = Get-Acl $EnvFile
    $acl.SetAccessRuleProtection($true, $false)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $env:USERNAME, "FullControl", "Allow")
    $acl.SetAccessRule($rule)
    Set-Acl $EnvFile $acl -ErrorAction SilentlyContinue

    Write-Host "✓ Ficheiro .env criado (dispositivo $DevIdx)"
} else {
    Write-Host "✓ Ficheiro .env já existe"
}

# ---------------------------------------------------------------------------
# 7. Criar lançador Windows (Iniciar Tradução.bat)
# ---------------------------------------------------------------------------
$LauncherBat = Join-Path $ScriptDir "Iniciar Tradução.bat"
@"
@echo off
cd /d "%~dp0"
set LOG_DIR=%~dp0logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo =================================================
echo   Servidor de Tradução IASD
echo =================================================
echo.

REM Verificar se já está a correr
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if %ERRORLEVEL% == 0 (
    echo Servidor ja esta a correr.
    timeout /t 1 >nul
    start http://localhost:8000/operator
    exit /b 0
)

call ".venv\Scripts\activate.bat"
cd backend
start /b python -m uvicorn main:app --host 0.0.0.0 --port 8000 >> "%LOG_DIR%\app.log" 2>&1

REM Aguardar servidor ficar pronto
echo A iniciar servidor...
for /l %%i in (1,1,15) do (
    timeout /t 1 >nul
    curl -s http://localhost:8000/health >nul 2>&1
    if not ERRORLEVEL 1 goto :ready
)
:ready
echo Servidor pronto!
REM Abrir wizard de configuracao na primeira vez
set OPEN_URL=http://localhost:8000/operator
if not exist "%~dp0.setup-done" set OPEN_URL=http://localhost:8000/setup
start %OPEN_URL%
echo. > "%~dp0.setup-done"
echo.
echo Para parar: feche esta janela
pause
"@ | Set-Content $LauncherBat -Encoding UTF8
Write-Host "✓ Lançador 'Iniciar Tradução.bat' criado"

# ---------------------------------------------------------------------------
# 8. Configurar auto-arranque (Task Scheduler) — opcional
# ---------------------------------------------------------------------------
if (-not $SkipAutoStart) {
    $answer = Read-Host "Deseja que o servidor arranque automaticamente no login? (s/N)"
    if ($answer -match "^[sS]$") {
        try {
            $Action = New-ScheduledTaskAction `
                -Execute $PythonExe `
                -Argument "-m uvicorn main:app --host 0.0.0.0 --port 8000" `
                -WorkingDirectory (Join-Path $ScriptDir "backend")
            $Trigger = New-ScheduledTaskTrigger -AtLogOn
            $Settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
            Register-ScheduledTask `
                -TaskName "IASD Traducao" `
                -Action $Action `
                -Trigger $Trigger `
                -Settings $Settings `
                -RunLevel Highest `
                -Force | Out-Null
            Write-Host "✓ Auto-arranque configurado (Task Scheduler)"
            Write-Host "  Para desativar: Procure 'Agendador de Tarefas' e elimine 'IASD Traducao'"
        } catch {
            Write-Host "  ⚠️  Não foi possível configurar auto-arranque: $_" -ForegroundColor Yellow
        }
    }
}

# ---------------------------------------------------------------------------
# 9. Resultado final
# ---------------------------------------------------------------------------
$IP = try {
    (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notmatch "^(127|169)" } | Select-Object -First 1).IPAddress
} catch { "127.0.0.1" }

Write-Host ""
Write-Host "================================================="
Write-Host ""
Write-Host "  Instalação concluída!" -ForegroundColor Green
Write-Host ""
Write-Host "  Para iniciar (duplo-clique):"
Write-Host "    Iniciar Tradução.bat"
Write-Host ""
Write-Host "  App dos membros:"
Write-Host "    http://${IP}:8000"
Write-Host ""
Write-Host "  Painel do operador:"
Write-Host "    http://${IP}:8000/operator"
Write-Host ""
Write-Host "  Logs:"
Write-Host "    $LogDir\app.log"
Write-Host ""
Write-Host "================================================="
