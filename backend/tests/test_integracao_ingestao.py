"""Teste de integração: ingestão de ponta a ponta via /promocoes/ingerir.

Os testes de `test_hash_dedup.py` cobrem a fórmula do hash isoladamente; este
cobre o caminho inteiro contra um banco real — parceiro novo cadastrado
automaticamente, promoção criada e classificada, e a segunda chamada idêntica
reconhecida como duplicata em vez de virar um segundo registro. É a rota onde
já apareceram bugs de sessão assíncrona (`MissingGreenlet`,
`MultipleResultsFound`) que um teste com mock de sessão não pega.
"""
from sqlalchemy import select

from domain.cadastros import Dominio, Parceiro, Programa
from domain.promocoes import Promocao


async def _seed_programa(db, nome="Livelo"):
    dominio = Dominio(nome="PROMOCOES")
    db.add(dominio)
    await db.flush()
    programa = Programa(dominio_id=dominio.id, nome=nome)
    db.add(programa)
    await db.flush()
    await db.commit()
    return programa


def _payload(**ajustes):
    base = dict(
        programa_nome="Livelo",
        parceiro_nome_bruto="Beach Park",
        titulo="Beach Park - 2 pontos por R$ 1",
        url_origem="https://livelo.com.br/juntar-pontos/parceiros/beach-park/BPK",
        pontuacao="2",
        unidade_pontuacao="pontos_por_real",
        origem_detalhe="teste-integracao",
    )
    base.update(ajustes)
    return base


async def test_ingestao_cria_parceiro_e_promocao_novos(db, client):
    await _seed_programa(db)

    resposta = await client.post("/api/v1/promocoes/ingerir", json=_payload())

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo is not None
    assert corpo["status"] == "PENDENTE"
    assert corpo["parceiro_nome"] == "Beach Park"
    assert corpo["classificacao_ativa"] is not None

    promocoes = (await db.execute(select(Promocao))).scalars().all()
    assert len(promocoes) == 1
    parceiros = (await db.execute(select(Parceiro))).scalars().all()
    assert len(parceiros) == 1


async def test_ingestao_duplicata_nao_cria_segunda_promocao(db, client):
    await _seed_programa(db)

    primeira = await client.post("/api/v1/promocoes/ingerir", json=_payload())
    assert primeira.json() is not None

    segunda = await client.post("/api/v1/promocoes/ingerir", json=_payload())

    assert segunda.status_code == 200
    assert segunda.json() is None

    promocoes = (await db.execute(select(Promocao))).scalars().all()
    assert len(promocoes) == 1
