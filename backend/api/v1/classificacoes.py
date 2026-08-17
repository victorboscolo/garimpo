import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.schemas import ClassificacaoOut
from application.motor.servico import classificar_promocao
from domain.motor import ENTIDADE_PROMOCAO, Classificacao
from domain.promocoes import Promocao
from infrastructure.db.session import get_db

router = APIRouter()


@router.get("/{promocao_id}/classificacoes", response_model=list[ClassificacaoOut])
async def listar_classificacoes(promocao_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Classificacao)
        .filter_by(entidade_tipo=ENTIDADE_PROMOCAO, entidade_id=promocao_id)
        .order_by(Classificacao.processada_em.desc())
    )
    resultado = await db.execute(stmt)
    return resultado.scalars().all()


@router.post("/{promocao_id}/reclassificar", response_model=ClassificacaoOut)
async def reclassificar_promocao(promocao_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    promocao = await db.get(Promocao, promocao_id)
    if promocao is None:
        raise HTTPException(status_code=404, detail="Promoção não encontrada.")

    classificacao = await classificar_promocao(db, promocao)
    await db.commit()
    await db.refresh(classificacao)
    return classificacao


@router.post("/reclassificar-todas")
async def reclassificar_todas(db: AsyncSession = Depends(get_db)):
    """Reprocessa todas as promoções PENDENTES ou APROVADAS com a versão
    atual do motor. Útil depois de acumular mais histórico aprovado, ou
    depois de recalibrar pesos/faixas em `configuracoes`.

    Promoções REJEITADAS não são reprocessadas (decisão já é definitiva).
    """
    from application.motor.servico import reclassificar_todas as executar

    return await executar(db)
