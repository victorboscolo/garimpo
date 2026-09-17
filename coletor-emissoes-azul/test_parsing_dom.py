"""Testes do parser DOM do azulpelomundo (`extrair_ofertas_azul_pelo_mundo_dom`).

Linhas `.componentFlight` reais, capturadas ao vivo numa busca GIG->LHR em
17/09/2026 (ver fixture_azul_pelo_mundo_dom.py) — depois do achado de que a
API (`/api/availability`) exige um token de reCAPTCHA que só o JS da
própria página gera, o coletor passou a ler o HTML já renderizado em vez de
refazer a chamada de rede.

Devolve duas ofertas (decisão do usuário, 17/09): a mais barata direto e a
mais barata com parada — não mais `taxa_reais` (só milhas), e com
`duracao_texto` novo.
"""
from fixture_azul_pelo_mundo_dom import (
    LINHA_DIRETO_BA,
    LINHA_UMA_PARADA_AF,
    LINHA_UMA_PARADA_AF_ULTIMOS_LUGARES,
)
from parsing import extrair_ofertas_azul_pelo_mundo_dom


def test_separa_a_mais_barata_direto_da_mais_barata_com_parada():
    resultado = extrair_ofertas_azul_pelo_mundo_dom([LINHA_DIRETO_BA, LINHA_UMA_PARADA_AF])
    assert resultado["direto"]["pontos"] == 376000
    assert resultado["com_parada"]["pontos"] == 171000


def test_traz_a_companhia_operadora_pelo_icone():
    resultado = extrair_ofertas_azul_pelo_mundo_dom([LINHA_UMA_PARADA_AF])
    assert resultado["com_parada"]["companhia_operadora"] == "AF"


def test_traz_a_duracao_como_texto():
    resultado = extrair_ofertas_azul_pelo_mundo_dom([LINHA_DIRETO_BA])
    assert resultado["direto"]["duracao_texto"] == "11h25"


def test_voo_direto_tem_zero_paradas():
    resultado = extrair_ofertas_azul_pelo_mundo_dom([LINHA_DIRETO_BA])
    assert resultado["direto"]["paradas"] == 0
    assert resultado["com_parada"] is None


def test_voo_com_parada_conta_o_numero_certo():
    resultado = extrair_ofertas_azul_pelo_mundo_dom([LINHA_UMA_PARADA_AF])
    assert resultado["com_parada"]["paradas"] == 1
    assert resultado["direto"] is None


def test_linha_com_aviso_de_ultimos_lugares_nao_quebra_o_parser():
    """"Últimos lugares nesse preço" é um selo extra no card — não deve
    interferir na extração de pontos/companhia/paradas.
    """
    resultado = extrair_ofertas_azul_pelo_mundo_dom([LINHA_UMA_PARADA_AF_ULTIMOS_LUGARES])
    assert resultado["com_parada"]["pontos"] == 171000
    assert resultado["com_parada"]["companhia_operadora"] == "AF"


def test_sem_linhas_devolve_as_duas_categorias_vazias():
    resultado = extrair_ofertas_azul_pelo_mundo_dom([])
    assert resultado == {"direto": None, "com_parada": None}
