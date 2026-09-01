"""Testes do pilar Amplitude, que mede o alcance da oferta no catálogo.

Uma oferta condicionada vale para uma fatia da loja, não para a compra inteira:
a Renner anuncia 10 pontos por real que só valem na categoria Básicos, enquanto
o resto do catálogo rende 2. Isso é exatamente uma redução de alcance, e é neste
pilar que deve doer — não na Confiabilidade, que mede se o dado está completo,
nem na Facilidade, que mede barreiras para o cliente aproveitar.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from application.motor.pilares import pilar_amplitude


def _promocao(**ajustes):
    padrao = dict(
        marketplace_status=None,
        valor_condicionado=False,
        pontuacao=Decimal("10"),
    )
    padrao.update(ajustes)
    return SimpleNamespace(**padrao)


def _condicionada(pontuacao, piso):
    return _promocao(valor_condicionado=True, pontuacao=pontuacao, valor_condicionado_piso=piso)


def test_oferta_condicionada_perde_alcance():
    ampla = pilar_amplitude(_promocao(valor_condicionado=False), quantidade_categorias=0)
    restrita = pilar_amplitude(_promocao(valor_condicionado=True), quantidade_categorias=0)
    assert restrita < ampla


def test_condicao_e_marketplace_somam():
    """São restrições independentes: valer só para uma categoria e não valer no
    marketplace estreitam o alcance por motivos diferentes.
    """
    so_condicionada = pilar_amplitude(
        _promocao(valor_condicionado=True, marketplace_status="PERMITIDO"), 0
    )
    ambas = pilar_amplitude(
        _promocao(valor_condicionado=True, marketplace_status="PROIBIDO"), 0
    )
    assert ambas < so_condicionada


def test_oferta_sem_restricao_alguma_pontua_mais():
    assert pilar_amplitude(
        _promocao(valor_condicionado=False, marketplace_status="PERMITIDO"), 0
    ) > 80


def test_nota_permanece_na_escala():
    """Nenhuma combinação de penalidades pode estourar os limites de 0 a 100."""
    pior = pilar_amplitude(
        _promocao(valor_condicionado=True, marketplace_status="PROIBIDO"), 5
    )
    assert 0 <= pior <= 100


def test_marketplace_parcial_penaliza_menos_no_varejo():
    """Decisão do usuário (01/09), a partir de um caso real (Magalu/Esfera, 7
    pontos, reduzido pra 1 só em loja parceira): restrição de canal de venda
    pesa bem menos que restrição de tipo de produto pra um parceiro de
    varejo com catálogo próprio já amplo — a loja própria cobre a maior
    parte do que se compra ali, então não valer no marketplace quase não
    reduz o alcance de verdade.
    """
    fora_do_varejo = pilar_amplitude(
        _promocao(marketplace_status="PARCIAL"), 0, segmento_varejo=False
    )
    no_varejo = pilar_amplitude(
        _promocao(marketplace_status="PARCIAL"), 0, segmento_varejo=True
    )
    assert no_varejo > fora_do_varejo


def test_segmento_varejo_nao_abranda_proibido():
    """PROIBIDO é bloqueio de verdade (nada rende no marketplace), não uma
    redução de taxa como o PARCIAL — continua penalizado igual em qualquer
    segmento.
    """
    fora_do_varejo = pilar_amplitude(
        _promocao(marketplace_status="PROIBIDO"), 0, segmento_varejo=False
    )
    no_varejo = pilar_amplitude(
        _promocao(marketplace_status="PROIBIDO"), 0, segmento_varejo=True
    )
    assert fora_do_varejo == no_varejo


# --- Penalidade de condição escala pelo tamanho do degrau -----------------
#
# Decisão do usuário (01/09), a partir de um caso real (Magalu/Esfera, 7
# pontos caindo pra 6 pra quem não é Clube — só 14% de queda) comparado ao
# exemplo original da Renner (10 caindo pra 2 — 80% de queda): as duas
# recebiam a mesma penalidade fixa de -25, mas a restrição real é bem
# diferente. "Tem que penalizar muito mais" a queda grande que a pequena.


def test_queda_grande_penaliza_quase_o_maximo():
    """Renner: 10 -> 2, 80% de queda. Perto do teto de -25."""
    nota = pilar_amplitude(_condicionada(Decimal("10"), Decimal("2")), 0)
    # base 50, penalidade = -25 * 0.8 = -20, +15 de quantidade_categorias=0
    assert nota == 45.0


def test_queda_pequena_penaliza_pouco():
    """Magalu/Esfera: 7 -> 6, ~14% de queda. Penalidade bem menor."""
    nota = pilar_amplitude(_condicionada(Decimal("7"), Decimal("6")), 0)
    # base 50, penalidade = -25 * (1/7) ≈ -3.57, +15 de quantidade_categorias=0
    assert nota == pytest.approx(61.43, abs=0.01)


def test_queda_maior_penaliza_mais_que_queda_menor():
    """A ordem importa, não só os valores absolutos calculados acima."""
    queda_grande = pilar_amplitude(_condicionada(Decimal("10"), Decimal("2")), 0)
    queda_pequena = pilar_amplitude(_condicionada(Decimal("7"), Decimal("6")), 0)
    assert queda_grande < queda_pequena


def test_sem_piso_conhecido_mantem_penalidade_plena():
    """"Até X" sem segunda pontuação no regulamento: a queda existe mas o
    tamanho dela não é conhecido — não inventamos um piso, mantém a
    penalidade cheia (o mesmo comportamento de antes desta mudança).
    """
    nota = pilar_amplitude(_condicionada(Decimal("8"), None), 0)
    # base 50, penalidade plena de -25, +15 de quantidade_categorias=0
    assert nota == 40.0
