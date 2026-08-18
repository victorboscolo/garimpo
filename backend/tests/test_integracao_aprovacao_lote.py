"""Teste de integração: aprovar em lote reclassifica as demais promoções.

Desde que os pilares comparativos passaram a pontuar por posição na
distribuição (ver `application/motor/historico.py`), aprovar uma oferta muda a
base de comparação de todas as outras — na primeira recalibração automática,
aprovar 26 ofertas mudou a nota de 360 das 369 existentes. Um teste de lógica
pura não pega essa dependência entre registros porque ela só existe quando há
um banco de verdade por trás; por isso este teste roda contra o banco real e
confere que uma promoção PENDENTE, não tocada pelo lote, ainda assim recebe
uma classificação nova depois que outra é aprovada.
"""
import uuid

from sqlalchemy import select

from domain.cadastros import Dominio, Programa
from domain.motor import ENTIDADE_PROMOCAO, Classificacao


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
        parceiro_nome_bruto="Parceiro Teste",
        titulo="Parceiro Teste - pontos",
        url_origem="https://livelo.com.br/parceiro-teste",
        pontuacao="3",
        unidade_pontuacao="pontos_por_real",
        origem_detalhe="teste-integracao",
    )
    base.update(ajustes)
    return base


async def _classificacao_ativa_id(db, promocao_id: str):
    stmt = select(Classificacao).filter_by(
        entidade_tipo=ENTIDADE_PROMOCAO, entidade_id=uuid.UUID(promocao_id), ativa=True
    )
    return (await db.execute(stmt)).scalar_one().id


async def test_aprovar_lote_reclassifica_promocoes_fora_do_lote(db, client):
    await _seed_programa(db)

    resposta_a = await client.post("/api/v1/promocoes/ingerir", json=_payload(
        parceiro_nome_bruto="Parceiro A", titulo="Parceiro A - 2 pontos", pontuacao="2",
        url_origem="https://livelo.com.br/parceiro-a",
    ))
    resposta_b = await client.post("/api/v1/promocoes/ingerir", json=_payload(
        parceiro_nome_bruto="Parceiro B", titulo="Parceiro B - 20 pontos", pontuacao="20",
        url_origem="https://livelo.com.br/parceiro-b",
    ))
    id_a = resposta_a.json()["id"]
    id_b = resposta_b.json()["id"]

    classificacao_a_antes = await _classificacao_ativa_id(db, id_a)

    resultado = await client.post("/api/v1/promocoes/aprovar-lote", json={"ids": [id_b]})

    assert resultado.status_code == 200
    corpo = resultado.json()
    assert corpo["processadas"] == 1
    assert corpo["ignoradas"] == []

    # Parceiro A continua PENDENTE (fora do lote), mas ganhou uma classificação
    # nova porque B entrou na base de comparação do mercado.
    detalhe_a = await client.get(f"/api/v1/promocoes/{id_a}")
    assert detalhe_a.json()["status"] == "PENDENTE"

    classificacao_a_depois = await _classificacao_ativa_id(db, id_a)
    assert classificacao_a_depois != classificacao_a_antes
