# Design: App de Tradução de Áudio — Igreja IASD

**Data:** 2026-04-05
**Autor:** Leandro (voluntário)
**Status:** Aprovado

---

## Contexto

App para traduzir cultos ao vivo de português para inglês para ~8 membros anglófonos da Igreja IASD. Capta áudio da mesa de som via cabo P2/USB, transcreve e traduz com Whisper, sintetiza voz em inglês com gTTS, e entrega legenda + áudio via web para celulares dos membros via QR Code ou link no WhatsApp.

---

## Requisitos

- Windows 11, 16GB RAM
- Internet WiFi sempre disponível na Igreja
- ~8 usuários simultâneos via navegador mobile
- Custo zero (voluntário)
- Legendas apenas em inglês
- Latência de 8–11 segundos é aceitável

---

## Arquitetura

### Stack

| Camada | Tecnologia |
|--------|-----------|
| Captura de áudio | PyAudio |
| Transcrição + Tradução | OpenAI Whisper `small` |
| Síntese de voz | gTTS (Google Text-to-Speech) |
| Servidor web | FastAPI + Uvicorn |
| Comunicação em tempo real | SSE (Server-Sent Events) |
| Frontend | HTML5 + CSS + JavaScript vanilla |
| QR Code | biblioteca `qrcode` |

### Fluxo de Dados

```
Mesa de Som (P2/USB)
    ↓
PyAudio — captura chunks de 5 segundos
    ↓
Whisper small — transcreve PT e traduz para EN
    ↓
gTTS — gera arquivo .mp3 com a voz em inglês
    ↓
FastAPI
  • GET /events     → SSE envia texto EN + URL do áudio
  • GET /audio/{id} → serve o .mp3 gerado
    ↓
Navegador (celular dos membros)
  • Legenda em inglês atualizada em tempo real
  • Áudio em inglês tocando automaticamente
```

---

## Estrutura de Pastas

```
projeto-traducao-iasd/
├── backend/
│   ├── main.py              # FastAPI app, endpoints SSE e /audio
│   ├── audio_capture.py     # PyAudio: captura chunks de 5s
│   ├── transcriber.py       # Whisper: transcreve PT → EN
│   ├── tts.py               # gTTS: texto EN → .mp3
│   ├── requirements.txt
│   └── .env                 # Configurações (porta, device index)
├── frontend/
│   ├── index.html           # Página única responsiva
│   ├── style.css            # Tela escura, texto grande
│   └── script.js            # SSE client, auto-play, reconexão
├── temp/                    # .mp3 temporários (deletados após 60s)
├── docs/
│   └── superpowers/specs/   # Este arquivo
├── generate_qr.py           # Detecta IP local e gera qrcode.png
├── qrcode.png               # QR Code gerado
└── README.md
```

---

## Componentes

### `audio_capture.py`
- Usa PyAudio para abrir o dispositivo de entrada configurado via `.env`
- Captura em loop contínuo, chunks de 5 segundos (taxa: 16000 Hz, mono)
- Salva cada chunk como `.wav` temporário e coloca em fila (`asyncio.Queue`)

### `transcriber.py`
- Carrega modelo Whisper `small` uma vez na inicialização
- Recebe arquivo `.wav` da fila
- Chama `whisper.transcribe(arquivo, task="translate")` — entrega texto em inglês diretamente
- Retorna o texto traduzido

### `tts.py`
- Recebe texto em inglês
- Chama `gTTS(text, lang='en')`
- Salva `.mp3` em `temp/{uuid}.mp3`
- Retorna o ID do arquivo gerado

### `main.py`
- Inicializa FastAPI
- Inicia `audio_capture` e loop de processamento em background (`asyncio`)
- **`GET /events`** — SSE: quando novo chunk processado, envia `{"text": "...", "audio_id": "..."}`
- **`GET /audio/{audio_id}`** — serve o `.mp3` com `FileResponse`
- Tarefa de limpeza: deleta `.mp3` com mais de 60 segundos de `temp/`

### `frontend/index.html` + `script.js`
- `EventSource('/events')` escuta o SSE
- A cada evento: atualiza elemento `<p id="legenda">` com o texto recebido
- Cria elemento `<audio>` e chama `.play()` automaticamente
- Se conexão SSE cair: tenta reconectar a cada 3 segundos
- Exibe indicador "🔴 AO VIVO" ou "⚫ OFFLINE"

### `generate_qr.py`
- Detecta IP local da máquina via `socket`
- Gera URL `http://{IP}:8000`
- Salva `qrcode.png` na raiz do projeto
- Imprime o link no terminal para copiar no WhatsApp

---

## Tratamento de Erros

| Situação | Comportamento |
|----------|--------------|
| Chunk de silêncio / ruído | Whisper retorna texto vazio → descarta silenciosamente |
| gTTS falha (internet lenta) | Envia SSE só com texto, sem `audio_id` → legenda aparece, sem áudio |
| Cliente perde SSE | JavaScript reconecta automaticamente a cada 3s |
| Whisper lento (chunk anterior não terminou) | Fila aguarda — chunks não são descartados, apenas atrasam |

---

## Configuração (`.env`)

```env
AUDIO_DEVICE_INDEX=0      # Índice do dispositivo de entrada (0 = padrão)
WHISPER_MODEL=small       # tiny | base | small
PORT=8000
CHUNK_SECONDS=5
```

---

## MVP — Checklist de Funcionalidades

- [ ] Captura áudio da entrada P2/USB configurada
- [ ] Whisper transcreve e traduz para inglês
- [ ] gTTS gera .mp3 com voz em inglês
- [ ] SSE entrega texto + áudio para clientes
- [ ] Frontend mostra legenda e toca áudio automaticamente
- [ ] Indicador ao vivo / offline
- [ ] QR Code gerado com IP local
- [ ] 8 usuários simultâneos funcionando
- [ ] Funciona todo sábado sem crash

---

## Fases Futuras (fora do escopo deste plano)

- **Fase 2:** Salvar gravações, interface de controle (ligar/desligar), histórico
- **Fase 3:** Deploy em nuvem, autenticação, app mobile, múltiplos idiomas
