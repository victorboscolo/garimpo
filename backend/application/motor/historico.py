"""Busca o histórico da família (parceiro_id + programa_id) e aplica peso
temporal, seguindo as decisões da auditoria (Cap. 3 Rev. 2, RN-008/RN-009).

Família histórica = (parceiro_id, programa_id), sempre automática.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from application.configuracoes_service import resolver_configuracao
from application.motor.percentil import valor_comparavel
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
    # Recorde separado da faixa Clube Livelo (achado do usuário, 14/09, caso
    # real da Centauro: "até 10 pontos" sem clube, mas 15 pontos pra quem tem
    # Clube — o maior valor que o parceiro já ofereceu, mesmo que só nessa
    # faixa). Fica de fora de `maior_valor_historico` de propósito: um
    # recorde que exige assinatura não é a mesma coisa que um recorde aberto
    # a qualquer comprador (ver `pilar_exclusividade`).
    maior_valor_historico_clube: Decimal | None = None


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
    valores_clube: list[Decimal] = []
    for campanha in campanhas:
        dias_atras = (agora - campanha.created_at).days
        if dias_atras <= peso_temporal["recente_dias"]:
            peso = peso_temporal["recente_peso"]
        elif dias_atras <= peso_temporal["medio_dias"]:
            peso = peso_temporal["medio_peso"]
        else:
            peso = peso_temporal["antigo_peso"]
        # valor_comparavel, não campanha.pontuacao (achado do usuário,
        # 09/09): o histórico do parceiro é a régua de comparação, e uma
        # oferta condicionada ("7 pontos só na marca própria, 1 no resto")
        # não deve entrar com o número anunciado nessa régua — entra com o
        # que qualquer comprador realmente recebia garantido.
        amostras.append((valor_comparavel(campanha), peso))
        # Recorde da faixa Clube, à parte (achado do usuário, 14/09) — só
        # entram campanhas que de fato tinham faixa Clube divulgada.
        if campanha.pontuacao_clube is not None:
            valores_clube.append(campanha.pontuacao_clube)

    soma_ponderada = sum(float(pontuacao) * peso for pontuacao, peso in amostras)
    soma_pesos = sum(peso for _, peso in amostras)
    media_ponderada = Decimal(str(soma_ponderada / soma_pesos)) if soma_pesos > 0 else None

    maior_valor = max(pontuacao for pontuacao, _ in amostras)
    maior_valor_clube = max(valores_clube) if valores_clube else None

    confianca = "ALTA" if total >= limiar["min_campanhas"] else "BAIXA"
    if confianca == "ALTA" and total < limiar["min_campanhas"] * 2:
        confianca = "MEDIA"

    return HistoricoFamilia(
        media_ponderada=media_ponderada,
        maior_valor_historico=maior_valor,
        total_campanhas_janela=total,
        confianca_historica=confianca,
        amostras=amostras,
        maior_valor_historico_clube=maior_valor_clube,
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
    # A distribuição inteira, e não só a média: a nota é a posição da oferta
    # dentro dela. Ver motor/percentil.py.
    distribuicao: list = field(default_factory=list)


async def _valores_do_segmento(db: AsyncSession, categoria_origem_id, programa_id):
    """Valores comparáveis das ofertas aprovadas de um segmento bruto
    (nível de slug de origem).

    Usado quando não há curadoria por parceiro — o fallback de sempre.
    Seleciona a promoção inteira, não só `pontuacao`, porque
    `valor_comparavel` precisa também de `valor_condicionado`/
    `valor_condicionado_piso` (achado do usuário, 09/09) — uma oferta
    condicionada não entra na régua de comparação com o número anunciado.
    """
    stmt = (
        select(Promocao)
        .join(ParceiroCategoria, ParceiroCategoria.parceiro_id == Promocao.parceiro_id)
        .filter(
            ParceiroCategoria.categoria_origem_id == categoria_origem_id,
            Promocao.programa_id == programa_id,
            Promocao.status.in_(["APROVADA", "PUBLICADA"]),
        )
    )
    promocoes = (await db.execute(stmt)).scalars().all()
    return [valor_comparavel(p) for p in promocoes]


async def _valores_da_categoria(db: AsyncSession, categoria_id, programa_id):
    """Valores comparáveis das ofertas aprovadas de todo parceiro cuja
    categoria canônica efetiva (curadoria por parceiro, com fallback pro
    padrão do slug de origem) é esta — dentro do mesmo programa, nunca
    misturando Livelo com Esfera. Mesmo motivo de `_valores_do_segmento`
    pra selecionar a promoção inteira, não só `pontuacao`.
    """
    stmt = (
        select(Promocao)
        .join(ParceiroCategoria, ParceiroCategoria.parceiro_id == Promocao.parceiro_id)
        .join(CategoriaOrigem, CategoriaOrigem.id == ParceiroCategoria.categoria_origem_id)
        .filter(
            func.coalesce(ParceiroCategoria.categoria_id, CategoriaOrigem.categoria_id) == categoria_id,
            Promocao.programa_id == programa_id,
            Promocao.status.in_(["APROVADA", "PUBLICADA"]),
        )
    )
    promocoes = (await db.execute(stmt)).scalars().all()
    return [valor_comparavel(p) for p in promocoes]


# Uma única oferta anterior não é histórico: é uma coincidência. Comparar com
# ela produz razões extremas — 7 contra 3 vira "o dobro do normal" e satura o
# pilar em 100 — sem que exista base para afirmar o que é normal para o
# parceiro. Abaixo deste mínimo, o segmento é a comparação mais honesta.
MINIMO_PARA_USAR_FAMILIA = 2

# Quantidade não basta: achado do usuário, 02/09, caso real do Magalu (2
# ofertas aprovadas, mas 1 e 7 pontos — média 4, um "meio do caminho" que
# não representa nada). Comparar 5 pontos contra [1, 7] rendeu 50º
# percentil por coincidência aritmética, não por sinal real. O coeficiente
# de variação (desvio padrão / média) mede dispersão independente da
# escala — [1, 7] tem CV ≈ 75%, [5, 6] tem CV ≈ 9%. Acima do corte, a
# amostra é dispersa demais pra sustentar um padrão, e a cascata desce pro
# segmento/mercado — mesmo caminho que já existe para amostra insuficiente.
CV_MAXIMO_PARA_USAR_FAMILIA = 0.5


def _coeficiente_variacao(valores: list[Decimal]) -> float:
    """Desvio padrão populacional dividido pela média.

    Mede dispersão relativa, não absoluta — um parceiro que oscila entre 2 e
    4 pontos e um que oscila entre 20 e 40 têm a mesma variação relativa
    (50%), mesmo em escalas bem diferentes.
    """
    if not valores:
        return 0.0
    n = len(valores)
    media = sum(float(v) for v in valores) / n
    if media == 0:
        return 0.0
    variancia = sum((float(v) - media) ** 2 for v in valores) / n
    return variancia ** 0.5 / media


async def obter_base_comparacao(
    db: AsyncSession,
    parceiro_id: uuid.UUID,
    programa_id: uuid.UUID,
    excluir_promocao_id: uuid.UUID | None = None,
    minimo_segmento: int = 5,
    minimo_familia: int | None = None,
    cv_maximo_familia: float | None = None,
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

    Quantidade suficiente não basta: a amostra também precisa ser coerente
    (ver `CV_MAXIMO_PARA_USAR_FAMILIA`) — duas ofertas muito diferentes
    entre si (ex: 1 e 7 pontos) não formam um padrão, mesmo já passando do
    mínimo de quantidade. Falha nesse critério desce a cascata pro
    segmento/mercado, igual já acontece com amostra insuficiente.
    """
    limiar = await resolver_configuracao(db, "historico_suficiente", programa_id=programa_id)
    if minimo_familia is None:
        minimo_familia = (limiar or {}).get("min_para_base", MINIMO_PARA_USAR_FAMILIA)
    if cv_maximo_familia is None:
        cv_maximo_familia = (limiar or {}).get("cv_maximo_familia", CV_MAXIMO_PARA_USAR_FAMILIA)

    familia = await obter_historico_familia(
        db, parceiro_id=parceiro_id, programa_id=programa_id,
        excluir_promocao_id=excluir_promocao_id,
    )
    valores_familia = [pontuacao for pontuacao, _ in familia.amostras]
    if (
        familia.media_ponderada is not None
        and familia.total_campanhas_janela >= minimo_familia
        and _coeficiente_variacao(valores_familia) <= cv_maximo_familia
    ):
        return BaseComparacao(
            media_ponderada=familia.media_ponderada,
            total=familia.total_campanhas_janela,
            nivel="FAMILIA",
            rotulo=None,
            confianca_historica=familia.confianca_historica,
            distribuicao=valores_familia,
        )

    # Vínculos do parceiro (não só o slug — precisa da curadoria por parceiro
    # também, que mora no vínculo, não no slug).
    vinculos = (await db.execute(
        select(ParceiroCategoria).filter_by(parceiro_id=parceiro_id)
    )).scalars().all()

    candidatos = []
    fonte_por_rotulo = {}  # rotulo -> ("categoria", categoria_id) | ("origem", categoria_origem_id)
    for vinculo in vinculos:
        origem = await db.get(CategoriaOrigem, vinculo.categoria_origem_id)
        if origem is None:
            continue
        # A curadoria por parceiro vence; na ausência dela, cai pro padrão do
        # slug (`categorias_origem.categoria_id`, hoje sem uso); sem nenhuma
        # das duas, usa o slug bruto — o comportamento de sempre.
        categoria_efetiva_id = vinculo.categoria_id or origem.categoria_id
        if categoria_efetiva_id is not None:
            canonica = await db.get(Categoria, categoria_efetiva_id)
            if canonica is not None:
                total = len(await _valores_da_categoria(db, categoria_efetiva_id, programa_id))
                candidatos.append((canonica.nome, total))
                fonte_por_rotulo[canonica.nome] = ("categoria", categoria_efetiva_id)
                continue
        total = len(await _valores_do_segmento(db, origem.id, programa_id))
        candidatos.append((origem.slug, total))
        fonte_por_rotulo[origem.slug] = ("origem", origem.id)

    escolhido = escolher_segmento(candidatos, minimo=minimo_segmento)
    if escolhido is not None:
        tipo, id_escolhido = fonte_por_rotulo[escolhido]
        if tipo == "categoria":
            valores = await _valores_da_categoria(db, id_escolhido, programa_id)
        else:
            valores = await _valores_do_segmento(db, id_escolhido, programa_id)
        media = Decimal(str(sum(valores) / len(valores))) if valores else None
        return BaseComparacao(
            media_ponderada=media, total=len(valores), nivel="SEGMENTO",
            rotulo=escolhido, confianca_historica="MEDIA", distribuicao=valores,
        )

    stmt_mercado = select(Promocao).filter(
        Promocao.programa_id == programa_id,
        Promocao.status.in_(["APROVADA", "PUBLICADA"]),
    )
    promocoes_mercado = (await db.execute(stmt_mercado)).scalars().all()
    valores = [valor_comparavel(p) for p in promocoes_mercado]
    if not valores:
        return BaseComparacao(None, 0, "NENHUMA", None, "BAIXA")
    return BaseComparacao(
        media_ponderada=Decimal(str(sum(valores) / len(valores))),
        total=len(valores), nivel="MERCADO", rotulo=None, confianca_historica="BAIXA",
        distribuicao=valores,
    )
