"""Infraestrutura dos testes de integração (API + banco real).

Os testes em `tests/test_*.py` que não usam os fixtures daqui são de lógica
pura (motor, hash, mensagens) e não tocam banco. Os testes de integração
existem à parte porque cobrem uma classe de bug que os de lógica pura não
alcançam: o caminho inteiro request -> serviço -> ORM -> banco -> resposta,
onde já apareceram `MissingGreenlet`, `MultipleResultsFound` e a fila de
publicação derrubando o lote inteiro por um canal mal configurado.

Banco: `garimpo_test`, um segundo banco no mesmo Postgres do docker-compose
(não um serviço novo). Schema criado via `Base.metadata.create_all()` — mais
rápido que rodar as migrations do Alembic uma a uma, ao custo de não validar
que as migrations em si aplicam limpo; isso continua coberto por rodá-las de
verdade no banco de desenvolvimento.

Isolamento por teste: cada teste roda dentro de uma transação de conexão que é
desfeita ao final, com um SAVEPOINT por baixo — necessário porque o próprio
código da aplicação chama `db.commit()` (ex: `ingerir_promocao_bruta`), e um
commit real encerraria a transação de isolamento se não houvesse o savepoint
por trás capturando cada commit interno.
"""
import asyncio
import os

_DATABASE_URL_ORIGINAL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://garimpo:garimpo@postgres:5432/garimpo"
)
os.environ["DATABASE_URL"] = _DATABASE_URL_ORIGINAL.rsplit("/", 1)[0] + "/garimpo_test"

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from domain import cadastros, emissoes, governanca, motor, promocoes  # noqa: F401 — popula Base.metadata
from infrastructure.db.base import Base
from infrastructure.db.session import get_db

TEST_DATABASE_URL = os.environ["DATABASE_URL"]
# NullPool: sem isso, uma conexão asyncpg aberta no event loop de um teste é
# reaproveitada do pool no teste seguinte, que roda num event loop novo — e o
# asyncpg recusa ("attached to a different loop"). Sem pool, cada `.connect()`
# abre conexão fresca no loop que estiver rodando na hora.
_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)


async def _recriar_schema():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


# Roda uma única vez, na coleta, no seu próprio event loop — e não como
# fixture pytest-asyncio: o modo `auto` dá a cada teste um event loop novo, e
# uma fixture de escopo `session` presa a um loop de um teste só (o primeiro a
# rodar) quebraria com "attached to a different loop" quando os testes
# seguintes, no loop deles, tentassem herdar a mesma conexão.
asyncio.run(_recriar_schema())


@pytest_asyncio.fixture
async def db():
    async with _engine.connect() as conn:
        await conn.begin()
        await conn.begin_nested()
        sessionmaker = async_sessionmaker(bind=conn, expire_on_commit=False, class_=AsyncSession)
        sessao = sessionmaker()

        @event.listens_for(sessao.sync_session, "after_transaction_end")
        def _reabrir_savepoint(session, transaction):
            if conn.closed:
                return
            if not conn.sync_connection.in_nested_transaction():
                conn.sync_connection.begin_nested()

        yield sessao

        await sessao.close()
        await conn.rollback()


@pytest_asyncio.fixture
async def client(db):
    from api.main import app

    app.dependency_overrides[get_db] = lambda: db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)
