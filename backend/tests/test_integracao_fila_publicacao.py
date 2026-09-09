"""Teste de integração: canal sem configuração não derruba a fila inteira.

Já aconteceu de um canal sem `TELEGRAM_CANAL_*_ID`/`TELEGRAM_BOT_TOKEN` no
`.env` recusar o disparo do lote inteiro, inclusive os itens do canal que
estava pronto (ver `publicacao_service.montar_fila`). O teste confere, contra
banco e config real (via `monkeypatch` no ambiente), que a fila devolve os
itens do canal configurado e simplesmente omite os do canal que não está —
sem lançar exceção nem esvaziar a fila inteira.
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
        parceiro_nome_bruto="Parceiro Fila",
        titulo="Parceiro Fila - 5 pontos",
        url_origem="https://livelo.com.br/parceiro-fila",
        pontuacao="5",
        unidade_pontuacao="pontos_por_real",
        origem_detalhe="teste-integracao",
    )
    base.update(ajustes)
    return base


async def test_fila_ignora_canal_sem_configuracao_sem_derrubar_os_demais(db, client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-fake-de-teste")
    monkeypatch.setenv("TELEGRAM_CANAL_PUBLICO_ID", "-100123456")
    monkeypatch.delenv("TELEGRAM_CANAL_AVANCADO_ID", raising=False)

    await _seed_programa(db)
    resposta = await client.post("/api/v1/promocoes/ingerir", json=_payload())
    promocao_id = resposta.json()["id"]

    # Leva a oferta ao topo do funil: aprovada e na categoria mais alta, que é
    # o que os dois canais (PUBLICO e AVANCADO) exigem no mínimo.
    promocao = await db.get(Promocao, uuid.UUID(promocao_id))
    promocao.status = "APROVADA"
    stmt = select(Classificacao).filter_by(
        entidade_tipo=ENTIDADE_PROMOCAO, entidade_id=promocao.id, ativa=True
    )
    classificacao = (await db.execute(stmt)).scalar_one()
    classificacao.categoria = "EXCEPCIONAL"
    await db.commit()

    fila = await client.get("/api/v1/publicacoes/fila")

    assert fila.status_code == 200
    corpo = fila.json()
    tipos = {item["tipo"] for item in corpo["itens"]}
    assert "PUBLICO" in tipos
    assert "AVANCADO" not in tipos


async def test_campanha_de_hoje_continua_na_fila_ate_o_fim_do_dia(db, client, monkeypatch):
    """Achado do usuário (09/09): aprovou uma campanha de um dia só, e ela
    não aparecia na fila mesmo ainda sendo o próprio dia.

    A data extraída do regulamento ("Campanha válida em 09/09/2026") vira
    `date(2026, 9, 9)`, que ao ser gravada numa coluna `DateTime` fica
    meia-noite do início do dia — não o fim dele. Comparar direto com
    `agora` tirava a campanha da fila a partir da própria meia-noite do
    dia em que ela ainda vale.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-fake-de-teste")
    monkeypatch.setenv("TELEGRAM_CANAL_AVANCADO_ID", "-100123456")

    await _seed_programa(db)
    agora = datetime.now(timezone.utc)
    meia_noite_de_hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0)

    resposta = await client.post("/api/v1/promocoes/ingerir", json=_payload(
        url_origem="https://livelo.com.br/parceiro-fila-hoje",
    ))
    promocao_id = resposta.json()["id"]

    promocao = await db.get(Promocao, uuid.UUID(promocao_id))
    promocao.status = "APROVADA"
    promocao.data_fim = meia_noite_de_hoje
    stmt = select(Classificacao).filter_by(
        entidade_tipo=ENTIDADE_PROMOCAO, entidade_id=promocao.id, ativa=True
    )
    classificacao = (await db.execute(stmt)).scalar_one()
    classificacao.categoria = "BOA"
    await db.commit()

    fila = await client.get("/api/v1/publicacoes/fila")

    assert fila.status_code == 200
    urls = {item["parceiro"] for item in fila.json()["itens"]}
    assert "Parceiro Fila" in urls


async def test_campanha_de_ontem_sai_da_fila(db, client, monkeypatch):
    """Contraprova: uma campanha cujo último dia válido já passou (não é
    hoje) não deve mais aparecer — o corte é por dia civil, não abre a
    fila pra sempre.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-fake-de-teste")
    monkeypatch.setenv("TELEGRAM_CANAL_AVANCADO_ID", "-100123456")

    await _seed_programa(db)
    ontem_meia_noite = (datetime.now(timezone.utc) - timedelta(days=2)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    resposta = await client.post("/api/v1/promocoes/ingerir", json=_payload(
        url_origem="https://livelo.com.br/parceiro-fila-ontem",
    ))
    promocao_id = resposta.json()["id"]

    promocao = await db.get(Promocao, uuid.UUID(promocao_id))
    promocao.status = "APROVADA"
    promocao.data_fim = ontem_meia_noite
    stmt = select(Classificacao).filter_by(
        entidade_tipo=ENTIDADE_PROMOCAO, entidade_id=promocao.id, ativa=True
    )
    classificacao = (await db.execute(stmt)).scalar_one()
    classificacao.categoria = "BOA"
    await db.commit()

    fila = await client.get("/api/v1/publicacoes/fila")

    assert fila.status_code == 200
    urls = {item["parceiro"] for item in fila.json()["itens"]}
    assert "Parceiro Fila" not in urls
