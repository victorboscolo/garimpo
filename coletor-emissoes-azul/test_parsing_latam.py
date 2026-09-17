"""Testes do parser DOM da LATAM (`extrair_ofertas_latam_dom`).

Blocos `card-expander-N` reais, capturados ao vivo numa busca GRU->MIA em
17/09/2026 (ver fixture_latam.py), com sessão autenticada manualmente pelo
usuário — a LATAM nunca teve bloqueio Akamai, a barreira sempre foi login.
"""
from fixture_latam import BLOCO_DIRETO, BLOCO_COM_PARADA
from parsing_latam import extrair_ofertas_latam_dom


def test_separa_a_mais_barata_direto_da_mais_barata_com_parada():
    resultado = extrair_ofertas_latam_dom(BLOCO_DIRETO + BLOCO_COM_PARADA)
    assert resultado["direto"]["pontos"] == 116115
    assert resultado["com_parada"]["pontos"] == 37572


def test_traz_a_companhia_por_extenso():
    resultado = extrair_ofertas_latam_dom(BLOCO_DIRETO)
    assert resultado["direto"]["companhia_operadora"] == "LATAM Airlines Brasil"


def test_traz_a_duracao_como_texto():
    resultado = extrair_ofertas_latam_dom(BLOCO_DIRETO)
    assert resultado["direto"]["duracao_texto"] == "8 h 30 min."


def test_voo_direto_tem_zero_paradas():
    resultado = extrair_ofertas_latam_dom(BLOCO_DIRETO)
    assert resultado["direto"]["paradas"] == 0
    assert resultado["com_parada"] is None


def test_voo_com_parada_conta_o_numero_certo():
    resultado = extrair_ofertas_latam_dom(BLOCO_COM_PARADA)
    assert resultado["com_parada"]["paradas"] == 1
    assert resultado["direto"] is None


def test_sem_blocos_devolve_as_duas_categorias_vazias():
    resultado = extrair_ofertas_latam_dom("")
    assert resultado == {"direto": None, "com_parada": None}
