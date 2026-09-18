"""Coletor Livelo NATIVO - roda direto no macOS (fora do Docker).

Motivo de existir fora do container: o site da Livelo tem protecao
anti-robo que bloqueia (403) o Chromium headless rodando dentro de um
container Linux, mesmo com user-agent/headers disfarcados. Rodando
nativamente no Mac, COM JANELA VISIVEL (headless=False), o navegador
passa pela protecao normalmente.

Este script NAO acessa o banco de dados diretamente - ele envia cada
promocao coletada via HTTP para o endpoint POST /api/v1/promocoes/ingerir
da API (que roda no Docker, exposta em localhost:8000).

Uso manual: python3 coletor_livelo_nativo.py
Uso agendado: configurado via launchd (ver com.garimpo.coletor-livelo.plist)
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import httpx
from playwright.async_api import async_playwright

from parceiros_json import extrair_parceiros, parceiro_para_bruta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("garimpo.coletor_nativo.livelo")

URL_LIVELO_PARCEIROS = "https://www.livelo.com.br/juntar-pontos/todos-os-parceiros"
API_INGERIR_URL = "http://localhost:8000/api/v1/promocoes/ingerir"
API_EXECUCOES_URL = "http://localhost:8000/api/v1/execucoes"
JOB = "coletor_livelo"


def _chave_api() -> str | None:
    """Lê COLETOR_API_KEY do .env na raiz do repo — o painel passou a exigir
    autenticação em toda rota (18/09), e o coletor roda em venv próprio,
    fora do Docker, sem env_file pra herdar a variável."""
    if os.environ.get("COLETOR_API_KEY"):
        return os.environ["COLETOR_API_KEY"]
    caminho = os.path.join(os.path.dirname(__file__), "..", ".env")
    try:
        with open(caminho) as f:
            for linha in f:
                if linha.strip().startswith("COLETOR_API_KEY="):
                    return linha.strip().split("=", 1)[1]
    except FileNotFoundError:
        pass
    return None


HEADERS = {"X-API-Key": _chave_api()} if _chave_api() else {}

# Padroes validados contra texto real capturado do navegador em 10/08/2026.
PADRAO_PONTOS = re.compile(r'(Até\s+)?(\d+)\s*pontos?\s*por\s*(R\$|U\$)\s*(\d+)')
PADRAO_ERAM = re.compile(r'Eram\s+(\d+)\s*pontos?')

UNIDADE_POR_MOEDA = {"R$": "pontos_por_real", "U$": "pontos_por_dolar"}

# A pagina de detalhe do parceiro traz uma linha comecando com "Campanha
# valida" que descreve a restricao real da oferta. Validado em 14/08/2026
# contra Renner, Olympikus e Beleza na Web.
PADRAO_CAMPANHA = re.compile(r"^\s*Campanha v[áa]lida.*$", re.MULTILINE | re.IGNORECASE)

# "de 14/08/2026 a 16/08/2026" e tambem "de 13 a 14/08/2026", em que o dia
# inicial vem solto e herda mes e ano do fim.
PADRAO_VALIDADE = re.compile(
    r"de\s+(\d{1,2})(?:/(\d{1,2})/(\d{4}))?\s+a\s+(\d{1,2})/(\d{1,2})/(\d{4})",
    re.IGNORECASE,
)

# "Campanha valida em 14/08/2026" — campanha de um dia so.
PADRAO_VALIDADE_DIA_UNICO = re.compile(r"v[áa]lida\s+em\s+(\d{1,2})/(\d{1,2})/(\d{4})", re.IGNORECASE)

# "Utilize o cupom LIVELO." — sem o cupom o cliente nao pontua.
PADRAO_CUPOM = re.compile(r"cupom\s+([A-Z0-9]{3,})")

# alt da logo: 'Logo Liga Vitória Consórcio'. Unica fonte do subtitulo da
# variante — ele nao existe no texto visivel do card.
PADRAO_ALT = re.compile(r'alt="([^"]*)"')


@dataclass
class PromocaoBruta:
    programa_nome: str
    parceiro_nome_bruto: str
    titulo: str
    url_origem: str
    pontuacao: Decimal
    unidade_pontuacao: str
    regulamento_texto: str | None = None
    requer_clube: bool = False
    qual_clube: str | None = None
    requer_cupom: bool = False
    cupom: str | None = None
    # "Ate X pontos" e um teto promocional, nao um valor garantido. O valor
    # coletado continua sendo X; esta marca diz que ele e um limite.
    pontuacao_e_teto: bool = False
    # Pontuacao para assinantes do Clube Livelo, quando o card traz as duas.
    # `pontuacao` continua sendo sempre a de qualquer cliente.
    pontuacao_clube: Decimal | None = None
    # Codigo da variante na URL. Um mesmo slug pode ter ofertas diferentes:
    # beach-park/BPK sao os Hoteis e beach-park/BHP os Ingressos.
    codigo_externo: str | None = None
    # Nome legivel vindo do alt da logo ("Liga Vitoria Consorcio"). So para
    # exibicao — a identidade do parceiro continua sendo nome+codigo da URL.
    nome_exibicao: str | None = None
    # "Eram 1 ponto": valor anterior da oferta. Diz o tamanho do salto — de 1
    # para 100 e noticia, de 2 para 3 nao e.
    pontuacao_anterior: Decimal | None = None
    # Selo "Promocao" no card: campanha ativa, portanto temporaria. Eixo
    # diferente da nota, que mede se a oferta e boa.
    em_promocao: bool = False
    # Periodo da campanha, extraido do regulamento na pagina de detalhe.
    data_inicio: date | None = None
    data_fim: date | None = None
    # Pontuacao fora de campanha (`parityBau`). O piso real: a Liga Vitoria
    # anuncia "ate 100" e volta a 1 quando a promocao acabar.
    pontuacao_base: Decimal | None = None
    # Categorias do parceiro segundo a propria Livelo, sem traducao.
    categorias: list = None
    # Interno: nao vai para a API. Marca os cards com selo "Promocao", que sao
    # os que tem campanha ativa e, portanto, regulamento a buscar.
    buscar_detalhe: bool = False


def _extrair_nome_da_url(href: str) -> str:
    """O nome do parceiro nao aparece no texto do card, so na URL.
    Ex: '/juntar-pontos/parceiros/casas-bahia/CSB' -> 'Casas Bahia'
    """
    partes = href.rstrip("/").split("/")
    slug = partes[-2] if len(partes) >= 2 else partes[-1]
    return slug.replace("-", " ").title()


def _extrair_codigo_da_url(href: str) -> str | None:
    """Codigo da variante, o ultimo segmento da URL.
    Ex: '/juntar-pontos/parceiros/beach-park/BPK' -> 'BPK'

    Sem esse codigo, duas ofertas distintas do mesmo slug virariam o mesmo
    parceiro e o motor usaria uma como historico da outra. URL fora do padrao
    devolve None em vez de quebrar a coleta.

    Maiusculiza o resultado: a Livelo ja serviu o mesmo codigo em caixas
    diferentes em coletas distintas ('ban' via URL, 'BAN' via JSON), o que fez
    o mesmo parceiro virar dois registros no banco (a busca por codigo e
    exata). A caixa nao tem significado, so identifica.
    """
    partes = href.strip().rstrip("/").split("/")
    if len(partes) < 2 or partes[-2] == "parceiros":
        return None
    # A Livelo serve alguns hrefs com espaco no fim ('/klubi-auto/AUT '):
    # sem limpar, 'AUT ' viraria um parceiro diferente de 'AUT'.
    codigo = partes[-1].strip()
    return codigo.upper() or None


def _extrair_nome_exibicao(html_card: str) -> str | None:
    """Nome legivel do parceiro, tirado do alt da logo.

    O subtitulo que distingue as variantes ("Seguro Viagem", "Consorcio",
    "Ingressos") aparece so na imagem, nunca no texto do card. E a unica fonte
    que nomeia as 6 variantes da Liga Vitoria e revela que hero/HRH e o seguro
    viagem. Presente nos 248 cards em 14/08/2026.

    Vai para `nome_exibicao`, nunca para `nome`: este ultimo entra no hash de
    deduplicacao e na identidade do parceiro, e mudar a fonte dele faria a
    coleta seguinte nao reconhecer nada.
    """
    achado = PADRAO_ALT.search(html_card)
    if not achado:
        return None
    alt = achado.group(1).strip()
    if alt.lower().startswith("logo "):
        alt = alt[5:].strip()
    return alt or None


def _extrair_regulamento(texto_pagina: str) -> str | None:
    """A linha 'Campanha valida ...' da pagina de detalhe.

    E a unica fonte da restricao real: o card da listagem nao a contem. O
    Renner anuncia '10 pontos' sem qualquer ressalva, e so aqui aparece que os
    10 valem na categoria Basicos e o resto da loja rende 2.
    """
    achado = PADRAO_CAMPANHA.search(texto_pagina)
    return achado.group(0).strip() if achado else None


def _extrair_validade(regulamento: str) -> tuple[date | None, date | None]:
    """Periodo da campanha. Devolve (None, None) quando o texto nao informa —
    nunca chuta data, porque validade errada e pior que validade ausente.
    """
    achado = PADRAO_VALIDADE.search(regulamento)
    if not achado:
        # Campanha de um dia so: "valida em 14/08/2026". Inicio e fim coincidem.
        dia_unico = PADRAO_VALIDADE_DIA_UNICO.search(regulamento)
        if dia_unico:
            d, m, a = dia_unico.groups()
            so_um_dia = date(int(a), int(m), int(d))
            return so_um_dia, so_um_dia
        return None, None

    dia_ini, mes_ini, ano_ini, dia_fim, mes_fim, ano_fim = achado.groups()
    fim = date(int(ano_fim), int(mes_fim), int(dia_fim))
    inicio = date(
        int(ano_ini) if ano_ini else fim.year,
        int(mes_ini) if mes_ini else fim.month,
        int(dia_ini),
    )
    return inicio, fim


def _extrair_cupom(regulamento: str) -> str | None:
    achado = PADRAO_CUPOM.search(regulamento)
    return achado.group(1) if achado else None


def _parsear_card(texto: str, href: str, html: str = "") -> PromocaoBruta | None:
    m_pontos = PADRAO_PONTOS.search(texto)
    if not m_pontos:
        return None
    # Quando o card tem variante de Clube, ha duas pontuacoes e a primeira e
    # sempre a de qualquer cliente — verificado nos 15 casos em 13/08/2026.
    ate, valor, moeda, base = m_pontos.groups()
    e_teto = ate is not None

    # Depois da palavra "Clube" vem a pontuacao para assinantes. Verificado nos
    # 15 cards com clube em 13/08/2026: a de qualquer cliente vem sempre antes.
    pontuacao_clube = None
    if "Clube" in texto:
        m_clube = PADRAO_PONTOS.search(texto.split("Clube", 1)[1])
        if m_clube:
            pontuacao_clube = Decimal(m_clube.group(2))

    nome = _extrair_nome_da_url(href)

    m_eram = PADRAO_ERAM.search(texto)
    eram = m_eram.group(1) if m_eram else None
    pontuacao_anterior = Decimal(eram) if eram else None
    descricao = (
        f"Coletado do site oficial da Livelo. Base de comparacao anterior (Eram): {eram} pontos."
        if eram else "Coletado do site oficial da Livelo."
    )

    url_completa = f"https://www.livelo.com.br{href}" if href.startswith("/") else href

    prefixo_teto = "Até " if e_teto else ""

    return PromocaoBruta(
        programa_nome="Livelo",
        parceiro_nome_bruto=nome,
        titulo=f"{nome} - {prefixo_teto}{valor} pontos por {moeda} {base}",
        url_origem=url_completa,
        pontuacao=Decimal(valor),
        unidade_pontuacao=UNIDADE_POR_MOEDA.get(moeda, "pontos_por_real"),
        regulamento_texto=descricao,
        pontuacao_e_teto=e_teto,
        pontuacao_clube=pontuacao_clube,
        codigo_externo=_extrair_codigo_da_url(href),
        nome_exibicao=_extrair_nome_exibicao(html) if html else None,
        pontuacao_anterior=pontuacao_anterior,
        em_promocao="Promoção" in texto,
        # So os cards com selo "Promocao" tem campanha ativa — 40 dos 248 em
        # 14/08/2026. Visitar so esses mantem a coleta leve (~2 min em vez de
        # ~12) e cobre exatamente onde mora o regulamento.
        buscar_detalhe="Promoção" in texto,
    )


def _aplicar_regulamento(item: PromocaoBruta, regulamento: str) -> None:
    """Aplica a um item o que o regulamento da campanha declara.

    O regulamento e a fonte autoritativa; o rotulo do card, nao. O card do
    Olympikus marca a segunda pontuacao como "Clube", mas o regulamento diz que
    os 15 pontos sao "exclusivo para primeira compra" — condicao diferente.
    Sem mencao a Clube no texto, o valor nao e afirmado como sendo de Clube.

    Quando nao ha regulamento (oferta sem campanha ativa, cujo detalhe nem e
    visitado), o card segue sendo a unica fonte e continua valendo.
    """
    item.regulamento_texto = regulamento
    item.data_inicio, item.data_fim = _extrair_validade(regulamento)

    cupom = _extrair_cupom(regulamento)
    if cupom:
        item.requer_cupom = True
        item.cupom = cupom

    if item.pontuacao_clube is not None and "clube" not in regulamento.lower():
        logger.info(
            "'%s': card anuncia Clube mas o regulamento nao menciona — descartando pontuacao de clube.",
            item.parceiro_nome_bruto,
        )
        item.pontuacao_clube = None


async def enriquecer_com_detalhe(page, item: PromocaoBruta, tentativas: int = 2) -> None:
    """Visita a pagina do parceiro e preenche regulamento, validade e cupom.

    Tenta mais de uma vez porque desistir na primeira falha tem custo alto: o
    cupom entra no hash de deduplicacao, entao gravar a oferta sem ele e
    descobri-lo na execucao seguinte cria um registro duplicado da mesma
    oferta, um com a informacao e outro sem. Ja aconteceu com Carters,
    Individual e John John em 14/08/2026.

    Se todas as tentativas falharem, a promocao segue com o que veio da
    listagem — perder a oferta seria pior que perder a restricao.
    """
    texto = None
    for tentativa in range(1, tentativas + 1):
        try:
            resposta = await page.goto(item.url_origem, wait_until="domcontentloaded", timeout=60000)
            if resposta and resposta.status == 200:
                await page.wait_for_timeout(2500)
                texto = await page.locator("body").inner_text()
                break
            motivo = f"HTTP {resposta.status}" if resposta else "sem resposta"
        except Exception as e:
            motivo = str(e)

        if tentativa < tentativas:
            logger.warning("Detalhe de '%s' falhou (%s), tentando de novo.", item.parceiro_nome_bruto, motivo)
            await page.wait_for_timeout(2000)
        else:
            logger.warning("Detalhe de '%s' falhou em %d tentativas (%s).",
                           item.parceiro_nome_bruto, tentativas, motivo)

    if texto is None:
        return

    regulamento = _extrair_regulamento(texto)
    if not regulamento:
        return

    # Substitui a frase sintetica que o coletor escrevia por si mesmo pelo
    # texto real da campanha — a unica fonte da restricao.
    _aplicar_regulamento(item, regulamento)


def _do_json(dados, href_por_codigo: dict) -> PromocaoBruta | None:
    """Monta uma PromocaoBruta a partir do objeto estruturado da pagina.

    `parceiro_nome_bruto` continua vindo do slug da URL, e nao do `name` do
    JSON: ele participa do hash de deduplicacao, e trocar sua origem faria a
    coleta seguinte nao reconhecer nenhuma oferta existente.
    """
    if dados.pontuacao is None or not dados.codigo_externo:
        return None

    href = href_por_codigo.get(dados.codigo_externo) or dados.url_origem or ""
    nome = _extrair_nome_da_url(href) if "/parceiros/" in href else (dados.nome_exibicao or "")
    if not nome:
        return None

    prefixo = "Até " if dados.pontuacao_e_teto else ""
    return PromocaoBruta(
        programa_nome="Livelo",
        parceiro_nome_bruto=nome,
        titulo=f"{nome} - {prefixo}{dados.pontuacao} pontos",
        url_origem=dados.url_origem or href,
        pontuacao=dados.pontuacao,
        unidade_pontuacao=dados.unidade_pontuacao,
        regulamento_texto=dados.regulamento_texto,
        pontuacao_e_teto=dados.pontuacao_e_teto,
        pontuacao_clube=dados.pontuacao_clube,
        pontuacao_base=dados.pontuacao_base,
        codigo_externo=dados.codigo_externo,
        nome_exibicao=dados.nome_exibicao,
        em_promocao=dados.em_promocao,
        data_inicio=dados.data_inicio,
        data_fim=dados.data_fim,
        categorias=dados.categorias,
        # O cupom continua saindo do texto do regulamento: o JSON nao tem campo
        # proprio para ele.
        requer_cupom=bool(_extrair_cupom(dados.regulamento_texto or "")),
        cupom=_extrair_cupom(dados.regulamento_texto or ""),
    )


async def coletar() -> list[PromocaoBruta]:
    promocoes: list[PromocaoBruta] = []
    vistos: set[str] = set()  # evita duplicar quando ha 2 links pro mesmo parceiro na pagina

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = await browser.new_page(
            viewport={"width": 1920, "height": 1080},
            locale="pt-BR",
        )

        logger.info("Navegando até %s ...", URL_LIVELO_PARCEIROS)
        # 60s, não 30s (achado 28/08): duas falhas seguidas por timeout bem no
        # horário do wake agendado do Mac, sem causa única confirmada (não é
        # bloqueio da Livelo — reproduzido ao vivo sem problema). Mitigação
        # barata: absorver uma carga pontualmente lenta sem derrubar a coleta.
        response = await page.goto(URL_LIVELO_PARCEIROS, wait_until="domcontentloaded", timeout=60000)
        logger.info("Status HTTP: %s", response.status if response else "sem resposta")

        if not response or response.status != 200:
            logger.error("Não foi possível carregar a página (status != 200). Abortando coleta.")
            await browser.close()
            return promocoes

        await page.wait_for_timeout(3000)  # tempo para o conteúdo dinâmico terminar de renderizar

        # Caminho principal: a página embute um objeto por parceiro com tudo
        # tipado — pontuação, base, clube, teto, datas, regulamento e
        # categorias. Dispensa o regex sobre texto e a visita a ~50 páginas de
        # regras. Ver parceiros_json.py.
        html_pagina = await page.content()
        estruturados = extrair_parceiros(html_pagina)
        logger.info("JSON estruturado: %d parceiros encontrados na página.", len(estruturados))

        href_por_codigo = {}
        links = await page.locator("a[href*='/juntar-pontos/parceiros/']").all()
        for link in links:
            try:
                href = await link.get_attribute("href")
            except Exception:
                continue
            codigo = _extrair_codigo_da_url(href or "")
            if codigo and codigo not in href_por_codigo:
                href_por_codigo[codigo] = href

        if estruturados:
            for codigo, objeto in estruturados.items():
                item = _do_json(parceiro_para_bruta(objeto), href_por_codigo)
                if item is None:
                    continue
                chave = f"{item.parceiro_nome_bruto}|{item.codigo_externo}|{item.pontuacao}|{item.unidade_pontuacao}"
                if chave in vistos:
                    continue
                vistos.add(chave)
                promocoes.append(item)

            await browser.close()
            logger.info("Coleta finalizada pelo JSON: %d promoções.", len(promocoes))
            return promocoes

        logger.warning(
            "JSON estruturado não encontrado — a Livelo pode ter mudado a página. "
            "Caindo no parsing de texto renderizado."
        )

        links = await page.locator("a[href*='/juntar-pontos/parceiros/']").all()
        logger.info("Encontrados %d links de parceiros.", len(links))

        for link in links:
            try:
                href = await link.get_attribute("href")
                texto = await link.inner_text()
                # O subtitulo da variante so existe no alt da logo, entao o
                # HTML do card precisa vir junto do texto visivel.
                html = await link.inner_html()
            except Exception:
                continue
            if not href or not texto:
                continue

            item = _parsear_card(texto, href, html)
            if item is None:
                continue

            # O codigo entra na chave: sem ele, duas variantes do mesmo slug
            # com a mesma pontuacao (ex: beach-park/BPK e /BHP) seriam tratadas
            # como duplicata e uma sumiria em silencio.
            chave = f"{item.parceiro_nome_bruto}|{item.codigo_externo}|{item.pontuacao}|{item.unidade_pontuacao}"
            if chave in vistos:
                continue
            vistos.add(chave)
            promocoes.append(item)

        com_campanha = [item for item in promocoes if item.buscar_detalhe]
        logger.info(
            "Buscando regulamento de %d ofertas com campanha ativa (de %d).",
            len(com_campanha), len(promocoes),
        )
        for indice, item in enumerate(com_campanha, start=1):
            await enriquecer_com_detalhe(page, item)
            if indice % 10 == 0:
                logger.info("  %d/%d detalhes visitados", indice, len(com_campanha))

        await browser.close()

    logger.info("Coleta finalizada: %d promoções extraídas (após remover duplicatas).", len(promocoes))
    return promocoes


async def enviar_para_api(promocoes: list[PromocaoBruta]) -> dict:
    enviados, falhas, descartados = 0, 0, 0

    async with httpx.AsyncClient(timeout=30.0, headers=HEADERS) as client:
        for p in promocoes:
            payload = {
                "programa_nome": p.programa_nome,
                "parceiro_nome_bruto": p.parceiro_nome_bruto,
                "titulo": p.titulo,
                "url_origem": p.url_origem,
                "pontuacao": str(p.pontuacao),
                "unidade_pontuacao": p.unidade_pontuacao,
                "regulamento_texto": p.regulamento_texto,
                "requer_clube": p.requer_clube,
                "qual_clube": p.qual_clube,
                "requer_cupom": p.requer_cupom,
                "cupom": p.cupom,
                "pontuacao_e_teto": p.pontuacao_e_teto,
                "pontuacao_clube": str(p.pontuacao_clube) if p.pontuacao_clube is not None else None,
                "codigo_externo": p.codigo_externo,
                "nome_exibicao": p.nome_exibicao,
                "pontuacao_base": str(p.pontuacao_base) if p.pontuacao_base is not None else None,
                "categorias": p.categorias or [],
                "pontuacao_anterior": str(p.pontuacao_anterior) if p.pontuacao_anterior is not None else None,
                "em_promocao": p.em_promocao,
                "data_inicio": p.data_inicio.isoformat() if p.data_inicio else None,
                "data_fim": p.data_fim.isoformat() if p.data_fim else None,
                "origem_detalhe": "COLETOR_NATIVO_LIVELO",
            }
            try:
                resposta = await client.post(API_INGERIR_URL, json=payload)
                if resposta.status_code == 200:
                    corpo = resposta.json()
                    if corpo is None:
                        descartados += 1
                    else:
                        enviados += 1
                else:
                    falhas += 1
                    logger.warning(
                        "Falha ao enviar '%s': HTTP %s - %s",
                        p.parceiro_nome_bruto, resposta.status_code, resposta.text[:200],
                    )
            except httpx.RequestError as e:
                falhas += 1
                logger.error("Erro de conexão ao enviar '%s': %s", p.parceiro_nome_bruto, e)

    logger.info(
        "Envio concluído: %d criadas, %d descartadas (duplicata/parceiro não cadastrado), %d falhas.",
        enviados, descartados, falhas,
    )
    return {"criadas": enviados, "descartadas": descartados, "falhas": falhas}


async def _reportar_execucao(status: str, **campos) -> None:
    """Registra o resultado desta execução pro Painel de Saúde.

    Nunca deve derrubar a coleta: se a própria API estiver fora do ar, é
    exatamente o cenário que o painel deveria estar avisando, então uma falha
    aqui só é logada, não propagada.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=HEADERS) as client:
            await client.post(API_EXECUCOES_URL, json={"job": JOB, "status": status, **campos})
    except httpx.RequestError as e:
        logger.warning("Não foi possível registrar a execução no Painel de Saúde: %s", e)


async def main():
    try:
        promocoes = await coletar()
    except Exception as e:
        logger.exception("Coleta falhou.")
        await _reportar_execucao("FALHA", erro=str(e)[:500])
        sys.exit(1)

    if not promocoes:
        logger.warning("Nenhuma promoção coletada — verifique se o site está acessível e sem bloqueio.")
        await _reportar_execucao("FALHA", erro="Nenhuma promoção coletada")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"AMOSTRA (10 primeiras de {len(promocoes)}):")
    print(f"{'='*70}")
    for item in promocoes[:10]:
        print(f"  {item.parceiro_nome_bruto:30s} {item.pontuacao:>6} {item.unidade_pontuacao}")
    print()

    resultado = await enviar_para_api(promocoes)
    await _reportar_execucao("SUCESSO", **resultado)


if __name__ == "__main__":
    asyncio.run(main())