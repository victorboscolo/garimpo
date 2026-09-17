"""Cria o `Programa` "LATAM" (domínio EMISSOES) e popula `rotas_emissao`
com o catálogo inicial — escopo pequeno de propósito (decisão do usuário,
17/09, mesmo espírito da Azul em 21/08 e da Smiles em 17/09).

Catálogo inicial: as duas rotas já testadas manualmente com sucesso na
investigação de 17/09, com a sessão autenticada (GRU->MIA, GIG->SCL).

Uso:
    docker compose exec backend python -m scripts_backfill.seed_latam
    docker compose exec backend python -m scripts_backfill.seed_latam --aplicar

Sem --aplicar, só simula e mostra o que criaria. Idempotente: pula
qualquer combinação origem+destino que já exista pro programa.
"""
import asyncio
import sys

from sqlalchemy import select

from domain.cadastros import Dominio, Programa
from domain.emissoes import RotaEmissao
from infrastructure.db.session import AsyncSessionLocal

CATALOGO_INICIAL = [
    ("GRU", "MIA", "LATAM"),
    ("GIG", "SCL", "LATAM"),
]


async def executar(aplicar: bool) -> None:
    async with AsyncSessionLocal() as db:
        programa = (await db.execute(
            select(Programa).filter_by(nome="LATAM")
        )).scalar_one_or_none()

        if programa is None:
            dominio = (await db.execute(
                select(Dominio).filter_by(nome="EMISSOES")
            )).scalar_one_or_none()
            if dominio is None:
                print("Domínio 'EMISSOES' não encontrado — rode a arquitetura de Emissões antes (migration 0010+).")
                return
            print(f"Programa 'LATAM' não existe{'  — criando' if aplicar else ' (seria criado com --aplicar)'}.")
            if aplicar:
                programa = Programa(dominio_id=dominio.id, nome="LATAM")
                db.add(programa)
                await db.flush()

        existentes: set[tuple[str, str]] = set()
        if programa is not None:
            existentes = {
                (r.origem, r.destino)
                for r in (await db.execute(
                    select(RotaEmissao).filter_by(programa_id=programa.id)
                )).scalars()
            }

        novas = [(o, d, f) for o, d, f in CATALOGO_INICIAL if (o, d) not in existentes]

        print(f"Catálogo: {len(CATALOGO_INICIAL)} rotas ({len(CATALOGO_INICIAL) - len(novas)} já existentes, {len(novas)} novas)")
        for origem, destino, fonte in novas:
            print(f"  {origem} -> {destino}  ({fonte})")
            if aplicar and programa is not None:
                db.add(RotaEmissao(programa_id=programa.id, origem=origem, destino=destino, fonte=fonte))

        if aplicar:
            await db.commit()
            print(f"\n  APLICADO — {len(novas)} rotas criadas.")
        else:
            print("\n  SIMULAÇÃO — nada foi gravado. Rode com --aplicar para valer.")


if __name__ == "__main__":
    asyncio.run(executar(aplicar="--aplicar" in sys.argv))
