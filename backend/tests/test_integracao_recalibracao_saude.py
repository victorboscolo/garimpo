"""Teste de integração: recalibração disparada pelo painel aparece na Saúde.

Achado do usuário (08/10): a aprovação em lote já reprocessa a base
inteira, mas só o job semanal registrava a execução — com ele desligado, a
aba Saúde acusava "atrasada" enquanto a recalibração rodava todo dia.
"""
from domain.cadastros import Dominio, Programa


async def _seed_programa(db):
    dominio = Dominio(nome="PROMOCOES")
    db.add(dominio)
    await db.flush()
    db.add(Programa(dominio_id=dominio.id, nome="Livelo"))
    await db.commit()


async def _ingerir(client):
    resposta = await client.post("/api/v1/promocoes/ingerir", json=dict(
        programa_nome="Livelo", parceiro_nome_bruto="Loja Saude", titulo="Loja Saude - 5 pontos",
        url_origem="https://livelo.com.br/loja-saude", pontuacao="5",
        unidade_pontuacao="pontos_por_real", origem_detalhe="teste-integracao",
    ))
    return resposta.json()["id"]


async def _situacao_da_recalibracao(client):
    jobs = (await client.get("/api/v1/saude")).json()["jobs"]
    return next(j for j in jobs if j["job"] == "recalibracao")


async def test_aprovar_em_lote_registra_a_recalibracao(db, client):
    await _seed_programa(db)
    promocao_id = await _ingerir(client)
    assert (await _situacao_da_recalibracao(client))["situacao"] == "NUNCA_RODOU"

    await client.post("/api/v1/promocoes/aprovar-lote", json={"ids": [promocao_id]})

    recalibracao = await _situacao_da_recalibracao(client)
    assert recalibracao["situacao"] == "OK"
    assert recalibracao["ultima_execucao"]["criadas"] == 1


async def test_reprocessar_tudo_registra_a_recalibracao(db, client):
    await _seed_programa(db)
    await _ingerir(client)

    await client.post("/api/v1/promocoes/reclassificar-todas")

    assert (await _situacao_da_recalibracao(client))["situacao"] == "OK"


async def test_lote_sem_nada_aprovado_nao_registra(db, client):
    await _seed_programa(db)

    await client.post("/api/v1/promocoes/aprovar-lote", json={"ids": []})

    assert (await _situacao_da_recalibracao(client))["situacao"] == "NUNCA_RODOU"
