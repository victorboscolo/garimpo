"""Login do painel: e-mail + senha, sessão via cookie httponly.

Sem CORS envolvido — o painel (`/admin`) e a API são servidos pelo mesmo
processo FastAPI, mesma origem, então o cookie basta e não precisa de
token manipulado em JS (mais simples e sem superfície de XSS pra roubo de
token, que existiria se o token vivesse em localStorage).
"""
import os

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from application import auth_service
from domain.governanca import Usuario
from infrastructure.db.session import get_db

router = APIRouter()

NOME_COOKIE = "garimpo_token"


class LoginIn(BaseModel):
    email: str
    senha: str


def _ambiente_producao() -> bool:
    return os.environ.get("AMBIENTE", "local") != "local"


@router.post("/login")
async def login(payload: LoginIn, response: Response, db: AsyncSession = Depends(get_db)):
    usuario = await auth_service.autenticar(db, payload.email, payload.senha)
    if usuario is None:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")

    token = auth_service.criar_token(usuario)
    minutos = int(os.environ.get("JWT_EXPIRATION_MINUTES", "480"))
    response.set_cookie(
        NOME_COOKIE, token,
        httponly=True,
        samesite="lax",
        secure=_ambiente_producao(),
        max_age=minutos * 60,
    )
    return {"nome": usuario.nome, "email": usuario.email}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(NOME_COOKIE)
    return {"ok": True}


@router.get("/me")
async def me(
    garimpo_token: str | None = Cookie(default=None, alias=NOME_COOKIE),
    db: AsyncSession = Depends(get_db),
):
    """Usado pelo painel ao carregar a página, pra saber se já há sessão
    válida ou se precisa mostrar a tela de login.
    """
    usuario_id = auth_service.decodificar_token(garimpo_token) if garimpo_token else None
    if usuario_id is None:
        raise HTTPException(status_code=401, detail="Não autenticado.")

    usuario = await db.get(Usuario, usuario_id)
    if usuario is None or not usuario.ativo:
        raise HTTPException(status_code=401, detail="Não autenticado.")

    return {"nome": usuario.nome, "email": usuario.email}
