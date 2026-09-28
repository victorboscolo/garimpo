"""Teste de integração: pendente vencida não aparece mais na fila.

Achado do usuário (28/09): nada foi revisado no fim de semana, e
segunda-feira a aba Pendentes trazia ofertas que já tinham expirado nesse
meio-tempo — pendente é fila de ação, uma oferta vencida não tem mais o
que decidir. Aprovada/Rejeitada continuam vigentes mesmo vencidas: ali é
histórico, não fila.
"""
import uuid
from datetime import datetime, timedelta, timezone

from domain.cadastros import Dominio, Programa
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
        parceiro_nome_bruto="Parceiro Vigencia",
        titulo="Parceiro Vigencia - 5 pontos",
        url_origem="https://livelo.com.br/parceiro-vigencia",
        pontuacao="5",
        unidade_pontuacao="pontos_por_real",
        origem_detalhe="teste-integracao",
    )
    base.update(ajustes)
    return base


async def test_pendente_vencida_some_do_status_pendente(db, client):
    await _seed_programa(db)
    resposta = await client.post("/api/v1/promocoes/ingerir", json=_payload())
    promocao = await db.get(Promocao, uuid.UUID(resposta.json()["id"]))
    promocao.data_fim = (datetime.now(timezone.utc) - timedelta(days=2)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    await db.commit()

    resultado = await client.get("/api/v1/promocoes", params={"status": "PENDENTE"})
    nomes = {item["parceiro_nome"] for item in resultado.json()}
    assert "Parceiro Vigencia" not in nomes


async def test_pendente_vencida_some_tambem_de_todas(db, client):
    await _seed_programa(db)
    resposta = await client.post("/api/v1/promocoes/ingerir", json=_payload(
        url_origem="https://livelo.com.br/parceiro-vigencia-todas",
    ))
    promocao = await db.get(Promocao, uuid.UUID(resposta.json()["id"]))
    promocao.data_fim = (datetime.now(timezone.utc) - timedelta(days=2)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    await db.commit()

    resultado = await client.get("/api/v1/promocoes")
    nomes = {item["parceiro_nome"] for item in resultado.json()}
    assert "Parceiro Vigencia" not in nomes


async def test_pendente_ainda_no_prazo_continua_aparecendo(db, client):
    await _seed_programa(db)
    resposta = await client.post("/api/v1/promocoes/ingerir", json=_payload(
        url_origem="https://livelo.com.br/parceiro-vigencia-ok",
    ))
    promocao = await db.get(Promocao, uuid.UUID(resposta.json()["id"]))
    promocao.data_fim = (datetime.now(timezone.utc) + timedelta(days=5))
    await db.commit()

    resultado = await client.get("/api/v1/promocoes", params={"status": "PENDENTE"})
    nomes = {item["parceiro_nome"] for item in resultado.json()}
    assert "Parceiro Vigencia" in nomes


async def test_aprovada_vencida_continua_aparecendo_em_todas(db, client):
    """Contraprova: o filtro é só pra PENDENTE, aprovada vencida é histórico."""
    await _seed_programa(db)
    resposta = await client.post("/api/v1/promocoes/ingerir", json=_payload(
        url_origem="https://livelo.com.br/parceiro-vigencia-aprovada",
    ))
    promocao = await db.get(Promocao, uuid.UUID(resposta.json()["id"]))
    promocao.status = "APROVADA"
    promocao.data_fim = (datetime.now(timezone.utc) - timedelta(days=30)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    await db.commit()

    resultado = await client.get("/api/v1/promocoes", params={"status": "APROVADA"})
    nomes = {item["parceiro_nome"] for item in resultado.json()}
    assert "Parceiro Vigencia" in nomes
