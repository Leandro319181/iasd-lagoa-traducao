import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import os


def test_text_to_speech_cria_arquivo_mp3(tmp_path):
    """Garante que um arquivo .mp3 é criado."""
    with patch("tts._synthesize", new_callable=AsyncMock) as mock_synth:
        import tts
        audio_id = tts.text_to_speech("Hello world", output_dir=str(tmp_path))

    assert audio_id is not None
    mock_synth.assert_called_once()
    call_args = mock_synth.call_args[0]
    assert call_args[0] == "Hello world"
    assert str(tmp_path) in call_args[2]  # filepath contém output_dir


def test_text_to_speech_texto_vazio_retorna_none(tmp_path):
    """Garante que texto vazio retorna None sem chamar edge-tts."""
    import tts
    result = tts.text_to_speech("", output_dir=str(tmp_path))
    assert result is None


def test_text_to_speech_voz_feminina(tmp_path):
    """Garante que voice='female' usa a voz feminina correta."""
    with patch("tts._synthesize", new_callable=AsyncMock) as mock_synth:
        import tts
        tts.text_to_speech("Hello", voice="female", output_dir=str(tmp_path))

    voice_arg = mock_synth.call_args[0][1]
    assert voice_arg == tts.VOICE_FEMALE


def test_text_to_speech_voz_masculina(tmp_path):
    """Garante que voice='male' usa a voz masculina correta."""
    with patch("tts._synthesize", new_callable=AsyncMock) as mock_synth:
        import tts
        tts.text_to_speech("Hello", voice="male", output_dir=str(tmp_path))

    voice_arg = mock_synth.call_args[0][1]
    assert voice_arg == tts.VOICE_MALE


def test_text_to_speech_retorna_none_quando_falha(tmp_path):
    """Garante que falha de rede retorna None em vez de crashar."""
    with patch("tts._synthesize", new_callable=AsyncMock) as mock_synth:
        mock_synth.side_effect = Exception("Network error")
        import tts
        result = tts.text_to_speech("Hello", output_dir=str(tmp_path))

    assert result is None
