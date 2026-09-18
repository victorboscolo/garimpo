"""Teste de integração: login do painel e a autorização das rotas.

Usa um client próprio (`client_sem_bypass`), sem o override de
`exigir_acesso` que o fixture `client` genérico tem — aqui o objetivo é
exatamente testar essa checagem, não pular por ela.
"""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from application.auth_service import gerar_hash_senha
from domain.governanca import Usuario
from infrastructure.db.session import get_db


@pytest_asyncio.fixture
async def client_sem_bypass(db):
    from api.main import app

    app.dependency_overrides[get_db] = lambda: db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


async def _criar_usuario(db, email="teste@garimpo.com", senha="senha-forte-123") -> Usuario:
    usuario = Usuario(nome="Teste", email=email, senha_hash=gerar_hash_senha(senha), ativo=True)
    db.add(usuario)
    await db.commit()
    return usuario


async def test_rota_protegida_sem_credencial_nenhuma_da_401(client_sem_bypass):
    resultado = await client_sem_bypass.get("/api/v1/promocoes")
    assert resultado.status_code == 401


async def test_chave_de_api_correta_da_acesso(client_sem_bypass, monkeypatch):
    monkeypatch.setenv("COLETOR_API_KEY", "chave-de-teste")
    resultado = await client_sem_bypass.get(
        "/api/v1/promocoes", headers={"X-API-Key": "chave-de-teste"},
    )
    assert resultado.status_code == 200


async def test_chave_de_api_errada_da_401(client_sem_bypass, monkeypatch):
    monkeypatch.setenv("COLETOR_API_KEY", "chave-de-teste")
    resultado = await client_sem_bypass.get(
        "/api/v1/promocoes", headers={"X-API-Key": "chave-errada"},
    )
    assert resultado.status_code == 401


async def test_login_com_senha_certa_devolve_cookie_e_libera_acesso(client_sem_bypass, db, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "segredo-de-teste")
    await _criar_usuario(db)

    login = await client_sem_bypass.post(
        "/api/v1/auth/login", json={"email": "teste@garimpo.com", "senha": "senha-forte-123"},
    )
    assert login.status_code == 200
    assert "garimpo_token" in login.cookies

    resultado = await client_sem_bypass.get("/api/v1/promocoes")
    assert resultado.status_code == 200


async def test_login_com_senha_errada_nao_autentica(client_sem_bypass, db, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "segredo-de-teste")
    await _criar_usuario(db)

    login = await client_sem_bypass.post(
        "/api/v1/auth/login", json={"email": "teste@garimpo.com", "senha": "senha-errada"},
    )
    assert login.status_code == 401
    assert "garimpo_token" not in login.cookies


async def test_apos_limite_de_tentativas_bloqueia_mesmo_com_senha_certa(client_sem_bypass, db, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "segredo-de-teste")
    await _criar_usuario(db, email="bloqueio@garimpo.com")

    for _ in range(5):
        resposta = await client_sem_bypass.post(
            "/api/v1/auth/login", json={"email": "bloqueio@garimpo.com", "senha": "senha-errada"},
        )
        assert resposta.status_code == 401

    # A sexta tentativa já está bloqueada, mesmo com a senha certa agora.
    resposta = await client_sem_bypass.post(
        "/api/v1/auth/login", json={"email": "bloqueio@garimpo.com", "senha": "senha-forte-123"},
    )
    assert resposta.status_code == 401


async def test_logout_invalida_a_sessao(client_sem_bypass, db, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "segredo-de-teste")
    await _criar_usuario(db, email="logout@garimpo.com")

    await client_sem_bypass.post(
        "/api/v1/auth/login", json={"email": "logout@garimpo.com", "senha": "senha-forte-123"},
    )
    await client_sem_bypass.post("/api/v1/auth/logout")

    resultado = await client_sem_bypass.get("/api/v1/promocoes")
    assert resultado.status_code == 401


async def test_me_sem_sessao_da_401(client_sem_bypass):
    resultado = await client_sem_bypass.get("/api/v1/auth/me")
    assert resultado.status_code == 401
