"""Testes do parsing dos cards da Livelo.

Os textos usados aqui foram capturados do site real em 13/08/2026 — não são
inventados. Ver os casos que motivaram cada teste no diagnóstico daquela data.

Rodar: venv/bin/python3 -m pytest test_coletor_livelo.py -v
"""
from __future__ import annotations

from decimal import Decimal

from coletor_livelo_nativo import (
    _extrair_codigo_da_url,
    _extrair_cupom,
    _extrair_nome_da_url,
    _extrair_regulamento,
    _extrair_validade,
    _parsear_card,
)

# Textos reais das páginas de detalhe, capturados em 14/08/2026.
REG_RENNER = (
    "Campanha válida de 14/08/2026 a 16/08/2026. Ganhe 10 pontos por real na "
    "categoria Básicos e 2 pontos demais produtos. Consulte o regulamento."
)
REG_OLYMPIKUS = (
    "Campanha válida de 13 a 14/08/2026. Ganhe 15 pontos por real gasto exclusivo "
    "para primeira compra e 5 pontos por real nas demais compras. Utilize o cupom "
    "LIVELO. Consulte o regulamento."
)


def test_pontuacao_fixa_nao_e_teto():
    card = _parsear_card("2 pontos por R$ 1\nIr para regras do parceiro", "/juntar-pontos/parceiros/beach-park/BPK")
    assert card.pontuacao == Decimal("2")
    assert card.pontuacao_e_teto is False


def test_ate_marca_pontuacao_como_teto():
    """'Até 6 pontos' é um teto promocional, não um valor garantido. O valor
    coletado continua sendo 6 — o que muda é saber que é um limite.
    """
    card = _parsear_card(
        "Promoção\nAté 6 pontos por R$ 1\nEram 1 ponto\nIr para regras do parceiro",
        "/juntar-pontos/parceiros/carrefour/CRM",
    )
    assert card.pontuacao == Decimal("6")
    assert card.pontuacao_e_teto is True


def test_card_com_clube_usa_a_pontuacao_de_qualquer_cliente():
    """O card traz duas pontuações: a de todos primeiro, a do Clube depois.
    A coletada tem que ser a primeira — a que vale para qualquer pessoa.
    """
    card = _parsear_card(
        "Promoção\n5 pontos por R$ 1\nEram 1 ponto\nClube\n15 pontos por R$ 1\nEram 1 ponto\nIr para regras do parceiro",
        "/juntar-pontos/parceiros/olympikus/OVC",
    )
    assert card.pontuacao == Decimal("5")
    assert card.requer_clube is False


def test_pontuacao_do_clube_capturada_quando_existe():
    """Card real da Beleza na Web em 13/08/2026: 8 pontos para qualquer
    cliente e 10 para assinantes do Clube Livelo. As duas são informação útil.
    """
    card = _parsear_card(
        "Promoção\nAté 8 pontos por R$ 1\nEram 2 pontos\nClube\nAté 10 pontos por R$ 1\nEram 2 pontos\nIr para regras do parceiro",
        "/juntar-pontos/parceiros/beleza-na-web/BLZ",
    )
    assert card.pontuacao == Decimal("8")
    assert card.pontuacao_clube == Decimal("10")


def test_sem_clube_a_pontuacao_de_clube_fica_vazia():
    card = _parsear_card("2 pontos por R$ 1\nIr para regras do parceiro", "/juntar-pontos/parceiros/beach-park/BPK")
    assert card.pontuacao_clube is None


def test_clube_nao_confunde_a_pontuacao_principal():
    """O valor do Clube é sempre maior; se fosse ele a virar `pontuacao`, a
    oferta pareceria melhor do que é para quem não assina.
    """
    card = _parsear_card(
        "Promoção\n5 pontos por R$ 1\nEram 1 ponto\nClube\n15 pontos por R$ 1\nEram 1 ponto\nIr para regras do parceiro",
        "/juntar-pontos/parceiros/olympikus/OVC",
    )
    assert card.pontuacao == Decimal("5")
    assert card.pontuacao_clube == Decimal("15")


def test_codigo_da_variante_extraido_da_url():
    """Beach Park tem duas ofertas sob o mesmo slug, distintas só pelo código:
    BPK são os Hotéis (2 pts) e BHP os Ingressos (1 pt).
    """
    assert _extrair_codigo_da_url("/juntar-pontos/parceiros/beach-park/BPK") == "BPK"
    assert _extrair_codigo_da_url("/juntar-pontos/parceiros/beach-park/BHP") == "BHP"


def test_nome_do_parceiro_continua_vindo_do_slug():
    assert _extrair_nome_da_url("/juntar-pontos/parceiros/casas-bahia/CSB") == "Casas Bahia"
    assert _extrair_nome_da_url("/juntar-pontos/parceiros/liga-vitoria-auto/LSA") == "Liga Vitoria Auto"


def test_codigo_com_espaco_na_url_e_normalizado():
    """A Livelo serve '/parceiros/klubi-auto/AUT ' com espaço no fim. Sem
    limpar, 'AUT ' viraria um parceiro diferente de 'AUT'.
    """
    assert _extrair_codigo_da_url("/juntar-pontos/parceiros/klubi-auto/AUT ") == "AUT"


def test_url_sem_codigo_nao_quebra():
    """Um card fora do padrão não pode derrubar a coleta inteira."""
    assert _extrair_codigo_da_url("/juntar-pontos/parceiros/algum-parceiro") is None


def test_codigo_vai_para_a_promocao_coletada():
    card = _parsear_card("1 ponto por R$ 1\nIr para regras do parceiro", "/juntar-pontos/parceiros/beach-park/BHP")
    assert card.codigo_externo == "BHP"
    assert card.parceiro_nome_bruto == "Beach Park"


def test_regulamento_extraido_do_texto_da_pagina():
    """A página tem ~90 linhas; a que interessa é a que começa com
    'Campanha válida'. É ela que diz a restrição real da oferta.
    """
    pagina = "Renner\nJuntar pontos\n" + REG_RENNER + "\nCompartilhar\nRodapé"
    assert _extrair_regulamento(pagina) == REG_RENNER


def test_pagina_sem_campanha_nao_inventa_regulamento():
    assert _extrair_regulamento("Renner\nJuntar pontos\n2 pontos por real\nRodapé") is None


def test_validade_com_data_completa_nos_dois_lados():
    inicio, fim = _extrair_validade(REG_RENNER)
    assert (inicio.day, inicio.month, inicio.year) == (14, 8, 2026)
    assert (fim.day, fim.month, fim.year) == (16, 8, 2026)


def test_validade_com_dia_solto_no_inicio():
    """'de 13 a 14/08/2026' — o início herda mês e ano do fim."""
    inicio, fim = _extrair_validade(REG_OLYMPIKUS)
    assert (inicio.day, inicio.month, inicio.year) == (13, 8, 2026)
    assert (fim.day, fim.month, fim.year) == (14, 8, 2026)


def test_texto_sem_validade_nao_inventa_datas():
    assert _extrair_validade("Ganhe 5 pontos por real. Consulte o regulamento.") == (None, None)


def test_cupom_extraido_quando_exigido():
    """Sem o cupom o cliente não pontua — é a informação mais crítica da
    oferta e hoje é invisível no painel.
    """
    assert _extrair_cupom(REG_OLYMPIKUS) == "LIVELO"


def test_sem_cupom_devolve_nada():
    assert _extrair_cupom(REG_RENNER) is None


def test_validade_de_um_dia_so():
    """Formato real da Amobeleza em 14/08/2026: 'Campanha válida em
    14/08/2026' — campanha de um dia, sem intervalo. Início e fim coincidem.
    """
    inicio, fim = _extrair_validade("Campanha válida em 14/08/2026. Ganhe 10 pontos por real.")
    assert (inicio.day, inicio.month, inicio.year) == (14, 8, 2026)
    assert inicio == fim
