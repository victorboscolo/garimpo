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
from application.motor.segmento import escolher_segmento
from domain.cadastros import Categoria, CategoriaOrigem, ParceiroCategoria
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


@dataclass
class BaseComparacao:
    """Contra o que a oferta foi comparada, e com que confiança.

    O nível deixa explícito na classificação qual base sustentou a nota, em vez
    de escondê-lo atrás de um número.
    """
    media_ponderada: Decimal | None
    total: int
    nivel: str  # FAMILIA | SEGMENTO | MERCADO | NENHUMA
    rotulo: str | None  # o segmento usado, quando for o caso
    confianca_historica: str


async def _media_do_segmento(db: AsyncSession, categoria_origem_id, programa_id):
    """Média e volume das ofertas aprovadas de um segmento."""
    stmt = (
        select(Promocao.pontuacao)
        .join(ParceiroCategoria, ParceiroCategoria.parceiro_id == Promocao.parceiro_id)
        .filter(
            ParceiroCategoria.categoria_origem_id == categoria_origem_id,
            Promocao.programa_id == programa_id,
            Promocao.status.in_(["APROVADA", "PUBLICADA"]),
        )
    )
    valores = (await db.execute(stmt)).scalars().all()
    if not valores:
        return None, 0
    return Decimal(str(sum(valores) / len(valores))), len(valores)


# Uma única oferta anterior não é histórico: é uma coincidência. Comparar com
# ela produz razões extremas — 7 contra 3 vira "o dobro do normal" e satura o
# pilar em 100 — sem que exista base para afirmar o que é normal para o
# parceiro. Abaixo deste mínimo, o segmento é a comparação mais honesta.
MINIMO_PARA_USAR_FAMILIA = 2


async def obter_base_comparacao(
    db: AsyncSession,
    parceiro_id: uuid.UUID,
    programa_id: uuid.UUID,
    excluir_promocao_id: uuid.UUID | None = None,
    minimo_segmento: int = 5,
    minimo_familia: int | None = None,
) -> BaseComparacao:
    """Resolve contra o que comparar a oferta, em cascata.

    1. Histórico próprio do parceiro. É o mais informativo, porque compara a
       oferta com o que aquele mesmo parceiro já fez.
    2. Segmento, quando não há histórico próprio — o caso de 223 dos 249
       parceiros. Usa a categoria mais específica com amostra suficiente
       (ver motor/segmento.py).
    3. Mercado (o programa inteiro), como última opção.

    A comparação por segmento é mais grosseira que a por histórico próprio:
    "servicos" reúne 29 parceiros que fazem coisas bem diferentes. Por isso ela
    fica no nível 2 e a confiança cai para MEDIA quando é usada.
    """
    limiar = await resolver_configuracao(db, "historico_suficiente", programa_id=programa_id)
    if minimo_familia is None:
        minimo_familia = (limiar or {}).get("min_para_base", MINIMO_PARA_USAR_FAMILIA)

    familia = await obter_historico_familia(
        db, parceiro_id=parceiro_id, programa_id=programa_id,
        excluir_promocao_id=excluir_promocao_id,
    )
    if familia.media_ponderada is not None and familia.total_campanhas_janela >= minimo_familia:
        return BaseComparacao(
            media_ponderada=familia.media_ponderada,
            total=familia.total_campanhas_janela,
            nivel="FAMILIA",
            rotulo=None,
            confianca_historica=familia.confianca_historica,
        )

    # Categorias do parceiro, com o volume aprovado de cada uma.
    vinculos = (await db.execute(
        select(ParceiroCategoria.categoria_origem_id).filter_by(parceiro_id=parceiro_id)
    )).scalars().all()

    candidatos = []
    por_id = {}
    for categoria_origem_id in vinculos:
        _, total = await _media_do_segmento(db, categoria_origem_id, programa_id)
        origem = await db.get(CategoriaOrigem, categoria_origem_id)
        if origem is None:
            continue
        # O agrupamento canônico, quando existir, é o rótulo preferido: é a
        # decisão de curadoria sobrepondo-se ao vocabulário bruto da fonte.
        rotulo = origem.slug
        if origem.categoria_id is not None:
            canonica = await db.get(Categoria, origem.categoria_id)
            if canonica is not None:
                rotulo = canonica.nome
        candidatos.append((rotulo, total))
        por_id[rotulo] = categoria_origem_id

    escolhido = escolher_segmento(candidatos, minimo=minimo_segmento)
    if escolhido is not None:
        media, total = await _media_do_segmento(db, por_id[escolhido], programa_id)
        return BaseComparacao(
            media_ponderada=media, total=total, nivel="SEGMENTO",
            rotulo=escolhido, confianca_historica="MEDIA",
        )

    stmt_mercado = select(Promocao.pontuacao).filter(
        Promocao.programa_id == programa_id,
        Promocao.status.in_(["APROVADA", "PUBLICADA"]),
    )
    valores = (await db.execute(stmt_mercado)).scalars().all()
    if not valores:
        return BaseComparacao(None, 0, "NENHUMA", None, "BAIXA")
    return BaseComparacao(
        media_ponderada=Decimal(str(sum(valores) / len(valores))),
        total=len(valores), nivel="MERCADO", rotulo=None, confianca_historica="BAIXA",
    )
