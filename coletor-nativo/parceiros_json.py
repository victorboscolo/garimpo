"""Leitura do JSON estruturado que a listagem da Livelo embute na página.

Descoberto em 14/08/2026. A página renderiza os cards a partir de um objeto por
parceiro que já traz tudo tipado, o que torna desnecessário tanto o regex sobre
texto renderizado quanto a visita à página de regras de cada campanha.

O que a estrutura entrega e o texto renderizado não entregava:

- `parityBau`: a pontuação fora de campanha. É quanto a oferta vale quando a
  promoção acabar — a Decolar anuncia 12 e volta a 6. Nenhum lugar da tela
  mostra isso.
- `categories`: a classificação do parceiro, vinda da fonte em vez de heurística.
- `dateStart`/`dateEnd`: período com hora e fuso, em vez de datas extraídas de
  prosa.
- `legalTerms`: o regulamento, sem precisar visitar ~50 páginas por coleta.
- `separatorSlug`, `promotion`, `parityClub`: campos no lugar de padrões de texto.

Esta é uma estrutura interna do site e pode mudar sem aviso. Por isso
`extrair_parceiros` devolve dicionário vazio em vez de estourar quando não
encontra nada — cabe ao chamador cair no parsing de texto, que continua
funcionando.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

# Toda entrada de parceiro carrega este campo; ele serve de âncora para achar o
# objeto que a contém.
ANCORA = '"partnerDetailsPage"'

UNIDADE_POR_MOEDA = {"R$": "pontos_por_real", "U$": "pontos_por_dolar"}

# "todos" aparece em praticamente todos os parceiros e não classifica nada.
CATEGORIA_IGNORADA = "todos"

PADRAO_TAG_HTML = re.compile(r"<[^>]+>")
PADRAO_DATA = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


@dataclass
class ParceiroJson:
    """Campos que o JSON entrega, já convertidos para os tipos do domínio."""
    codigo_externo: str
    nome_exibicao: str
    pontuacao: Decimal
    unidade_pontuacao: str
    pontuacao_clube: Decimal | None
    pontuacao_base: Decimal | None
    pontuacao_e_teto: bool
    em_promocao: bool
    regulamento_texto: str | None
    data_inicio: date | None
    data_fim: date | None
    categorias: list[str]
    url_origem: str | None


def _objeto_ao_redor(texto: str, posicao: int) -> dict | None:
    """Isola o objeto JSON que contém a posição dada, contando chaves.

    Percorre para trás procurando uma abertura que feche num objeto válido; a
    primeira que fechar é a mais próxima, ou seja, a entrada do parceiro.
    """
    inicio = texto.rfind("{", 0, posicao)
    while inicio > 0:
        profundidade = 0
        for i in range(inicio, min(len(texto), inicio + 30000)):
            if texto[i] == "{":
                profundidade += 1
            elif texto[i] == "}":
                profundidade -= 1
                if profundidade == 0:
                    try:
                        return json.loads(texto[inicio:i + 1])
                    except ValueError:
                        break
        inicio = texto.rfind("{", 0, inicio)
    return None


def extrair_parceiros(html: str) -> dict[str, dict]:
    """Mapa {codigo_externo: objeto do parceiro} extraído da página.

    Devolve vazio quando a estrutura não é encontrada, para que o chamador possa
    voltar ao parsing de texto em vez de perder a coleta do dia.

    A chave é maiusculizada: a Livelo já serviu o mesmo "id" em caixas
    diferentes em coletas distintas (achado real: Bankei, "ban" no JSON vs
    "BAN" na URL), o que fez o mesmo parceiro virar dois `Parceiro` no banco —
    a busca por código lá é exata. A caixa não tem significado, só identifica.
    """
    encontrados: dict[str, dict] = {}
    for achado in re.finditer(ANCORA, html):
        objeto = _objeto_ao_redor(html, achado.start())
        if not isinstance(objeto, dict):
            continue
        codigo = objeto.get("id")
        if codigo and isinstance(objeto.get("parity"), dict):
            encontrados[codigo.upper()] = objeto
    return encontrados


def _decimal_ou_none(valor) -> Decimal | None:
    if valor is None or valor == "":
        return None
    try:
        return Decimal(str(valor))
    except ValueError:
        return None


def _data_ou_none(valor: str | None) -> date | None:
    """'2026-08-12-00:00:00 GMT-03:00' -> date(2026, 8, 12).

    Guarda só o dia: validade de campanha é data de calendário, e converter o
    instante para outro fuso já exibiu "16/08" onde o regulamento dizia 17.
    """
    if not valor:
        return None
    achado = PADRAO_DATA.search(valor)
    if not achado:
        return None
    ano, mes, dia = achado.groups()
    return date(int(ano), int(mes), int(dia))


def _texto_limpo(html_bruto: str | None) -> str | None:
    if not html_bruto:
        return None
    texto = PADRAO_TAG_HTML.sub("", html_bruto)
    texto = texto.replace("&nbsp;", " ").replace("&amp;", "&")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto or None


def parceiro_para_bruta(objeto: dict) -> ParceiroJson:
    parity = objeto.get("parity") or {}
    moeda = parity.get("currency") or "R$"

    categorias = [
        c for c in (objeto.get("categories") or "").split()
        if c and c != CATEGORIA_IGNORADA
    ]

    pontuacao = _decimal_ou_none(parity.get("parity"))

    # `parityClub` vem preenchido em todos os parceiros, quase sempre igual à
    # pontuação normal — nesses casos não há oferta de clube alguma. Registrar
    # o valor mesmo assim seria ruído na tela e, pior, mudaria o hash de
    # deduplicação de toda a base, já que `pontuacao_clube` entra nele.
    clube = _decimal_ou_none(parity.get("parityClub"))
    if clube is not None and pontuacao is not None and clube <= pontuacao:
        clube = None

    _id = objeto.get("id")
    return ParceiroJson(
        codigo_externo=_id.upper() if _id else None,
        nome_exibicao=objeto.get("name"),
        pontuacao=pontuacao,
        unidade_pontuacao=UNIDADE_POR_MOEDA.get(moeda, "pontos_por_real"),
        pontuacao_clube=clube,
        pontuacao_base=_decimal_ou_none(parity.get("parityBau")),
        pontuacao_e_teto=parity.get("separatorSlug") == "ATE",
        em_promocao=bool(parity.get("promotion")),
        regulamento_texto=_texto_limpo(parity.get("legalTerms")),
        data_inicio=_data_ou_none(parity.get("dateStart")),
        data_fim=_data_ou_none(parity.get("dateEnd")),
        categorias=categorias,
        url_origem=objeto.get("partnerDetailsPage") or objeto.get("link"),
    )
