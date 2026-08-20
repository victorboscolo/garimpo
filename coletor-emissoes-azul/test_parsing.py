"""Testes do parser da resposta do azulpelomundo (`/api/availability`).

Usa um recorte fiel de uma resposta real (fixture_azul_pelo_mundo.py, capturada
20/08/2026), não JSON inventado — a estrutura tem uma armadilha: o preço da
combinação ida+volta mora dentro de
`departureFlights.flights[].recommendations[].returnFlights[].categories[].points.value`,
não no `points` do nível do voo de ida (que é só o trecho de ida sozinho,
sempre maior que o preço combinado real).
"""
from parsing import extrair_mais_barata_azul_pelo_mundo
from fixture_azul_pelo_mundo import RESPOSTA_REAL_TRIMMED


def test_acha_a_combinacao_mais_barata():
    resultado = extrair_mais_barata_azul_pelo_mundo(RESPOSTA_REAL_TRIMMED)

    # 142.000 (Avianca, conexão) é mais barato que 240.000 (British, direto).
    assert resultado["pontos"] == 142000


def test_nao_confunde_o_preco_so_da_ida_com_o_combinado():
    """O voo da British tem points.value=256500 no nível do voo de ida, mas
    o preço real da combinação ida+volta é 240000 — bem menor. O parser não
    pode pegar o valor errado.
    """
    resultado = extrair_mais_barata_azul_pelo_mundo(RESPOSTA_REAL_TRIMMED)
    valores_no_nivel_do_voo_de_ida = {256500, 192500}
    assert resultado["pontos"] not in valores_no_nivel_do_voo_de_ida


def test_traz_a_companhia_operadora():
    resultado = extrair_mais_barata_azul_pelo_mundo(RESPOSTA_REAL_TRIMMED)
    assert resultado["companhia_operadora"] == "AV"


def test_traz_a_taxa_em_reais():
    resultado = extrair_mais_barata_azul_pelo_mundo(RESPOSTA_REAL_TRIMMED)
    assert resultado["taxa_reais"] == 1144.96


def test_voo_direto_e_marcado_corretamente():
    """A oferta mais barata (Avianca) tem conexão — connection=1."""
    resultado = extrair_mais_barata_azul_pelo_mundo(RESPOSTA_REAL_TRIMMED)
    assert resultado["voo_direto"] is False


def test_sem_voos_devolve_none():
    vazio = {"data": {"departureFlights": {"flights": []}}}
    assert extrair_mais_barata_azul_pelo_mundo(vazio) is None
