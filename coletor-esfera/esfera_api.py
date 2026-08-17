"""Leitura da API pública de parceiros da Esfera.

Descoberto em 17/08/2026: `GET /bff-product/ehcs/products?categoryId=esf02163`
devolve os ~168 parceiros de "Lojas Parceiras" num único request, sem exigir
cookie, sessão ou qualquer cabeçalho especial — confirmado com `curl` puro.
Ao contrário da Livelo, não há bloqueio anti-robô aqui: nada de Playwright,
nada de rodar fora do Docker por causa de Chromium disfarçado.

Duas ausências, por desenho, comparado ao coletor da Livelo:

- **`pontuacao_base`** (piso fora de campanha): a Livelo expõe isso num campo
  limpo (`parityBau`). A Esfera só menciona o valor padrão dentro do texto
  livre do regulamento ("O acúmulo padrão é de 2 pontos..."), com redação que
  varia por parceiro — um teste em 167 parceiros ativos achou o padrão em
  só 36. Regex nesse cenário adivinharia, não extrairia.
- **`data_inicio`/`data_fim`**: mesma história. `esf_tempOfferInit/End` existe
  como campo, mas está vazio (placeholder "dd-mm-yyyy HH:MM") em 167 dos 168
  parceiros — só o período em prosa está preenchido, e com formato
  inconsistente entre parceiros (a Casas Bahia, por exemplo, aplica datas
  diferentes por categoria na mesma frase).

Essas duas lacunas ficam para quando a Esfera expuser (ou passar a preencher)
um campo estruturado — não para uma tentativa de regex sobre prosa variável.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
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
    data_inicio: None = None
    data_fim: None = None


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


def parceiro_para_bruta(item: dict) -> ParceiroEsfera:
    prefixo = (item.get("esf_accumulationPrefix") or "").strip().lower()

    return ParceiroEsfera(
        codigo_externo=item["id"],
        nome_exibicao=item["displayName"],
        pontuacao=Decimal(item["esf_accumulationValue"]),
        unidade_pontuacao=_unidade(item.get("esf_accumulationFactorDescription")),
        pontuacao_e_teto=prefixo == "até",
        regulamento_texto=_texto_limpo(item.get("esf_accumulationGeneralRules")),
        categorias=_categorias(item.get("parentCategories") or []),
        url_origem=f"{BASE_URL}{item['route']}",
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
