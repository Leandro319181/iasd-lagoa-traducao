import sys
from unittest.mock import MagicMock

# Mock whisper so tests work without openai-whisper installed
sys.modules['whisper'] = MagicMock()

# Mock gtts so tests work without gtts installed
gtts_mock = MagicMock()
sys.modules['gtts'] = gtts_mock

# Mock pyaudio so tests work without PyAudio installed
pyaudio_mock = MagicMock()
pyaudio_mock.paInt16 = 8
sys.modules['pyaudio'] = pyaudio_mock
