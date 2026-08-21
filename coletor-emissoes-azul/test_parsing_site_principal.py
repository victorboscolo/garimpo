"""Testes do parser de cards do site principal da Azul.

O site principal não devolve JSON por uma chamada de rede simples de
interceptar (achado de 20/08: toda busca faz reload completo da página,
o payload nunca foi capturado). O caminho que funcionou (21/08): ler
direto do DOM renderizado — cada card de voo tem um `data-test-id` estável
pro preço em pontos e atributos `data-leg-*` com assentos restantes. Os
dois HTMLs de fixture são `outerHTML` real, capturados ao vivo, não
reconstruídos de memória.
"""
from parsing_site_principal import (
    extrair_assentos_restantes,
    extrair_paradas,
    extrair_preco_pontos,
    menor_preco_entre_os_cards,
)
from fixture_site_principal import CARD_DIRETO, CARD_DISPONIVEL, CARD_INDISPONIVEL


def test_extrai_o_preco_em_pontos_do_card_disponivel():
    assert extrair_preco_pontos(CARD_DISPONIVEL) == 334620


def test_card_indisponivel_nao_tem_preco():
    assert extrair_preco_pontos(CARD_INDISPONIVEL) is None


def test_nao_confunde_o_preco_riscado_com_o_preco_real():
    """O card tem "338000 pontos" (preço riscado, antes do desconto) E
    "334.620" (preço real, com desconto) — o parser tem que pegar o
    segundo, que é o que a Azul cobra de verdade.
    """
    preco = extrair_preco_pontos(CARD_DISPONIVEL)
    assert preco != 338000
    assert preco == 334620


def test_extrai_assentos_restantes():
    assert extrair_assentos_restantes(CARD_DISPONIVEL) == 17


def test_assentos_restantes_do_indisponivel():
    assert extrair_assentos_restantes(CARD_INDISPONIVEL) == 8


def test_menor_preco_ignora_indisponiveis():
    assert menor_preco_entre_os_cards([CARD_INDISPONIVEL, CARD_DISPONIVEL]) == 334620


def test_menor_preco_sem_nenhum_disponivel():
    assert menor_preco_entre_os_cards([CARD_INDISPONIVEL, CARD_INDISPONIVEL]) is None


def test_extrai_paradas_do_card_com_conexao():
    assert extrair_paradas(CARD_DISPONIVEL) == 1


def test_extrai_paradas_do_card_direto():
    """Voo direto não tem número na frente de "Direto" — vira 0, não None."""
    assert extrair_paradas(CARD_DIRETO) == 0
