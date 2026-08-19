"""Teste de integração: o Painel de Saúde avisa no Telegram, não só na tela.

Duas mecânicas diferentes (ver application/saude_service.py):
- FALHA é evento: dispara na hora que o job registra a execução.
- ATRASADA é estado: só existe checagem periódica (verificar_atrasados_e_alertar),
  chamada por scripts/verificar_saude.sh via launchd.

Em nenhum teste aqui um Telegram de verdade é chamado — `cliente.enviar` é
substituído por um dublê que só grava as chamadas.
"""
from datetime import datetime, timedelta, timezone

from infrastructure.telegram import cliente


def _dublê_enviar(chamadas: list):
    async def _enviar(tipo, texto):
        chamadas.append((tipo, texto))
    return _enviar


async def test_falha_dispara_alerta_no_telegram(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-fake")
    monkeypatch.setenv("TELEGRAM_CANAL_ALERTA_ID", "12345")
    chamadas = []
    monkeypatch.setattr(cliente, "enviar", _dublê_enviar(chamadas))

    resposta = await client.post("/api/v1/execucoes", json={
        "job": "coletor_livelo", "status": "FALHA", "erro": "timeout na Livelo",
    })

    assert resposta.status_code == 200
    assert len(chamadas) == 1
    tipo, texto = chamadas[0]
    assert tipo == "ALERTA"
    assert "timeout na Livelo" in texto


async def test_sucesso_nao_dispara_alerta(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-fake")
    monkeypatch.setenv("TELEGRAM_CANAL_ALERTA_ID", "12345")
    chamadas = []
    monkeypatch.setattr(cliente, "enviar", _dublê_enviar(chamadas))

    resposta = await client.post("/api/v1/execucoes", json={
        "job": "coletor_livelo", "status": "SUCESSO", "criadas": 5,
    })

    assert resposta.status_code == 200
    assert chamadas == []


async def test_falha_sem_canal_configurado_nao_quebra_o_registro(client, monkeypatch):
    monkeypatch.delenv("TELEGRAM_CANAL_ALERTA_ID", raising=False)

    resposta = await client.post("/api/v1/execucoes", json={
        "job": "backup", "status": "FALHA", "erro": "disco cheio",
    })

    assert resposta.status_code == 200


async def test_falha_no_envio_do_alerta_nao_quebra_o_registro(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-fake")
    monkeypatch.setenv("TELEGRAM_CANAL_ALERTA_ID", "12345")

    async def _enviar_com_erro(tipo, texto):
        raise RuntimeError("Telegram fora do ar")
    monkeypatch.setattr(cliente, "enviar", _enviar_com_erro)

    resposta = await client.post("/api/v1/execucoes", json={
        "job": "backup", "status": "FALHA", "erro": "disco cheio",
    })

    assert resposta.status_code == 200


async def test_verificar_atrasados_dispara_alerta_quando_ha_atraso(db, client, monkeypatch):
    from domain.governanca import Execucao

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-fake")
    monkeypatch.setenv("TELEGRAM_CANAL_ALERTA_ID", "12345")
    chamadas = []
    monkeypatch.setattr(cliente, "enviar", _dublê_enviar(chamadas))

    # Bem além da janela de 30h do coletor_livelo.
    db.add(Execucao(
        job="coletor_livelo", status="SUCESSO", criadas=1,
        created_at=datetime.now(timezone.utc) - timedelta(hours=48),
    ))
    await db.commit()

    resposta = await client.post("/api/v1/saude/verificar-atrasados")

    assert resposta.status_code == 200
    assert "coletor_livelo" in resposta.json()["atrasados"]
    assert len(chamadas) == 1
    assert chamadas[0][0] == "ALERTA"


async def test_verificar_atrasados_nao_dispara_quando_tudo_em_dia(db, client, monkeypatch):
    from domain.governanca import Execucao

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-fake")
    monkeypatch.setenv("TELEGRAM_CANAL_ALERTA_ID", "12345")
    chamadas = []
    monkeypatch.setattr(cliente, "enviar", _dublê_enviar(chamadas))

    for job in ("coletor_livelo", "coletor_esfera", "recalibracao", "backup"):
        db.add(Execucao(job=job, status="SUCESSO"))
    await db.commit()

    resposta = await client.post("/api/v1/saude/verificar-atrasados")

    assert resposta.status_code == 200
    assert resposta.json()["atrasados"] == []
    assert chamadas == []
