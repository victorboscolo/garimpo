"""Posição de uma pontuação dentro da distribuição de referência.

Substitui a curva `pontuação ÷ referência × 50`, que tinha teto em 100 e por
isso tratava como iguais todas as ofertas acima do dobro da referência. Como as
referências ficam entre 2 e 5,5 pontos, isso significava perder a distinção
acima de 4 a 11 pontos — enquanto o mercado oferece 20, 40 e 100.

A leitura da nota muda junto, para melhor: deixa de ser "quantas vezes a média"
e passa a ser "quanto do mercado esta oferta supera". Uma consequência
importante é ser autocalibrante — se todas as ofertas dobrarem, ninguém muda de
posição e portanto ninguém muda de categoria, o que não acontecia antes.
"""
from decimal import Decimal


def percentil(valor: Decimal, distribuicao: list[Decimal]) -> float:
    """0 a 100: quanto da distribuição o valor supera.

    Empates dividem a posição (método do rank médio): com metade do mercado em
    2 pontos, uma oferta de 2 fica no meio, porque empata com essa metade em vez
    de superá-la. Sem esse cuidado, o valor mais comum do mercado — que é 2 —
    receberia 0 ou 100 conforme o critério de desempate.

    Distribuição vazia devolve o neutro 50: sem base não se afirma nada, nem
    para premiar nem para penalizar.
    """
    if not distribuicao:
        return 50.0

    total = len(distribuicao)
    menores = sum(1 for v in distribuicao if v < valor)
    iguais = sum(1 for v in distribuicao if v == valor)

    return round((menores + iguais / 2) / total * 100, 2)


def valor_comparavel(promocao) -> Decimal:
    """O valor real, sem pegadinha, pra comparar esta oferta com outras.

    Achado do usuário (09/09), caso real: o Carrefour anunciou "7 pontos"
    (20/08), mas só valia em produtos da marca própria — 1 ponto pra tudo
    mais. Comparar um 5 pontos incondicional (09/09) contra esse "7" não é
    justo: o 7 nunca foi o valor real pra maior parte das compras, é o
    mesmo problema de fundo que já corrigimos no pilar Amplitude (a
    penalidade de `valor_condicionado` escalando pela queda relativa), só
    que aqui do lado da **comparação**, não da nota da própria oferta.

    Quando a oferta é condicionada e o piso é conhecido, o piso — o que
    qualquer comprador realmente recebe, garantido — é o valor que entra
    em qualquer distribuição de comparação (histórico, segmento, mercado)
    e também o valor usado pra posicionar esta mesma oferta dentro delas.
    Sem piso conhecido (caso do "Até X" sem segunda pontuação no texto),
    não há valor melhor pra usar — mantém o anunciado, mesmo sabendo que
    pode estar inflado.

    Fica em `percentil.py`, não em `pilares.py`, porque `historico.py`
    também precisa dele e já é importado por `pilares.py` — colocar aqui
    evita import circular.
    """
    if getattr(promocao, "valor_condicionado", False):
        piso = getattr(promocao, "valor_condicionado_piso", None)
        if piso is not None:
            return piso
    return promocao.pontuacao
