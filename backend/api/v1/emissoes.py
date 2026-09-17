"""Endpoints do Garimpo Emissões: rotas monitoradas e ofertas coletadas.

Sem motor nem aprovação automática — ver application/emissoes_service.py.
"""
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from application import emissoes_service
from infrastructure.db.session import get_db

router = APIRouter()


class OfertaEmissaoIn(BaseModel):
    programa_nome: str
    origem: str
    destino: str
    data_ida: date
    classe: str
    pontos: int
    taxa_reais: Decimal | None = None
    companhia_operadora: str | None = None
    paradas: int | None = None
    assentos_restantes: int | None = None
    duracao_texto: str | None = None


@router.post("/ofertas")
async def registrar_oferta(payload: OfertaEmissaoIn, db: AsyncSession = Depends(get_db)):
    """Chamado pelo coletor a cada rota+data+classe pesquisada (uma perna,
    só ida) — só a oferta mais barata encontrada, não a lista inteira de
    voos.
    """
    rota = await emissoes_service.resolver_rota(db, payload.programa_nome, payload.origem, payload.destino)
    if rota is None:
        raise HTTPException(
            status_code=404,
            detail=f"Rota {payload.origem}-{payload.destino} não cadastrada para '{payload.programa_nome}'.",
        )

    oferta = await emissoes_service.registrar_oferta(
        db, rota_id=rota.id, data_ida=payload.data_ida, classe=payload.classe, pontos=payload.pontos,
        taxa_reais=payload.taxa_reais, companhia_operadora=payload.companhia_operadora,
        paradas=payload.paradas, assentos_restantes=payload.assentos_restantes,
        duracao_texto=payload.duracao_texto,
    )
    return {"id": str(oferta.id)}


@router.get("/ofertas")
async def ofertas_atuais(programa_nome: str | None = None, db: AsyncSession = Depends(get_db)):
    """O retrato de agora, pro painel: a oferta mais recente de cada rota,
    separada em direto/com-parada. Não é o histórico inteiro — ver
    `emissoes_service.listar_ofertas_atuais`.
    """
    return await emissoes_service.listar_ofertas_atuais(db, programa_nome)


@router.get("/rotas")
async def rotas(programa_nome: str | None = None, db: AsyncSession = Depends(get_db)):
    """Catálogo de rotas ativas — o que o coletor deve pesquisar."""
    rotas = await emissoes_service.listar_rotas_ativas(db, programa_nome)
    return [
        {
            "id": str(r.id), "origem": r.origem, "destino": r.destino, "fonte": r.fonte,
        }
        for r in rotas
    ]
