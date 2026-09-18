import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.db.url import preparar_conexao

DATABASE_URL, _connect_args = preparar_conexao(os.environ["DATABASE_URL"])

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True, connect_args=_connect_args)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncSession:
    """Dependency do FastAPI: fornece uma sessão por requisição."""
    async with AsyncSessionLocal() as session:
        yield session
