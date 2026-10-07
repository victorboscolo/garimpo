"""Autorização das rotas da API v1.

Duas origens de chamada, dois mecanismos — o mesmo endpoint pode receber as
duas (ex: `GET /promocoes` é lido tanto pelo painel quanto por
`scripts/recalibrar.sh` como checagem de saúde da API antes de reprocessar):

- **Humano, pelo painel**: cookie de sessão (JWT), criado em `POST
  /auth/login`. Verificado contra `usuarios` a cada requisição.
- **Máquina, por script ou coletor local**: cabeçalho `X-API-Key`, comparado
  a `COLETOR_API_KEY` (`.env`) — Livelo, Esfera, Azul, Smiles, LATAM, e os
  scripts de recalibração/saúde/backup que rodam via `launchd`, sem humano
  na tela.

`exigir_acesso` é a checagem em si (aplicada a todo router de v1 exceto
`auth`, em `api/main.py`); `usuario_atual` só lê o que `exigir_acesso` já
validou, para as rotas que precisam saber *quem* aprovou algo — devolve
`None` quando o acesso foi por chave de API, porque um script não é um
usuário.
"""
import os
import time

from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from application import auth_service
from domain.governanca import Usuario
from infrastructure.db.session import get_db


# Cada clique no painel refazia `SELECT usuarios` só pra confirmar quem já
# estava logado — uma ida e volta ao banco a mais por requisição, cara com o
# banco em outro continente (ver infrastructure/db/session.py). O usuário
# validado fica guardado por este tempo; o preço é que desativar alguém leva
# até um minuto pra valer, aceitável com 1-2 contas no painel.
_SEGUNDOS_CACHE_USUARIO = 60
_usuarios_validados: dict = {}


async def _usuario_ativo(db: AsyncSession, usuario_id) -> Usuario | None:
    guardado = _usuarios_validados.get(usuario_id)
    if guardado is not None and guardado[0] > time.monotonic():
        return guardado[1]
    usuario = await db.get(Usuario, usuario_id)
    if usuario is None or not usuario.ativo:
        _usuarios_validados.pop(usuario_id, None)
        return None
    _usuarios_validados[usuario_id] = (time.monotonic() + _SEGUNDOS_CACHE_USUARIO, usuario)
    return usuario


async def exigir_acesso(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    garimpo_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> None:
    chave_esperada = os.environ.get("COLETOR_API_KEY")
    if chave_esperada and x_api_key == chave_esperada:
        request.state.usuario = None
        return

    if garimpo_token:
        usuario_id = auth_service.decodificar_token(garimpo_token)
        if usuario_id is not None:
            usuario = await _usuario_ativo(db, usuario_id)
            if usuario is not None:
                request.state.usuario = usuario
                return

    raise HTTPException(status_code=401, detail="Não autenticado.")


def usuario_atual(request: Request) -> Usuario | None:
    """Só lê `request.state.usuario`, já populado por `exigir_acesso` — não
    autentica de novo. Usar depois de `exigir_acesso` já ter rodado na
    mesma rota.
    """
    return getattr(request.state, "usuario", None)
