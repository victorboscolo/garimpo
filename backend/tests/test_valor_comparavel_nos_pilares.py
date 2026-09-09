"""Testes de como `valor_comparavel` entra nos pilares Histórico,
Atratividade e Exclusividade — não só a função em si (isso já está em
`test_percentil.py`), mas o efeito real na nota quando a oferta ou a base
de comparação envolve uma condicionada.

Caso real que motivou a mudança (09/09): o Carrefour anunciou "7 pontos"
(20/08), mas só valia em produtos da marca própria — 1 ponto pra tudo
mais. Um 5 pontos incondicional comparado contra esse "7" saía perdendo
sem razão, porque o 7 nunca foi o valor real pra maior parte das compras.
"""
from decimal import Decimal
from types import SimpleNamespace

from application.motor.historico import BaseComparacao, HistoricoFamilia
from application.motor.pilares import pilar_atratividade, pilar_exclusividade, pilar_historico_com_base


def _promocao(**ajustes):
    padrao = dict(pontuacao=Decimal("5"), valor_condicionado=False, valor_condicionado_piso=None)
    padrao.update(ajustes)
    return SimpleNamespace(**padrao)


def _base(distribuicao):
    return BaseComparacao(
        media_ponderada=None, total=len(distribuicao), nivel="FAMILIA",
        rotulo=None, confianca_historica="MEDIA", distribuicao=distribuicao,
    )


# --- pilar_historico_com_base ---------------------------------------------


def test_oferta_incondicional_nao_perde_pra_recorde_inflado():
    """A base já vem com o piso das condicionadas (1, não 7) — o 5
    incondicional bate esse piso em vez de perder pra um "7" que nunca foi
    o valor real da maioria das compras.
    """
    promocao = _promocao(pontuacao=Decimal("5"), valor_condicionado=False)
    base = _base([Decimal("5"), Decimal("6"), Decimal("6"), Decimal("1"), Decimal("1"), Decimal("3")])
    nota = pilar_historico_com_base(promocao, base)
    # menores: [1,1,3] = 3; iguais: [5] = 1 -> (3 + 0.5)/6*100 = 58.33
    assert nota == 58.33


def test_oferta_condicionada_entra_na_base_pelo_piso():
    """A própria oferta sendo avaliada, se condicionada, também é
    posicionada pelo piso — não pelo número anunciado.
    """
    promocao = _promocao(
        pontuacao=Decimal("7"), valor_condicionado=True, valor_condicionado_piso=Decimal("1"),
    )
    base = _base([Decimal("5"), Decimal("6")])
    nota = pilar_historico_com_base(promocao, base)
    # 1 (o piso, não o 7) fica abaixo dos dois -> 0.0
    assert nota == 0.0


# --- pilar_atratividade ----------------------------------------------------


def test_atratividade_usa_o_piso_do_mercado():
    promocao = _promocao(pontuacao=Decimal("5"), valor_condicionado=False)
    mercado = [Decimal("1"), Decimal("1"), Decimal("3"), Decimal("5")]
    nota = pilar_atratividade(promocao, mercado)
    # menores: [1,1,3]=3; iguais: [5]=1 -> (3+0.5)/4*100 = 87.5
    assert nota == 87.5


# --- pilar_exclusividade ---------------------------------------------------


def test_recorde_condicionado_nao_conta_como_recorde_de_verdade():
    """O "recorde" de 7 pontos era só na marca própria — o histórico já
    guarda o piso (1) como o recorde real, então um 5 incondicional bate
    esse recorde, não perde pra ele.
    """
    promocao = _promocao(pontuacao=Decimal("5"), valor_condicionado=False)
    historico = HistoricoFamilia(
        media_ponderada=Decimal("2"), maior_valor_historico=Decimal("1"),
        total_campanhas_janela=6, confianca_historica="MEDIA",
    )
    assert pilar_exclusividade(promocao, historico) == 100.0


def test_propria_oferta_condicionada_usa_o_piso_contra_o_recorde():
    promocao = _promocao(
        pontuacao=Decimal("7"), valor_condicionado=True, valor_condicionado_piso=Decimal("1"),
    )
    historico = HistoricoFamilia(
        media_ponderada=Decimal("3"), maior_valor_historico=Decimal("5"),
        total_campanhas_janela=3, confianca_historica="MEDIA",
    )
    # o piso (1) é usado, não o 7 anunciado -> bem abaixo do recorde de 5
    nota = pilar_exclusividade(promocao, historico)
    assert nota < 30
