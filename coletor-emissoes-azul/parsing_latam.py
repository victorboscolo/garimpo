"""Extrai as ofertas de uma busca de ida na LATAM, do HTML já renderizado
— mesmo princípio dos outros dois parsers. A LATAM não é bloqueada por
Akamai/anti-robô (achado antigo, reconfirmado 17/09): a barreira sempre foi
login. Com uma sessão autenticada manualmente pelo usuário (nunca por
código — ver coletor_emissoes_latam.py), a busca com `redemption=true`
devolve resultado normal.

Cada oferta é um bloco que começa em `data-testid="card-expander-N"`
(achado 17/09: esse marcador aparece no início de cada card, na mesma
ordem que os cards são exibidos — fatiar o HTML nesses pontos isola cada
oferta sem precisar de um seletor de container único). Dentro do bloco:
- Preço: texto "N.NNN milhas" — sempre o valor 100%-milhas, não a versão
  "milhas + dinheiro" (que a LATAM também mostra, mas não é o que
  interessa aqui — mesma decisão do usuário de só milhas).
- Duração: o texto que segue o rótulo "Duração" ("8 h 30 min.").
- Direto/parada: o texto do link de detalhes ("Direto" ou "N parada(s)").
- Companhia: o atributo `alt` da imagem do operador (`data-testid="image-
  <nome>"`) — já vem por extenso (ex: "LATAM Airlines Brasil"), sem
  precisar de dicionário de código IATA como a Azul.

Achado à parte (17/09, não usado ainda): o texto "+ BRL X,XX" ao lado das
milhas parece ser taxa de embarque/impostos de verdade sobre a própria
oferta em milhas ("Inclui taxas e impostos") — diferente do padrão da
Azul/Smiles, onde esse tipo de valor era um produto alternativo. Decisão
do usuário (17/09): não gravar por ora, só milhas.
"""
from __future__ import annotations

import re

_PADRAO_MILHAS = re.compile(r'([\d.]+)\s*milhas</span>')
_PADRAO_DURACAO = re.compile(r'>Duração</span><span[^>]*>([^<]+)</span>')
_PADRAO_PARADAS_NUM = re.compile(r'(\d+)\s*(?:parada|escala)')
_PADRAO_DIRETO = re.compile(r'<span>Direto</span>')
_PADRAO_COMPANHIA = re.compile(r'data-testid="image-([^"]+)"')


def _paradas(bloco: str) -> int | None:
    achado = _PADRAO_PARADAS_NUM.search(bloco)
    if achado:
        return int(achado.group(1))
    if _PADRAO_DIRETO.search(bloco):
        return 0
    return None


def _oferta_do_bloco(bloco: str) -> dict | None:
    achado_milhas = _PADRAO_MILHAS.search(bloco)
    if achado_milhas is None:
        return None

    duracao = _PADRAO_DURACAO.search(bloco)
    companhia = _PADRAO_COMPANHIA.search(bloco)
    return {
        "pontos": int(achado_milhas.group(1).replace(".", "")),
        "companhia_operadora": companhia.group(1) if companhia else None,
        "paradas": _paradas(bloco),
        "duracao_texto": duracao.group(1).strip() if duracao else None,
    }


def _blocos_por_card(html: str) -> list[str]:
    """Fatia o HTML da página de resultados em um pedaço por card, usando
    `card-expander-N` como marcador de início — ver docstring do módulo.
    """
    marcadores = [m.start() for m in re.finditer(r'data-testid="card-expander-\d+"', html)]
    blocos = []
    for i, inicio in enumerate(marcadores):
        fim = marcadores[i + 1] if i + 1 < len(marcadores) else len(html)
        blocos.append(html[inicio:fim])
    return blocos


def extrair_ofertas_latam_dom(html: str) -> dict:
    """Varre a página de resultados e devolve as duas mais baratas — a
    melhor direto e a melhor com parada, cada uma podendo ser `None` se a
    categoria não tiver nenhuma oferta.

    Devolve `{"direto": dict | None, "com_parada": dict | None}`.
    """
    melhor_direto = None
    melhor_com_parada = None
    for bloco in _blocos_por_card(html):
        oferta = _oferta_do_bloco(bloco)
        if oferta is None:
            continue

        if oferta["paradas"] == 0:
            if melhor_direto is None or oferta["pontos"] < melhor_direto["pontos"]:
                melhor_direto = oferta
        elif oferta["paradas"] is not None and oferta["paradas"] > 0:
            if melhor_com_parada is None or oferta["pontos"] < melhor_com_parada["pontos"]:
                melhor_com_parada = oferta

    return {"direto": melhor_direto, "com_parada": melhor_com_parada}
