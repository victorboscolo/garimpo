"""Testes do parser DOM do azulpelomundo (`extrair_mais_barata_azul_pelo_mundo_dom`).

Linhas `.componentFlight` reais, capturadas ao vivo numa busca GIG->LHR em
17/09/2026 (ver fixture_azul_pelo_mundo_dom.py) — depois do achado de que a
API (`/api/availability`) exige um token de reCAPTCHA que só o JS da
própria página gera, o coletor passou a ler o HTML já renderizado em vez de
refazer a chamada de rede.
"""
from fixture_azul_pelo_mundo_dom import (
    LINHA_DIRETO_BA,
    LINHA_UMA_PARADA_AF,
    LINHA_UMA_PARADA_AF_ULTIMOS_LUGARES,
)
from parsing import extrair_mais_barata_azul_pelo_mundo_dom


def test_acha_o_voo_mais_barato_entre_varias_linhas():
    # BA direto: 376.000. AF c/ 1 parada: 171.000 — a mais barata das duas.
    resultado = extrair_mais_barata_azul_pelo_mundo_dom([LINHA_DIRETO_BA, LINHA_UMA_PARADA_AF])
    assert resultado["pontos"] == 171000


def test_traz_a_companhia_operadora_pelo_icone():
    resultado = extrair_mais_barata_azul_pelo_mundo_dom([LINHA_UMA_PARADA_AF])
    assert resultado["companhia_operadora"] == "AF"


def test_traz_a_taxa_em_reais():
    resultado = extrair_mais_barata_azul_pelo_mundo_dom([LINHA_UMA_PARADA_AF])
    assert resultado["taxa_reais"] == 520.0


def test_voo_direto_tem_zero_paradas():
    resultado = extrair_mais_barata_azul_pelo_mundo_dom([LINHA_DIRETO_BA])
    assert resultado["paradas"] == 0


def test_voo_com_parada_conta_o_numero_certo():
    resultado = extrair_mais_barata_azul_pelo_mundo_dom([LINHA_UMA_PARADA_AF])
    assert resultado["paradas"] == 1


def test_linha_com_aviso_de_ultimos_lugares_nao_quebra_o_parser():
    """"Últimos lugares nesse preço" é um selo extra no card — não deve
    interferir na extração de pontos/companhia/paradas.
    """
    resultado = extrair_mais_barata_azul_pelo_mundo_dom([LINHA_UMA_PARADA_AF_ULTIMOS_LUGARES])
    assert resultado["pontos"] == 171000
    assert resultado["companhia_operadora"] == "AF"
    assert resultado["paradas"] == 1


def test_sem_linhas_devolve_none():
    assert extrair_mais_barata_azul_pelo_mundo_dom([]) is None
