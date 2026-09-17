"""Testes do parser DOM da Smiles (`extrair_ofertas_smiles_dom`).

Cartões `.select-flight-list-accordion-item` reais, capturados ao vivo numa
busca GIG->REC em 17/09/2026 (ver fixture_smiles.py) — um voo direto e um
com parada, ambos da GOL.

Devolve duas ofertas (decisão do usuário, 17/09): a mais barata direto e a
mais barata com parada — não mais `taxa_reais` (só milhas), e com
`duracao_texto` novo.
"""
from fixture_smiles import CARTAO_DIRETO, CARTAO_UMA_PARADA
from parsing_smiles import extrair_ofertas_smiles_dom


def test_separa_a_mais_barata_direto_da_mais_barata_com_parada():
    resultado = extrair_ofertas_smiles_dom([CARTAO_DIRETO, CARTAO_UMA_PARADA])
    assert resultado["direto"]["pontos"] == 58700
    assert resultado["com_parada"]["pontos"] == 58700


def test_traz_a_companhia():
    resultado = extrair_ofertas_smiles_dom([CARTAO_DIRETO])
    assert resultado["direto"]["companhia_operadora"] == "GOL Linhas Aéreas"


def test_traz_a_duracao_como_texto():
    resultado = extrair_ofertas_smiles_dom([CARTAO_DIRETO])
    assert resultado["direto"]["duracao_texto"] == "02h50min"


def test_voo_direto_tem_zero_paradas():
    resultado = extrair_ofertas_smiles_dom([CARTAO_DIRETO])
    assert resultado["direto"]["paradas"] == 0
    assert resultado["com_parada"] is None


def test_voo_com_parada_conta_o_numero_certo():
    resultado = extrair_ofertas_smiles_dom([CARTAO_UMA_PARADA])
    assert resultado["com_parada"]["paradas"] == 1
    assert resultado["direto"] is None


def test_sem_cartoes_devolve_as_duas_categorias_vazias():
    resultado = extrair_ofertas_smiles_dom([])
    assert resultado == {"direto": None, "com_parada": None}
