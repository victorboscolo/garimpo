"""Teste de integração: ingestão de ofertas do Garimpo Emissões.

Sem motor, sem dedup por hash — cada POST cria uma linha nova (histórico de
preço é o dado). `rotas_emissao` é catálogo curado; uma rota fora dele é
rejeitada, não criada na hora. Por perna, só ida (decisão do usuário,
21/08) — não existe mais `data_volta`/`voo_direto`, uma oferta de volta é
outro registro, na rota oposta.
"""
from sqlalchemy import select

from domain.cadastros import Dominio, Programa
from domain.emissoes import OfertaEmissao, RotaEmissao


async def _seed_programa_e_rota(db, origem="GIG", destino="LIS", fonte="SITE_PRINCIPAL"):
    dominio = Dominio(nome="EMISSOES")
    db.add(dominio)
    await db.flush()
    programa = Programa(dominio_id=dominio.id, nome="Azul")
    db.add(programa)
    await db.flush()
    rota = RotaEmissao(programa_id=programa.id, origem=origem, destino=destino, fonte=fonte)
    db.add(rota)
    await db.commit()
    return programa, rota


async def test_registrar_oferta_numa_rota_cadastrada(client, db):
    await _seed_programa_e_rota(db)

    resposta = await client.post("/api/v1/emissoes/ofertas", json={
        "programa_nome": "Azul", "origem": "GIG", "destino": "LIS",
        "data_ida": "2026-11-15", "classe": "ECONOMY", "pontos": 85000,
        "companhia_operadora": "Azul", "paradas": 0, "assentos_restantes": 9,
    })

    assert resposta.status_code == 200
    assert "id" in resposta.json()

    oferta = (await db.execute(select(OfertaEmissao))).scalar_one()
    assert oferta.paradas == 0
    assert oferta.assentos_restantes == 9


async def test_rota_nao_cadastrada_e_rejeitada(client, db):
    await _seed_programa_e_rota(db)

    resposta = await client.post("/api/v1/emissoes/ofertas", json={
        "programa_nome": "Azul", "origem": "GIG", "destino": "NRT",
        "data_ida": "2026-11-15", "classe": "ECONOMY", "pontos": 85000,
    })

    assert resposta.status_code == 404


async def test_duas_coletas_da_mesma_rota_e_data_criam_duas_linhas(client, db):
    """O histórico é o dado — a segunda coleta não substitui a primeira."""
    await _seed_programa_e_rota(db)
    payload = {
        "programa_nome": "Azul", "origem": "GIG", "destino": "LIS",
        "data_ida": "2026-11-15", "classe": "ECONOMY", "pontos": 85000,
    }

    r1 = await client.post("/api/v1/emissoes/ofertas", json=payload)
    payload_mais_barato = {**payload, "pontos": 70000}
    r2 = await client.post("/api/v1/emissoes/ofertas", json=payload_mais_barato)

    assert r1.json()["id"] != r2.json()["id"]


async def test_lista_rotas_ativas(client, db):
    await _seed_programa_e_rota(db, origem="GIG", destino="LIS")
    await _seed_programa_e_rota(db, origem="GRU", destino="LHR", fonte="AZUL_PELO_MUNDO")

    resposta = await client.get("/api/v1/emissoes/rotas")

    assert resposta.status_code == 200
    origens_destinos = {(r["origem"], r["destino"]) for r in resposta.json()}
    assert ("GIG", "LIS") in origens_destinos
    assert ("GRU", "LHR") in origens_destinos


async def test_lista_rotas_filtra_por_programa(client, db):
    await _seed_programa_e_rota(db)

    resposta = await client.get("/api/v1/emissoes/rotas?programa_nome=Smiles")

    assert resposta.status_code == 200
    assert resposta.json() == []


async def _oferta(client, origem, destino):
    return await client.post("/api/v1/emissoes/ofertas", json={
        "programa_nome": "Azul", "origem": origem, "destino": destino,
        "data_ida": "2026-11-15", "classe": "ECONOMY", "pontos": 85000, "paradas": 0,
    })


async def test_definir_rotas_ativas_desativa_as_outras_e_esconde_as_ofertas(client, db):
    """Pedido do usuário (07/10): pesquisar só uma rota em vez do catálogo
    inteiro. As demais param de ser coletadas E somem da aba Emissões — o
    que já tinham coletado só ficaria envelhecendo na tela.
    """
    programa, _ = await _seed_programa_e_rota(db)
    db.add(RotaEmissao(programa_id=programa.id, origem="GRU", destino="SCL", fonte="SITE_PRINCIPAL"))
    await db.commit()
    await _oferta(client, "GIG", "LIS")
    await _oferta(client, "GRU", "SCL")

    resposta = await client.put("/api/v1/emissoes/rotas/ativas", json={
        "rotas": [{"programa_nome": "Azul", "origem": "GRU", "destino": "SCL"}],
    })

    assert resposta.json() == {"ativas": 1, "desativadas": 1, "nao_encontradas": []}
    rotas = (await client.get("/api/v1/emissoes/rotas")).json()
    assert [(r["origem"], r["destino"]) for r in rotas] == [("GRU", "SCL")]
    ofertas = (await client.get("/api/v1/emissoes/ofertas")).json()
    assert [(o["origem"], o["destino"]) for o in ofertas] == [("GRU", "SCL")]
    # Desativar não apaga: o histórico continua no banco.
    assert len((await db.execute(select(OfertaEmissao))).scalars().all()) == 2


async def test_definir_rotas_ativas_com_rota_inexistente_nao_altera_nada(client, db):
    """Um erro de digitação não pode desligar o catálogo inteiro."""
    await _seed_programa_e_rota(db)

    resposta = await client.put("/api/v1/emissoes/rotas/ativas", json={
        "rotas": [{"programa_nome": "Azul", "origem": "GRU", "destino": "XXX"}],
    })

    assert resposta.status_code == 404
    rotas = (await client.get("/api/v1/emissoes/rotas")).json()
    assert [(r["origem"], r["destino"]) for r in rotas] == [("GIG", "LIS")]


async def test_plano_pareia_ida_e_volta_pela_duracao(client, db, monkeypatch):
    """Pedido do usuário (09/10): o plano de viagem disponível na aba
    Emissões — pra cada data de ida, a volta N dias depois, com a coleta
    mais recente de cada categoria.
    """
    from datetime import date

    from application import planos_emissao

    programa, _ = await _seed_programa_e_rota(db, origem="GRU", destino="SCL")
    db.add(RotaEmissao(programa_id=programa.id, origem="SCL", destino="GRU", fonte="SITE_PRINCIPAL"))
    await db.commit()
    monkeypatch.setattr(planos_emissao, "PLANOS", [{
        "nome": "Teste", "programa_nome": "Azul", "origem": "GRU", "destino": "SCL",
        "ida_inicio": date(2027, 7, 16), "ida_fim": date(2027, 7, 17), "dias": 6,
    }])

    async def oferta(origem, destino, data, pontos, paradas):
        await client.post("/api/v1/emissoes/ofertas", json={
            "programa_nome": "Azul", "origem": origem, "destino": destino,
            "data_ida": data, "classe": "ECONOMY", "pontos": pontos, "paradas": paradas,
        })

    await oferta("GRU", "SCL", "2027-07-16", 40000, 0)
    # O teste inteiro roda numa transação só, então `now()` daria o mesmo
    # instante às duas coletas — a antiga é empurrada pra trás à mão.
    from datetime import datetime, timezone
    antiga = (await db.execute(select(OfertaEmissao))).scalar_one()
    antiga.created_at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    await db.commit()
    await oferta("GRU", "SCL", "2027-07-16", 33636, 0)   # coleta mais recente vence
    await oferta("GRU", "SCL", "2027-07-16", 32076, 1)
    await oferta("SCL", "GRU", "2027-07-22", 33636, 0)
    await oferta("SCL", "GRU", "2027-07-30", 99999, 0)   # fora do plano

    plano = (await client.get("/api/v1/emissoes/planos")).json()[0]

    assert [(l["data_ida"], l["data_volta"]) for l in plano["linhas"]] == [
        ("2027-07-16", "2027-07-22"), ("2027-07-17", "2027-07-23"),
    ]
    primeira, segunda = plano["linhas"]
    assert primeira["ida"]["direto"]["pontos"] == 33636
    assert primeira["ida"]["com_parada"]["pontos"] == 32076
    assert primeira["volta"]["direto"]["pontos"] == 33636
    assert primeira["volta"]["com_parada"] is None
    # Data do plano sem nenhuma oferta gravada: perna vazia, não erro.
    assert segunda["ida"] is None and segunda["volta"] is None
