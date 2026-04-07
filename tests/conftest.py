import sys
from unittest.mock import MagicMock

# Mock whisper so tests work without openai-whisper installed
sys.modules['whisper'] = MagicMock()

# Mock edge_tts so tests work without edge-tts installed
sys.modules['edge_tts'] = MagicMock()

# Mock pyaudio so tests work without PyAudio installed
pyaudio_mock = MagicMock()
pyaudio_mock.paInt16 = 8
sys.modules['pyaudio'] = pyaudio_mock
