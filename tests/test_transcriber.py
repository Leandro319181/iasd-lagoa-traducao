import pytest
from transcriber import _is_hallucination


@pytest.mark.parametrize("texto", [
    "Aplausos",
    "A Aplausos.",
    "Música",
    "Obrigado por assistir!",
    "Acesse o nosso site www.sertimus.com.br.",
    "Acesse o nosso site [www.mesmerism.com.br](https://www.mesmerism.com.br).",
    "Legendas pela comunidade Amara.org",
    "Se inscreva no canal e deixe seu like",
])
def test_alucinacoes_conhecidas_sao_filtradas(texto):
    filtrado, motivo = _is_hallucination(texto, 0.0)
    assert filtrado is True, f"Devia filtrar: {texto}"


@pytest.mark.parametrize("texto", [
    "Faz saber ao Rei de Israel as palavras que falas.",
    "Irmãos, abram as vossas Bíblias no livro de Salmos.",
    "Ele era um inimigo do povo de Deus.",
    "Glória a Deus, aleluia!",
    "Hoje vamos estudar a lição da Escola Sabatina.",
])
def test_frases_de_sermao_passam(texto):
    filtrado, motivo = _is_hallucination(texto, 0.0)
    assert filtrado is False, f"Não devia filtrar: {texto} ({motivo})"


def test_texto_vazio_ou_curto_e_filtrado():
    assert _is_hallucination("", 0.0)[0] is True
    assert _is_hallucination("ok", 0.0)[0] is True


def test_no_speech_alto_e_filtrado():
    assert _is_hallucination("Irmãos, abram as Bíblias.", 0.9)[0] is True
