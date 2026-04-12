"""
Script de preview — inicia o servidor sem Whisper/PyAudio/gTTS instalados.
Serve o frontend em http://localhost:8000 para visualização.
"""
import sys
import os
from unittest.mock import MagicMock

# Mocka dependências pesadas para não precisar instalar
sys.modules['whisper']      = MagicMock()
sys.modules['pyaudio']      = MagicMock()
sys.modules['pyaudio'].paInt16 = 8
sys.modules['gtts']         = MagicMock()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import uvicorn
import main

print("\n🔍 PREVIEW MODE — audio capture and translation are disabled")
print("📱 Open in browser: http://localhost:8000\n")

uvicorn.run(main.app, host="127.0.0.1", port=8000)
