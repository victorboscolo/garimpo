"""Endpoints do Painel de Saúde: cada job registra o próprio resultado ao
terminar, e o painel lê o consolidado.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from application import saude_service
from infrastructure.db.session import get_db

router = APIRouter()


class ExecucaoIn(BaseModel):
    job: str
    status: str  # SUCESSO | FALHA
    criadas: int | None = None
    descartadas: int | None = None
    falhas: int | None = None
    erro: str | None = None


@router.post("/execucoes")
async def registrar_execucao(payload: ExecucaoIn, db: AsyncSession = Depends(get_db)):
    """Chamado pelo próprio job (coletor, recalibração, backup) ao terminar,
    sucesso ou falha — é o que sustenta o Painel de Saúde.
    """
    execucao = await saude_service.registrar_execucao(
        db, job=payload.job, status=payload.status,
        criadas=payload.criadas, descartadas=payload.descartadas,
        falhas=payload.falhas, erro=payload.erro,
    )
    return {"id": str(execucao.id)}


@router.get("/saude")
async def saude(db: AsyncSession = Depends(get_db)):
    return {"jobs": await saude_service.obter_saude(db)}


@router.post("/saude/verificar-atrasados")
async def verificar_atrasados(db: AsyncSession = Depends(get_db)):
    """Chamado periodicamente (scripts/verificar_saude.sh via launchd) — ver
    o porquê em `saude_service.verificar_atrasados_e_alertar`.
    """
    return await saude_service.verificar_atrasados_e_alertar(db)
