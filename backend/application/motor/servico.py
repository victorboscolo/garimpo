"""Orquestrador do Motor de Análise V1.

Combina os 6 pilares (média ponderada pelos pesos de `configuracoes`),
resolve a categoria pelas faixas configuradas, e persiste o resultado em
`classificacoes` — sempre desativando a classificação anterior da mesma
entidade (RN-002, Cap. 3 Rev. 2).
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application.configuracoes_service import resolver_configuracao
from application.motor import pilares
from application.motor.historico import obter_historico_familia
from domain.motor import ENTIDADE_PROMOCAO, Classificacao
from domain.promocoes import CategoriaPromocao, Promocao

VERSAO_MOTOR = "v1.0"

PESOS_DEFAULT = {
    "historico": 25, "atratividade": 25, "amplitude": 20,
    "facilidade": 10, "exclusividade": 10, "confiabilidade_dados": 10,
}

FAIXAS_DEFAULT = {
    "excepcional": {"min": 90, "max": 100},
    "excelente": {"min": 75, "max": 89},
    "boa": {"min": 55, "max": 74},
    "comum": {"min": 35, "max": 54},
    "pouco_atrativa": {"min": 0, "max": 34},
}


async def _media_mercado(db: AsyncSession, programa_id) -> Decimal | None:
    """Média simples de pontuação de todas as promoções aprovadas/publicadas
    do mesmo programa (proxy de 'mercado competitivo' para o pilar Atratividade).
    """
    stmt = select(Promocao.pontuacao).filter_by(programa_id=programa_id).filter(
        Promocao.status.in_(["APROVADA", "PUBLICADA"])
    )
    resultado = await db.execute(stmt)
    valores = resultado.scalars().all()
    if not valores:
        return None
    return sum(valores) / len(valores)


def _resolver_categoria(nota: float, faixas: dict) -> str:
    for chave, intervalo in faixas.items():
        if intervalo["min"] <= nota <= intervalo["max"]:
            return chave.upper()
    return "COMUM"  # fallback defensivo — nunca deve ser atingido com faixas bem configuradas


def _montar_justificativa(criterios: dict, categoria: str, confianca_historica: str) -> str:
    """Camada de Interpretação: texto simplificado que PODE cruzar critérios
    narrativamente, mesmo que a nota em si seja calculada por critérios
    independentes (decisão da auditoria original).
    """
    partes = [f"Classificada como {categoria.replace('_', ' ').title()}."]

    if criterios["atratividade"] >= 75:
        partes.append("Pontuação bem acima da média de mercado.")
    elif criterios["atratividade"] <= 35:
        partes.append("Pontuação abaixo da média de mercado.")

    if criterios["exclusividade"] >= 95:
        partes.append("Iguala ou supera o recorde histórico deste parceiro.")

    if criterios["facilidade"] < 60:
        partes.append("Possui restrições relevantes (clube, cupom ou disponibilidade limitada).")

    if confianca_historica == "BAIXA":
        partes.append("Histórico desta parceria ainda é limitado — avaliação com menor precisão comparativa.")

    return " ".join(partes)


async def classificar_promocao(db: AsyncSession, promocao: Promocao) -> Classificacao:
    """Executa o Motor V1 sobre uma promoção e persiste o resultado.

    Desativa qualquer classificação ativa anterior da mesma entidade antes
    de criar a nova (regra: apenas uma `ativa=True` por entidade).
    """
    pesos = await resolver_configuracao(
        db, "pesos_motor_v1", programa_id=promocao.programa_id, parceiro_id=promocao.parceiro_id
    ) or PESOS_DEFAULT
    faixas = await resolver_configuracao(
        db, "faixas_classificacao", programa_id=promocao.programa_id, parceiro_id=promocao.parceiro_id
    ) or FAIXAS_DEFAULT

    historico = await obter_historico_familia(
        db, parceiro_id=promocao.parceiro_id, programa_id=promocao.programa_id,
        excluir_promocao_id=promocao.id,
    )
    media_mercado = await _media_mercado(db, promocao.programa_id)

    stmt_categorias = select(CategoriaPromocao).filter_by(promocao_id=promocao.id)
    resultado_categorias = await db.execute(stmt_categorias)
    qtd_categorias = len(resultado_categorias.scalars().all())

    criterios = {
        "historico": pilares.pilar_historico(promocao, historico),
        "atratividade": pilares.pilar_atratividade(promocao, media_mercado),
        "amplitude": pilares.pilar_amplitude(promocao, qtd_categorias),
        "facilidade": pilares.pilar_facilidade(promocao),
        "exclusividade": pilares.pilar_exclusividade(promocao, historico),
        "confiabilidade_dados": pilares.pilar_confiabilidade_dados(promocao),
    }

    soma_pesos = sum(pesos.values())
    nota = sum(criterios[chave] * peso for chave, peso in pesos.items()) / soma_pesos
    nota = round(nota, 2)

    categoria = _resolver_categoria(nota, faixas)
    justificativa = _montar_justificativa(criterios, categoria, historico.confianca_historica)

    # Desativa a classificação anterior, se existir
    stmt_ativa = select(Classificacao).filter_by(
        entidade_tipo=ENTIDADE_PROMOCAO, entidade_id=promocao.id, ativa=True
    )
    resultado_ativa = await db.execute(stmt_ativa)
    anterior = resultado_ativa.scalar_one_or_none()
    if anterior is not None:
        anterior.ativa = False

    nova_classificacao = Classificacao(
        entidade_tipo=ENTIDADE_PROMOCAO,
        entidade_id=promocao.id,
        versao_motor=VERSAO_MOTOR,
        nota=Decimal(str(nota)),
        categoria=categoria,
        criterios_avaliados=criterios,
        confianca_historica=historico.confianca_historica,
        confiabilidade_dados=Decimal(str(criterios["confiabilidade_dados"])),
        justificativa=justificativa,
        ativa=True,
        processada_em=datetime.now(timezone.utc),
    )
    db.add(nova_classificacao)
    await db.flush()

    return nova_classificacao
