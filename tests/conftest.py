import os
import sys
from unittest.mock import MagicMock

# Isolar os testes do .env real: sem Telegram e sem Groq.
# load_dotenv() não substitui variáveis que já existem, por isso
# isto tem de correr ANTES de qualquer import do backend.
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_CHAT_ID"] = ""
os.environ["GROQ_API_KEY"] = ""

# Mock whisper so tests work without openai-whisper installed
sys.modules['whisper'] = MagicMock()
# Mock kokoro so tests work without kokoro installed
sys.modules['kokoro'] = MagicMock()
# Mock pyaudio so tests work without PyAudio installed
pyaudio_mock = MagicMock()
pyaudio_mock.paInt16 = 8
sys.modules['pyaudio'] = pyaudio_mock
