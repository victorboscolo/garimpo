"""Endpoints de publicação: ver a fila e disparar o lote.

A fila existe para separar duas decisões que hoje o painel colava: aprovar é
dizer "o dado está correto"; publicar é dizer "isto vale o tempo de quem lê".
Manter as duas juntas transformaria uma revisão de 40 aprovações numa rajada de
40 mensagens no canal.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from application import publicacao_service
from infrastructure.db.session import get_db

router = APIRouter()


@router.get("/fila")
async def ver_fila(tipo: str | None = None, db: AsyncSession = Depends(get_db)):
    """O que está prestes a sair, com a mensagem já montada.

    Serve para conferir o texto antes de ele existir para os outros — não há
    como despublicar no Telegram.
    """
    config = await publicacao_service.carregar_config(db)
    fila = await publicacao_service.montar_fila(db, config, tipo)
    return {
        "modo": publicacao_service.modo_efetivo(config),
        "total": len(fila),
        "itens": [
            {**item, "promocao_id": str(item["promocao_id"])} for item in fila
        ],
    }


@router.post("/despachar")
async def despachar(
    tipo: str | None = None, limite: int | None = None, db: AsyncSession = Depends(get_db)
):
    """Envia a fila. `limite` permite começar pequeno — mandar 2 mensagens e
    conferir como chegaram antes de soltar o lote inteiro.
    """
    config = await publicacao_service.carregar_config(db)
    return await publicacao_service.despachar(db, config, tipo=tipo, limite=limite)
