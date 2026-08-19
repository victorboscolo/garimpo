"""Teste de fumaça: as migrations do Alembic aplicam limpo, do zero.

Os testes de integração (`test_integracao_*.py`) montam o schema via
`Base.metadata.create_all()` — rápido, mas não valida as migrations em si.
Uma migration com erro de sintaxe, dependência trocada ou índice que já
existe só apareceria rodando de verdade contra um banco vazio, do jeito que
uma sessão nova faria. Roda num banco próprio (`garimpo_test_migrations`),
separado do `garimpo_test` usado pelos testes de integração, porque este
precisa de DDL fora de transação (DROP/CREATE DATABASE) incompatível com o
isolamento por SAVEPOINT do `conftest.py`.
"""
import os
import subprocess

import asyncpg

_DATABASE_URL_ORIGINAL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://garimpo:garimpo@postgres:5432/garimpo"
)
_HOST_E_CREDENCIAIS = _DATABASE_URL_ORIGINAL.replace("postgresql+asyncpg://", "").rsplit("/", 1)[0]
NOME_BANCO = "garimpo_test_migrations"
URL_MANUTENCAO = f"postgresql://{_HOST_E_CREDENCIAIS}/postgres"
URL_TESTE = f"postgresql+asyncpg://{_HOST_E_CREDENCIAIS}/{NOME_BANCO}"


async def test_alembic_upgrade_head_aplica_limpo():
    conexao_manutencao = await asyncpg.connect(URL_MANUTENCAO)
    try:
        await conexao_manutencao.execute(f'DROP DATABASE IF EXISTS "{NOME_BANCO}"')
        await conexao_manutencao.execute(f'CREATE DATABASE "{NOME_BANCO}"')
    finally:
        await conexao_manutencao.close()

    raiz_backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resultado = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=raiz_backend,
        env={**os.environ, "DATABASE_URL": URL_TESTE},
        capture_output=True, text=True,
    )
    assert resultado.returncode == 0, f"alembic upgrade head falhou:\n{resultado.stderr}"

    conexao_verificacao = await asyncpg.connect(URL_TESTE.replace("+asyncpg", ""))
    try:
        tabelas = {
            row["table_name"] for row in await conexao_verificacao.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            )
        }
    finally:
        await conexao_verificacao.close()

    # Uma tabela de cada geração de migration — se qualquer uma faltar, algo
    # no meio da cadeia 0001-0009 não aplicou.
    for tabela in ("promocoes", "parceiro_categorias", "execucoes"):
        assert tabela in tabelas, f"tabela '{tabela}' não existe após alembic upgrade head"
