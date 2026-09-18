import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.environ["DATABASE_URL"]

# Provedores gerenciados (Neon, e a maioria dos outros) devolvem a URL com
# `?sslmode=require` — parâmetro do libpq/psycopg. O driver `asyncpg` não
# reconhece esse nome e falha na primeira conexão (TypeError: unexpected
# keyword argument 'sslmode'); ele exige SSL via `connect_args={"ssl": ...}`
# em vez de um parâmetro na própria URL. Local (Postgres do docker-compose,
# sem TLS) não tem esse parâmetro, então não entra nesse caminho.
connect_args = {}
if "sslmode=require" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("?sslmode=require", "").replace("&sslmode=require", "")
    connect_args["ssl"] = "require"

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True, connect_args=connect_args)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncSession:
    """Dependency do FastAPI: fornece uma sessão por requisição."""
    async with AsyncSessionLocal() as session:
        yield session
