import asyncio
import pytest
import main


@pytest.fixture(autouse=True)
def estado_limpo():
    main.clients.clear()
    main.is_paused = True
    main._auto_stop_task = None
    yield
    t = main._auto_stop_task
    if t is not None and not t.done():
        try:
            t.cancel()
        except RuntimeError:
            pass
    main._auto_stop_task = None
    main.clients.clear()


def _liga():
    q = object()
    main.clients.append(q)
    main._on_member_connected()
    return q


def _desliga(q):
    main.clients.remove(q)
    main._on_member_disconnected()


def test_primeiro_membro_arranca_traducao():
    _liga()
    assert main.is_paused is False


def test_pausa_manual_respeitada_quando_entra_mais_alguem():
    _liga()
    main._pause_translation("operador")
    _liga()  # 2.º membro
    assert main.is_paused is True


@pytest.mark.asyncio
async def test_sem_membros_pausa_apos_atraso(monkeypatch):
    monkeypatch.setattr(main, "AUTO_STOP_DELAY", 0.05)
    q = _liga()
    _desliga(q)
    assert main.is_paused is False      # ainda não passou o atraso
    await asyncio.sleep(0.15)
    assert main.is_paused is True


@pytest.mark.asyncio
async def test_membro_volta_cancela_pausa(monkeypatch):
    monkeypatch.setattr(main, "AUTO_STOP_DELAY", 0.1)
    q = _liga()
    _desliga(q)
    await asyncio.sleep(0.03)
    _liga()                             # voltou antes do atraso
    await asyncio.sleep(0.15)
    assert main.is_paused is False


@pytest.mark.asyncio
async def test_operador_inicia_sem_membros_pausa_apos_atraso(monkeypatch):
    monkeypatch.setattr(main, "AUTO_STOP_DELAY", 0.05)
    await main.control_resume()
    assert main.is_paused is False
    await asyncio.sleep(0.15)
    assert main.is_paused is True
