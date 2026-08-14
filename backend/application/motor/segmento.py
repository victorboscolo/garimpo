"""Escolha do segmento usado como base de comparação do motor.

Um parceiro tem de 1 a 8 categorias na Livelo (114 têm uma só, 73 têm três ou
mais). Quando ele não tem histórico próprio — o caso de 223 dos 249 parceiros —,
o motor compara a oferta com as do seu segmento. Mas precisa escolher qual, e a
escolha não pode ser arbitrária nem instável.
"""
from __future__ import annotations


def escolher_segmento(
    candidatos: list[tuple[str, int]], minimo: int
) -> str | None:
    """Segmento mais específico que ainda sustenta comparação.

    `candidatos` são pares (identificador, quantidade de ofertas aprovadas).
    Menos ofertas indica segmento mais específico, e comparar dentro dele diz
    mais: entre "modaebeleza" (93 ofertas) e "calcados" (38), calçados é a
    comparação mais informativa.

    A especificidade só vale até onde há amostra. Um segmento com 2 ofertas não
    sustenta conclusão nenhuma, então abaixo de `minimo` ele é descartado e a
    escolha sobe para o próximo. Sem nenhum candidato viável devolve None, e o
    chamador cai no nível seguinte da cascata (o mercado) em vez de comparar
    com uma base que não se sustenta.

    O desempate é pelo identificador, em ordem alfabética, para que a escolha
    seja estável: dois segmentos de mesmo tamanho não podem alternar entre
    execuções, senão a nota da oferta mudaria sozinha de um dia para o outro.
    """
    viaveis = [(quantidade, slug) for slug, quantidade in candidatos if quantidade >= minimo]
    if not viaveis:
        return None
    return min(viaveis)[1]
