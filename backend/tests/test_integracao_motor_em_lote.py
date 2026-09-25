"""Teste de integração: o reprocessamento em lote dá exatamente o mesmo
resultado que classificar uma promoção de cada vez.

O lote existe pra ler os dados de comparação uma vez só (ver
`motor/cache.py`) — otimização de desempenho, que não pode mudar nenhuma
nota. Em 24/09/2026 uma recalibração sem isso levou 32 min e gastou quase
todos os 5 GB mensais de transferência do Neon. A equivalência também foi
conferida contra 1.107 promoções reais (0 diferenças); este teste guarda
a garantia daqui pra frente.
"""
from sqlalchemy import select

from application.motor.servico import classificar_em_lote, classificar_promocao
from domain.cadastros import Dominio, Programa
from domain.promocoes import Promocao


async def _seed_programa(db):
    dominio = Dominio(nome="PROMOCOES")
    db.add(dominio)
    await db.flush()
    db.add(Programa(dominio_id=dominio.id, nome="Livelo"))
    await db.flush()
    await db.commit()


def _payload(parceiro, pontuacao, **extra):
    base = dict(
        programa_nome="Livelo", parceiro_nome_bruto=parceiro,
        titulo=f"{parceiro} - {pontuacao} pontos",
        url_origem=f"https://livelo.com.br/{parceiro.lower()}/{pontuacao}",
        pontuacao=str(pontuacao), unidade_pontuacao="pontos_por_real",
        origem_detalhe="teste-integracao",
    )
    base.update(extra)
    return base


async def test_lote_e_identico_a_classificar_uma_de_cada_vez(db, client):
    await _seed_programa(db)
    # Parceiros com e sem histórico, uma oferta condicionada e uma com clube,
    # pra passar pelos ramos da cascata (família, segmento, mercado).
    ofertas = [
        ("Alfa", 2), ("Alfa", 3), ("Alfa", 5), ("Beta", 10), ("Beta", 4),
        ("Gama", 1), ("Delta", 7), ("Delta", 8),
    ]
    for parceiro, pontos in ofertas:
        extra = {"pontuacao_e_teto": True} if parceiro == "Gama" else {}
        if parceiro == "Delta":
            extra = {"pontuacao_clube": str(pontos + 2), "requer_clube": True}
        resposta = await client.post("/api/v1/promocoes/ingerir", json=_payload(parceiro, pontos, **extra))
        assert resposta.status_code == 200

    promocoes = (await db.execute(select(Promocao).order_by(Promocao.id))).scalars().unique().all()
    # Aprova metade: a base de comparação só considera as aprovadas.
    for promocao in promocoes[::2]:
        promocao.status = "APROVADA"
    await db.commit()

    esperado = {}
    for promocao in promocoes:
        c = await classificar_promocao(db, promocao)
        esperado[promocao.id] = (c.nota, c.categoria, c.criterios_avaliados, c.confianca_historica, c.justificativa)

    criadas, erros = await classificar_em_lote(db, promocoes)

    assert erros == 0
    obtido = {
        c.entidade_id: (c.nota, c.categoria, c.criterios_avaliados, c.confianca_historica, c.justificativa)
        for c in criadas
    }
    assert obtido == esperado
