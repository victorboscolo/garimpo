"""Extrai a oferta mais barata da resposta de GET /api/availability do
portal azulpelomundo.

Estrutura da resposta (mapeada em 20/08/2026 contra uma resposta real, ver
fixture_azul_pelo_mundo.py): cada voo de ida em `departureFlights.flights`
tem um `points.value` no próprio nível — mas esse é só o preço do trecho de
ida sozinho, sempre maior que o preço combinado real. O preço da
combinação ida+volta que interessa mora dentro de
`recommendations[].returnFlights[].categories[].points.value`. Ignorar essa
diferença faria o coletor gravar um preço maior do que o site realmente
oferece.
"""
from __future__ import annotations


def extrair_mais_barata_azul_pelo_mundo(resposta: dict) -> dict | None:
    """Varre todas as combinações ida+volta e devolve a mais barata em
    pontos, ou None se a resposta não tem nenhum voo.
    """
    voos_ida = resposta.get("data", {}).get("departureFlights", {}).get("flights", [])

    melhor = None
    for ida in voos_ida:
        for recomendacao in ida.get("recommendations", []):
            for volta in recomendacao.get("returnFlights", []):
                for categoria in volta.get("categories", []):
                    pontos = categoria.get("points", {}).get("value")
                    if pontos is None:
                        continue
                    if melhor is None or pontos < melhor["pontos"]:
                        melhor = {
                            "pontos": int(pontos),
                            "taxa_reais": categoria.get("fee", {}).get("total", {}).get("value"),
                            "companhia_operadora": ida.get("marketingCarrier"),
                            "voo_direto": ida.get("connection") == 0,
                        }
    return melhor
