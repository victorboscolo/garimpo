"""Orquestra: coleta -> ingestão (hash/dedup/classificação via
application/ingestao_service.py, compartilhado com coletores externos).

Fluxo definido no Cap. 6. Cada execução isolada: falha em um coletor não
impede a execução dos demais nem derruba o sistema.
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from application.ingestao_service import PromocaoBrutaIn, ingerir_promocao_bruta
from coletores.base.coletor_base import ColetorBase, PromocaoBruta

logger = logging.getLogger("garimpo.coletores.pipeline")

MAX_TENTATIVAS = 3


def _converter(bruta: PromocaoBruta) -> PromocaoBrutaIn:
    return PromocaoBrutaIn(
        programa_nome=bruta.programa_nome,
        parceiro_nome_bruto=bruta.parceiro_nome_bruto,
        titulo=bruta.titulo,
        url_origem=bruta.url_origem,
        pontuacao=bruta.pontuacao,
        unidade_pontuacao=bruta.unidade_pontuacao,
        regulamento_texto=bruta.regulamento_texto,
        requer_clube=bruta.requer_clube,
        qual_clube=bruta.qual_clube,
        requer_cupom=bruta.requer_cupom,
        cupom=bruta.cupom,
    )


async def processar_coletor(coletor: ColetorBase, db: AsyncSession) -> None:
    """Executa um coletor com retry, isolado de falhas em outros coletores."""
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            brutas = await coletor.coletar()
            break
        except Exception:
            logger.exception(
                "Falha na tentativa %s/%s do coletor %s",
                tentativa, MAX_TENTATIVAS, coletor.origem_detalhe,
            )
            if tentativa == MAX_TENTATIVAS:
                logger.error("Coletor %s esgotou tentativas nesta execução.", coletor.origem_detalhe)
                return
    else:
        return

    for bruta in brutas:
        await ingerir_promocao_bruta(db, _converter(bruta), coletor.origem_detalhe)
