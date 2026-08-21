"""Extrai dados de um card de voo (outerHTML) do site principal da Azul.

Achado técnico de 21/08/2026: o site não expõe o resultado por uma chamada
de rede simples de interceptar (achado de 20/08: reload completo a cada
busca impediu capturar o payload). O caminho que funciona é ler o DOM já
renderizado — cada `.flight-card` tem:

- `data-test-id="fare-price fare-price-with-points"`: o preço em pontos que
  a Azul cobra de verdade (**não** o `.initial`, que é o preço riscado
  antes do desconto — os dois aparecem no mesmo card).
- `data-leg-remaining-seats`: assentos restantes, sinal de escassez.
- Um card sem oferta mostra "Indisponível" e não tem o `data-test-id` do
  preço — não é erro, é uma rota sem disponibilidade nessa data.

Achado de 22/08/2026: a busca virou só-ida (decisão do usuário, 21/08), mas
o card em si não muda — os mesmos anchors continuam valendo, só que agora
o resultado tem uma seção só (não mais duas, ida e volta separadas). O
número de paradas mora no mesmo texto do número do voo, em dois formatos
reais confirmados: "1 conexão    •  Voo 4450" (com conexão) e "Voo 4043
Direto" (sem conexão, sem número na frente).
"""
from __future__ import annotations

import re

_PADRAO_PRECO = re.compile(
    r'data-test-id="fare-price fare-price-with-points"[^>]*>([\d.]+)<span class="points">pontos</span>'
)
_PADRAO_ASSENTOS = re.compile(r'data-leg-remaining-seats="(\d+)"')
_PADRAO_CONEXAO = re.compile(r'(\d+)\s*conex')
_PADRAO_DIRETO = re.compile(r'\bDireto\b')


def extrair_preco_pontos(card_html: str) -> int | None:
    """O preço real (com desconto) em pontos, ou None se o card não tem
    oferta disponível pra essa data.
    """
    achado = _PADRAO_PRECO.search(card_html)
    if achado is None:
        return None
    return int(achado.group(1).replace(".", ""))


def extrair_assentos_restantes(card_html: str) -> int | None:
    achado = _PADRAO_ASSENTOS.search(card_html)
    return int(achado.group(1)) if achado else None


def extrair_paradas(card_html: str) -> int | None:
    """Número de conexões do voo (0 = direto), ou None se o card não tem
    nem "conexão" nem "Direto" no texto (não deveria acontecer num card
    válido, mas não vale a pena assumir).
    """
    achado = _PADRAO_CONEXAO.search(card_html)
    if achado:
        return int(achado.group(1))
    if _PADRAO_DIRETO.search(card_html):
        return 0
    return None


def menor_preco_entre_os_cards(cards_html: list[str]) -> int | None:
    """O menor preço em pontos entre uma lista de cards de uma busca
    só-ida, ignorando os indisponíveis. None se nenhum card da lista tem
    oferta.
    """
    precos = [extrair_preco_pontos(c) for c in cards_html]
    precos_validos = [p for p in precos if p is not None]
    return min(precos_validos) if precos_validos else None
