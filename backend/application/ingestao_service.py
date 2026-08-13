"""Serviço de ingestão de promoções brutas (vindas de qualquer coletor —
interno via Docker, ou externo via HTTP, como o coletor nativo do Mac).

Centraliza a regra: hash/dedup -> resolução de programa/parceiro -> criação
da Promocao -> acionamento do Motor de Análise. Usado tanto por
coletores/pipeline.py (coletores internos) quanto pelo endpoint
POST /promocoes/ingerir (coletores externos, ex: coletor nativo Livelo).
"""
import hashlib
import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application.motor.servico import classificar_promocao
from domain.cadastros import Marca, Parceiro, Programa
from domain.promocoes import Promocao

logger = logging.getLogger("garimpo.application.ingestao")


@dataclass
class PromocaoBrutaIn:
    programa_nome: str
    parceiro_nome_bruto: str
    titulo: str
    url_origem: str
    pontuacao: Decimal
    unidade_pontuacao: str
    regulamento_texto: str | None = None
    requer_clube: bool = False
    qual_clube: str | None = None
    requer_cupom: bool = False
    cupom: str | None = None
    pontuacao_e_teto: bool = False
    codigo_externo: str | None = None


def calcular_hash(bruta: PromocaoBrutaIn) -> str:
    """Identidade da oferta para fins de deduplicação.

    Inclui `codigo_externo` porque duas variantes do mesmo parceiro (Beach Park
    Hotéis e Ingressos) são ofertas distintas, e `pontuacao_e_teto` porque um
    card que passa de "6 pontos" para "Até 6 pontos" mudou de significado com o
    mesmo número.

    ATENÇÃO: alterar esta fórmula invalida todos os hashes já gravados — a
    próxima coleta trataria as ofertas existentes como novas e duplicaria o
    histórico. Qualquer mudança aqui exige migration que recalcule
    `promocoes.hash_promocao` (ver 0003_variantes_e_teto).
    """
    base = "|".join([
        bruta.programa_nome,
        bruta.parceiro_nome_bruto,
        str(bruta.codigo_externo),
        str(bruta.pontuacao),
        str(bruta.pontuacao_e_teto),
        bruta.unidade_pontuacao,
        str(bruta.requer_clube),
        str(bruta.qual_clube),
        str(bruta.requer_cupom),
        str(bruta.cupom),
    ])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


async def ingerir_promocao_bruta(
    db: AsyncSession, bruta: PromocaoBrutaIn, origem_detalhe: str
) -> Promocao | None:
    """Processa uma promoção bruta vinda de qualquer coletor.

    Retorna a Promocao criada, ou None se foi descartada (duplicata,
    programa/parceiro não cadastrado).
    """
    hash_calculado = calcular_hash(bruta)

    stmt_existente = select(Promocao).filter_by(hash_promocao=hash_calculado)
    resultado_existente = await db.execute(stmt_existente)
    if resultado_existente.scalar_one_or_none() is not None:
        logger.info("Promoção já existente (hash=%s), descartando.", hash_calculado)
        return None

    stmt_programa = select(Programa).filter_by(nome=bruta.programa_nome)
    resultado_programa = await db.execute(stmt_programa)
    programa = resultado_programa.scalar_one_or_none()
    if programa is None:
        logger.error("Programa '%s' não cadastrado — descartando item.", bruta.programa_nome)
        return None

    # Identidade do parceiro = nome + código da variante. Só o nome não basta:
    # beach-park/BPK (Hotéis) e beach-park/BHP (Ingressos) têm o mesmo nome e
    # são ofertas diferentes, com históricos que não podem se misturar.
    nome_normalizado = bruta.parceiro_nome_bruto.strip().lower()
    stmt_parceiro = select(Parceiro).filter_by(
        nome_normalizado=nome_normalizado, codigo_externo=bruta.codigo_externo
    )
    resultado_parceiro = await db.execute(stmt_parceiro)
    parceiro = resultado_parceiro.scalar_one_or_none()

    if parceiro is None:
        # Cadastro automático na primeira vez que o parceiro aparece —
        # pré-cadastrar centenas de parceiros manualmente antes do MVP
        # não é viável. Marca é criada 1:1 com o parceiro como ponto de
        # partida; um admin pode reorganizar (agrupar marcas, definir
        # categoria) depois pelo painel, sem afetar o histórico já coletado.
        nova_marca = Marca(nome=bruta.parceiro_nome_bruto)
        db.add(nova_marca)
        await db.flush()

        parceiro = Parceiro(
            marca_id=nova_marca.id,
            nome=bruta.parceiro_nome_bruto,
            nome_normalizado=nome_normalizado,
            codigo_externo=bruta.codigo_externo,
        )
        db.add(parceiro)
        await db.flush()
        logger.info("Parceiro '%s' cadastrado automaticamente (primeira ocorrência).", bruta.parceiro_nome_bruto)

    nova_promocao = Promocao(
        programa_id=programa.id,
        parceiro_id=parceiro.id,
        titulo=bruta.titulo,
        url_origem=bruta.url_origem,
        regulamento_texto=bruta.regulamento_texto,
        pontuacao=bruta.pontuacao,
        unidade_pontuacao=bruta.unidade_pontuacao,
        pontuacao_e_teto=bruta.pontuacao_e_teto,
        requer_clube=bruta.requer_clube,
        qual_clube=bruta.qual_clube,
        requer_cupom=bruta.requer_cupom,
        cupom=bruta.cupom,
        status="PENDENTE",
        origem="COLETOR",
        origem_detalhe=origem_detalhe,
        hash_promocao=hash_calculado,
    )
    # Atribui os relacionamentos explicitamente (em vez de deixar carregar
    # sob demanda) — necessário porque este objeto é novo em memória, nunca
    # veio de uma consulta ao banco, e lazy-load assíncrono não pode ser
    # disparado de forma síncrona na serialização da resposta da API.
    nova_promocao.parceiro = parceiro
    nova_promocao.programa = programa

    db.add(nova_promocao)
    await db.flush()

    await classificar_promocao(db, nova_promocao)
    await db.commit()

    logger.info("Promoção criada e classificada: id=%s origem=%s", nova_promocao.id, origem_detalhe)
    return nova_promocao
