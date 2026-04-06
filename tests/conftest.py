import sys
from unittest.mock import MagicMock

# Mock whisper so tests work without openai-whisper installed
sys.modules['whisper'] = MagicMock()
