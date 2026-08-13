import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.schemas import PromocaoIngerirIn, PromocaoOut, PromocaoRejeitarIn
from application.ingestao_service import PromocaoBrutaIn, ingerir_promocao_bruta
from domain.promocoes import Promocao
from infrastructure.db.session import get_db

router = APIRouter()


@router.get("", response_model=list[PromocaoOut])
async def listar_promocoes(
    status: str | None = None,
    programa_id: uuid.UUID | None = None,
    parceiro_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Promocao)
    if status:
        stmt = stmt.filter_by(status=status)
    if programa_id:
        stmt = stmt.filter_by(programa_id=programa_id)
    if parceiro_id:
        stmt = stmt.filter_by(parceiro_id=parceiro_id)
    resultado = await db.execute(stmt)
    return resultado.scalars().all()


@router.get("/pendentes", response_model=list[PromocaoOut])
async def listar_pendentes(db: AsyncSession = Depends(get_db)):
    stmt = select(Promocao).filter_by(status="PENDENTE")
    resultado = await db.execute(stmt)
    return resultado.scalars().all()


@router.get("/{promocao_id}", response_model=PromocaoOut)
async def obter_promocao(promocao_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    promocao = await db.get(Promocao, promocao_id)
    if promocao is None:
        raise HTTPException(status_code=404, detail="Promoção não encontrada.")
    return promocao


@router.post("/{promocao_id}/aprovar", response_model=PromocaoOut)
async def aprovar_promocao(
    promocao_id: uuid.UUID,
    # usuario_id viria do token JWT autenticado — omitido neste esqueleto inicial
    db: AsyncSession = Depends(get_db),
):
    promocao = await db.get(Promocao, promocao_id)
    if promocao is None:
        raise HTTPException(status_code=404, detail="Promoção não encontrada.")
    if promocao.status != "PENDENTE":
        raise HTTPException(status_code=409, detail=f"Promoção está em status '{promocao.status}', não 'PENDENTE'.")

    promocao.status = "APROVADA"
    promocao.aprovada_em = datetime.now(timezone.utc)
    # TODO: promocao.aprovada_por = usuario_id_do_token
    # TODO: disparar publicacao_service.publicar(promocao.id, tipo="PUBLICO") e tipo="AVANCADO"

    await db.commit()
    await db.refresh(promocao)
    return promocao


@router.post("/{promocao_id}/rejeitar", response_model=PromocaoOut)
async def rejeitar_promocao(
    promocao_id: uuid.UUID,
    payload: PromocaoRejeitarIn,
    db: AsyncSession = Depends(get_db),
):
    promocao = await db.get(Promocao, promocao_id)
    if promocao is None:
        raise HTTPException(status_code=404, detail="Promoção não encontrada.")
    if promocao.status != "PENDENTE":
        raise HTTPException(status_code=409, detail=f"Promoção está em status '{promocao.status}', não 'PENDENTE'.")

    promocao.status = "REJEITADA"
    promocao.motivo_rejeicao = payload.motivo_rejeicao
    promocao.aprovada_em = datetime.now(timezone.utc)
    # TODO: promocao.aprovada_por = usuario_id_do_token

    await db.commit()
    await db.refresh(promocao)
    return promocao


@router.post("/ingerir", response_model=PromocaoOut | None)
async def ingerir_promocao(
    payload: PromocaoIngerirIn,
    db: AsyncSession = Depends(get_db),
):
    """Recebe uma promoção bruta de um coletor externo (ex: coletor nativo
    do Mac, que roda fora do Docker por causa de proteção anti-robô do
    site de origem). Faz dedup/resolução/classificação via o mesmo
    serviço usado pelos coletores internos.

    TODO: proteger este endpoint com autenticação (ex: chave de API
    própria para coletores, separada do JWT de usuários do painel).
    """
    bruta = PromocaoBrutaIn(
        programa_nome=payload.programa_nome,
        parceiro_nome_bruto=payload.parceiro_nome_bruto,
        titulo=payload.titulo,
        url_origem=payload.url_origem,
        pontuacao=payload.pontuacao,
        unidade_pontuacao=payload.unidade_pontuacao,
        regulamento_texto=payload.regulamento_texto,
        requer_clube=payload.requer_clube,
        qual_clube=payload.qual_clube,
        requer_cupom=payload.requer_cupom,
        cupom=payload.cupom,
    )
    promocao = await ingerir_promocao_bruta(db, bruta, payload.origem_detalhe)
    return promocao
