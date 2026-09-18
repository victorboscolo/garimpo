"""Teste de integração: GET /promocoes/destaques — a vitrine de "melhor
agora" (aprovadas, vigentes, categoria Excepcional ou Excelente).
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from domain.cadastros import Dominio, Programa
from domain.motor import ENTIDADE_PROMOCAO, Classificacao
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
        parceiro_nome_bruto="Parceiro Destaque",
        titulo="Parceiro Destaque - 5 pontos",
        url_origem="https://livelo.com.br/parceiro-destaque",
        pontuacao="5",
        unidade_pontuacao="pontos_por_real",
        origem_detalhe="teste-integracao",
    )
    base.update(ajustes)
    return base


async def _aprovar_com_categoria(db, client, categoria, **ajustes_payload):
    await _seed_programa(db)
    resposta = await client.post("/api/v1/promocoes/ingerir", json=_payload(**ajustes_payload))
    promocao_id = resposta.json()["id"]

    promocao = await db.get(Promocao, uuid.UUID(promocao_id))
    promocao.status = "APROVADA"
    stmt = select(Classificacao).filter_by(
        entidade_tipo=ENTIDADE_PROMOCAO, entidade_id=promocao.id, ativa=True
    )
    classificacao = (await db.execute(stmt)).scalar_one()
    classificacao.categoria = categoria
    await db.commit()
    return promocao


async def test_excepcional_aprovada_e_vigente_aparece(db, client):
    await _aprovar_com_categoria(db, client, "EXCEPCIONAL")

    resposta = await client.get("/api/v1/promocoes/destaques")

    assert resposta.status_code == 200
    nomes = {item["parceiro_nome"] for item in resposta.json()}
    assert "Parceiro Destaque" in nomes


async def test_boa_nao_aparece_mesmo_aprovada_e_vigente(db, client):
    await _aprovar_com_categoria(
        db, client, "BOA", url_origem="https://livelo.com.br/parceiro-boa",
    )

    resposta = await client.get("/api/v1/promocoes/destaques")

    nomes = {item["parceiro_nome"] for item in resposta.json()}
    assert "Parceiro Destaque" not in nomes


async def test_excelente_pendente_nao_aparece(db, client):
    """Categoria de topo não basta — precisa estar aprovada."""
    await _seed_programa(db)
    resposta = await client.post("/api/v1/promocoes/ingerir", json=_payload(
        url_origem="https://livelo.com.br/parceiro-pendente",
    ))
    promocao_id = resposta.json()["id"]
    stmt = select(Classificacao).filter_by(
        entidade_tipo=ENTIDADE_PROMOCAO, entidade_id=uuid.UUID(promocao_id), ativa=True
    )
    classificacao = (await db.execute(stmt)).scalar_one()
    classificacao.categoria = "EXCELENTE"
    await db.commit()

    resultado = await client.get("/api/v1/promocoes/destaques")

    nomes = {item["parceiro_nome"] for item in resultado.json()}
    assert "Parceiro Destaque" not in nomes


async def test_excelente_vencida_nao_aparece(db, client):
    """Categoria de topo e aprovada não bastam — precisa estar vigente."""
    promocao = await _aprovar_com_categoria(
        db, client, "EXCELENTE", url_origem="https://livelo.com.br/parceiro-vencida",
    )
    promocao.data_fim = (datetime.now(timezone.utc) - timedelta(days=2)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    await db.commit()

    resposta = await client.get("/api/v1/promocoes/destaques")

    nomes = {item["parceiro_nome"] for item in resposta.json()}
    assert "Parceiro Destaque" not in nomes
