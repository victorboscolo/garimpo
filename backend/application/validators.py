"""Validação de referências polimórficas (RN-013, Cap. 3 Rev. 2).

classificacoes, arquivos e publicacoes usam entidade_tipo + entidade_id
sem FK nativa do Postgres. Esta função é a rede de segurança que substitui
a constraint de banco — deve ser chamada antes de qualquer insert nessas
3 tabelas.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.motor import ENTIDADE_EMISSAO, ENTIDADE_PROMOCAO
from domain.promocoes import Promocao


class EntidadeInvalidaError(ValueError):
    """Levantada quando entidade_id não existe para o entidade_tipo informado."""


async def validar_entidade(db: AsyncSession, entidade_tipo: str, entidade_id: uuid.UUID) -> None:
    if entidade_tipo == ENTIDADE_PROMOCAO:
        stmt = select(Promocao.id).filter_by(id=entidade_id)
    elif entidade_tipo == ENTIDADE_EMISSAO:
        # Reservado: quando o módulo Emissões existir, apontar para sua tabela principal aqui.
        raise EntidadeInvalidaError("Domínio EMISSAO ainda não implementado.")
    else:
        raise EntidadeInvalidaError(f"entidade_tipo desconhecido: {entidade_tipo}")

    resultado = await db.execute(stmt)
    if resultado.scalar_one_or_none() is None:
        raise EntidadeInvalidaError(
            f"{entidade_tipo} com id={entidade_id} não existe."
        )
