"""Testes da escolha do segmento usado como base de comparação.

Um parceiro tem de 1 a 8 categorias na Livelo. Quando ele não tem histórico
próprio, o motor compara com o segmento — mas precisa escolher qual, e a
escolha não pode ser arbitrária.

O critério é a categoria mais específica que ainda tenha amostra suficiente:
entre "modaebeleza" (83 parceiros) e "calcados" (35), comparar com calçados diz
mais. Se a mais específica não tiver ofertas aprovadas bastantes, sobe para a
seguinte, até acabar as opções.
"""
from application.motor.segmento import escolher_segmento


def test_escolhe_a_mais_especifica_com_amostra():
    """Renner é modaebeleza e modaeacessorios; a segunda é mais específica."""
    candidatos = [("modaebeleza", 93), ("modaeacessorios", 68)]
    assert escolher_segmento(candidatos, minimo=5) == "modaeacessorios"


def test_pula_a_especifica_sem_amostra_suficiente():
    """Comparar com um segmento de 2 ofertas é pior que comparar com um de 90:
    a especificidade não compensa a falta de base.
    """
    candidatos = [("modaebeleza", 93), ("chipdecelular", 2)]
    assert escolher_segmento(candidatos, minimo=5) == "modaebeleza"


def test_sem_nenhum_segmento_com_amostra():
    """Devolve None para o motor cair no nível seguinte (mercado), em vez de
    comparar com uma base que não sustenta conclusão.
    """
    assert escolher_segmento([("chipdecelular", 2), ("giftcard", 1)], minimo=5) is None


def test_parceiro_sem_categoria():
    assert escolher_segmento([], minimo=5) is None


def test_empate_de_tamanho_e_resolvido_de_forma_estavel():
    """Dois segmentos com a mesma contagem não podem alternar entre execuções:
    a nota mudaria sozinha de um dia para o outro.
    """
    candidatos = [("bbb", 10), ("aaa", 10)]
    assert escolher_segmento(candidatos, minimo=5) == "aaa"
    assert escolher_segmento(list(reversed(candidatos)), minimo=5) == "aaa"
