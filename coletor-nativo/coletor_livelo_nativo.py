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
import re
import sys
from dataclasses import dataclass
from decimal import Decimal

import httpx
from playwright.async_api import async_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("garimpo.coletor_nativo.livelo")

URL_LIVELO_PARCEIROS = "https://www.livelo.com.br/juntar-pontos/todos-os-parceiros"
API_INGERIR_URL = "http://localhost:8000/api/v1/promocoes/ingerir"

# Padroes validados contra texto real capturado do navegador em 10/08/2026.
PADRAO_PONTOS = re.compile(r'(Até\s+)?(\d+)\s*pontos?\s*por\s*(R\$|U\$)\s*(\d+)')
PADRAO_ERAM = re.compile(r'Eram\s+(\d+)\s*pontos?')

UNIDADE_POR_MOEDA = {"R$": "pontos_por_real", "U$": "pontos_por_dolar"}


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


def _extrair_nome_da_url(href: str) -> str:
    """O nome do parceiro nao aparece no texto do card, so na URL.
    Ex: '/juntar-pontos/parceiros/casas-bahia/CSB' -> 'Casas Bahia'
    """
    partes = href.rstrip("/").split("/")
    slug = partes[-2] if len(partes) >= 2 else partes[-1]
    return slug.replace("-", " ").title()


def _parsear_card(texto: str, href: str) -> PromocaoBruta | None:
    m_pontos = PADRAO_PONTOS.search(texto)
    if not m_pontos:
        return None
    _, valor, moeda, base = m_pontos.groups()

    nome = _extrair_nome_da_url(href)

    m_eram = PADRAO_ERAM.search(texto)
    eram = m_eram.group(1) if m_eram else None
    descricao = (
        f"Coletado do site oficial da Livelo. Base de comparacao anterior (Eram): {eram} pontos."
        if eram else "Coletado do site oficial da Livelo."
    )

    url_completa = f"https://www.livelo.com.br{href}" if href.startswith("/") else href

    return PromocaoBruta(
        programa_nome="Livelo",
        parceiro_nome_bruto=nome,
        titulo=f"{nome} - {valor} pontos por {moeda} {base}",
        url_origem=url_completa,
        pontuacao=Decimal(valor),
        unidade_pontuacao=UNIDADE_POR_MOEDA.get(moeda, "pontos_por_real"),
        regulamento_texto=descricao,
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
        response = await page.goto(URL_LIVELO_PARCEIROS, wait_until="domcontentloaded", timeout=30000)
        logger.info("Status HTTP: %s", response.status if response else "sem resposta")

        if not response or response.status != 200:
            logger.error("Não foi possível carregar a página (status != 200). Abortando coleta.")
            await browser.close()
            return promocoes

        await page.wait_for_timeout(3000)  # tempo para o conteúdo dinâmico terminar de renderizar

        links = await page.locator("a[href*='/juntar-pontos/parceiros/']").all()
        logger.info("Encontrados %d links de parceiros.", len(links))

        for link in links:
            try:
                href = await link.get_attribute("href")
                texto = await link.inner_text()
            except Exception:
                continue
            if not href or not texto:
                continue

            item = _parsear_card(texto, href)
            if item is None:
                continue

            chave = f"{item.parceiro_nome_bruto}|{item.pontuacao}|{item.unidade_pontuacao}"
            if chave in vistos:
                continue
            vistos.add(chave)
            promocoes.append(item)

        await browser.close()

    logger.info("Coleta finalizada: %d promoções extraídas (após remover duplicatas).", len(promocoes))
    return promocoes


async def enviar_para_api(promocoes: list[PromocaoBruta]) -> None:
    enviados, falhas, descartados = 0, 0, 0

    async with httpx.AsyncClient(timeout=30.0) as client:
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


async def main():
    promocoes = await coletar()
    if not promocoes:
        logger.warning("Nenhuma promoção coletada — verifique se o site está acessível e sem bloqueio.")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"AMOSTRA (10 primeiras de {len(promocoes)}):")
    print(f"{'='*70}")
    for item in promocoes[:10]:
        print(f"  {item.parceiro_nome_bruto:30s} {item.pontuacao:>6} {item.unidade_pontuacao}")
    print()

    await enviar_para_api(promocoes)


if __name__ == "__main__":
    asyncio.run(main())