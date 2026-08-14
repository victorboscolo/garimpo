"""Decide o que publicar, para qual canal, e registra cada envio.

Fronteira do Cap. 6: o módulo Telegram nunca toca em `promocoes` — consome este
serviço. Adicionar um público novo é acrescentar um canal na configuração e um
template de mensagem, sem mexer aqui.

## Modo de publicação

A configuração vive em `configuracoes`, chave `publicacao`, com a mesma
hierarquia GLOBAL → DOMÍNIO → PROGRAMA → PARCEIRO usada pelos pesos e faixas do
motor. Trocar o comportamento é editar dado, não código.

`modo` admite dois valores:

- MANUAL: as aprovadas entram numa fila e um humano dispara o lote. É o modo de
  hoje, escolhido enquanto o motor amadurece e as notas ainda merecem curadoria.
- AUTOMATICO: **arquitetura prevista, ainda não implementada**. A intenção é que
  aprovar uma oferta acima do limiar já dispare a publicação. Quando for
  implementado, o gancho é uma chamada em `aprovar_promocao` — o resto (limiar
  por canal, montagem da mensagem, registro em `publicacoes`) já existe e é o
  mesmo. Configurar AUTOMATICO hoje registra um aviso e se comporta como MANUAL,
  para que ninguém suponha que está ligado.

Em nenhum dos modos a publicação precede a aprovação humana. AUTOMATICO
significa "publica sozinho depois que você aprovou", nunca "publica sem você" —
publicar sem aprovação seria outra decisão, de produto, e não está contemplada.
"""
import logging

logger = logging.getLogger("garimpo.application.publicacao")

# Da pior para a melhor. A comparação é por posição, não por nome, para que
# mudar os rótulos das faixas não quebre silenciosamente o limiar.
ORDEM_CATEGORIAS = ["POUCO_ATRATIVA", "COMUM", "BOA", "EXCELENTE", "EXCEPCIONAL"]

CONFIG_PADRAO = {
    "modo": "MANUAL",
    "canais": {
        # Os validadores recebem mais: é preciso ver também o que o motor achou
        # mediano para poder criticar que ele errou para baixo.
        "AVANCADO": {"categoria_minima": "BOA"},
        "PUBLICO": {"categoria_minima": "EXCELENTE"},
    },
}


def deve_publicar(classificacao, tipo: str, config: dict) -> bool:
    """A oferta atinge o limiar do canal?

    Sem classificação, ou com canal fora da configuração, devolve False: mandar
    para um canal não configurado é pior que não mandar.
    """
    if classificacao is None:
        return False

    canal = (config.get("canais") or {}).get(tipo)
    if not canal:
        return False

    minima = canal.get("categoria_minima")
    if minima not in ORDEM_CATEGORIAS or classificacao.categoria not in ORDEM_CATEGORIAS:
        return False

    return ORDEM_CATEGORIAS.index(classificacao.categoria) >= ORDEM_CATEGORIAS.index(minima)


def modo_efetivo(config: dict) -> str:
    """MANUAL ou AUTOMATICO, avisando quando o segundo ainda não existe."""
    modo = (config or {}).get("modo", "MANUAL")
    if modo == "AUTOMATICO":
        logger.warning(
            "Modo de publicação AUTOMATICO está configurado, mas o disparo na aprovação "
            "ainda não foi implementado. Tratando como MANUAL."
        )
        return "MANUAL"
    return "MANUAL"


async def carregar_config(db) -> dict:
    """Configuração de publicação, com a hierarquia GLOBAL → DOMÍNIO → PROGRAMA
    → PARCEIRO usada pelos pesos e faixas do motor.
    """
    from application.configuracoes_service import resolver_configuracao
    return await resolver_configuracao(db, "publicacao") or CONFIG_PADRAO


async def montar_fila(db, config: dict, tipo: str | None = None) -> list[dict]:
    """O que está aprovado, atinge o limiar do canal e ainda não foi enviado.

    A fila é derivada, não materializada: nada é pré-criado em `publicacoes`.
    Assim ela nunca fica desatualizada em relação a uma reclassificação, a uma
    mudança de limiar ou a uma rejeição posterior — e não sobra lixo de itens
    enfileirados que nunca saíram.
    """
    from sqlalchemy import and_, select
    from application.telegram.mensagens import montar_mensagem
    from domain.motor import ENTIDADE_PROMOCAO, Classificacao, Publicacao
    from domain.promocoes import Promocao

    canais = list((config.get("canais") or {}).keys())
    if tipo:
        canais = [c for c in canais if c == tipo]

    stmt = (
        select(Promocao, Classificacao)
        .join(Classificacao, and_(
            Classificacao.entidade_id == Promocao.id,
            Classificacao.entidade_tipo == ENTIDADE_PROMOCAO,
            Classificacao.ativa.is_(True),
        ))
        .filter(Promocao.status == "APROVADA")
        .order_by(Classificacao.nota.desc())
    )
    aprovadas = (await db.execute(stmt)).unique().all()

    enviadas = {
        (p.entidade_id, p.tipo)
        for p in (await db.execute(
            select(Publicacao).filter_by(entidade_tipo=ENTIDADE_PROMOCAO, status="ENVIADO")
        )).scalars().all()
    }

    fila = []
    for promocao, classificacao in aprovadas:
        for canal in canais:
            if (promocao.id, canal) in enviadas:
                continue
            if not deve_publicar(classificacao, canal, config):
                continue
            fila.append({
                "promocao_id": promocao.id,
                "tipo": canal,
                "parceiro": promocao.parceiro_nome,
                "categoria": classificacao.categoria,
                "mensagem": montar_mensagem(promocao, classificacao, canal),
            })
    return fila


async def despachar(db, config: dict, tipo: str | None = None, limite: int | None = None) -> dict:
    """Envia a fila e registra cada tentativa em `publicacoes`.

    Falha de um item não interrompe o lote: cada envio vira uma linha com
    ENVIADO ou FALHA e o motivo, para que o problema fique visível sem impedir
    o resto de sair.
    """
    from datetime import datetime, timezone
    from domain.motor import ENTIDADE_PROMOCAO, Publicacao
    from infrastructure.telegram import cliente

    fila = await montar_fila(db, config, tipo)
    if limite is not None:
        fila = fila[:limite]

    # Recusa antes de começar, em vez de falhar no meio com metade enviada.
    canais_pedidos = {item["tipo"] for item in fila}
    nao_configurados = [c for c in canais_pedidos if not cliente.esta_configurado(c)]
    if nao_configurados:
        return {
            "enviadas": 0, "falhas": 0, "total": len(fila),
            "erro": " ".join(cliente.motivo_nao_configurado(c) for c in nao_configurados),
        }

    enviadas = falhas = 0
    for item in fila:
        publicacao = Publicacao(
            entidade_tipo=ENTIDADE_PROMOCAO, entidade_id=item["promocao_id"],
            canal="TELEGRAM", tipo=item["tipo"], status="PENDENTE",
        )
        db.add(publicacao)
        await db.flush()
        try:
            await cliente.enviar(item["tipo"], item["mensagem"])
            publicacao.status = "ENVIADO"
            publicacao.data_envio = datetime.now(timezone.utc)
            enviadas += 1
        except Exception as erro:
            publicacao.status = "FALHA"
            publicacao.erro_resumido = str(erro)[:500]
            falhas += 1
            logger.warning("Falha ao publicar %s em %s: %s", item["promocao_id"], item["tipo"], erro)

    await db.commit()
    return {"enviadas": enviadas, "falhas": falhas, "total": len(fila), "erro": None}
