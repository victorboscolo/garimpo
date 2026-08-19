"""Teste de integração: registrar e ler a saúde dos jobs contra o banco real."""


async def test_job_nunca_executado_aparece_como_tal(client):
    resultado = await client.get("/api/v1/saude")

    assert resultado.status_code == 200
    jobs = {item["job"]: item for item in resultado.json()["jobs"]}
    assert jobs["coletor_livelo"]["situacao"] == "NUNCA_RODOU"


async def test_execucao_registrada_aparece_na_saude(client):
    registro = await client.post("/api/v1/execucoes", json={
        "job": "coletor_esfera", "status": "SUCESSO", "criadas": 8, "descartadas": 159, "falhas": 0,
    })
    assert registro.status_code == 200

    resultado = await client.get("/api/v1/saude")
    jobs = {item["job"]: item for item in resultado.json()["jobs"]}

    assert jobs["coletor_esfera"]["situacao"] == "OK"
    assert jobs["coletor_esfera"]["ultima_execucao"]["criadas"] == 8


async def test_execucao_com_falha_aparece_como_falha(client):
    await client.post("/api/v1/execucoes", json={
        "job": "coletor_livelo", "status": "FALHA", "erro": "timeout na Livelo",
    })

    resultado = await client.get("/api/v1/saude")
    jobs = {item["job"]: item for item in resultado.json()["jobs"]}

    assert jobs["coletor_livelo"]["situacao"] == "FALHA"
    assert jobs["coletor_livelo"]["ultima_execucao"]["erro"] == "timeout na Livelo"


async def test_so_a_execucao_mais_recente_conta(client):
    await client.post("/api/v1/execucoes", json={"job": "backup", "status": "FALHA", "erro": "disco cheio"})
    await client.post("/api/v1/execucoes", json={"job": "backup", "status": "SUCESSO"})

    resultado = await client.get("/api/v1/saude")
    jobs = {item["job"]: item for item in resultado.json()["jobs"]}

    assert jobs["backup"]["situacao"] == "OK"
