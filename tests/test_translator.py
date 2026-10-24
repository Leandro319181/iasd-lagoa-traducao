from unittest.mock import patch, MagicMock
import translator

PT_LONGO = ("Irmãos, abram as vossas Bíblias no livro de Salmos, "
            "capítulo vinte e três, que nós vamos ler juntos agora.")


def _resp(content):
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = content
    return r


def _client(*conteudos):
    c = MagicMock()
    c.chat.completions.create.side_effect = [_resp(x) for x in conteudos]
    return c


def test_traducao_normal():
    c = _client("Brothers, open your Bibles to Psalms.")
    with patch.object(translator, "_client", c):
        r = translator.translate_pt_to_en("Irmãos, abram as Bíblias em Salmos.")
    assert r == "Brothers, open your Bibles to Psalms."


def test_vazio_devolve_string_vazia_sem_retry():
    c = _client("")
    with patch.object(translator, "_client", c):
        r = translator.translate_pt_to_en("Aplausos e barulho")
    assert r == ""
    assert c.chat.completions.create.call_count == 1


def test_erro_do_groq_devolve_none():
    c = MagicMock()
    c.chat.completions.create.side_effect = RuntimeError("rate limit")
    with patch.object(translator, "_client", c):
        r = translator.translate_pt_to_en("Bom dia, irmãos.")
    assert r is None


def test_saida_em_portugues_faz_retry():
    c = _client(PT_LONGO, "Brothers, open your Bibles to Psalms 23.")
    with patch.object(translator, "_client", c):
        r = translator.translate_pt_to_en(PT_LONGO)
    assert r == "Brothers, open your Bibles to Psalms 23."
    assert c.chat.completions.create.call_count == 2


def test_portugues_duas_vezes_descarta():
    c = _client(PT_LONGO, PT_LONGO)
    with patch.object(translator, "_client", c):
        r = translator.translate_pt_to_en(PT_LONGO)
    assert r is None


def test_remove_aspas_a_volta():
    c = _client('"Hello, brothers and sisters."')
    with patch.object(translator, "_client", c):
        r = translator.translate_pt_to_en("Olá, irmãos e irmãs.")
    assert r == "Hello, brothers and sisters."
