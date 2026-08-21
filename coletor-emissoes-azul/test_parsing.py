"""Testes do parser da resposta do azulpelomundo (`/api/availability`),
busca só-ida.

Duas respostas reais e completas, recortadas só na quantidade de voos (ver
fixture_azul_pelo_mundo.py): GRU->LIS (TAP Portugal, voos diretos) e
GRU->HND (Japan Airlines, com conexão) — capturadas ao vivo em 21/08/2026
depois da mudança pra busca só-ida.
"""
from parsing import extrair_mais_barata_azul_pelo_mundo
from fixture_azul_pelo_mundo import RESPOSTA_REAL_GRU_LIS, RESPOSTA_REAL_GRU_HND


def test_acha_o_voo_mais_barato():
    resultado = extrair_mais_barata_azul_pelo_mundo(RESPOSTA_REAL_GRU_LIS)
    # 410.000 (voo 84, 00:45) é mais barato que 494.000 (voo 88, 20:45).
    assert resultado["pontos"] == 410000


def test_traz_a_companhia_operadora():
    resultado = extrair_mais_barata_azul_pelo_mundo(RESPOSTA_REAL_GRU_LIS)
    assert resultado["companhia_operadora"] == "TP"


def test_traz_a_taxa_em_reais():
    resultado = extrair_mais_barata_azul_pelo_mundo(RESPOSTA_REAL_GRU_LIS)
    assert resultado["taxa_reais"] == 68.61


def test_voo_direto_tem_zero_paradas():
    resultado = extrair_mais_barata_azul_pelo_mundo(RESPOSTA_REAL_GRU_LIS)
    assert resultado["paradas"] == 0


def test_voo_com_conexao_tem_paradas_maior_que_zero():
    """GRU->HND (Japan Airlines) só tem opções com conexão — connection=1
    é o número de paradas de verdade, não um booleano.
    """
    resultado = extrair_mais_barata_azul_pelo_mundo(RESPOSTA_REAL_GRU_HND)
    assert resultado["paradas"] == 1


def test_sem_voos_devolve_none():
    vazio = {"data": {"departureFlights": {"flights": []}}}
    assert extrair_mais_barata_azul_pelo_mundo(vazio) is None
