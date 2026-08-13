"""Resolução hierárquica de parâmetros: PARCEIRO > PROGRAMA > DOMÍNIO > GLOBAL.

Implementa RN-011 (Cap. 3 Rev. 2): sempre usa o valor mais específico
disponível. Esta é a única forma correta de ler um parâmetro do motor —
nunca consultar `configuracoes` diretamente por fora deste serviço.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.governanca import Configuracao


async def resolver_configuracao(
    db: AsyncSession,
    chave: str,
    dominio_id: uuid.UUID | None = None,
    programa_id: uuid.UUID | None = None,
    parceiro_id: uuid.UUID | None = None,
) -> dict | None:
    """Retorna o `valor` (JSONB) mais específico disponível para a chave dada.

    Ordem de resolução: PARCEIRO -> PROGRAMA -> DOMÍNIO -> GLOBAL.
    Retorna None se a chave não estiver configurada em nenhum nível.
    """
    candidatos = []
    if parceiro_id is not None:
        candidatos.append({"parceiro_id": parceiro_id})
    if programa_id is not None:
        candidatos.append({"programa_id": programa_id, "parceiro_id": None})
    if dominio_id is not None:
        candidatos.append({"dominio_id": dominio_id, "programa_id": None, "parceiro_id": None})
    candidatos.append({"dominio_id": None, "programa_id": None, "parceiro_id": None})  # GLOBAL

    for filtro in candidatos:
        stmt = select(Configuracao).filter_by(chave=chave, **filtro)
        resultado = await db.execute(stmt)
        config = resultado.scalar_one_or_none()
        if config is not None:
            return config.valor

    return None
