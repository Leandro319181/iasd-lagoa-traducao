import pytest
from unittest.mock import patch, MagicMock
import numpy as np
import os


def test_texto_vazio_retorna_none(tmp_path):
    """text_to_speech com texto vazio deve retornar None sem chamar o pipeline."""
    import tts
    with patch.object(tts, "_get_pipeline") as mock_get:
        result = tts.text_to_speech("", output_dir=str(tmp_path))
    assert result is None
    mock_get.assert_not_called()
    assert list(tmp_path.glob("*.wav")) == []


def test_cria_ficheiro_wav_e_retorna_audio_id(tmp_path):
    """text_to_speech deve criar .wav e retornar UUID."""
    fake_audio = np.zeros(24000, dtype=np.float32)
    mock_pipeline = MagicMock(return_value=iter([("g", "p", fake_audio)]))

    import tts
    with patch.object(tts, "_get_pipeline", return_value=mock_pipeline):
        audio_id = tts.text_to_speech("Hello world.", output_dir=str(tmp_path))

    assert audio_id is not None
    assert (tmp_path / f"{audio_id}.wav").exists()
    assert (tmp_path / f"{audio_id}.wav").stat().st_size > 0


def test_voz_masculina_usa_am_michael(tmp_path):
    """Voz 'male' deve chamar pipeline com voice='am_michael'."""
    fake_audio = np.zeros(24000, dtype=np.float32)
    mock_pipeline = MagicMock(return_value=iter([("g", "p", fake_audio)]))

    import tts
    with patch.object(tts, "_get_pipeline", return_value=mock_pipeline):
        tts.text_to_speech("Hello.", voice="male", output_dir=str(tmp_path))

    call_kwargs = mock_pipeline.call_args
    assert call_kwargs[1]["voice"] == "am_michael"


def test_voz_feminina_usa_af_heart(tmp_path):
    """Voz 'female' (padrão) deve chamar pipeline com voice='af_heart'."""
    fake_audio = np.zeros(24000, dtype=np.float32)
    mock_pipeline = MagicMock(return_value=iter([("g", "p", fake_audio)]))

    import tts
    with patch.object(tts, "_get_pipeline", return_value=mock_pipeline):
        tts.text_to_speech("Hello.", voice="female", output_dir=str(tmp_path))

    call_kwargs = mock_pipeline.call_args
    assert call_kwargs[1]["voice"] == "af_heart"


def test_erro_retorna_none_sem_ficheiro_residual(tmp_path):
    """Se Kokoro falhar, retorna None e não deixa ficheiro .wav."""
    import tts
    with patch.object(tts, "_get_pipeline", side_effect=RuntimeError("Kokoro down")):
        result = tts.text_to_speech("Hello.", output_dir=str(tmp_path))

    assert result is None
    assert list(tmp_path.glob("*.wav")) == []
