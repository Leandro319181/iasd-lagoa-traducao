# 🎙️ PROMPT: Desenvolvedor IA para App de Tradução de Áudio - Igreja IASD

## CONTEXTO DO PROJETO
Estou desenvolvendo um app simples para minha Igreja IASD que:
- Capta áudio em PORTUGUÊS da mesa de som no sábado de manhã
- Transcreve automaticamente em tempo real
- Traduz para INGLÊS (síntese de voz)
- Transmite via web para ~8 pessoas acessarem por QR Code
- Usa Python puro (sou junior em programação)
- Custo zero/mínimo
- Funciona 100% offline ou com internet básica

## ESPECIFICAÇÕES TÉCNICAS

### Hardware
- PC/Laptop rodando o servidor
- Entrada de áudio: cabo P2 ou USB da mesa de som → PC
- Internet: WiFi normal (não precisa fibra)

### Stack de Desenvolvimento
**Backend:**
- Python 3.10+
- FastAPI (servidor web)
- OpenAI Whisper (transcrição português)
- gTTS - Google Text-to-Speech (síntese voz inglês)
- PyAudio (capturar áudio do microfone)
- Pydub (processar áudio)

**Frontend:**
- HTML5 simples
- JavaScript vanilla
- Player de áudio nativo

**Hospedagem:**
- Localhost (PC próprio) para começar
- Depois: Render.com ou Railway.app (FREE tier)

### Fluxo de Dados
```
Mesa de Som (P2/USB)
    ↓ [PyAudio]
Entrada de Áudio do PC
    ↓ [Whisper]
Transcrição em Português
    ↓ [gTTS]
Síntese de Voz em Inglês
    ↓ [FastAPI Stream]
Transmissão HTTP ao Navegador
    ↓ [HTML5 Audio Tag]
Áudio em Inglês no App Web
```

## ESTRUTURA DE PASTAS ESPERADA

```
projeto-traducao-iasd/
├── backend/
│   ├── main.py                 # FastAPI app principal
│   ├── audio_handler.py        # Captura e processa áudio
│   ├── transcriber.py          # Whisper integration
│   ├── translator.py           # Text-to-Speech gTTS
│   ├── requirements.txt        # Dependências Python
│   └── .env                    # Variáveis de ambiente
├── frontend/
│   ├── index.html             # Página web
│   ├── style.css              # Estilos
│   └── script.js              # Lógica frontend
├── docs/
│   ├── INSTALACAO.md          # Como instalar
│   ├── COMO_USAR.md           # Guia de uso
│   └── TROUBLESHOOTING.md     # Soluções de problemas
├── qrcode/
│   └── qrcode.png             # QR Code gerado
├── docker-compose.yml         # Para deploy depois
└── README.md

```

## REQUISITOS FUNCIONAIS

### MVP (Mínimo Viável)
- [x] Capturar áudio de entrada (microfone/P2)
- [x] Transcrever para texto português em tempo real
- [x] Converter texto para voz em inglês
- [x] Transmitir áudio via HTTP streaming
- [x] Página web simples com player
- [x] QR Code para acesso rápido

### Fase 2 (Melhorias)
- [ ] Salvar gravações em arquivo
- [ ] Interface para ativar/desativar transmissão
- [ ] Indicador de status (ao vivo/offline)
- [ ] Histórico de transmissões
- [ ] Legendas em tempo real (português + inglês)

### Fase 3 (Avançado)
- [ ] App mobile nativa (React Native)
- [ ] Deploy em servidor na nuvem
- [ ] Autenticação (só membros podem acessar)
- [ ] Qualidade de áudio ajustável
- [ ] Múltiplas línguas

## INSTRUÇÕES PARA A IA

**Seu papel:** Você é um assistente de programação especializado em Python e desenvolvimento web.

**Meu nível:** Sou junior em Python, iniciante em FastAPI, nunca usei Whisper ou gTTS.

**Como me ajudar:**
1. **Explique cada linha de código** - não assuma conhecimento
2. **Mostre exemplos práticos** - código que funciona de verdade
3. **Passo a passo** - quebra problemas complexos em passos pequenos
4. **Testes** - como testar cada parte do código
5. **Erros comuns** - antecipe problemas que iniciantes têm
6. **Documentação** - comenta o código bem

**Ordem preferida de desenvolvimento:**
1. Primeiro: Estrutura básica (pastas, arquivos, venv)
2. Segundo: Capturar áudio (PyAudio)
3. Terceiro: Transcrever (Whisper)
4. Quarto: Sintetizar voz (gTTS)
5. Quinto: Servidor FastAPI
6. Sexto: Frontend HTML/JS
7. Sétimo: QR Code
8. Oitavo: Deploy e testes

## RESPOSTAS QUE QUERO

**Para cada tarefa, quero:**

```
## [Nome da tarefa]

### Objetivo
[O que vamos fazer]

### Pré-requisitos
- Ter instalado X
- Entender Y
- Ter arquivo Z

### Código Completo
\`\`\`python
# Código aqui
\`\`\`

### Explicação linha por linha
1. Linha X: Faz isso porque...
2. Linha Y: Faz aquilo porque...

### Como testar
1. Rode assim: `python script.py`
2. Espere isso: [resultado esperado]
3. Se der erro X, faça Y

### Erros comuns
- ❌ Erro: "ModuleNotFoundError"
  ✅ Solução: Instale com `pip install modulo`

### Próximo passo
[O que fazer depois disso]
```

## ARQUIVOS QUE VOU CRIAR

**Quando pedir arquivo novo, gere:**
- Nome completo do arquivo
- Caminho relativo (`backend/main.py`)
- Código completo
- Instruções de onde salvar
- Dependências novas (se houver)

## TECNOLOGIAS E CONFIGURAÇÃO

### Python venv
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### Instalações
```bash
pip install fastapi uvicorn openai-whisper gtts pyaudio pydub python-multipart qrcode pillow python-dotenv
```

### Testes locais
- Frontend: `http://localhost:8000`
- API: `http://localhost:8000/docs` (Swagger)
- Stream: `http://localhost:8000/stream-audio`

## SITUAÇÕES ESPECIAIS

### Entrada de áudio
- Pode ser microfone padrão do PC
- Ou entrada linha P2/USB da mesa de som
- A entrada será configurada no código com índice do dispositivo

### Latência
- Esperado: 3-5 segundos entre fala em português e áudio em inglês
- Isso é normal (transcrição + síntese leva tempo)
- Não tente "otimizar demais" no início

### Performance
- Whisper "base" usa ~4GB RAM (ok pra notebook)
- Se tiver problema, pode trocar para "tiny" (menos preciso, rápido)
- gTTS é rápido (depende da internet)

## QUANDO PEDIR AJUDA, USE ESTES FORMATOS

### Formato 1: Preciso fazer X
```
Preciso implementar: [descrição]
Tenho dúvida em: [específico]
Contexto: [onde isso se encaixa]
```

### Formato 2: Tenho um erro
```
Erro exato: [mensagem de erro]
Código: [linha que tá dando erro]
O que eu fiz: [passos para reproduzir]
```

### Formato 3: Não entendi
```
Linha de código: [copie aqui]
Não entendi: [a parte confusa]
Por que faz assim: [o que você pensava que era]
```

## CHECKLIST FINAL

Quando terminar o desenvolvimento, verificar:
- [ ] Código roda sem erros
- [ ] FastAPI inicia corretamente
- [ ] Captura áudio da entrada
- [ ] Transcreve português corretamente
- [ ] Sintetiza voz em inglês
- [ ] Streaming funciona no navegador
- [ ] 8 pessoas conseguem acessar simultaneamente
- [ ] QR Code funciona
- [ ] Documentação está clara
- [ ] Funciona todo sábado sem crash

## OBSERVAÇÕES IMPORTANTES

⚠️ **Privacidade:** O áudio é processado localmente (Python). Não sai da sua Igreja (a não ser o stream web pro navegador)

⚠️ **Internet:** Whisper pode rodar offline. gTTS precisa de internet (ou usar TTS offline depois)

⚠️ **Backup:** Guarde as gravações de áudio original em arquivo .wav para arquivo da Igreja

⚠️ **Qualidade:** Quanto melhor o áudio de entrada, melhor a transcrição

---

## COMECE AQUI

**Primeira pergunta para a IA:**

"Ajude-me a criar a estrutura de pastas e instalar as dependências do projeto. Quero um passo a passo que qualquer iniciante consegue seguir no Windows/Mac/Linux."

---

Você também pode copiar e colar este prompt inteiro na IA do VS Code (Copilot, Claude extension, etc) e ela entenderá exatamente o que você precisa.

Boa sorte! 🙏✨
