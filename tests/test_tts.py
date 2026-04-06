import pytest
from unittest.mock import patch, MagicMock
import os


def test_text_to_speech_cria_arquivo_mp3(tmp_path):
    """Garante que um arquivo .mp3 é criado no diretório correto."""
    mock_gtts = MagicMock()

    with patch("tts.gTTS", return_value=mock_gtts):
        import tts
        audio_id = tts.text_to_speech("Hello world", output_dir=str(tmp_path))

    assert audio_id is not None
    mp3_path = tmp_path / f"{audio_id}.mp3"
    mock_gtts.save.assert_called_once_with(str(mp3_path))


def test_text_to_speech_texto_vazio_retorna_none(tmp_path):
    """Garante que texto vazio não gera arquivo e retorna None."""
    import tts
    result = tts.text_to_speech("", output_dir=str(tmp_path))
    assert result is None


def test_text_to_speech_usa_idioma_ingles(tmp_path):
    """Garante que gTTS é chamado com lang='en'."""
    mock_gtts_class = MagicMock()

    with patch("tts.gTTS", mock_gtts_class):
        import tts
        tts.text_to_speech("Hello", output_dir=str(tmp_path))

    call_kwargs = mock_gtts_class.call_args[1]
    assert call_kwargs["lang"] == "en"
    assert call_kwargs["text"] == "Hello"
