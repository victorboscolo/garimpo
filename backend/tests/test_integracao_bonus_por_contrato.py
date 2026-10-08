"""Teste de integração: bônus fixo por contrato fora das comparações.

Achado de 08/10 (Localiza Meoo): "30 mil pontos a cada assinatura" gravado
como pontos por real saía Excepcional — 30.000 comparado com ofertas de 5
por real — e ainda entrava na régua contra a qual as outras são medidas.
"""
import uuid
from decimal import Decimal

from domain.cadastros import Dominio, Programa
from domain.promocoes import Promocao


async def _seed_programa(db):
    dominio = Dominio(nome="PROMOCOES")
    db.add(dominio)
    await db.flush()
    db.add(Programa(dominio_id=dominio.id, nome="Esfera"))
    await db.commit()


def _payload(parceiro, pontuacao, unidade="pontos_por_real"):
    return dict(
        programa_nome="Esfera", parceiro_nome_bruto=parceiro, titulo=parceiro,
        url_origem=f"https://esfera.com.vc/p/{parceiro.lower().replace(' ', '-')}",
        pontuacao=str(pontuacao), unidade_pontuacao=unidade, origem_detalhe="teste-integracao",
    )


async def _ingerir_aprovada(client, db, parceiro, pontuacao, unidade="pontos_por_real"):
    resposta = await client.post("/api/v1/promocoes/ingerir", json=_payload(parceiro, pontuacao, unidade))
    promocao_id = resposta.json()["id"]
    await client.post(f"/api/v1/promocoes/{promocao_id}/aprovar")
    return promocao_id


async def test_bonus_por_contrato_nao_ganha_nota_por_comparacao(client, db):
    await _seed_programa(db)
    for i, pontos in enumerate([2, 3, 5, 8]):
        await _ingerir_aprovada(client, db, f"Loja {i}", pontos)

    resposta = await client.post(
        "/api/v1/promocoes/ingerir", json=_payload("Assinatura de Carro", 30000, "pontos_por_contrato")
    )
    classificacao = resposta.json()["classificacao_ativa"]

    assert classificacao["criterios_avaliados"]["atratividade"] == 50
    assert classificacao["criterios_avaliados"]["historico"] == 50
    assert classificacao["categoria"] not in ("EXCEPCIONAL", "EXCELENTE")
    assert "Bônus fixo por contrato" in classificacao["justificativa"]


async def test_bonus_por_contrato_nao_entra_na_regua_das_outras(client, db):
    await _seed_programa(db)
    for i, pontos in enumerate([2, 3, 5]):
        await _ingerir_aprovada(client, db, f"Loja {i}", pontos)
    await _ingerir_aprovada(client, db, "Assinatura de Carro", 30000, "pontos_por_contrato")

    resposta = await client.post("/api/v1/promocoes/ingerir", json=_payload("Loja Nova", 8))

    # 8 supera as três ofertas por real; se o bônus de 30.000 estivesse na
    # régua, ficaria abaixo dele e não tiraria o topo.
    assert resposta.json()["classificacao_ativa"]["criterios_avaliados"]["atratividade"] == 100


async def test_corrigir_pontuacao_e_unidade_reclassifica(client, db):
    await _seed_programa(db)
    for i, pontos in enumerate([2, 3, 5, 8]):
        await _ingerir_aprovada(client, db, f"Loja {i}", pontos)
    promocao_id = await _ingerir_aprovada(client, db, "Assinatura de Carro", 30000)

    resposta = await client.post(f"/api/v1/promocoes/{promocao_id}/corrigir", json={
        "unidade_pontuacao": "pontos_por_contrato", "motivo": "bônus fixo gravado como taxa por real",
    })

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["unidade_pontuacao"] == "pontos_por_contrato"
    assert "Bônus fixo por contrato" in corpo["classificacao_ativa"]["justificativa"]

    resposta = await client.post(f"/api/v1/promocoes/{promocao_id}/corrigir", json={
        "pontuacao": "30", "unidade_pontuacao": "pontos_por_real", "motivo": "erro de digitação da fonte",
    })
    promocao = await db.get(Promocao, uuid.UUID(promocao_id))
    await db.refresh(promocao)
    assert promocao.pontuacao == Decimal("30")


async def test_corrigir_sem_nada_a_mudar_e_recusado(client, db):
    await _seed_programa(db)
    promocao_id = await _ingerir_aprovada(client, db, "Loja", 5)

    resposta = await client.post(f"/api/v1/promocoes/{promocao_id}/corrigir", json={"motivo": "nada"})

    assert resposta.status_code == 422
