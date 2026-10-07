import os
import time

from sqlalchemy import event, exc
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.db.url import preparar_conexao

DATABASE_URL, _connect_args = preparar_conexao(os.environ["DATABASE_URL"])

engine = create_async_engine(DATABASE_URL, echo=False, connect_args=_connect_args)

# Servidor (Render, Virgínia) e banco (Neon, São Paulo) ficam em continentes
# diferentes: cada ida e volta ao banco custa caro. O `pool_pre_ping=True` que
# existia aqui gastava uma delas em TODA requisição só pra confirmar que a
# conexão estava viva (medido em 07/10: ~0,7s de piso em qualquer chamada que
# toca o banco, contra 0,19s nas que não tocam).
#
# A checagem continua existindo, mas só quando faz sentido: se a conexão
# ficou parada no pool por mais que este tempo — o Neon derruba conexão
# ociosa e suspende o banco depois de 5 minutos sem uso. Em uso contínuo
# (clicando de aba em aba) ela é pulada.
_SEGUNDOS_OCIOSA_PARA_CHECAR = 30


@event.listens_for(engine.sync_engine, "checkin")
def _marcar_devolucao(dbapi_connection, connection_record):
    connection_record.info["devolvida_em"] = time.monotonic()


@event.listens_for(engine.sync_engine, "checkout")
def _checar_conexao_ociosa(dbapi_connection, connection_record, connection_proxy):
    devolvida_em = connection_record.info.get("devolvida_em")
    if devolvida_em is None or time.monotonic() - devolvida_em < _SEGUNDOS_OCIOSA_PARA_CHECAR:
        return
    try:
        viva = engine.sync_engine.dialect.do_ping(dbapi_connection)
    except Exception:
        viva = False
    if not viva:
        # O pool descarta esta conexão e tenta de novo com uma nova.
        raise exc.DisconnectionError()


AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncSession:
    """Dependency do FastAPI: fornece uma sessão por requisição."""
    async with AsyncSessionLocal() as session:
        yield session
