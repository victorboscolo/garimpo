"""Coletor Livelo — implementação real, baseada em inspeção do site em
07-08/08/2026 (página https://www.livelo.com.br/juntar-pontos/todos-os-parceiros).

DECISÃO DE DESIGN: extração por regex sobre o texto visível de cada card,
em vez de seletores CSS fixos. O site é renderizado via JS e as classes CSS
não são estáveis o suficiente para inspeção externa — texto visível
("X pontos por R$ Y", "Eram Z pontos") é mais resistente a mudanças de
front-end do que nomes de classe, que podem ser trocados a qualquer deploy
sem aviso.

Cada card de parceiro pode gerar até 2 PromocaoBruta: a oferta padrão e,
se existir, a oferta do Clube Livelo (requer_clube=True).

IMPORTANTE: respeitar os termos de uso e limites de acesso do site
(decisão já registrada na fundação do projeto). Este coletor faz UMA
navegação à página de listagem por execução — não faz requisições em
paralelo nem em loop agressivo.
"""
import logging
import re
from decimal import Decimal

from playwright.async_api import async_playwright

from coletores.base.coletor_base import ColetorBase, PromocaoBruta

logger = logging.getLogger("garimpo.coletores.livelo")

URL_LIVELO_PARCEIROS = "https://www.livelo.com.br/juntar-pontos/todos-os-parceiros"

# Padrões extraídos por inspeção real do site (ver docstring acima).
PADRAO_PONTOS = re.compile(r'(Até\s+)?\*{0,2}(\d+)\*{0,2}\s*pontos?\*{0,2}\s*por\s*(R\$|U\$)\s*(\d+)')
PADRAO_CLUBE = re.compile(r'Clube\s*(Até\s+)?\*{0,2}(\d+)\*{0,2}\s*pontos?\*{0,2}\s*por\s*(R\$|U\$)\s*(\d+)')
PADRAO_ERAM = re.compile(r'Eram\s+(\d+)\s*pontos?')
PADRAO_NOME = re.compile(r'(?:Nova)?(?:Promoção)?Logo\s+(.+?)(?:\*{2}|\s*Até\s)')

UNIDADE_POR_MOEDA = {"R$": "pontos_por_real", "U$": "pontos_por_dolar"}


def _extrair_codigo_parceiro(href: str) -> str | None:
    """Extrai o código de 3 letras do parceiro a partir da URL.

    Ex: '/juntar-pontos/parceiros/lojas-torra/TRA' -> 'TRA'
    """
    partes = href.rstrip("/").split("/")
    return partes[-1] if partes else None


def _parsear_card(texto: str, href: str) -> list[PromocaoBruta]:
    """Extrai 1 ou 2 PromocaoBruta (padrão + Clube, se existir) de um card."""
    resultado: list[PromocaoBruta] = []

    m_nome = PADRAO_NOME.search(texto)
    if not m_nome:
        return resultado
    nome = m_nome.group(1).strip()

    m_pontos = PADRAO_PONTOS.search(texto)
    if not m_pontos:
        return resultado
    _, valor, moeda, base = m_pontos.groups()

    m_eram = PADRAO_ERAM.search(texto)
    eram = m_eram.group(1) if m_eram else None

    descricao = (
        f"Coletado do site oficial da Livelo. Base de comparação anterior (Eram): {eram} pontos."
        if eram else "Coletado do site oficial da Livelo."
    )

    resultado.append(PromocaoBruta(
        programa_nome="Livelo",
        parceiro_nome_bruto=nome,
        titulo=f"{nome} - {valor} pontos por {moeda} {base}",
        url_origem=f"https://www.livelo.com.br{href}" if href.startswith("/") else href,
        pontuacao=Decimal(valor),
        unidade_pontuacao=UNIDADE_POR_MOEDA.get(moeda, "pontos_por_real"),
        regulamento_texto=descricao,
    ))

    m_clube = PADRAO_CLUBE.search(texto)
    if m_clube:
        _, valor_clube, moeda_clube, base_clube = m_clube.groups()
        resultado.append(PromocaoBruta(
            programa_nome="Livelo",
            parceiro_nome_bruto=nome,
            titulo=f"{nome} - {valor_clube} pontos por {moeda_clube} {base_clube} (Clube Livelo)",
            url_origem=f"https://www.livelo.com.br{href}" if href.startswith("/") else href,
            pontuacao=Decimal(valor_clube),
            unidade_pontuacao=UNIDADE_POR_MOEDA.get(moeda_clube, "pontos_por_real"),
            regulamento_texto=descricao,
            requer_clube=True,
            qual_clube="Clube Livelo",
        ))

    return resultado


class ColetorLivelo(ColetorBase):
    origem_detalhe = "COLETOR_LIVELO"

    async def coletar(self) -> list[PromocaoBruta]:
        promocoes: list[PromocaoBruta] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(URL_LIVELO_PARCEIROS, wait_until="networkidle")

            # Cada parceiro é um link para /juntar-pontos/parceiros/{slug}/{codigo}.
            links = await page.locator("a[href*='/juntar-pontos/parceiros/']").all()
            logger.info("Encontrados %d links de parceiros na página.", len(links))

            for link in links:
                try:
                    href = await link.get_attribute("href")
                    texto = await link.inner_text()
                except Exception:
                    logger.warning("Falha ao ler um card de parceiro, pulando.", exc_info=True)
                    continue

                if not href or not texto:
                    continue

                itens = _parsear_card(texto, href)
                if not itens:
                    logger.debug("Card sem padrão de pontos reconhecível: %r", texto[:80])
                promocoes.extend(itens)

            await browser.close()

        logger.info("Coleta Livelo finalizada: %d promoções extraídas.", len(promocoes))
        return promocoes
