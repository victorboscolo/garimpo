import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from api.v1.schemas import (
    LoteResultadoOut,
    PromocaoAprovarLoteIn,
    PromocaoIngerirIn,
    PromocaoOut,
    PromocaoRejeitarIn,
    PromocaoRejeitarLoteIn,
)
from application.ingestao_service import PromocaoBrutaIn, ingerir_promocao_bruta
from domain.motor import ENTIDADE_PROMOCAO, Classificacao
from domain.promocoes import Promocao
from infrastructure.db.session import get_db

router = APIRouter()


def _stmt_listagem():
    """Listagem com a classificação ativa embutida e ordenada pela nota.

    O join é explícito (e não pelo lazy="joined" do relacionamento) porque a
    ordenação precisa referenciar a coluna `nota` diretamente. Promoção sem
    classificação vai para o fim da lista em vez de desaparecer — daí o
    outerjoin com NULLS LAST.
    """
    return (
        select(Promocao)
        .outerjoin(
            Classificacao,
            and_(
                Classificacao.entidade_id == Promocao.id,
                Classificacao.entidade_tipo == ENTIDADE_PROMOCAO,
                Classificacao.ativa.is_(True),
            ),
        )
        .options(contains_eager(Promocao.classificacao_ativa))
        .order_by(Classificacao.nota.desc().nullslast(), Promocao.created_at.desc())
    )


@router.get("", response_model=list[PromocaoOut])
async def listar_promocoes(
    status: str | None = None,
    programa_id: uuid.UUID | None = None,
    parceiro_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = _stmt_listagem()
    if status:
        stmt = stmt.filter(Promocao.status == status)
    if programa_id:
        stmt = stmt.filter(Promocao.programa_id == programa_id)
    if parceiro_id:
        stmt = stmt.filter(Promocao.parceiro_id == parceiro_id)
    resultado = await db.execute(stmt)
    return resultado.scalars().unique().all()


@router.get("/pendentes", response_model=list[PromocaoOut])
async def listar_pendentes(db: AsyncSession = Depends(get_db)):
    stmt = _stmt_listagem().filter(Promocao.status == "PENDENTE")
    resultado = await db.execute(stmt)
    return resultado.scalars().unique().all()


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


async def _decidir_lote(
    db: AsyncSession,
    ids: list[uuid.UUID],
    novo_status: str,
    motivo_rejeicao: str | None = None,
) -> LoteResultadoOut:
    """Aplica aprovação ou rejeição a um lote, tolerando falha parcial.

    Uma promoção que deixou de ser PENDENTE entre o carregamento da tela e o
    clique é ignorada e reportada, em vez de derrubar o lote inteiro — o
    endpoint individual devolve 409 nesse caso, o que aqui seria pior.
    """
    resultado = await db.execute(select(Promocao).filter(Promocao.id.in_(ids)))
    promocoes = resultado.scalars().unique().all()
    encontradas = {promocao.id: promocao for promocao in promocoes}

    processadas = 0
    ignoradas = []
    agora = datetime.now(timezone.utc)

    for promocao_id in ids:
        promocao = encontradas.get(promocao_id)
        if promocao is None:
            ignoradas.append({"id": promocao_id, "motivo": "Promoção não encontrada."})
            continue
        if promocao.status != "PENDENTE":
            ignoradas.append({"id": promocao_id, "motivo": f"Já estava em status '{promocao.status}'."})
            continue

        promocao.status = novo_status
        promocao.aprovada_em = agora
        if motivo_rejeicao is not None:
            promocao.motivo_rejeicao = motivo_rejeicao
        # TODO: promocao.aprovada_por = usuario_id_do_token
        processadas += 1

    await db.commit()
    return LoteResultadoOut(solicitadas=len(ids), processadas=processadas, ignoradas=ignoradas)


@router.post("/aprovar-lote", response_model=LoteResultadoOut)
async def aprovar_lote(payload: PromocaoAprovarLoteIn, db: AsyncSession = Depends(get_db)):
    """Aprova o lote e reprocessa as classificações em seguida.

    Aprovar não é um ato neutro sobre as demais promoções: desde que os pilares
    comparativos pontuam por posição na distribuição, entrar na base de
    comparação desloca todo mundo. Na primeira recalibração automática, aprovar
    26 ofertas mudou a nota de 360 das 369 e a categoria de 63.

    Sem reprocessar aqui, a fila de publicação seria montada com notas de antes
    da aprovação — e chegou a acontecer: três mensagens publicadas em 17/08
    mudaram de categoria 20 minutos depois, sem que nada no mundo tivesse
    mudado além das próprias aprovações.

    Custa ~2 segundos para as ~370 atuais, e só roda quando algo foi de fato
    aprovado.
    """
    from application.motor.servico import reclassificar_todas

    resultado = await _decidir_lote(db, payload.ids, novo_status="APROVADA")
    if resultado.processadas > 0:
        await reclassificar_todas(db)
    return resultado


@router.post("/rejeitar-lote", response_model=LoteResultadoOut)
async def rejeitar_lote(payload: PromocaoRejeitarLoteIn, db: AsyncSession = Depends(get_db)):
    return await _decidir_lote(
        db, payload.ids, novo_status="REJEITADA", motivo_rejeicao=payload.motivo_rejeicao
    )


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
        pontuacao_e_teto=payload.pontuacao_e_teto,
        pontuacao_clube=payload.pontuacao_clube,
        codigo_externo=payload.codigo_externo,
        nome_exibicao=payload.nome_exibicao,
        pontuacao_base=payload.pontuacao_base,
        categorias=payload.categorias,
        pontuacao_anterior=payload.pontuacao_anterior,
        em_promocao=payload.em_promocao,
        data_inicio=payload.data_inicio,
        data_fim=payload.data_fim,
    )
    promocao = await ingerir_promocao_bruta(db, bruta, payload.origem_detalhe)
    return promocao
