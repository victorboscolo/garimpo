"""Extrai a oferta mais barata da resposta de GET /api/availability do
portal azulpelomundo, busca só-ida (tripType=ONE_WAY).

Achado empírico (21/08/2026, ver fixture_azul_pelo_mundo.py): numa busca
só-ida `returnFlights` vem `null` e o `points.value` no nível do próprio
voo já é o preço real da perna — diferente da busca ida-e-volta (não usada
mais, decisão do usuário 21/08), onde esse mesmo campo era só o trecho de
ida isolado e o preço real da combinação morava um nível mais fundo, dentro
de `recommendations[].returnFlights[].categories[]`. A taxa em reais agora
mora um nível mais raso, em `recommendations[0].fee.total.value`.

`connection` é o número de conexões de verdade, não um booleano — resposta
real GRU->HND trouxe `connection: 1` com um `flightGroup` de duas pernas
(GRU->JFK->HND). Por isso vira `paradas` direto, sem conversão pra bool.
"""
from __future__ import annotations


def extrair_mais_barata_azul_pelo_mundo(resposta: dict) -> dict | None:
    """Varre os voos de ida e devolve o mais barato em pontos, ou None se a
    resposta não tem nenhum voo.
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
