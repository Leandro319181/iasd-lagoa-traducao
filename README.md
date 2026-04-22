# App de Tradução IASD Lagoa

Tradução simultânea em tempo real para membros da congregação, via microfone/mesa de som + Whisper AI + Kokoro TTS.

---

## Instalação rápida

### Mac

Duplo-clique em **`install.command`** e siga as instruções no Terminal.

Ou via Terminal:
```bash
bash install.sh
```

### Windows

Clique com o botão direito em **`install.ps1`** → "Executar com PowerShell".

Ou em PowerShell como Administrador:
```powershell
.\install.ps1
```

A instalação demora **10-15 minutos** na primeira vez (descarrega os modelos de IA).

---

## Iniciar o servidor

### Mac
Duplo-clique em **`Iniciar Tradução.command`**

### Windows
Duplo-clique em **`Iniciar Tradução.bat`**

O painel do operador abre automaticamente no browser.

---

## Requisitos

| | Mac | Windows |
|---|---|---|
| Sistema | macOS 12+ | Windows 10/11 |
| RAM | 4 GB mínimo | 4 GB mínimo |
| Espaço | 2 GB livres | 2 GB livres |
| Internet | Necessária na instalação | Necessária na instalação |

O instalador trata de tudo o resto (Python, ffmpeg, modelos de IA).

---

## URLs

| Página | URL |
|---|---|
| App membros | `http://IP-DO-COMPUTADOR:8000` |
| Painel operador | `http://IP-DO-COMPUTADOR:8000/operator` |
| Diagnósticos | `http://IP-DO-COMPUTADOR:8000/api/diagnostics` |

Partilhe o QR Code no painel do operador com os membros para acederem pelo telemóvel.

---

## Problemas frequentes

### "Não consigo ouvir áudio"
1. Abra `http://localhost:8000/api/diagnostics` no browser
2. Verifique o campo `audio.configured_index`
3. Se errado, edite `backend/.env` e altere `AUDIO_DEVICE_INDEX=X`
4. Reinicie o servidor

### "Erro de microfone no Mac"
- Vá a **Preferências do Sistema → Privacidade e Segurança → Microfone**
- Certifique-se que o Terminal tem permissão de acesso ao microfone

### "Whisper não transcreve / está lento"
- O modelo `small` requer ~4 GB RAM e pode demorar 5-10 segundos por chunk
- Em computadores lentos, edite `backend/.env` e mude `WHISPER_MODEL=tiny`

### "Porta 8000 já está em uso"
- Mac: `lsof -i :8000` para ver o processo; `kill -9 PID` para terminar
- Windows: `netstat -ano | findstr :8000` e termine o processo no Gestor de Tarefas

### "Servidor não arranca após atualização"
```bash
# Mac/Linux
cd /caminho/para/API-Traducao
bash install.sh
```

---

## Auto-arranque

O instalador pergunta se quer ativar o auto-arranque. Se disse não e quer ativar depois:

**Mac:**
```bash
# Ativar
launchctl load ~/Library/LaunchAgents/com.iasd-lagoa.traducao.plist

# Desativar
launchctl unload ~/Library/LaunchAgents/com.iasd-lagoa.traducao.plist
```

**Windows:**
Abra o "Agendador de Tarefas" e procure "IASD Traducao".

---

## Logs

- Mac/Linux: `logs/app.log`, `logs/stdout.log`, `logs/stderr.log`
- Windows: `logs\app.log`

---

## Desinstalar

**Mac:**
```bash
# Parar auto-arranque
launchctl unload ~/Library/LaunchAgents/com.iasd-lagoa.traducao.plist
rm ~/Library/LaunchAgents/com.iasd-lagoa.traducao.plist

# Apagar pasta do projeto
rm -rf /caminho/para/API-Traducao
```

**Windows:**
1. Abra o Agendador de Tarefas e elimine "IASD Traducao"
2. Apague a pasta do projeto

---

## Estrutura

```
API-Traducao/
├── install.command      ← Duplo-clique para instalar (Mac)
├── install.sh           ← Script de instalação (Mac/Linux)
├── install.ps1          ← Script de instalação (Windows)
├── Iniciar Tradução.command  ← Lançador duplo-clique (Mac)
├── Iniciar Tradução.bat      ← Lançador duplo-clique (Windows)
├── start.sh             ← Lançador via terminal
├── backend/
│   ├── main.py          ← Servidor FastAPI
│   ├── requirements.txt ← Dependências Python
│   └── .env             ← Configuração (criado na instalação)
├── frontend/            ← Interface web
└── logs/                ← Ficheiros de log
```
