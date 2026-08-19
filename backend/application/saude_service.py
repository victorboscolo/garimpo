"""Painel de Saúde: registra e avalia a execução dos jobs de infraestrutura
(coletores, recalibração, backup).

Sem isso, um coletor que parou de rodar (Mac desligado, site mudou de
estrutura, anti-robô passou a bloquear) só é percebido quando alguém nota a
ausência de ofertas novas — não há sinal ativo de falha. Cada job registra o
próprio resultado ao terminar, via POST /api/v1/execucoes; o painel lê a
última execução de cada um e destaca o que está atrasado ou falhou.
"""
from datetime import datetime, timedelta, timezone

# Cada job roda numa cadência diferente (coleta é diária, recalibração é
# semanal); a janela é "cadência esperada + folga", pra não acusar atraso por
# uma execução só um pouco mais lenta que o normal. Só há entendimento
# informal dos horários reais (ver HANDOFF seção 6), por isso a folga é larga.
JANELA_POR_JOB = {
    "coletor_livelo": timedelta(hours=30),
    "coletor_esfera": timedelta(hours=30),
    "recalibracao": timedelta(days=8),
    "backup": timedelta(hours=30),
}
JANELA_PADRAO = timedelta(hours=30)


def avaliar_saude(job: str, ultima_execucao, agora: datetime | None = None) -> dict:
    """Situação de um job a partir da última execução registrada (ou None).

    `ultima_execucao` é qualquer objeto com os atributos de `Execucao`
    (status, created_at, criadas, descartadas, falhas, erro) — aceita tanto o
    modelo do ORM quanto um `SimpleNamespace` de teste, sem acoplar a lógica
    de avaliação ao SQLAlchemy.
    """
    agora = agora or datetime.now(timezone.utc)

    if ultima_execucao is None:
        return {"job": job, "situacao": "NUNCA_RODOU", "ultima_execucao": None}

    detalhe = {
        "status": ultima_execucao.status,
        "criadas": ultima_execucao.criadas,
        "descartadas": ultima_execucao.descartadas,
        "falhas": ultima_execucao.falhas,
        "erro": ultima_execucao.erro,
        "executado_em": ultima_execucao.created_at.isoformat(),
    }

    if ultima_execucao.status == "FALHA":
        return {"job": job, "situacao": "FALHA", "ultima_execucao": detalhe}

    janela = JANELA_POR_JOB.get(job, JANELA_PADRAO)
    if agora - ultima_execucao.created_at > janela:
        return {"job": job, "situacao": "ATRASADA", "ultima_execucao": detalhe}

    return {"job": job, "situacao": "OK", "ultima_execucao": detalhe}


async def registrar_execucao(
    db, job: str, status: str,
    criadas: int | None = None, descartadas: int | None = None,
    falhas: int | None = None, erro: str | None = None,
):
    from domain.governanca import Execucao

    execucao = Execucao(
        job=job, status=status, criadas=criadas, descartadas=descartadas,
        falhas=falhas, erro=erro,
    )
    db.add(execucao)
    await db.commit()
    await db.refresh(execucao)
    return execucao


async def obter_saude(db) -> list[dict]:
    """Última execução de cada job conhecido, avaliada.

    Percorre `JANELA_POR_JOB` (não os jobs que existirem no banco) para que um
    job que nunca rodou nenhuma vez ainda apareça no painel como NUNCA_RODOU,
    em vez de simplesmente não aparecer.
    """
    from sqlalchemy import select

    from domain.governanca import Execucao

    resultado = []
    for job in JANELA_POR_JOB:
        stmt = (
            select(Execucao)
            .filter_by(job=job)
            .order_by(Execucao.codigo.desc())
            .limit(1)
        )
        ultima = (await db.execute(stmt)).scalars().first()
        resultado.append(avaliar_saude(job, ultima))
    return resultado
