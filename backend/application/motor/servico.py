"""Orquestrador do Motor de Análise V1.

Combina os 6 pilares (média ponderada pelos pesos de `configuracoes`),
resolve a categoria pelas faixas configuradas, e persiste o resultado em
`classificacoes` — sempre desativando a classificação anterior da mesma
entidade (RN-002, Cap. 3 Rev. 2).
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from application.configuracoes_service import resolver_configuracao
from application.motor import pilares
from application.motor.cache import CacheMotor
from application.motor.historico import _aprovadas_leves, obter_base_comparacao, obter_historico_familia, vinculos_do_parceiro
from application.motor.percentil import valor_comparavel
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


async def _mercado(db: AsyncSession, programa_id, cache=None) -> list:
    """Valores comparáveis das ofertas aprovadas/publicadas do programa —
    o 'mercado competitivo' contra o qual o pilar Atratividade posiciona
    a oferta.

    Devolve a distribuição inteira, e não a média: a nota é a posição da oferta
    dentro dela. Ver motor/percentil.py.

    Usa `valor_comparavel`, não `Promocao.pontuacao` direto (achado do
    usuário, 09/09) — uma oferta condicionada não pode inflar o mercado
    com o número anunciado, quando o que qualquer comprador realmente
    recebe é o piso.
    """
    async def montar():
        linhas = await _aprovadas_leves(db, programa_id, cache)
        return [valor_comparavel(l) for l in linhas]

    if cache is None:
        return await montar()
    return await cache.obter(("mercado", programa_id), montar)


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


async def _parceiro_e_varejo(db: AsyncSession, parceiro_id, cache=None) -> bool:
    """O parceiro está classificado na categoria canônica "Varejo"?

    Decisão do usuário (01/09): pra um parceiro de varejo com catálogo
    próprio amplo, a oferta não valer no marketplace (`pilar_amplitude`,
    `marketplace_status=PARCIAL`) não reduz o alcance na prática — a loja
    própria já cobre a maior parte do que se compra ali.

    Duas fontes, nessa ordem: primeiro a curadoria por vínculo
    (`ParceiroCategoria` — mesma fonte que o histórico por segmento já usa;
    curadoria do parceiro vence, na ausência dela cai pro padrão do slug em
    `categorias_origem`); na ausência de qualquer vínculo, cai pro
    `Parceiro.categoria_id` direto — usado quando a fonte de origem não tem
    taxonomia própria pra curar (caso real: Esfera filtra o único
    `parentCategories` que a Magalu carrega por ser só o contêiner
    genérico "Lojas Parceiras", que "não classifica nada"
    — `esfera_api._categorias`). Nesses casos a classificação é uma decisão
    humana direta, não derivada de vínculo nenhum.
    """
    if cache is not None:
        return await cache.obter(("varejo", parceiro_id), lambda: _varejo_de_verdade(db, parceiro_id, cache))
    return await _varejo_de_verdade(db, parceiro_id, None)


async def _varejo_de_verdade(db: AsyncSession, parceiro_id, cache) -> bool:
    from domain.cadastros import Categoria, CategoriaOrigem, Parceiro

    async def obter(modelo, id_):
        return await (cache.obter_por_id(db, modelo, id_) if cache else db.get(modelo, id_))

    vinculos = await vinculos_do_parceiro(db, parceiro_id, cache)

    for vinculo in vinculos:
        categoria_efetiva_id = vinculo.categoria_id
        if categoria_efetiva_id is None:
            origem = await obter(CategoriaOrigem, vinculo.categoria_origem_id)
            categoria_efetiva_id = origem.categoria_id if origem else None
        if categoria_efetiva_id is None:
            continue
        categoria = await obter(Categoria, categoria_efetiva_id)
        if categoria is not None and categoria.nome == "Varejo":
            return True

    parceiro = await obter(Parceiro, parceiro_id)
    if parceiro is not None and parceiro.categoria_id is not None:
        categoria = await obter(Categoria, parceiro.categoria_id)
        if categoria is not None and categoria.nome == "Varejo":
            return True

    return False


async def classificar_promocao(db: AsyncSession, promocao: Promocao, cache: CacheMotor | None = None) -> Classificacao:
    """Executa o Motor V1 sobre uma promoção e persiste o resultado.

    Desativa qualquer classificação ativa anterior da mesma entidade antes
    de criar a nova (regra: apenas uma `ativa=True` por entidade).

    `cache` (só o lote passa um, ver `reclassificar_todas`): leituras
    repetidas entre promoções saem do cache, e o `flush` fica pro `commit`
    do lote — o resultado gravado é o mesmo.
    """
    pesos = await resolver_configuracao(
        db, "pesos_motor_v1", programa_id=promocao.programa_id, parceiro_id=promocao.parceiro_id, cache=cache
    ) or PESOS_DEFAULT
    faixas = await resolver_configuracao(
        db, "faixas_classificacao", programa_id=promocao.programa_id, parceiro_id=promocao.parceiro_id, cache=cache
    ) or FAIXAS_DEFAULT

    historico = await obter_historico_familia(
        db, parceiro_id=promocao.parceiro_id, programa_id=promocao.programa_id,
        excluir_promocao_id=promocao.id, cache=cache,
    )
    # Base do pilar Histórico, em cascata: histórico próprio -> segmento ->
    # mercado. Sem isso o pilar devolvia neutro para 223 dos 249 parceiros, que
    # não têm oferta aprovada anterior com que se comparar.
    base = await obter_base_comparacao(
        db, parceiro_id=promocao.parceiro_id, programa_id=promocao.programa_id,
        excluir_promocao_id=promocao.id, cache=cache,
    )
    mercado = await _mercado(db, promocao.programa_id, cache)

    if cache is not None and "qtd_categorias" in cache.dados:
        qtd_categorias = cache.dados["qtd_categorias"].get(promocao.id, 0)
    else:
        stmt_categorias = select(CategoriaPromocao).filter_by(promocao_id=promocao.id)
        resultado_categorias = await db.execute(stmt_categorias)
        qtd_categorias = len(resultado_categorias.scalars().all())

    segmento_varejo = await _parceiro_e_varejo(db, promocao.parceiro_id, cache)

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
    if cache is not None and "ativas" in cache.dados:
        anterior = cache.dados["ativas"].get(promocao.id)
    else:
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
    if cache is None:
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

    _, erros = await classificar_em_lote(db, promocoes)
    await db.commit()

    return {"total": len(promocoes), "processadas": len(promocoes) - erros, "erros": erros}


async def classificar_em_lote(db: AsyncSession, promocoes: list) -> tuple[list, int]:
    """Classifica várias promoções lendo os dados de comparação uma vez só.

    Sem isto, cada promoção relia o mercado, o segmento e as configurações
    do zero. Com o banco no Neon isso virou 32 min e a maior parte dos 5 GB
    mensais de transferência num único reprocessamento (24/09/2026); em
    lote, a leitura é uma por programa/segmento/parceiro (ver
    `motor/cache.py`). O resultado de cada promoção é idêntico ao de
    `classificar_promocao` sem cache — não faz `commit`, quem chama decide.

    Devolve (classificações criadas, quantidade de erros).
    """
    cache = CacheMotor()
    ids = [p.id for p in promocoes]

    contagem = (await db.execute(
        select(CategoriaPromocao.promocao_id, func.count())
        .filter(CategoriaPromocao.promocao_id.in_(ids)).group_by(CategoriaPromocao.promocao_id)
    )).all() if ids else []
    cache.dados["qtd_categorias"] = {promocao_id: n for promocao_id, n in contagem}

    ativas = (await db.execute(
        select(Classificacao).filter(
            Classificacao.entidade_tipo == ENTIDADE_PROMOCAO,
            Classificacao.ativa.is_(True),
            Classificacao.entidade_id.in_(ids),
        )
    )).scalars().all() if ids else []
    cache.dados["ativas"] = {c.entidade_id: c for c in ativas}

    criadas, erros = [], 0
    # Sem autoflush: a nota de uma promoção não depende das classificações
    # das outras (só de promoções, vínculos e configurações), então nada
    # precisa ser gravado antes do fim — o commit do chamador grava tudo em
    # lote, em vez de um INSERT/UPDATE por promoção.
    with db.no_autoflush:
        for promocao in promocoes:
            try:
                criadas.append(await classificar_promocao(db, promocao, cache))
            except Exception:
                logger.exception("Falha ao reclassificar promoção %s", promocao.id)
                erros += 1
    return criadas, erros
