"""Popula `rotas_emissao` com o catálogo curado do Garimpo Emissões (Azul).

Catálogo fechado com o usuário em 20/08/2026 (HANDOFF seção 5) e a
interpretação direcional confirmada em 21/08/2026: cada linha aqui é uma
perna (origem→destino), não um par — a volta, quando existir, é outra
linha, no sentido oposto.

Uso:
    docker compose exec backend python -m scripts_backfill.seed_rotas_emissao
    docker compose exec backend python -m scripts_backfill.seed_rotas_emissao --aplicar

Sem --aplicar, só simula e mostra o que criaria. Idempotente: pula
qualquer combinação origem+destino que já exista pro programa (a
constraint `uq_rota_emissao_programa_od` também garante isso no banco).
"""
import asyncio
import sys

from sqlalchemy import select

from domain.cadastros import Programa
from domain.emissoes import RotaEmissao
from infrastructure.db.session import AsyncSessionLocal

ORIGENS = ["GIG", "SDU", "GRU", "CGH", "VCP"]

# Malha própria da Azul — busca no site principal (voeazul.com.br).
NORDESTE = ["SSA", "REC", "FOR", "BPS", "MCZ", "NAT"]
SUL = ["POA", "FLN", "CWB"]
MINAS_GERAIS = ["CNF"]
INTERNACIONAL_PROPRIA = ["MCO", "LIS", "ORY"]  # Flórida, Lisboa, Paris (Orly, não CDG)

# Rede de parceiros — busca no azulpelomundo.voeazul.com.br.
INTERNACIONAL_PARCEIRO = ["LHR", "MAD", "FCO", "JFK", "MIA", "LAX"]

# GIG/SDU (Rio) x GRU/CGH/VCP (SP) — tráfego real nos dois sentidos,
# diferente das demais categorias (só ida-pra-fora dos 5 aeroportos-base).
RJ = ["GIG", "SDU"]
SP = ["GRU", "CGH", "VCP"]


def montar_catalogo() -> list[tuple[str, str, str]]:
    """Devolve a lista de (origem, destino, fonte), sem duplicatas."""
    rotas: list[tuple[str, str, str]] = []

    destinos_site_principal = NORDESTE + SUL + MINAS_GERAIS + INTERNACIONAL_PROPRIA
    for origem in ORIGENS:
        for destino in destinos_site_principal:
            rotas.append((origem, destino, "SITE_PRINCIPAL"))
        for destino in INTERNACIONAL_PARCEIRO:
            rotas.append((origem, destino, "AZUL_PELO_MUNDO"))

    for rj in RJ:
        for sp in SP:
            rotas.append((rj, sp, "SITE_PRINCIPAL"))
            rotas.append((sp, rj, "SITE_PRINCIPAL"))

    return rotas


async def executar(aplicar: bool) -> None:
    async with AsyncSessionLocal() as db:
        programa = (await db.execute(
            select(Programa).filter_by(nome="Azul")
        )).scalar_one_or_none()
        if programa is None:
            print("Programa 'Azul' não encontrado — rode a arquitetura de Emissões antes (migration 0010+).")
            return

        existentes = {
            (r.origem, r.destino)
            for r in (await db.execute(
                select(RotaEmissao).filter_by(programa_id=programa.id)
            )).scalars()
        }

        catalogo = montar_catalogo()
        novas = [(o, d, f) for o, d, f in catalogo if (o, d) not in existentes]

        print(f"Catálogo: {len(catalogo)} rotas ({len(catalogo) - len(novas)} já existentes, {len(novas)} novas)")
        for origem, destino, fonte in novas:
            print(f"  {origem} -> {destino}  ({fonte})")
            if aplicar:
                db.add(RotaEmissao(programa_id=programa.id, origem=origem, destino=destino, fonte=fonte))

        if aplicar:
            await db.commit()
            print(f"\n  APLICADO — {len(novas)} rotas criadas.")
        else:
            print("\n  SIMULAÇÃO — nada foi gravado. Rode com --aplicar para valer.")


if __name__ == "__main__":
    asyncio.run(executar(aplicar="--aplicar" in sys.argv))
