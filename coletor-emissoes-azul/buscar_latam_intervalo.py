"""Busca pontual da LATAM num intervalo de datas — fora da cadência diária
do coletor agendado (`coletor_emissoes_latam.py`, que sempre busca "hoje +
30 dias").

Pedido do usuário (21/09/2026): GRU-SCL e SCL-GRU, todos os dias da
segunda quinzena de julho/2027, mostrando o mais barato em milhas por
perna. Escrito genérico (origem/destino/intervalo por argumento), não
hardcoded pra essa data — reaproveitável pra qualquer pesquisa pontual
futura do mesmo tipo.

Reaproveita a sessão logada manualmente (perfil-latam-dedicado/) e o
parser já existentes — só troca "hoje + N dias" por uma lista explícita
de datas.

Uso:
    ./venv/bin/python3 buscar_latam_intervalo.py \
        --origem GRU --destino SCL --inicio 2027-07-16 --fim 2027-07-31

    (roda as duas direções de uma vez; passe --origem/--destino uma vez
    só, o script busca origem->destino e destino->origem)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import date, datetime, timedelta

from playwright.async_api import async_playwright

from coletor_emissoes_latam import PERFIL_LATAM, buscar_latam

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("garimpo.buscar_latam_intervalo")


def _datas_no_intervalo(inicio: date, fim: date) -> list[date]:
    dias = (fim - inicio).days
    return [inicio + timedelta(days=i) for i in range(dias + 1)]


def _mais_barata(ofertas: dict) -> dict | None:
    """Entre direto e com parada, a de menor preço em milhas — é o que o
    usuário pediu ("o valor mais barato ... para cada perna"), não as duas
    categorias separadas como o coletor agendado grava.
    """
    candidatas = [o for o in (ofertas.get("direto"), ofertas.get("com_parada")) if o is not None]
    if not candidatas:
        return None
    return min(candidatas, key=lambda o: o["pontos"])


async def buscar_perna(page, origem: str, destino: str, datas: list[date]) -> dict[date, dict | None]:
    resultado: dict[date, dict | None] = {}
    for data_ida in datas:
        try:
            ofertas, _ = await buscar_latam(page, origem, destino, data_ida)
        except Exception:
            logger.exception("Falha buscando %s -> %s (%s)", origem, destino, data_ida)
            resultado[data_ida] = None
            continue
        resultado[data_ida] = _mais_barata(ofertas)
        oferta = resultado[data_ida]
        if oferta:
            logger.info("  %s -> %s %s: %s milhas (%s parada(s))", origem, destino, data_ida, oferta["pontos"], oferta["paradas"])
        else:
            logger.info("  %s -> %s %s: sem oferta.", origem, destino, data_ida)
    return resultado


def _imprimir_tabela(origem: str, destino: str, resultado: dict[date, dict | None]) -> None:
    print(f"\n{origem} -> {destino}")
    print("-" * 40)
    for data_ida, oferta in sorted(resultado.items()):
        if oferta:
            print(f"  {data_ida}  {oferta['pontos']:>7} milhas  ({oferta['paradas']} parada(s))")
        else:
            print(f"  {data_ida}  sem oferta")


async def main(origem: str, destino: str, inicio: date, fim: date) -> None:
    # Sem aquecer() aqui de propósito: este script nunca fala com a nossa
    # API (só lê o site da LATAM e imprime), diferente do coletor agendado.
    if not os.path.isdir(PERFIL_LATAM):
        logger.error(
            "Perfil %s não existe — o usuário precisa logar manualmente na LATAM "
            "nesse perfil antes de rodar esta busca.", PERFIL_LATAM,
        )
        return

    datas = _datas_no_intervalo(inicio, fim)
    logger.info("Buscando %s<->%s em %d dias (%s a %s)", origem, destino, len(datas), inicio, fim)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            PERFIL_LATAM, channel="chrome", headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1400, "height": 900}, locale="pt-BR",
        )
        page = context.pages[0] if context.pages else await context.new_page()

        ida = await buscar_perna(page, origem, destino, datas)
        volta = await buscar_perna(page, destino, origem, datas)

        await context.close()

    _imprimir_tabela(origem, destino, ida)
    _imprimir_tabela(destino, origem, volta)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--origem", required=True)
    parser.add_argument("--destino", required=True)
    parser.add_argument("--inicio", required=True, help="YYYY-MM-DD")
    parser.add_argument("--fim", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()

    asyncio.run(main(
        args.origem, args.destino,
        datetime.strptime(args.inicio, "%Y-%m-%d").date(),
        datetime.strptime(args.fim, "%Y-%m-%d").date(),
    ))
