"""Leitura da API pública de parceiros da Esfera.

Descoberto em 17/08/2026: `GET /bff-product/ehcs/products?categoryId=esf02163`
devolve os ~168 parceiros de "Lojas Parceiras" num único request, sem exigir
cookie, sessão ou qualquer cabeçalho especial — confirmado com `curl` puro.
Ao contrário da Livelo, não há bloqueio anti-robô aqui: nada de Playwright,
nada de rodar fora do Docker por causa de Chromium disfarçado.

Uma ausência, por desenho, comparado ao coletor da Livelo:

- **`pontuacao_base`** (piso fora de campanha): a Livelo expõe isso num campo
  limpo (`parityBau`). A Esfera só menciona o valor padrão dentro do texto
  livre do regulamento ("O acúmulo padrão é de 2 pontos..."), com redação que
  varia por parceiro — um teste em 167 parceiros ativos achou o padrão em
  só 36. Regex nesse cenário adivinharia, não extrairia. Fica pra quando a
  Esfera expuser (ou passar a preencher) um campo estruturado.

`data_inicio`/`data_fim` tinham a mesma decisão (`esf_tempOfferInit/End`
vem vazio em 167 dos 168 parceiros), mas foi revertida em 28/09/2026: uma
oferta da Rentcars ficou aprovada e visível no painel dias depois de vencida
("Condições válidas... até 27/09/2026" no próprio regulamento, `data_fim`
nulo porque nada extraía isso) — grave, porque o painel filtra por
vigência usando exatamente esse campo. Um teste contra 350 regulamentos
reais em 28/09 achou o padrão "válid[ao]s ... até [HHhMMmin do dia]
DD/MM/YYYY" em 107 deles (106 com início+fim, 1 só com fim, caso da
própria Rentcars) — frequente e consistente o bastante pra extrair de
verdade, ao contrário do padrão de `pontuacao_base`. As outras ~243 ofertas
sem match ficam com `data_fim=None`, tratadas como sem prazo conhecido
(a mesma semântica de sempre — nunca inventa, só quando o texto afirma).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import httpx

API_URL = "https://apigw.esfera.com.vc/bff-product/ehcs/products"
CATEGORIA_LOJAS_PARCEIRAS = "esf02163"
BASE_URL = "https://esfera.com.vc"

# O contêiner que todo parceiro carrega (a própria categoria "Lojas
# Parceiras") — equivalente ao "todos" da Livelo, não classifica nada.
CATEGORIA_CONTAINER = "new02163"

PADRAO_TAG_HTML = re.compile(r"<[^>]+>")


@dataclass
class ParceiroEsfera:
    """Campos que a API entrega, já convertidos para os tipos do domínio."""
    codigo_externo: str
    nome_exibicao: str
    pontuacao: Decimal
    unidade_pontuacao: str
    pontuacao_e_teto: bool
    regulamento_texto: str | None
    categorias: list[str]
    url_origem: str
    pontuacao_base: None = None
    data_inicio: date | None = None
    data_fim: date | None = None


def _texto_limpo(html_bruto: str | None) -> str | None:
    if not html_bruto:
        return None
    texto = PADRAO_TAG_HTML.sub("", html_bruto)
    texto = texto.replace("&nbsp;", " ").replace("&amp;", "&")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto or None


def _unidade(descricao: str | None) -> str:
    """"dólar em compra" -> pontos_por_dolar; qualquer outra coisa (incluindo
    ausência, como no único caso sem o campo) -> pontos_por_real.
    """
    if descricao and "dólar" in descricao.lower():
        return "pontos_por_dolar"
    return "pontos_por_real"


def _categorias(parent_categories: list[dict]) -> list[str]:
    """Só a taxonomia "new_" (mais nova) menos o contêiner universal.

    A taxonomia "esf_" antiga fica de fora: a "new_" foi escolhida porque
    precisa dialogar com as categorias da Livelo na camada canônica
    (`categorias`), e nomes como "newModaCalcadosAcessorios" (contra
    "esf02163") se prestam mais a esse agrupamento futuro.
    """
    vistas = []
    for categoria in parent_categories or []:
        repo_id = categoria.get("repositoryId") or ""
        if not repo_id.startswith("new") or repo_id.startswith("new_"):
            continue
        if repo_id == CATEGORIA_CONTAINER:
            continue
        if repo_id not in vistas:
            vistas.append(repo_id)
    return vistas


# "Condições válidas para [reservas realizadas|compras efetuadas] de
# 00h00min do dia DD/MM/YYYY até 23h59min do dia DD/MM/YYYY" — a forma mais
# comum, com início e fim. `[^.]*?` prende a busca à mesma frase, pra não
# pegar uma data de outro trecho do regulamento por acidente.
_PADRAO_VALIDADE_COMPLETA = re.compile(
    r"v[áa]lidas?[^.]*?de\s+\d{1,2}h\d{2}min?\s+do\s+dia\s+(\d{1,2}/\d{1,2}/\d{4})"
    r"\s+até\s+\d{1,2}h\d{2}min?\s+do\s+dia\s+(\d{1,2}/\d{1,2}/\d{4})",
    re.IGNORECASE,
)
# Forma curta, sem início explícito — achado real (28/09/2026, Rentcars):
# "Condições válidas para reservas realizadas até 27/09/2026, às 23h59".
_PADRAO_VALIDADE_SO_FIM = re.compile(r"v[áa]lidas?[^.]*?até\s+(\d{1,2}/\d{1,2}/\d{4})", re.IGNORECASE)


def _data(texto: str) -> date:
    dia, mes, ano = texto.split("/")
    return date(int(ano), int(mes), int(dia))


def _extrair_validade(regulamento: str | None) -> tuple[date | None, date | None]:
    """(data_inicio, data_fim) do regulamento, ou (None, None) sem padrão
    reconhecido — a maioria dos parceiros não tem prazo (oferta contínua),
    e fica assim de propósito: nunca inventa uma data que o texto não afirma.
    """
    if not regulamento:
        return None, None
    m = _PADRAO_VALIDADE_COMPLETA.search(regulamento)
    if m:
        return _data(m.group(1)), _data(m.group(2))
    m = _PADRAO_VALIDADE_SO_FIM.search(regulamento)
    if m:
        return None, _data(m.group(1))
    return None, None


def parceiro_para_bruta(item: dict) -> ParceiroEsfera:
    prefixo = (item.get("esf_accumulationPrefix") or "").strip().lower()
    regulamento = _texto_limpo(item.get("esf_accumulationGeneralRules"))
    data_inicio, data_fim = _extrair_validade(regulamento)

    return ParceiroEsfera(
        codigo_externo=item["id"],
        nome_exibicao=item["displayName"],
        pontuacao=Decimal(item["esf_accumulationValue"]),
        unidade_pontuacao=_unidade(item.get("esf_accumulationFactorDescription")),
        pontuacao_e_teto=prefixo == "até",
        regulamento_texto=regulamento,
        categorias=_categorias(item.get("parentCategories") or []),
        url_origem=f"{BASE_URL}{item['route']}",
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


def buscar_parceiros() -> list[dict]:
    """Busca a listagem completa de "Lojas Parceiras" — um request só.

    `totalResults` (168 em 17/08/2026) sempre coube dentro do `limit` padrão
    da API (250); se a Esfera crescer além disso, paginar vira necessário.
    """
    resposta = httpx.get(
        API_URL, params={"categoryId": CATEGORIA_LOJAS_PARCEIRAS}, timeout=30.0
    )
    resposta.raise_for_status()
    corpo = resposta.json()
    return [item for item in corpo.get("items", []) if item.get("active")]
