"""Extrai a oferta mais barata do portal azulpelomundo, busca só-ida
(tripType=ONE_WAY).

Duas versões, do achado mais antigo pro mais recente:

`extrair_mais_barata_azul_pelo_mundo` lê o JSON de `GET /api/availability`
(achado 21/08/2026, ver fixture_azul_pelo_mundo.py) — funciona quando dá pra
capturar a resposta de rede de verdade (Playwright tinha
`page.expect_response`). Mantida porque a lógica em si (qual campo é o
preço, o que é `connection`) continua correta; só não dá mais pra alimentá-
la puxando a API direto pelo browser: achado de 17/09, a API exige um token
de reCAPTCHA gerado pelo JS da própria página a cada chamada, então refazer
o `fetch` de fora (sem ter clicado em nada) devolve 400
`MISSING_TOKEN` — mesmo já com os cookies de uma sessão que carregou a
página com sucesso.

`extrair_ofertas_azul_pelo_mundo_dom` é o caminho que o coletor usa de
verdade agora: lê o HTML já renderizado (mesmo princípio do site principal,
`parsing_site_principal.py`) — o resultado chega na tela de qualquer jeito,
então não precisa da API crua. Cada oferta é um `.componentFlight`; dentro
dele, `.labelValuePoints` é o preço em pontos, `.icon-XX` (classe, não
texto) é o código IATA da companhia, `.elapsedFlightTime` é a duração total
(texto, "11h25"), e o texto de conexão é "Voo direto" ou "N Parada(s)".

Devolve duas ofertas, não uma (decisão do usuário, 17/09): a mais barata
direto e a mais barata com parada, cada uma sua própria linha em
`ofertas_emissao` — nenhuma domina a outra, porque nem todo mundo aceita
trocar tempo de voo por preço.

`taxa_reais` não é mais preenchido (decisão do usuário, 17/09: só milhas) —
o valor que existia em `.labelPointsPlusMoney` era de uma oferta
alternativa (menos pontos + dinheiro), não uma taxa sobre a oferta em
pontos.
"""
from __future__ import annotations

import re


def extrair_mais_barata_azul_pelo_mundo(resposta: dict) -> dict | None:
    """Varre os voos de ida e devolve o mais barato em pontos, ou None se a
    resposta não tem nenhum voo. Ver docstring do módulo — só serve se
    alguém encontrar como anexar o token de reCAPTCHA a esse GET.
    """
    voos = resposta.get("data", {}).get("departureFlights", {}).get("flights", [])

    melhor = None
    for voo in voos:
        pontos = voo.get("points", {}).get("value")
        if pontos is None:
            continue
        if melhor is None or pontos < melhor["pontos"]:
            recomendacoes = voo.get("recommendations", [])
            taxa = recomendacoes[0].get("fee", {}).get("total", {}).get("value") if recomendacoes else None
            melhor = {
                "pontos": int(pontos),
                "taxa_reais": taxa,
                "companhia_operadora": voo.get("marketingCarrier"),
                "paradas": voo.get("connection"),
            }
    return melhor


_PADRAO_PONTOS = re.compile(r'<div class="labelValuePoints">([\d.]+)</div>')
_PADRAO_COMPANHIA = re.compile(r'"icon-([A-Za-z0-9]+)"')
_PADRAO_PARADAS = re.compile(r"(\d+)\s*[Pp]arada")
_PADRAO_DIRETO = re.compile(r"\bVoo direto\b")
_PADRAO_DURACAO = re.compile(r'elapsedFlightTime[^>]*>([^<]+)</label>')


def _paradas_do_texto(texto: str) -> int | None:
    achado = _PADRAO_PARADAS.search(texto)
    if achado:
        return int(achado.group(1))
    if _PADRAO_DIRETO.search(texto):
        return 0
    return None


def _oferta_da_linha(linha: str) -> dict | None:
    achado_pontos = _PADRAO_PONTOS.search(linha)
    if achado_pontos is None:
        return None

    companhia = _PADRAO_COMPANHIA.search(linha)
    duracao = _PADRAO_DURACAO.search(linha)
    return {
        "pontos": int(achado_pontos.group(1).replace(".", "")),
        "companhia_operadora": companhia.group(1) if companhia else None,
        "paradas": _paradas_do_texto(linha),
        "duracao_texto": duracao.group(1).strip() if duracao else None,
    }


def extrair_ofertas_azul_pelo_mundo_dom(linhas_html: list[str]) -> dict:
    """Varre as linhas `.componentFlight` já renderizadas (uma por voo) e
    devolve as duas mais baratas — a melhor direto e a melhor com parada,
    cada uma podendo ser `None` se a categoria não tiver nenhuma oferta
    (ex: rota sem voo direto nenhum — não é erro).

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
