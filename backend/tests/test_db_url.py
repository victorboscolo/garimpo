"""Teste de lógica pura: adaptação da DATABASE_URL de provedores gerenciados
pro driver asyncpg (ver infrastructure/db/url.py).
"""
from infrastructure.db.url import preparar_conexao


def test_url_local_sem_parametro_fica_igual():
    url, connect_args = preparar_conexao("postgresql+asyncpg://garimpo:senha@postgres:5432/garimpo")
    assert url == "postgresql+asyncpg://garimpo:senha@postgres:5432/garimpo"
    assert connect_args == {}


def test_neon_tira_sslmode_e_channel_binding_e_pede_ssl():
    url, connect_args = preparar_conexao(
        "postgresql://user:senha@ep-xxx.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    )
    assert "sslmode" not in url
    assert "channel_binding" not in url
    assert url == "postgresql://user:senha@ep-xxx.sa-east-1.aws.neon.tech/neondb"
    assert connect_args == {"ssl": "require"}


def test_preserva_outros_parametros_da_query():
    url, _ = preparar_conexao(
        "postgresql://user:senha@host/db?sslmode=require&application_name=garimpo"
    )
    assert "application_name=garimpo" in url
    assert "sslmode" not in url
