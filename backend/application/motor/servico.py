"""Orquestrador do Motor de Análise V1.

Combina os 6 pilares (média ponderada pelos pesos de `configuracoes`),
resolve a categoria pelas faixas configuradas, e persiste o resultado em
`classificacoes` — sempre desativando a classificação anterior da mesma
entidade (RN-002, Cap. 3 Rev. 2).
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application.configuracoes_service import resolver_configuracao
from application.motor import pilares
from application.motor.historico import obter_base_comparacao, obter_historico_familia
from domain.motor import ENTIDADE_PROMOCAO, Classificacao
from domain.promocoes import CategoriaPromocao, Promocao

logger = logging.getLogger("garimpo.motor")

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


async def _mercado(db: AsyncSession, programa_id) -> list:
    """Pontuações aprovadas/publicadas do programa — o 'mercado competitivo'
    contra o qual o pilar Atratividade posiciona a oferta.

    Devolve a distribuição inteira, e não a média: a nota é a posição da oferta
    dentro dela. Ver motor/percentil.py.
    """
    stmt = select(Promocao.pontuacao).filter_by(programa_id=programa_id).filter(
        Promocao.status.in_(["APROVADA", "PUBLICADA"])
    )
    return list((await db.execute(stmt)).scalars().all())


def _resolver_categoria(nota: float, faixas: dict) -> str:
    """Resolve a categoria pela faixa de maior piso que ainda cabe na nota.

    Só o piso (`min`) decide. As faixas configuradas têm limites inteiros
    (excelente até 89, excepcional a partir de 90), mas a nota é decimal —
    comparar também contra o teto deixava 89,5 fora de todas as faixas, caindo
    no fallback. Ordenar por piso decrescente ainda torna o resultado
    independente da ordem das chaves, que vem alfabética do JSONB do banco.
    """
    for chave, intervalo in sorted(faixas.items(), key=lambda item: item[1]["min"], reverse=True):
        if nota >= intervalo["min"]:
            return chave.upper()
    return "POUCO_ATRATIVA"  # nota abaixo de todos os pisos


def _montar_justificativa(criterios: dict, categoria: str, confianca_historica: str, base=None) -> str:
    """Camada de Interpretação: texto simplificado que PODE cruzar critérios
    narrativamente, mesmo que a nota em si seja calculada por critérios
    independentes (decisão da auditoria original).
    """
    partes = [f"Classificada como {categoria.replace('_', ' ').title()}."]

    # A nota dos pilares comparativos é posição na distribuição, não razão com
    # a média — o texto precisa dizer a mesma coisa que o número mede.
    atratividade = criterios["atratividade"]
    if atratividade >= 90:
        partes.append(f"Supera {atratividade:.0f}% das ofertas do programa.")
    elif atratividade >= 75:
        partes.append(f"Melhor que {atratividade:.0f}% das ofertas do programa.")
    elif atratividade <= 35:
        partes.append(f"Abaixo de {100 - atratividade:.0f}% das ofertas do programa.")

    if criterios["exclusividade"] >= 95:
        partes.append("Iguala ou supera o recorde histórico deste parceiro.")

    if criterios["facilidade"] < 60:
        partes.append("Possui restrições relevantes (clube, cupom ou disponibilidade limitada).")

    # Dizer contra o que a oferta foi comparada é o que torna a nota audível:
    # sem isso, "Boa" é um número sem procedência.
    if base is not None:
        if base.nivel == "FAMILIA":
            partes.append(f"Comparada com o histórico do próprio parceiro ({base.total} oferta(s) aprovada(s)).")
        elif base.nivel == "SEGMENTO":
            partes.append(
                f"Sem histórico próprio: comparada com o segmento '{base.rotulo}' "
                f"({base.total} ofertas aprovadas)."
            )
        elif base.nivel == "MERCADO":
            partes.append("Sem histórico próprio nem segmento com amostra suficiente: comparada com o mercado.")
        else:
            partes.append("Sem base de comparação disponível ainda.")
    elif confianca_historica == "BAIXA":
        partes.append("Histórico desta parceria ainda é limitado — avaliação com menor precisão comparativa.")

    return " ".join(partes)


async def _parceiro_e_varejo(db: AsyncSession, parceiro_id) -> bool:
    """O parceiro tem algum vínculo curado na categoria canônica "Varejo"?

    Decisão do usuário (01/09): pra um parceiro de varejo com catálogo
    próprio amplo, a oferta não valer no marketplace (`pilar_amplitude`,
    `marketplace_status=PARCIAL`) não reduz o alcance na prática — a loja
    própria já cobre a maior parte do que se compra ali. Usa a mesma fonte
    de curadoria por vínculo que o histórico por segmento já usa
    (`ParceiroCategoria` — curadoria do parceiro vence; na ausência dela,
    cai pro padrão do slug em `categorias_origem`), não o `Parceiro.categoria_id`
    direto, que não é preenchido por nenhum fluxo hoje.
    """
    from domain.cadastros import Categoria, CategoriaOrigem, ParceiroCategoria

    vinculos = (await db.execute(
        select(ParceiroCategoria).filter_by(parceiro_id=parceiro_id)
    )).scalars().all()

    for vinculo in vinculos:
        categoria_efetiva_id = vinculo.categoria_id
        if categoria_efetiva_id is None:
            origem = await db.get(CategoriaOrigem, vinculo.categoria_origem_id)
            categoria_efetiva_id = origem.categoria_id if origem else None
        if categoria_efetiva_id is None:
            continue
        categoria = await db.get(Categoria, categoria_efetiva_id)
        if categoria is not None and categoria.nome == "Varejo":
            return True

    return False


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
    # Base do pilar Histórico, em cascata: histórico próprio -> segmento ->
    # mercado. Sem isso o pilar devolvia neutro para 223 dos 249 parceiros, que
    # não têm oferta aprovada anterior com que se comparar.
    base = await obter_base_comparacao(
        db, parceiro_id=promocao.parceiro_id, programa_id=promocao.programa_id,
        excluir_promocao_id=promocao.id,
    )
    mercado = await _mercado(db, promocao.programa_id)

    stmt_categorias = select(CategoriaPromocao).filter_by(promocao_id=promocao.id)
    resultado_categorias = await db.execute(stmt_categorias)
    qtd_categorias = len(resultado_categorias.scalars().all())

    segmento_varejo = await _parceiro_e_varejo(db, promocao.parceiro_id)

    criterios = {
        "historico": pilares.pilar_historico_com_base(promocao, base),
        "atratividade": pilares.pilar_atratividade(promocao, mercado),
        "amplitude": pilares.pilar_amplitude(promocao, qtd_categorias, segmento_varejo),
        "facilidade": pilares.pilar_facilidade(promocao),
        "exclusividade": pilares.pilar_exclusividade(promocao, historico),
        "confiabilidade_dados": pilares.pilar_confiabilidade_dados(promocao),
    }

    soma_pesos = sum(pesos.values())
    nota = sum(criterios[chave] * peso for chave, peso in pesos.items()) / soma_pesos
    nota = round(nota, 2)

    categoria = _resolver_categoria(nota, faixas)
    justificativa = _montar_justificativa(criterios, categoria, base.confianca_historica, base)

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
        confianca_historica=base.confianca_historica,
        confiabilidade_dados=Decimal(str(criterios["confiabilidade_dados"])),
        justificativa=justificativa,
        ativa=True,
        processada_em=datetime.now(timezone.utc),
    )
    db.add(nova_classificacao)
    await db.flush()

    return nova_classificacao


async def reclassificar_todas(db: AsyncSession) -> dict:
    """Reprocessa todas as promoções PENDENTES e APROVADAS.

    Existe como serviço, e não só como endpoint, porque tem mais de um
    chamador: o botão do painel, o job semanal e a aprovação em lote.

    Por que a aprovação precisa disparar isto: desde que os pilares
    comparativos passaram a pontuar por posição na distribuição, a nota deixou
    de ser propriedade da oferta e virou posição relativa. Aprovar uma promoção
    a coloca na base de comparação e desloca todas as outras — na primeira
    recalibração automática, aprovar 26 ofertas mudou a nota de 360 das 369
    existentes e a categoria de 63. Sem reprocessar no mesmo ato, a fila de
    publicação é montada com notas de antes da aprovação, e chega-se a publicar
    categoria que já não vale: três mensagens enviadas em 17/08 mudaram de
    categoria 20 minutos depois.

    REJEITADAS ficam de fora: elas não entram na base de comparação, então
    reprocessá-las não muda nada de ninguém.
    """
    promocoes = (await db.execute(
        select(Promocao).filter(Promocao.status.in_(["PENDENTE", "APROVADA"]))
    )).scalars().unique().all()

    processadas = erros = 0
    for promocao in promocoes:
        try:
            await classificar_promocao(db, promocao)
            processadas += 1
        except Exception:
            logger.exception("Falha ao reclassificar promoção %s", promocao.id)
            erros += 1
    await db.commit()

    return {"total": len(promocoes), "processadas": processadas, "erros": erros}
