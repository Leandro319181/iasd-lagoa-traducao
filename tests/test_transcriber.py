import pytest
from unittest.mock import patch, MagicMock
import os


def test_load_model_chama_whisper_load_model():
    """Garante que load_model chama whisper.load_model com o nome correto."""
    with patch("transcriber.whisper") as mock_whisper:
        import transcriber
        transcriber._model = None  # reseta para forçar o carregamento
        transcriber.load_model("tiny")
        mock_whisper.load_model.assert_called_once_with("tiny")


def test_transcribe_retorna_texto_traduzido(tmp_path):
    """Garante que transcribe_and_translate chama o modelo e retorna o texto."""
    wav_file = tmp_path / "audio.wav"
    wav_file.write_bytes(b"fake_wav_data")

    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "  Hello world  "}

    with patch("transcriber._model", mock_model):
        import transcriber
        result = transcriber.transcribe_and_translate(str(wav_file))

    assert result == "Hello world"
    mock_model.transcribe.assert_called_once_with(
        str(wav_file), task="translate", language="pt"
    )


def test_transcribe_deleta_wav_apos_processar(tmp_path):
    """Garante que o .wav temporário é deletado após transcrição."""
    wav_file = tmp_path / "audio.wav"
    wav_file.write_bytes(b"fake_wav_data")

    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "Test"}

    with patch("transcriber._model", mock_model):
        import transcriber
        transcriber.transcribe_and_translate(str(wav_file))

    assert not wav_file.exists()


def test_transcribe_sem_modelo_lanca_erro(tmp_path):
    """Garante que erro claro é lançado se load_model não foi chamado."""
    wav_file = tmp_path / "audio.wav"
    wav_file.write_bytes(b"fake")

    with patch("transcriber._model", None):
        import transcriber
        with pytest.raises(RuntimeError, match="load_model"):
            transcriber.transcribe_and_translate(str(wav_file))


def test_load_model_usa_small_como_padrao():
    """Garante que o modelo padrão é 'small' quando nenhum argumento é passado."""
    with patch("transcriber.whisper") as mock_whisper:
        import transcriber
        transcriber._model = None
        transcriber.load_model()
        mock_whisper.load_model.assert_called_once_with("small")
