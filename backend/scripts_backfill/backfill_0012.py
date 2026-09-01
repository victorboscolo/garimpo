"""Backfill do piso do valor condicionado após a migration 0012.

`valor_condicionado_piso` é campo novo — nenhuma promoção existente com
`valor_condicionado=True` tem esse valor preenchido ainda, porque a coluna
não existia quando elas foram coletadas. Recalcula a partir do que já está
gravado (`pontuacao` e `regulamento_texto`), com a mesma função
(`application.condicoes.piso_do_valor_condicionado`) que o ingestão usa —
não é dado novo, é leitura do que já estava lá. Não entra no hash de
dedup (mesmo raciocínio do `valor_condicionado` original, migration 0006),
então não precisa recalcular hash nenhum.

Depois de rodar com --aplicar, vale rodar `scripts/recalibrar.sh` pra
propagar o piso pro pilar Amplitude nas classificações existentes.

Uso:
    docker compose exec backend python -m scripts_backfill.backfill_0012
    docker compose exec backend python -m scripts_backfill.backfill_0012 --aplicar
"""
import asyncio
import sys

from sqlalchemy import select

from application.condicoes import piso_do_valor_condicionado
from domain import governanca  # noqa: F401 — registra Usuario, que promocoes.aprovada_por referencia
from domain.promocoes import Promocao
from infrastructure.db.session import AsyncSessionLocal


async def executar(aplicar: bool) -> None:
    async with AsyncSessionLocal() as db:
        promocoes = (await db.execute(
            select(Promocao).filter_by(valor_condicionado=True)
        )).scalars().unique().all()

        preenchidas = 0
        for promocao in promocoes:
            piso = piso_do_valor_condicionado(promocao.pontuacao, promocao.regulamento_texto)
            if promocao.valor_condicionado_piso != piso:
                preenchidas += 1
                if aplicar:
                    promocao.valor_condicionado_piso = piso

        print(f"  promoções condicionadas: {len(promocoes)}")
        print(f"  pisos preenchidos/atualizados: {preenchidas}")

        if aplicar:
            await db.commit()
            print("\n  APLICADO. Rode scripts/recalibrar.sh pra propagar pro pilar Amplitude.")
        else:
            print("\n  SIMULAÇÃO — nada foi gravado. Rode com --aplicar para valer.")


if __name__ == "__main__":
    asyncio.run(executar(aplicar="--aplicar" in sys.argv))
