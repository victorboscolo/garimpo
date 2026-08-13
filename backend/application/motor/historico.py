"""Busca o histórico da família (parceiro_id + programa_id) e aplica peso
temporal, seguindo as decisões da auditoria (Cap. 3 Rev. 2, RN-008/RN-009).

Família histórica = (parceiro_id, programa_id), sempre automática.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application.configuracoes_service import resolver_configuracao
from domain.promocoes import Promocao


@dataclass
class HistoricoFamilia:
    media_ponderada: Decimal | None
    maior_valor_historico: Decimal | None
    total_campanhas_janela: int
    confianca_historica: str  # ALTA | MEDIA | BAIXA
    amostras: list[tuple[Decimal, float]] = field(default_factory=list)  # (pontuacao, peso)


async def obter_historico_familia(
    db: AsyncSession,
    parceiro_id: uuid.UUID,
    programa_id: uuid.UUID,
    dominio_id: uuid.UUID | None = None,
    excluir_promocao_id: uuid.UUID | None = None,
) -> HistoricoFamilia:
    """Retorna o histórico ponderado da família, com nível de confiança.

    Regra (RN-009 / decisão da auditoria): histórico "suficiente" = mínimo
    de N campanhas dentro da janela configurada (default 3 campanhas / 365
    dias). Abaixo disso, confianca_historica = BAIXA (o fallback para
    parceiro/mercado, quando implementado, deve ser acionado pelo chamador).
    """
    limiar = await resolver_configuracao(db, "historico_suficiente", dominio_id=dominio_id, programa_id=programa_id, parceiro_id=parceiro_id)
    limiar = limiar or {"min_campanhas": 3, "janela_dias": 365}

    peso_temporal = await resolver_configuracao(db, "peso_temporal", dominio_id=dominio_id, programa_id=programa_id, parceiro_id=parceiro_id)
    peso_temporal = peso_temporal or {
        "recente_dias": 180, "recente_peso": 1.0,
        "medio_dias": 365, "medio_peso": 0.6,
        "antigo_peso": 0.3,
    }

    janela_inicio = datetime.now(timezone.utc) - timedelta(days=limiar["janela_dias"])

    stmt = select(Promocao).filter_by(parceiro_id=parceiro_id, programa_id=programa_id)
    stmt = stmt.filter(Promocao.created_at >= janela_inicio)
    stmt = stmt.filter(Promocao.status.in_(["APROVADA", "PUBLICADA"]))
    if excluir_promocao_id is not None:
        stmt = stmt.filter(Promocao.id != excluir_promocao_id)

    resultado = await db.execute(stmt)
    campanhas = resultado.scalars().all()

    total = len(campanhas)
    if total == 0:
        return HistoricoFamilia(
            media_ponderada=None,
            maior_valor_historico=None,
            total_campanhas_janela=0,
            confianca_historica="BAIXA",
        )

    agora = datetime.now(timezone.utc)
    amostras: list[tuple[Decimal, float]] = []
    for campanha in campanhas:
        dias_atras = (agora - campanha.created_at).days
        if dias_atras <= peso_temporal["recente_dias"]:
            peso = peso_temporal["recente_peso"]
        elif dias_atras <= peso_temporal["medio_dias"]:
            peso = peso_temporal["medio_peso"]
        else:
            peso = peso_temporal["antigo_peso"]
        amostras.append((campanha.pontuacao, peso))

    soma_ponderada = sum(float(pontuacao) * peso for pontuacao, peso in amostras)
    soma_pesos = sum(peso for _, peso in amostras)
    media_ponderada = Decimal(str(soma_ponderada / soma_pesos)) if soma_pesos > 0 else None

    maior_valor = max(pontuacao for pontuacao, _ in amostras)

    confianca = "ALTA" if total >= limiar["min_campanhas"] else "BAIXA"
    if confianca == "ALTA" and total < limiar["min_campanhas"] * 2:
        confianca = "MEDIA"

    return HistoricoFamilia(
        media_ponderada=media_ponderada,
        maior_valor_historico=maior_valor,
        total_campanhas_janela=total,
        confianca_historica=confianca,
        amostras=amostras,
    )
