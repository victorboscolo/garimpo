"""Autenticação de usuários do painel: senha com hash, bloqueio por
tentativa e token de sessão (JWT em cookie).

Mesmo padrão de bloqueio do Guardião Financeiro (`src/auth/tentativas.ts`):
LIMITE tentativas erradas seguidas bloqueiam o e-mail por BLOQUEIO_MINUTOS,
e uma tentativa certa (ou o fim da janela de bloqueio) reseta o contador.

Separado da autenticação por chave de API dos coletores (`api/dependencies.py`)
— um humano loga com e-mail e senha; um coletor não tem senha, só uma chave
fixa em `.env`.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.governanca import TentativaLogin, Usuario

_contexto_senha = CryptContext(schemes=["bcrypt"], deprecated="auto")

LIMITE_TENTATIVAS = 5
BLOQUEIO_MINUTOS = 15
ALGORITMO_JWT = "HS256"


def gerar_hash_senha(senha: str) -> str:
    return _contexto_senha.hash(senha)


def conferir_senha(senha: str, hash_armazenado: str) -> bool:
    try:
        return _contexto_senha.verify(senha, hash_armazenado)
    except ValueError:
        return False


async def _esta_bloqueado(db: AsyncSession, email: str) -> bool:
    tentativa = await db.get(TentativaLogin, email)
    if tentativa is None or tentativa.bloqueado_ate is None:
        return False
    return tentativa.bloqueado_ate > datetime.now(timezone.utc)


async def _registrar_falha(db: AsyncSession, email: str) -> None:
    agora = datetime.now(timezone.utc)
    tentativa = await db.get(TentativaLogin, email)
    if tentativa is None:
        tentativa = TentativaLogin(email=email, tentativas=0)
        db.add(tentativa)
    elif tentativa.bloqueado_ate is not None and tentativa.bloqueado_ate <= agora:
        # Janela de bloqueio anterior já expirou — recomeça a contagem.
        tentativa.tentativas = 0
        tentativa.bloqueado_ate = None

    tentativa.tentativas += 1
    if tentativa.tentativas >= LIMITE_TENTATIVAS:
        tentativa.bloqueado_ate = agora + timedelta(minutes=BLOQUEIO_MINUTOS)
    await db.commit()


async def _limpar_tentativas(db: AsyncSession, email: str) -> None:
    tentativa = await db.get(TentativaLogin, email)
    if tentativa is not None:
        await db.delete(tentativa)
        await db.commit()


async def autenticar(db: AsyncSession, email: str, senha: str) -> Usuario | None:
    """Devolve o usuário se a credencial confere, senão None — nunca diz
    qual das duas (e-mail ou senha) está errada, pra não confirmar pra quem
    tenta adivinhar se um e-mail existe na base.
    """
    email = email.strip().lower()
    if await _esta_bloqueado(db, email):
        return None

    resultado = await db.execute(
        select(Usuario).filter(Usuario.email == email, Usuario.ativo.is_(True))
    )
    usuario = resultado.scalar_one_or_none()
    if usuario is None or not conferir_senha(senha, usuario.senha_hash):
        await _registrar_falha(db, email)
        return None

    await _limpar_tentativas(db, email)
    return usuario


def criar_token(usuario: Usuario) -> str:
    segredo = os.environ["JWT_SECRET"]
    minutos = int(os.environ.get("JWT_EXPIRATION_MINUTES", "480"))
    agora = datetime.now(timezone.utc)
    payload = {"sub": str(usuario.id), "iat": agora, "exp": agora + timedelta(minutes=minutos)}
    return jwt.encode(payload, segredo, algorithm=ALGORITMO_JWT)


def decodificar_token(token: str) -> uuid.UUID | None:
    """Devolve o id do usuário se o token é válido e não expirou, senão None."""
    segredo = os.environ["JWT_SECRET"]
    try:
        payload = jwt.decode(token, segredo, algorithms=[ALGORITMO_JWT])
        return uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None
