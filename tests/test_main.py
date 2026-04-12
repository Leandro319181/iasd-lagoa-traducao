import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json


@pytest.fixture
def client():
    with patch("main.load_model"), \
         patch("main.start_capture", return_value=MagicMock()):
        import main
        main.clients.clear()
        main.audio_files.clear()
        with TestClient(main.app) as c:
            yield c


def test_audio_inexistente_retorna_erro(client):
    """GET /audio/id-inexistente deve retornar JSON com 'error'."""
    response = client.get("/audio/id-que-nao-existe-99999")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data


def test_audio_path_traversal_retorna_erro(client):
    """GET /audio/ com path traversal deve retornar erro."""
    response = client.get("/audio/../backend/main.py")
    assert response.status_code in [200, 404, 422]
    if response.status_code == 200:
        data = response.json()
        assert "error" in data


@pytest.mark.skip(
    reason="SSE endpoint streams indefinitely — sync TestClient hangs. "
    "Verify manually: start server and check http://localhost:8000/events"
)
def test_events_retorna_event_stream(client):
    """GET /events deve retornar status 200 e content-type text/event-stream."""
    with client.stream("GET", "/events") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]


@pytest.fixture
def client_v2():
    """Fixture com estado limpo para testes dos endpoints de controlo."""
    with patch("main.load_model"), \
         patch("main.start_capture", return_value=MagicMock()):
        import main
        main.clients.clear()
        main.operator_clients.clear()
        main.audio_files.clear()
        main.is_paused = False
        main.stats.update({"chunks_processed": 0, "last_text": "", "last_error": "", "tts_failures": 0})
        with TestClient(main.app) as c:
            yield c


def test_status_retorna_json(client_v2):
    """/status deve retornar JSON com campos esperados."""
    res = client_v2.get("/status")
    assert res.status_code == 200
    data = res.json()
    assert "is_paused" in data
    assert "clients" in data
    assert "voice" in data
    assert "chunks_processed" in data


def test_pause_e_resume(client_v2):
    """/control/pause deve pausar e /control/resume deve retomar."""
    import main
    assert main.is_paused is False

    res = client_v2.post("/control/pause")
    assert res.status_code == 200
    assert res.json()["paused"] is True
    assert main.is_paused is True

    res = client_v2.post("/control/resume")
    assert res.status_code == 200
    assert res.json()["paused"] is False
    assert main.is_paused is False


def test_set_voice_invalida_retorna_400(client_v2):
    """/set-voice com gender inválido deve retornar 400."""
    res = client_v2.post(
        "/set-voice",
        json={"gender": "robot"},
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 400
