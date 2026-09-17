"""Testes do parser DOM da Smiles (`extrair_mais_barata_smiles_dom`).

Cartões `.select-flight-list-accordion-item` reais, capturados ao vivo numa
busca GIG->REC em 17/09/2026 (ver fixture_smiles.py) — um voo direto e um
com parada, ambos da GOL.
"""
from fixture_smiles import CARTAO_DIRETO, CARTAO_UMA_PARADA
from parsing_smiles import extrair_mais_barata_smiles_dom


def test_acha_a_oferta_entre_varios_cartoes():
    resultado = extrair_mais_barata_smiles_dom([CARTAO_DIRETO, CARTAO_UMA_PARADA])
    assert resultado["pontos"] == 58700


def test_traz_a_companhia():
    resultado = extrair_mais_barata_smiles_dom([CARTAO_DIRETO])
    assert resultado["companhia_operadora"] == "GOL Linhas Aéreas"


def test_traz_a_taxa_em_reais_da_opcao_combinada():
    resultado = extrair_mais_barata_smiles_dom([CARTAO_DIRETO])
    assert resultado["taxa_reais"] == 1185.81


def test_voo_direto_tem_zero_paradas():
    resultado = extrair_mais_barata_smiles_dom([CARTAO_DIRETO])
    assert resultado["paradas"] == 0


def test_voo_com_parada_conta_o_numero_certo():
    resultado = extrair_mais_barata_smiles_dom([CARTAO_UMA_PARADA])
    assert resultado["paradas"] == 1


def test_sem_cartoes_devolve_none():
    assert extrair_mais_barata_smiles_dom([]) is None
