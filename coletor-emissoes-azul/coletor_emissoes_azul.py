"""Coletor de Emissões (Azul) — primeira versão, escopo pequeno de propósito.

Roda nativamente no macOS (fora do Docker), mesmo motivo do coletor da
Livelo: o `azulpelomundo` é protegido por Akamai Bot Manager e só passa
com fingerprint de navegador real (`headless=False`) — confirmado em
20/08/2026, bare `curl` e replay de cookies reais tomam 403 os dois.

Escopo desta primeira versão (decisão do usuário, 21/08: "a ideia é
começar a ver algo funcionando e verificar possíveis melhorias" — não
tentar cobrir as 107 rotas do catálogo de uma vez):
- Só um pequeno número de rotas por execução (`--limite`, padrão 2 por
  fonte), lidas do catálogo real (`GET /api/v1/emissoes/rotas`).
- Uma classe só (Economy) e uma data só por rota — a amostragem de datas
  (6 pontos entre 30-180 dias) e a cobertura de Business ficam para
  depois de validar que a costura completa funciona.
- Sem agendamento nem registro no Painel de Saúde ainda.

Cada `fonte` (SITE_PRINCIPAL | AZUL_PELO_MUNDO) tem sessão própria: a
primeira busca do grupo passa pelo formulário de verdade (aquece a
sessão — confirmado 20-21/08, buscar direto sem isso não funciona); as
seguintes usam a URL direta (`urls.py`), encadeada na mesma página.

Uso manual: ./venv/bin/python3 coletor_emissoes_azul.py [--limite N]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
from datetime import date, datetime, timedelta

import httpx
from playwright.async_api import Page, async_playwright

from parsing import extrair_mais_barata_azul_pelo_mundo
from parsing_site_principal import extrair_assentos_restantes, extrair_paradas, extrair_preco_pontos
from urls import url_azul_pelo_mundo, url_site_principal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("garimpo.coletor_emissoes_azul")

API_ROTAS_URL = "http://localhost:8000/api/v1/emissoes/rotas?programa_nome=Azul"
API_OFERTAS_URL = "http://localhost:8000/api/v1/emissoes/ofertas"

# Data-alvo do site principal: precisa cair dentro dos dois meses que o
# calendário já mostra por padrão (mês atual + seguinte), porque a
# navegação entre meses ainda não foi automatizada nesta versão (ver
# README — os botões de navegação do calendário não têm um seletor
# estável, achado 21/08).
DIAS_A_FRENTE_SITE_PRINCIPAL = 20

CLASSE = "ECONOMY"


async def _fechar_popover_beneficios(page: Page) -> None:
    """O site principal às vezes abre um popover "Benefícios Azul
    Fidelidade" ao carregar — intercepta clique se não for fechado.
    Não é garantido aparecer, por isso ignora silenciosamente se não achar.
    """
    try:
        await page.get_by_label(re.compile("fechar", re.IGNORECASE)).first.click(timeout=2000)
    except Exception:
        pass


async def _selecionar_opcao_por_prefixo(page: Page, prefixo: str) -> None:
    """Site principal: sugestões são `option`, texto começa com o código
    (ex: "REC Recife")."""
    opcoes = page.get_by_role("option")
    for _ in range(10):
        if await opcoes.count() > 0:
            break
        await page.wait_for_timeout(300)
    n = await opcoes.count()
    for i in range(n):
        texto = (await opcoes.nth(i).inner_text()).strip()
        if texto.startswith(prefixo):
            await opcoes.nth(i).click()
            return
    raise RuntimeError(f"Nenhuma opção do site principal começando com '{prefixo}'")


async def _selecionar_opcao_contendo(page: Page, trecho: str) -> None:
    """azulpelomundo: sugestões são `link`, texto contém "(CÓDIGO)"."""
    opcoes = page.get_by_role("link", name=trecho)
    for _ in range(10):
        if await opcoes.count() > 0:
            break
        await page.wait_for_timeout(300)
    if await opcoes.count() == 0:
        raise RuntimeError(f"Nenhuma opção do azulpelomundo contendo '{trecho}'")
    await opcoes.first.click()


async def _cards_site_principal(page: Page) -> list[str]:
    await page.wait_for_timeout(3000)
    return await page.eval_on_selector_all(".flight-card", "els => els.map(e => e.outerHTML)")


def _oferta_mais_barata_dos_cards(cards_html: list[str]) -> dict | None:
    melhor = None
    for html in cards_html:
        pontos = extrair_preco_pontos(html)
        if pontos is None:
            continue
        if melhor is None or pontos < melhor["pontos"]:
            melhor = {
                "pontos": pontos,
                "paradas": extrair_paradas(html),
                "assentos_restantes": extrair_assentos_restantes(html),
            }
    return melhor


async def buscar_site_principal(page: Page, origem: str, destino: str, primeira_busca: bool) -> tuple[dict | None, date]:
    """Devolve (oferta ou None, data efetivamente buscada)."""
    if primeira_busca:
        data_ida = date.today() + timedelta(days=DIAS_A_FRENTE_SITE_PRINCIPAL)
        logger.info("Site principal: aquecendo sessão com busca via formulário (%s -> %s, %s)", origem, destino, data_ida)
        await page.goto("https://www.voeazul.com.br/br/pt/home", wait_until="domcontentloaded")
        await _fechar_popover_beneficios(page)

        await page.get_by_role("combobox", name="Origem").click()
        await page.keyboard.type(origem)
        await _selecionar_opcao_por_prefixo(page, origem)

        await page.get_by_role("combobox", name="Destino").click()
        await page.keyboard.type(destino)
        await _selecionar_opcao_por_prefixo(page, destino)

        await page.locator(f'button[data-date="{data_ida.isoformat()}"]').first.click()
        await page.get_by_role("button", name="Selecionar apenas data de ida").click()

        checkbox = page.locator('input[type="checkbox"]').first
        if not await checkbox.is_checked():
            await checkbox.click()

        await page.keyboard.press("Escape")
        await page.get_by_role("button", name="Buscar passagens").click()
        await page.wait_for_load_state("domcontentloaded")
    else:
        data_ida = date.today() + timedelta(days=DIAS_A_FRENTE_SITE_PRINCIPAL)
        url = url_site_principal(origem, destino, data_ida)
        logger.info("Site principal: busca encadeada %s -> %s (%s)", origem, destino, data_ida)
        await page.goto(url, wait_until="domcontentloaded")

    cards = await _cards_site_principal(page)
    return _oferta_mais_barata_dos_cards(cards), data_ida


async def buscar_azul_pelo_mundo(page: Page, origem: str, destino: str, primeira_busca: bool) -> tuple[dict | None, date]:
    """Devolve (oferta ou None, data efetivamente buscada)."""
    if primeira_busca:
        logger.info("azulpelomundo: aquecendo sessão com busca via formulário (%s -> %s)", origem, destino)
        await page.goto("https://azulpelomundo.voeazul.com.br", wait_until="domcontentloaded")

        await page.get_by_placeholder("Selecione a origem").click()
        await page.keyboard.type(origem)
        await _selecionar_opcao_contendo(page, f"({origem})")

        await page.get_by_placeholder("Selecione o destino").click()
        await page.keyboard.type(destino)
        await _selecionar_opcao_contendo(page, f"({destino})")

        # A data de partida vem preenchida com um padrão do próprio site
        # (achado 21/08) — não navegamos calendário aqui, só lemos de
        # volta qual data ele realmente usou, da URL da resposta.
        await page.get_by_text("somente ida ou volta", exact=False).click()

        async with page.expect_response(lambda r: "/api/availability" in r.url, timeout=30000) as resp_info:
            await page.get_by_role("button", name="Buscar passagens").click()
        response = await resp_info.value
    else:
        data_ida = date.today() + timedelta(days=DIAS_A_FRENTE_SITE_PRINCIPAL)
        url = url_azul_pelo_mundo(origem, destino, data_ida, CLASSE)
        logger.info("azulpelomundo: busca encadeada %s -> %s (%s)", origem, destino, data_ida)
        async with page.expect_response(lambda r: "/api/availability" in r.url, timeout=30000) as resp_info:
            await page.goto(url, wait_until="domcontentloaded")
        response = await resp_info.value

    dados = await response.json()
    data_efetiva = _data_da_url_da_resposta(response.url)
    resultado = extrair_mais_barata_azul_pelo_mundo(dados)
    return resultado, data_efetiva


def _data_da_url_da_resposta(url: str) -> date:
    achado = re.search(r"departureDateTime=(\d{4}-\d{2}-\d{2})", url)
    if achado is None:
        return date.today() + timedelta(days=DIAS_A_FRENTE_SITE_PRINCIPAL)
    return datetime.strptime(achado.group(1), "%Y-%m-%d").date()


async def buscar_rotas(client: httpx.AsyncClient, limite: int) -> list[dict]:
    resposta = await client.get(API_ROTAS_URL)
    resposta.raise_for_status()
    todas = resposta.json()

    por_fonte: dict[str, list[dict]] = {}
    for rota in todas:
        por_fonte.setdefault(rota["fonte"], []).append(rota)

    return [rota for fonte, rotas in por_fonte.items() for rota in rotas[:limite]]


async def enviar_oferta(client: httpx.AsyncClient, rota: dict, data_ida: date, oferta: dict) -> bool:
    payload = {
        "programa_nome": "Azul",
        "origem": rota["origem"],
        "destino": rota["destino"],
        "data_ida": data_ida.isoformat(),
        "classe": CLASSE,
        "pontos": oferta["pontos"],
        "taxa_reais": oferta.get("taxa_reais"),
        "companhia_operadora": oferta.get("companhia_operadora"),
        "paradas": oferta.get("paradas"),
        "assentos_restantes": oferta.get("assentos_restantes"),
    }
    try:
        resposta = await client.post(API_OFERTAS_URL, json=payload, timeout=10.0)
    except httpx.RequestError as e:
        logger.error("Erro de conexão ao enviar %s -> %s: %s", rota["origem"], rota["destino"], e)
        return False

    if resposta.status_code == 200:
        logger.info(
            "  %s -> %s: %s pontos, %s parada(s), gravado.",
            rota["origem"], rota["destino"], oferta["pontos"], oferta.get("paradas"),
        )
        return True

    logger.warning(
        "Falha ao enviar %s -> %s: HTTP %s - %s",
        rota["origem"], rota["destino"], resposta.status_code, resposta.text[:200],
    )
    return False


async def main(limite: int) -> None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        rotas = await buscar_rotas(client, limite)

        if not rotas:
            logger.error("Nenhuma rota encontrada em rotas_emissao — rode o seed antes.")
            return

        logger.info("Rodando %d rota(s): %s", len(rotas), [f"{r['origem']}->{r['destino']}" for r in rotas])

        gravadas, sem_oferta, falhas = 0, 0, 0

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )

            for fonte, buscar in (
                ("SITE_PRINCIPAL", buscar_site_principal),
                ("AZUL_PELO_MUNDO", buscar_azul_pelo_mundo),
            ):
                rotas_da_fonte = [r for r in rotas if r["fonte"] == fonte]
                if not rotas_da_fonte:
                    continue

                page = await browser.new_page(viewport={"width": 1280, "height": 720}, locale="pt-BR")
                for indice, rota in enumerate(rotas_da_fonte):
                    try:
                        oferta, data_ida = await buscar(page, rota["origem"], rota["destino"], indice == 0)
                    except Exception:
                        logger.exception("Falha buscando %s -> %s (%s)", rota["origem"], rota["destino"], fonte)
                        falhas += 1
                        continue

                    if oferta is None:
                        logger.info("  %s -> %s: sem oferta disponível.", rota["origem"], rota["destino"])
                        sem_oferta += 1
                        continue

                    if await enviar_oferta(client, rota, data_ida, oferta):
                        gravadas += 1
                    else:
                        falhas += 1

                await page.close()

            await browser.close()

        logger.info("Concluído: %d gravadas, %d sem oferta, %d falhas.", gravadas, sem_oferta, falhas)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, default=2, help="Rotas por fonte (padrão: 2)")
    args = parser.parse_args()
    asyncio.run(main(args.limite))
