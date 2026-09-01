"""Testes do pilar Amplitude, que mede o alcance da oferta no catálogo.

Uma oferta condicionada vale para uma fatia da loja, não para a compra inteira:
a Renner anuncia 10 pontos por real que só valem na categoria Básicos, enquanto
o resto do catálogo rende 2. Isso é exatamente uma redução de alcance, e é neste
pilar que deve doer — não na Confiabilidade, que mede se o dado está completo,
nem na Facilidade, que mede barreiras para o cliente aproveitar.
"""
from decimal import Decimal
from types import SimpleNamespace

from application.motor.pilares import pilar_amplitude


def _promocao(**ajustes):
    padrao = dict(
        marketplace_status=None,
        valor_condicionado=False,
        pontuacao=Decimal("10"),
    )
    padrao.update(ajustes)
    return SimpleNamespace(**padrao)


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
