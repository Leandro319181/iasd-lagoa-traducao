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
