"""Teste de integração: aviso quando aprovação avulsa não reclassifica sozinha.

`/promocoes/{id}/aprovar` não chama o motor de novo (decisão de custo — ver
`aprovar_promocao`), ao contrário de `aprovar-lote`. Sem isso a fila de
publicação podia mostrar nota desatualizada sem que ninguém percebesse; o
aviso em `GET /publicacoes/aviso-reclassificacao` é o substituto barato.
"""
from domain.cadastros import Dominio, Programa


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


async def test_sem_aprovacao_nenhuma_nao_ha_aviso(db, client):
    await _seed_programa(db)

    resultado = await client.get("/api/v1/publicacoes/aviso-reclassificacao")

    assert resultado.status_code == 200
    assert resultado.json() == {"pendente": False, "quantidade": 0}


async def test_aprovacao_avulsa_dispara_o_aviso(db, client):
    await _seed_programa(db)

    resposta = await client.post("/api/v1/promocoes/ingerir", json=_payload())
    promocao_id = resposta.json()["id"]

    await client.post(f"/api/v1/promocoes/{promocao_id}/aprovar")

    aviso = (await client.get("/api/v1/publicacoes/aviso-reclassificacao")).json()

    assert aviso == {"pendente": True, "quantidade": 1}


async def test_reprocessar_tudo_limpa_o_aviso(db, client):
    await _seed_programa(db)

    resposta = await client.post("/api/v1/promocoes/ingerir", json=_payload())
    promocao_id = resposta.json()["id"]
    await client.post(f"/api/v1/promocoes/{promocao_id}/aprovar")

    aviso_antes = (await client.get("/api/v1/publicacoes/aviso-reclassificacao")).json()
    assert aviso_antes["pendente"] is True

    resultado = await client.post("/api/v1/promocoes/reclassificar-todas")
    assert resultado.status_code == 200

    aviso_depois = (await client.get("/api/v1/publicacoes/aviso-reclassificacao")).json()
    assert aviso_depois == {"pendente": False, "quantidade": 0}
