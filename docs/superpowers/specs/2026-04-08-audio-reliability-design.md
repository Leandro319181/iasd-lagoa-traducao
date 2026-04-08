# Design: Melhoria de Fiabilidade de Áudio — Igreja IASD

**Data:** 2026-04-08
**Autor:** Leandro (voluntário)
**Status:** Aprovado

---

## Contexto

O app de tradução ao vivo (PT → EN) para ~8 membros anglófonos da Igreja IASD está funcional, mas com falhas intermitentes no áudio: o TTS externo (edge-tts) falha esporadicamente e o Chrome mobile suspende o AudioContext quando o ecrã dimma, congelando a fila de reprodução. Este documento descreve as melhorias para tornar o sistema fiável para uso em cultos.

**Ambiente de deploy:** Mac Mini da igreja (usado também para transmissão ao vivo).
**Utilizadores:** ~8 membros no telemóvel, ecrã aceso, na mesma rede Wi-Fi da igreja.
**Pregadores:** alternam entre pt-PT e pt-BR.

---

## Problemas Identificados

| # | Problema | Origem | Impacto |
|---|----------|--------|---------|
| 1 | edge-tts falha com "No audio received" | API Microsoft sem SLA | Chunks sem áudio |
| 2 | `onended` do Web Audio API não dispara sempre | Chrome mobile | Fila de áudio congela |
| 3 | AudioContext suspende quando ecrã dimma | Política do browser | Áudio para sem aviso |
| 4 | Whisper sem dica de idioma | Configuração omissa | Menor precisão em pt-PT |
| 5 | Sem painel de monitorização | Feature inexistente | Operador não sabe se está a funcionar |
| 6 | Instalação manual e técnica | Sem script de setup | Difícil de instalar por não-técnicos |

---

## Arquitetura Actualizada

```
Mesa de Som (P2/USB)
    ↓
PyAudio — captura chunks de 5s
    ↓
Whisper small (language="pt") — transcreve PT e traduz para EN
    ↓
Kokoro TTS (local, no Mac Mini) — gera .wav com voz inglesa
    ↓
FastAPI
  • GET  /          → app dos membros (PWA)
  • GET  /operator  → painel do operador
  • GET  /events    → SSE: texto EN + audio_id (membros e operador)
  • GET  /audio/{id}→ serve o .wav gerado
  • GET  /status    → JSON com estado actual
  • POST /set-voice → troca voz (male/female)
  • POST /control/pause          → pausa tradução
  • POST /control/resume         → retoma tradução
  • POST /control/restart-capture → reinicia captura de microfone
    ↓
Membros (PWA no telemóvel)        Operador (browser Mac Mini ou tablet)
  • Wake Lock: ecrã sempre aceso    • Status em tempo real
  • Fila de áudio robusta           • Controles de operação
  • Toggle áudio ON/OFF             • Histórico de legendas
```

---

## Mudanças por Componente

### 1. TTS — Kokoro Local (`backend/tts.py`)

Substituir edge-tts por **Kokoro TTS** (`hexgrad/kokoro`).

- **Modelo:** ~80MB, descarregado automaticamente na primeira execução
- **Vozes:** `af_heart` (feminina) / `am_michael` (masculina) — inglês americano
- **Formato de saída:** WAV 24kHz mono (sem necessidade de ffmpeg)
- **Latência esperada:** 0.3–1s por chunk no Mac Mini Intel; <0.3s no M-series
- **Fallback:** se Kokoro falhar, loga o erro e envia evento sem `audio_id` (legenda aparece, sem áudio — melhor que silêncio total)

```python
# Interface pública mantida igual:
audio_id = text_to_speech(text, voice="female")  # retorna UUID ou None
```

**Serviço de ficheiros:** endpoint `/audio/{id}` passa a servir `.wav` em vez de `.mp3`. O Web Audio API do browser suporta WAV nativamente.

### 2. Transcrição — Fix Português (`backend/transcriber.py`)

Adicionar `language="pt"` na chamada do Whisper:

```python
result = _model.transcribe(wav_path, task="translate", language="pt")
```

Isto melhora precisão para pt-PT (sotaque europeu) sem prejudicar pt-BR, pois o modelo recebe dica explícita de idioma em vez de auto-detectar.

### 3. Servidor — Novos Endpoints (`backend/main.py`)

**Estado partilhado adicional:**
```python
is_paused: bool = False          # tradução pausada pelo operador
operator_clients: list = []      # filas SSE do painel operador
stats: dict = {                  # métricas para /status
    "chunks_processed": 0,
    "last_text": "",
    "last_error": "",
    "tts_failures": 0,
}
```

**Novos endpoints:**
- `GET /operator` — serve `operator.html`
- `GET /status` — retorna JSON com `stats` + `is_paused` + `len(clients)` + `current_voice`
- `POST /control/pause` — define `is_paused = True`, loga
- `POST /control/resume` — define `is_paused = False`, loga
- `POST /control/restart-capture` — para thread de captura e inicia nova
- `GET /operator-events` — SSE dedicado ao operador com eventos enriquecidos (inclui erros, contagem de clientes, etc.)

**`process_loop` actualizado:** respeita `is_paused` antes de processar cada chunk.

### 4. App dos Membros — PWA + Wake Lock (`frontend/`)

**Novos ficheiros:**
- `frontend/manifest.json` — PWA manifest (nome, ícone, `display: standalone`)
- `frontend/sw.js` — Service Worker mínimo (cache do HTML/CSS/JS para reload offline)

**Mudanças em `index.html`:**
- Adicionar `<link rel="manifest">` e `<meta name="theme-color">`
- Botão de áudio ON/OFF mais proeminente e com estado visual claro

**Mudanças em `script.js`:**
- Solicitar **Wake Lock** ao carregar a página (mantém ecrã aceso)
- Renovar Wake Lock se for libertado (ex: ao voltar ao tab)
- Fila de áudio reescrita: estado `idle | loading | playing`, com timeout de segurança de `duração + 2s`
- Trocar Web Audio API por **HTML `<audio>` element gerido por estado** (mais simples, mais fiável no Chrome mobile para ficheiros WAV sequenciais)

### 5. Painel do Operador (`frontend/operator.html`, `frontend/operator.js`)

**Secção de Status (atualiza a cada 2s via polling `/status`):**
- 🟢/🔴 Captura de áudio ativa
- 🟢/🔴 TTS a funcionar (último erro se houver)
- Nº de membros conectados
- Última legenda traduzida
- Contagem de falhas de TTS na sessão

**Secção de Legendas (atualiza via SSE `/operator-events`):**
- Histórico das últimas 10 traduções com timestamp

**Secção de Controles:**
- ▶/⏸ Pausar / Retomar tradução (toggle)
- 🔄 Reiniciar captura de microfone
- 🎙 Voz: Feminina / Masculina (botões, mesmo que no app atual)
- 🔇 Mutar todos (envia evento SSE `{"action":"mute"}` para todos os clientes membros; cada cliente silencia localmente e mostra ícone 🔇)

### 6. Script de Instalação (`install.sh`)

Script shell executável por qualquer pessoa:

```
Passo 1 — Verificar Python 3.9+
Passo 2 — Criar venv em .venv/
Passo 3 — pip install -r backend/requirements.txt
Passo 4 — Descarregar modelo Kokoro (~80MB) com barra de progresso
Passo 5 — Detectar dispositivos de áudio e sugerir AUDIO_DEVICE_INDEX
Passo 6 — Criar backend/.env com valores padrão se não existir
Passo 7 — Criar temp/ se não existir
Passo 8 — Gerar start.sh (atalho para iniciar servidor)
Passo 9 — Mensagem final com URL de acesso e QR code
```

**`start.sh`** (gerado pelo install):
```bash
#!/bin/bash
cd "$(dirname "$0")/backend"
source ../.venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## Dependências Actualizadas

Remover do `requirements.txt`:
- `edge-tts`

Adicionar:
- `kokoro>=0.9`
- `soundfile>=0.12`

---

## Estrutura de Pastas Final

```
API-Traducao/
├── backend/
│   ├── main.py              # FastAPI: endpoints existentes + novos de controlo
│   ├── audio_capture.py     # PyAudio (sem alterações)
│   ├── transcriber.py       # Whisper + language="pt"
│   ├── tts.py               # Kokoro TTS (substitui edge-tts)
│   ├── requirements.txt     # kokoro + soundfile
│   └── .env
├── frontend/
│   ├── index.html           # + manifest link + wake lock
│   ├── style.css            # (ajustes menores)
│   ├── script.js            # PWA + Wake Lock + fila robusta
│   ├── manifest.json        # PWA manifest (novo)
│   ├── sw.js                # Service Worker (novo)
│   ├── operator.html        # Painel operador (novo)
│   └── operator.js          # Lógica painel operador (novo)
├── temp/                    # .wav temporários
├── install.sh               # Script de instalação (novo)
├── start.sh                 # Atalho de arranque (gerado pelo install)
├── generate_qr.py
└── docs/
    └── superpowers/
        └── specs/
            ├── 2026-04-05-traducao-audio-iasd-design.md
            └── 2026-04-08-audio-reliability-design.md
```

---

## Critérios de Sucesso

- [ ] TTS gera áudio sem falhas de rede (Kokoro local)
- [ ] Fila de áudio não congela no Chrome mobile durante 1h de culto
- [ ] Ecrã não apaga durante uso (Wake Lock ativo)
- [ ] Operador consegue pausar/retomar e ver estado em tempo real
- [ ] Instalação completa em <10 minutos por não-técnico seguindo o README
- [ ] Funciona com pt-PT e pt-BR sem configuração extra
