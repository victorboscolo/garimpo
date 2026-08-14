"""Compara o que foi publicado com o que o motor sustenta hoje.

Reprocessar muda notas, e a promoção já publicada não acompanha: o canal
continua afirmando a categoria da época. Como não existe despublicar no
Telegram, a única defesa é saber que a divergência aconteceu — e decidir se vale
uma correção.

Só é possível porque nada é sobrescrito: a classificação anterior é marcada como
inativa, não apagada, então dá para reconstruir o que valia em qualquer momento.
"""
import logging

logger = logging.getLogger("garimpo.application.divergencia")


def classificacao_vigente_em(classificacoes: list, momento):
    """A classificação que valia num instante, ou None se não havia nenhuma.

    Devolver None em vez de cair na mais antiga é deliberado: publicação sem
    classificação anterior é anomalia que merece ser reportada como tal, não
    disfarçada com um palpite.
    """
    anteriores = [c for c in classificacoes if c.processada_em <= momento]
    if not anteriores:
        return None
    return max(anteriores, key=lambda c: c.processada_em)


async def listar_divergencias(db) -> list[dict]:
    """Publicações cuja categoria mudou desde o envio."""
    from sqlalchemy import select

    from domain.cadastros import Parceiro
    from domain.motor import ENTIDADE_PROMOCAO, Classificacao, Publicacao
    from domain.promocoes import Promocao

    enviadas = (await db.execute(
        select(Publicacao).filter_by(entidade_tipo=ENTIDADE_PROMOCAO, status="ENVIADO")
    )).scalars().all()
    if not enviadas:
        return []

    ids = {p.entidade_id for p in enviadas}

    classificacoes: dict = {}
    for classificacao in (await db.execute(
        select(Classificacao).filter(
            Classificacao.entidade_tipo == ENTIDADE_PROMOCAO,
            Classificacao.entidade_id.in_(ids),
        )
    )).scalars().all():
        classificacoes.setdefault(classificacao.entidade_id, []).append(classificacao)

    promocoes = {
        p.id: p for p in (await db.execute(
            select(Promocao).filter(Promocao.id.in_(ids))
        )).scalars().unique().all()
    }
    parceiros = {
        p.id: p for p in (await db.execute(select(Parceiro))).scalars().all()
    }

    divergencias = []
    for publicacao in enviadas:
        historico = classificacoes.get(publicacao.entidade_id, [])
        na_epoca = classificacao_vigente_em(historico, publicacao.data_envio)
        atual = next((c for c in historico if c.ativa), None)
        if na_epoca is None or atual is None:
            continue
        if na_epoca.categoria == atual.categoria:
            continue

        promocao = promocoes.get(publicacao.entidade_id)
        parceiro = parceiros.get(promocao.parceiro_id) if promocao else None
        divergencias.append({
            "promocao_id": str(publicacao.entidade_id),
            "parceiro": (parceiro.nome_exibicao or parceiro.nome) if parceiro else "?",
            "canal": publicacao.tipo,
            "publicado_em": publicacao.data_envio.isoformat() if publicacao.data_envio else None,
            "categoria_publicada": na_epoca.categoria,
            "categoria_atual": atual.categoria,
        })
    return divergencias
