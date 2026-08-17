"""Serviço de ingestão de promoções brutas (vindas de qualquer coletor —
interno via Docker, ou externo via HTTP, como o coletor nativo do Mac).

Centraliza a regra: hash/dedup -> resolução de programa/parceiro -> criação
da Promocao -> acionamento do Motor de Análise. Usado tanto por
coletores/pipeline.py (coletores internos) quanto pelo endpoint
POST /promocoes/ingerir (coletores externos, ex: coletor nativo Livelo).
"""
import hashlib
import logging
from datetime import datetime
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from application.condicoes import (
    PADRAO_FRASE_DO_COLETOR,
    resolver_marketplace,
    valor_e_condicionado,
)
from application.motor.servico import classificar_promocao
from domain.cadastros import CategoriaOrigem, Marca, Parceiro, ParceiroCategoria, Programa
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
    pontuacao_clube: Decimal | None = None
    codigo_externo: str | None = None
    nome_exibicao: str | None = None
    pontuacao_base: Decimal | None = None
    categorias: list[str] | None = None
    pontuacao_anterior: Decimal | None = None
    em_promocao: bool = False
    data_inicio: datetime | None = None
    data_fim: datetime | None = None


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
        str(bruta.pontuacao_clube),
        bruta.unidade_pontuacao,
        str(bruta.requer_clube),
        str(bruta.qual_clube),
        str(bruta.requer_cupom),
        str(bruta.cupom),
    ])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _completar_dados_da_campanha(existente: Promocao, bruta: PromocaoBrutaIn) -> bool:
    """Preenche em uma promoção já existente os dados de campanha que só
    passamos a coletar depois que ela foi gravada. Devolve True se mudou algo.

    Exceção deliberada e estreita à imutabilidade da promoção (RN-001). A regra
    continua valendo para o conteúdo da oferta: mudança de pontuação, cupom,
    clube ou variante altera o hash e cria registro novo, nunca sobrescreve.

    O que se preenche aqui é diferente — são campos que a oferta sempre teve e
    nós é que não estávamos capturando, porque o coletor só lia a listagem. Sem
    isso, as campanhas já gravadas nunca receberiam seu regulamento: o hash não
    muda (regulamento e datas não entram nele), então a promoção seria
    descartada como duplicata e o texto buscado na página de detalhe se perderia.

    Só preenche o que está vazio. Nada aqui sobrescreve valor já existente.
    """
    mudou = False

    if bruta.regulamento_texto and not _tem_regulamento_real(existente.regulamento_texto):
        existente.regulamento_texto = bruta.regulamento_texto
        mudou = True
    if bruta.data_inicio and existente.data_inicio is None:
        existente.data_inicio = bruta.data_inicio
        mudou = True
    if bruta.data_fim and existente.data_fim is None:
        existente.data_fim = bruta.data_fim
        mudou = True
    if bruta.pontuacao_base is not None and existente.pontuacao_base is None:
        existente.pontuacao_base = bruta.pontuacao_base
        mudou = True
    if bruta.pontuacao_anterior is not None and existente.pontuacao_anterior is None:
        existente.pontuacao_anterior = bruta.pontuacao_anterior
        mudou = True
    if bruta.em_promocao and not existente.em_promocao:
        existente.em_promocao = True
        mudou = True

    # Recalculado sempre que o regulamento chega ou muda: é leitura dos dados
    # da oferta, não fato novo, então acompanhar a melhor informação disponível
    # é o comportamento correto.
    condicionado = valor_e_condicionado(
        existente.pontuacao, existente.regulamento_texto, existente.pontuacao_e_teto
    )
    if existente.valor_condicionado != condicionado:
        existente.valor_condicionado = condicionado
        mudou = True

    marketplace = resolver_marketplace(existente.regulamento_texto)
    if marketplace is not None and existente.marketplace_status != marketplace:
        existente.marketplace_status = marketplace
        mudou = True

    return mudou


async def _sincronizar_categorias(
    db: AsyncSession, parceiro_id, programa_id, slugs: list[str] | None
) -> None:
    """Liga o parceiro às categorias que o programa de origem declara.

    Os slugs são gravados como a fonte os informa, em `categorias_origem`. O
    agrupamento canônico (`categorias_origem.categoria_id`) nasce nulo e só é
    preenchido por curadoria — assim o que veio da Livelo permanece sempre
    distinguível do que nós decidimos, e agrupar depois não exige recoletar.

    Vínculos que a fonte deixou de listar são removidos: a categoria do parceiro
    é um retrato do que o programa afirma hoje, não um acúmulo histórico.
    """
    if not slugs:
        return

    existentes = (await db.execute(
        select(CategoriaOrigem).filter_by(programa_id=programa_id).filter(CategoriaOrigem.slug.in_(slugs))
    )).scalars().all()
    por_slug = {c.slug: c for c in existentes}

    for slug in slugs:
        if slug not in por_slug:
            nova = CategoriaOrigem(programa_id=programa_id, slug=slug)
            db.add(nova)
            await db.flush()
            por_slug[slug] = nova

    desejadas = {por_slug[slug].id for slug in slugs}
    atuais = {
        v.categoria_origem_id
        for v in (await db.execute(
            select(ParceiroCategoria).filter_by(parceiro_id=parceiro_id)
        )).scalars().all()
    }

    for categoria_origem_id in desejadas - atuais:
        db.add(ParceiroCategoria(parceiro_id=parceiro_id, categoria_origem_id=categoria_origem_id))
    for obsoleta in atuais - desejadas:
        await db.execute(
            delete(ParceiroCategoria).where(
                ParceiroCategoria.parceiro_id == parceiro_id,
                ParceiroCategoria.categoria_origem_id == obsoleta,
            )
        )


def _tem_regulamento_real(texto: str | None) -> bool:
    """O coletor antigo gravava uma frase sobre si mesmo ("Coletado do site
    oficial da Livelo...") em `regulamento_texto`. Isso não é regulamento e
    pode ser substituído pelo texto real da campanha.

    Antes verificava a presença de "campanha válida" — frase específica da
    Livelo que a Esfera nunca usa (0 dos 168 regulamentos reais dela contêm
    isso). Todo regulamento genuíno da Esfera parecia "não real": no painel,
    o card nunca mostrava o bloco de regulamento em destaque, e no backend
    toda coleta duplicada reescrevia o campo à toa. A checagem certa é o
    oposto — só não é real quando bate o padrão do placeholder antigo.
    """
    return bool(texto) and not PADRAO_FRASE_DO_COLETOR.match(texto.strip())


async def ingerir_promocao_bruta(
    db: AsyncSession, bruta: PromocaoBrutaIn, origem_detalhe: str
) -> Promocao | None:
    """Processa uma promoção bruta vinda de qualquer coletor.

    Retorna a Promocao criada, ou None se foi descartada (duplicata,
    programa/parceiro não cadastrado).
    """
    hash_calculado = calcular_hash(bruta)

    # `.first()` e não `.scalar_one_or_none()`: o hash não tem constraint de
    # unicidade e pode repetir legitimamente — uma correção de dado ou uma
    # oferta que volta ao valor anterior produzem duas linhas com o mesmo
    # hash. Isso não pode derrubar a ingestão do dia inteiro.
    stmt_existente = select(Promocao).filter_by(hash_promocao=hash_calculado).limit(1)
    resultado_existente = await db.execute(stmt_existente)
    existente = resultado_existente.scalars().first()
    if existente is not None:
        mudou = _completar_dados_da_campanha(existente, bruta)
        # O parceiro também é atualizado no caminho da duplicata: a imensa
        # maioria das coletas cai aqui, e sem isto os parceiros já cadastrados
        # nunca receberiam o nome legível — ele só chegaria em parceiro novo.
        #
        # O nome é sincronizado com a origem, não apenas preenchido quando
        # vazio: a Livelo é a fonte da verdade para como o parceiro se chama, e
        # uma renomeação lá deve chegar aqui. A contrapartida é que renomear à
        # mão no banco não se sustenta — a coleta seguinte devolve o nome da
        # origem. Um nome próprio, editável, precisaria de campo separado.
        if bruta.nome_exibicao:
            parceiro_existente = await db.get(Parceiro, existente.parceiro_id)
            if parceiro_existente is not None and parceiro_existente.nome_exibicao != bruta.nome_exibicao:
                parceiro_existente.nome_exibicao = bruta.nome_exibicao
                mudou = True
        if bruta.categorias:
            await _sincronizar_categorias(
                db, existente.parceiro_id, existente.programa_id, bruta.categorias
            )
            mudou = True
        if mudou:
            await db.commit()
            logger.info("Promoção já existente (hash=%s), dados complementados.", hash_calculado)
        else:
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
            nome_exibicao=bruta.nome_exibicao,
        )
        db.add(parceiro)
        await db.flush()
        logger.info("Parceiro '%s' cadastrado automaticamente (primeira ocorrência).", bruta.parceiro_nome_bruto)
    elif bruta.nome_exibicao and not parceiro.nome_exibicao:
        # Preenche o nome legível em parceiros já cadastrados antes de
        # passarmos a capturar o alt da logo. Só quando está vazio: curadoria
        # manual futura não pode ser sobrescrita pela coleta.
        parceiro.nome_exibicao = bruta.nome_exibicao

    await _sincronizar_categorias(db, parceiro.id, programa.id, bruta.categorias)

    nova_promocao = Promocao(
        programa_id=programa.id,
        parceiro_id=parceiro.id,
        titulo=bruta.titulo,
        url_origem=bruta.url_origem,
        regulamento_texto=bruta.regulamento_texto,
        pontuacao=bruta.pontuacao,
        unidade_pontuacao=bruta.unidade_pontuacao,
        pontuacao_e_teto=bruta.pontuacao_e_teto,
        pontuacao_clube=bruta.pontuacao_clube,
        pontuacao_base=bruta.pontuacao_base,
        pontuacao_anterior=bruta.pontuacao_anterior,
        em_promocao=bruta.em_promocao,
        valor_condicionado=valor_e_condicionado(
            bruta.pontuacao, bruta.regulamento_texto, bruta.pontuacao_e_teto
        ),
        marketplace_status=resolver_marketplace(bruta.regulamento_texto),
        data_inicio=bruta.data_inicio,
        data_fim=bruta.data_fim,
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

    classificacao = await classificar_promocao(db, nova_promocao)
    # Mesmo motivo dos relacionamentos acima: `classificacao_ativa` faz parte
    # da resposta da API, e sem preencher aqui o Pydantic tentaria carregá-la
    # sob demanda ao serializar — lazy-load que estoura em sessão assíncrona.
    # `set_committed_value` popula sem marcar alteração (a relação é viewonly).
    set_committed_value(nova_promocao, "classificacao_ativa", classificacao)

    await db.commit()

    logger.info("Promoção criada e classificada: id=%s origem=%s", nova_promocao.id, origem_detalhe)
    return nova_promocao
