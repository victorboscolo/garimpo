"""Agendador em processo separado. NÃO ESTÁ EM USO desde 14/08/2026.

Foi desligado por dois motivos que se somavam. Ele disparava `ColetorLivelo`, o
coletor que roda dentro do Docker e é bloqueado pela proteção anti-robô da
Livelo com HTTP 403 — ou seja, executava código que não podia dar certo. E,
mesmo isso, ele não executava: rodando em container, perdia as execuções sempre
que o Mac dormia, acumulando avisos de "run time was missed by 3:17:28" por
dias seguidos.

O que de fato roda está no `launchd` do macOS, que recupera execuções perdidas
ao acordar: a coleta diária (`coletor-nativo/com.garimpo.coletor-livelo.plist`)
e a recalibração semanal (`scripts/com.garimpo.recalibrar.plist`).

O arquivo permanece porque a estrutura serve a um coletor futuro que consiga
rodar dentro do container — a Esfera, por exemplo, se não tiver a mesma
proteção. Para religar, é preciso recriar o serviço no docker-compose e resolver
antes o problema das execuções perdidas.
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
