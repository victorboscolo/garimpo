"""Endpoints de publicação: ver a fila e disparar o lote.

A fila existe para separar duas decisões que hoje o painel colava: aprovar é
dizer "o dado está correto"; publicar é dizer "isto vale o tempo de quem lê".
Manter as duas juntas transformaria uma revisão de 40 aprovações numa rajada de
40 mensagens no canal.
"""
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from application import publicacao_service
from infrastructure.db.session import get_db

router = APIRouter()


class ItemPublicacaoIn(BaseModel):
    promocao_id: uuid.UUID
    tipo: str


class DespacharIn(BaseModel):
    """Seleção a publicar. Sem `itens`, vale a fila inteira (com `limite`)."""
    itens: list[ItemPublicacaoIn] | None = None


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


@router.get("/divergencias")
async def divergencias(db: AsyncSession = Depends(get_db)):
    """Publicações cuja categoria mudou desde o envio.

    Reprocessar o motor muda notas, e o que já foi publicado não acompanha —
    não existe despublicar no Telegram. Este relatório é a única forma de saber
    que o canal passou a afirmar algo que o sistema não sustenta mais.
    """
    from application.divergencia import listar_divergencias

    itens = await listar_divergencias(db)
    return {"total": len(itens), "itens": itens}


@router.get("/diagnostico")
async def diagnostico(db: AsyncSession = Depends(get_db)):
    """Confere a configuração do Telegram sem publicar nada.

    Um erro de configuração se manifesta de forma pouco óbvia — token errado,
    bot fora do canal, bot sem permissão e ID errado falham de jeitos
    diferentes e igualmente crípticos.
    """
    from infrastructure.telegram import cliente

    config = await publicacao_service.carregar_config(db)
    canais = list((config.get("canais") or {}).keys())
    return {"canais": [await cliente.diagnosticar(tipo) for tipo in canais]}


@router.post("/despachar")
async def despachar(
    payload: DespacharIn | None = None,
    tipo: str | None = None,
    limite: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Envia a fila. `limite` permite começar pequeno — mandar 2 mensagens e
    conferir como chegaram antes de soltar o lote inteiro.
    """
    config = await publicacao_service.carregar_config(db)
    itens = [item.model_dump() for item in payload.itens] if payload and payload.itens else None
    return await publicacao_service.despachar(db, config, tipo=tipo, limite=limite, itens=itens)
