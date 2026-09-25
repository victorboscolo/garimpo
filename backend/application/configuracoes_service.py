"""Resolução hierárquica de parâmetros: PARCEIRO > PROGRAMA > DOMÍNIO > GLOBAL.

Implementa RN-011 (Cap. 3 Rev. 2): sempre usa o valor mais específico
disponível. Esta é a única forma correta de ler um parâmetro do motor —
nunca consultar `configuracoes` diretamente por fora deste serviço.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.ext.asyncio import AsyncSession

from domain.governanca import Configuracao


async def resolver_configuracao(
    db: AsyncSession,
    chave: str,
    dominio_id: uuid.UUID | None = None,
    programa_id: uuid.UUID | None = None,
    parceiro_id: uuid.UUID | None = None,
    cache=None,
) -> dict | None:
    """Retorna o `valor` (JSONB) mais específico disponível para a chave dada.

    Ordem de resolução: PARCEIRO -> PROGRAMA -> DOMÍNIO -> GLOBAL.
    Retorna None se a chave não estiver configurada em nenhum nível.

    `cache` (opcional, ver `motor/cache.py`): só o reprocessamento em lote
    passa um — evita repetir a mesma leitura a cada promoção.
    """
    candidatos = []
    if parceiro_id is not None:
        candidatos.append({"parceiro_id": parceiro_id})
    if programa_id is not None:
        candidatos.append({"programa_id": programa_id, "parceiro_id": None})
    if dominio_id is not None:
        candidatos.append({"dominio_id": dominio_id, "programa_id": None, "parceiro_id": None})
    candidatos.append({"dominio_id": None, "programa_id": None, "parceiro_id": None})  # GLOBAL

    if cache is not None:
        # Em lote: a tabela é minúscula (dezenas de linhas) e não muda durante
        # o reprocessamento — lê inteira uma vez e resolve em memória, com os
        # mesmos filtros (só as colunas listadas em cada candidato) e a mesma
        # ordem de especificidade da consulta abaixo.
        async def carregar():
            return (await db.execute(select(Configuracao))).scalars().all()
        todas = await cache.obter("configuracoes", carregar)
        for filtro in candidatos:
            achadas = [
                c for c in todas
                if c.chave == chave and all(getattr(c, coluna) == valor for coluna, valor in filtro.items())
            ]
            if len(achadas) > 1:
                raise MultipleResultsFound(f"Mais de uma configuração '{chave}' para {filtro}")
            if achadas:
                return achadas[0].valor
        return None

    for filtro in candidatos:
        stmt = select(Configuracao).filter_by(chave=chave, **filtro)
        resultado = await db.execute(stmt)
        config = resultado.scalar_one_or_none()
        if config is not None:
            return config.valor

    return None
