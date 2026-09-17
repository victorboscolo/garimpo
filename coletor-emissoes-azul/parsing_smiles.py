"""Extrai a oferta mais barata de uma busca de ida na Smiles, do HTML já
renderizado — mesmo princípio do site principal da Azul
(`parsing_site_principal.py`): a Smiles não expõe a API por trás de forma
utilizável de fora (achado de 09/09, Akamai), então lê-se o resultado que a
própria página já mostrou.

Cada oferta é um `.select-flight-list-accordion-item` (achado 17/09, via
`data-testid="flight-summary"` subindo a árvore); dentro dele:
- `.company` (texto, não ícone — diferente do azulpelomundo): nome da
  companhia que vendeu o trecho.
- `.scale-duration__type-flight`: "Direto" ou "N parada(s)".
- `.miles`: "A partir de <b>58.700 milhas</b> ou <b>R$ 1.185,81</b> por
  viajante" — os dois preços (só-milhas e milhas+dinheiro) no mesmo texto;
  a oferta interessa pelo valor só-milhas, a taxa em reais é a da opção
  combinada (mesmo padrão que a Azul já guarda pra `taxa_reais`).
"""
from __future__ import annotations

import re

_PADRAO_MILHAS = re.compile(r"A partir de\s*<strong>([\d.]+)\s*milhas</strong>")
_PADRAO_TAXA = re.compile(r"R\$[^\d]*([\d.,]+)[^0-9]*?por viajante")
_PADRAO_COMPANHIA = re.compile(r'<span class="company">([^<]+)</span>')
_PADRAO_PARADAS = re.compile(r"(\d+)\s*parada")
_PADRAO_DIRETO = re.compile(r'type-flight">Direto')


def _taxa_reais(texto: str) -> float | None:
    achado = _PADRAO_TAXA.search(texto)
    if achado is None:
        return None
    return float(achado.group(1).replace(".", "").replace(",", "."))


def _paradas(texto: str) -> int | None:
    achado = _PADRAO_PARADAS.search(texto)
    if achado:
        return int(achado.group(1))
    if _PADRAO_DIRETO.search(texto):
        return 0
    return None


def extrair_mais_barata_smiles_dom(linhas_html: list[str]) -> dict | None:
    """Varre as linhas `.select-flight-list-accordion-item` já renderizadas
    (uma por voo) e devolve a mais barata em milhas, ou None se nenhuma
    linha tem preço (rota sem oferta pra essa data — não é erro).
    """
    melhor = None
    for linha in linhas_html:
        achado_milhas = _PADRAO_MILHAS.search(linha)
        if achado_milhas is None:
            continue
        milhas = int(achado_milhas.group(1).replace(".", ""))
        if melhor is not None and milhas >= melhor["pontos"]:
            continue

        companhia = _PADRAO_COMPANHIA.search(linha)
        melhor = {
            "pontos": milhas,
            "taxa_reais": _taxa_reais(linha),
            "companhia_operadora": companhia.group(1).strip() if companhia else None,
            "paradas": _paradas(linha),
        }
    return melhor
