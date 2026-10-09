"""Planos de viagem acompanhados na aba Emissões.

Um plano é uma viagem concreta que o usuário está avaliando: ida num
intervalo de datas, volta um número fixo de dias depois. A aba Emissões
mostra, pra cada data de ida do plano, o menor preço em milhas da ida e da
volta correspondente — a mesma análise que antes era feita à mão a partir
da saída de `buscar_latam_intervalo.py` (pedido do usuário, 09/10: "aquele
plano para Guarulhos, Santiago do Chile" disponível no painel).

Fica em código, e não numa tabela, porque hoje existe um plano só e quem o
define é o usuário em conversa — uma tela de cadastro (e a migration que
ela exige) não se paga ainda. Trocar o plano é editar esta lista.

As ofertas em si são `OfertaEmissao` comuns, gravadas pela busca por
intervalo com `--gravar`; aqui só se escolhe quais datas mostrar e como
pareá-las.
"""
from datetime import date, timedelta

PLANOS = [
    {
        "nome": "São Paulo ⇄ Santiago, julho de 2027",
        "programa_nome": "LATAM",
        "origem": "GRU",
        "destino": "SCL",
        "ida_inicio": date(2027, 7, 16),
        "ida_fim": date(2027, 7, 25),
        "dias": 6,
    },
]


def datas_do_plano(plano: dict) -> list[tuple[date, date]]:
    """Pares (ida, volta) do plano — a volta é sempre `dias` depois da ida."""
    total = (plano["ida_fim"] - plano["ida_inicio"]).days
    return [
        (plano["ida_inicio"] + timedelta(days=i), plano["ida_inicio"] + timedelta(days=i + plano["dias"]))
        for i in range(total + 1)
    ]
