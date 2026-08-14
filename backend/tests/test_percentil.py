"""Testes da pontuação por posição na distribuição.

A curva anterior era `pontuação ÷ referência × 50`, com teto em 100 — ou seja, o
dobro da referência já era nota máxima. Como as referências ficam entre 2 e 5,5
pontos, o teto caía entre 4 e 11, e o mercado tem ofertas de 20, 40 e 100: 38
classificações saturavam o pilar Histórico e 33 o de Atratividade, justamente no
topo, que é onde as decisões de publicação acontecem.

Por percentil a régua passa a ser a distribuição real, e a nota diz quanto do
mercado a oferta supera. É autocalibrante: se todas as ofertas dobrarem, ninguém
muda de posição — e portanto ninguém muda de categoria.
"""
from decimal import Decimal

from application.motor.percentil import percentil


def _d(*valores):
    return [Decimal(str(v)) for v in valores]


def test_valor_na_mediana_fica_no_meio():
    assert 45 <= percentil(Decimal("3"), _d(1, 2, 3, 4, 5)) <= 55


def test_o_melhor_da_distribuicao_fica_no_topo():
    assert percentil(Decimal("100"), _d(1, 2, 3, 100)) > 85


def test_o_pior_da_distribuicao_fica_embaixo():
    assert percentil(Decimal("1"), _d(1, 2, 3, 100)) < 20


def test_nao_satura_como_a_curva_anterior():
    """O ponto do exercício: 12 e 40 pontos deixam de empatar.

    Na curva antiga, ambos passavam do dobro da média e viravam 100.
    """
    distribuicao = _d(1, 2, 2, 3, 5, 7, 12, 40)
    assert percentil(Decimal("40"), distribuicao) > percentil(Decimal("12"), distribuicao)


def test_valor_acima_de_toda_a_distribuicao():
    assert percentil(Decimal("500"), _d(1, 2, 3)) == 100.0


def test_distribuicao_vazia_e_neutra():
    """Sem base de comparação não se afirma nada: nem premia nem penaliza."""
    assert percentil(Decimal("10"), []) == 50.0


def test_empates_dividem_a_posicao():
    """Metade do mercado em 2 pontos: uma oferta de 2 não pode valer 0 nem 100,
    porque ela empata com essa metade em vez de superá-la.
    """
    resultado = percentil(Decimal("2"), _d(2, 2, 2, 2))
    assert 40 <= resultado <= 60


def test_escala_nao_muda_o_resultado():
    """Autocalibragem: dobrar o mercado inteiro não muda posição nenhuma."""
    original = percentil(Decimal("5"), _d(1, 2, 3, 5, 10))
    dobrado = percentil(Decimal("10"), _d(2, 4, 6, 10, 20))
    assert abs(original - dobrado) < 0.01
