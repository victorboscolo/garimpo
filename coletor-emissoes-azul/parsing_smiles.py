"""Extrai as ofertas de uma busca de ida na Smiles, do HTML já renderizado
— mesmo princípio do site principal da Azul (`parsing_site_principal.py`):
a Smiles não expõe a API por trás de forma utilizável de fora (achado de
09/09, Akamai), então lê-se o resultado que a própria página já mostrou.

Cada oferta é um `.select-flight-list-accordion-item` (achado 17/09, via
`data-testid="flight-summary"` subindo a árvore); dentro dele:
- `.company` (texto, não ícone — diferente do azulpelomundo): nome da
  companhia que vendeu o trecho.
- `.scale-duration__type-flight`: "Direto" ou "N parada(s)".
- `.scale-duration__time`: duração total do voo, texto ("02h50min").
- `.miles`: "A partir de <b>58.700 milhas</b> ou <b>R$ 1.185,81</b> por
  viajante" — o segundo valor é o preço 100%-dinheiro (sem usar milha
  nenhuma), uma forma de pagamento alternativa, não uma taxa sobre a
  oferta em milhas (achado do usuário, 17/09) — por isso não é mais
  extraído.

Devolve duas ofertas, não uma (decisão do usuário, 17/09): a mais barata
direto e a mais barata com parada, cada uma sua própria linha em
`ofertas_emissao`.
"""
from __future__ import annotations

import re

_PADRAO_MILHAS = re.compile(r"A partir de\s*<strong>([\d.]+)\s*milhas</strong>")
_PADRAO_COMPANHIA = re.compile(r'<span class="company">([^<]+)</span>')
_PADRAO_PARADAS = re.compile(r"(\d+)\s*parada")
_PADRAO_DIRETO = re.compile(r'type-flight">Direto')
_PADRAO_DURACAO = re.compile(r'scale-duration__time">([^<]+)</p>')


def _paradas(texto: str) -> int | None:
    achado = _PADRAO_PARADAS.search(texto)
    if achado:
        return int(achado.group(1))
    if _PADRAO_DIRETO.search(texto):
        return 0
    return None


def _oferta_da_linha(linha: str) -> dict | None:
    achado_milhas = _PADRAO_MILHAS.search(linha)
    if achado_milhas is None:
        return None

    companhia = _PADRAO_COMPANHIA.search(linha)
    duracao = _PADRAO_DURACAO.search(linha)
    return {
        "pontos": int(achado_milhas.group(1).replace(".", "")),
        "companhia_operadora": companhia.group(1).strip() if companhia else None,
        "paradas": _paradas(linha),
        "duracao_texto": duracao.group(1).strip() if duracao else None,
    }


def extrair_ofertas_smiles_dom(linhas_html: list[str]) -> dict:
    """Varre as linhas `.select-flight-list-accordion-item` já renderizadas
    (uma por voo) e devolve as duas mais baratas — a melhor direto e a
    melhor com parada, cada uma podendo ser `None` se a categoria não tiver
    nenhuma oferta.

    Devolve `{"direto": dict | None, "com_parada": dict | None}`.
    """
    melhor_direto = None
    melhor_com_parada = None
    for linha in linhas_html:
        oferta = _oferta_da_linha(linha)
        if oferta is None:
            continue

        if oferta["paradas"] == 0:
            if melhor_direto is None or oferta["pontos"] < melhor_direto["pontos"]:
                melhor_direto = oferta
        elif oferta["paradas"] is not None and oferta["paradas"] > 0:
            if melhor_com_parada is None or oferta["pontos"] < melhor_com_parada["pontos"]:
                melhor_com_parada = oferta

    return {"direto": melhor_direto, "com_parada": melhor_com_parada}
