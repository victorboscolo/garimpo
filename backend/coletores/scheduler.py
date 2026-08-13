"""Processo separado (container `scheduler` no docker-compose) que dispara
os coletores periodicamente. Roda isolado da API para que uma falha aqui
nunca derrube o backend web.
"""
import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from coletores.livelo.coletor_livelo import ColetorLivelo
from coletores.pipeline import processar_coletor
from infrastructure.db.session import AsyncSessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("garimpo.scheduler")

COLETORES = [ColetorLivelo()]


async def rodar_todos_coletores():
    async with AsyncSessionLocal() as db:
        for coletor in COLETORES:
            logger.info("Iniciando coletor: %s", coletor.origem_detalhe)
            await processar_coletor(coletor, db)


def main():
    scheduler = AsyncIOScheduler()
    # Frequência inicial: a cada 6 horas. Ajustar via configuracoes futuramente,
    # sem necessidade de alterar código (mesmo princípio dos demais parâmetros).
    scheduler.add_job(rodar_todos_coletores, "interval", hours=6)
    scheduler.start()

    logger.info("Scheduler iniciado. Aguardando execuções agendadas...")
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
