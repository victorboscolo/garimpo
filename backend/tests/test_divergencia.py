"""Testes da detecção de divergência entre o que foi publicado e o que vale hoje.

Reprocessar o motor muda notas. Se a promoção já foi publicada, o canal passa a
afirmar uma coisa e o sistema outra, e ninguém percebe — não existe despublicar
no Telegram. Quem leu agiu sobre uma avaliação que já não se sustenta.

A categoria da época é reconstruída do histórico de classificações, que existe
porque nada é sobrescrito: a classificação anterior é marcada como inativa, não
apagada.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from application.divergencia import classificacao_vigente_em

AGORA = datetime(2026, 8, 14, 21, 0, tzinfo=timezone.utc)


def _classificacao(categoria, minutos_atras, ativa=False):
    return SimpleNamespace(
        categoria=categoria,
        processada_em=AGORA - timedelta(minutes=minutos_atras),
        ativa=ativa,
    )


def test_pega_a_que_valia_no_momento_da_publicacao():
    """Três reprocessamentos depois, ainda é preciso saber o que o canal recebeu."""
    historico = [
        _classificacao("BOA", 180),
        _classificacao("EXCEPCIONAL", 120),
        _classificacao("EXCELENTE", 10, ativa=True),
    ]
    publicado_em = AGORA - timedelta(minutes=60)
    assert classificacao_vigente_em(historico, publicado_em).categoria == "EXCEPCIONAL"


def test_ignora_classificacoes_posteriores_a_publicacao():
    historico = [
        _classificacao("BOA", 180),
        _classificacao("EXCEPCIONAL", 5, ativa=True),
    ]
    publicado_em = AGORA - timedelta(minutes=60)
    assert classificacao_vigente_em(historico, publicado_em).categoria == "BOA"


def test_sem_classificacao_anterior_a_publicacao():
    """Não deve inventar: devolve None e o chamador reporta como desconhecida."""
    historico = [_classificacao("BOA", 10, ativa=True)]
    publicado_em = AGORA - timedelta(minutes=60)
    assert classificacao_vigente_em(historico, publicado_em) is None


def test_historico_vazio():
    assert classificacao_vigente_em([], AGORA) is None


def test_ordem_da_lista_nao_importa():
    """Os registros vêm do banco sem garantia de ordem."""
    historico = [
        _classificacao("EXCELENTE", 10, ativa=True),
        _classificacao("BOA", 180),
        _classificacao("EXCEPCIONAL", 120),
    ]
    publicado_em = AGORA - timedelta(minutes=60)
    assert classificacao_vigente_em(historico, publicado_em).categoria == "EXCEPCIONAL"
