"""Chave de API compartilhada pelos três coletores de Emissões (Azul,
Smiles, LATAM) — o painel passou a exigir autenticação em toda rota
(18/09), e um coletor não tem sessão de usuário, só essa chave fixa.

Cada coletor roda no seu próprio processo, fora do Docker, sem env_file
pra herdar a variável — por isso lê direto do `.env` na raiz do repo
quando ela não está no ambiente.
"""
from __future__ import annotations

import os


def chave_api() -> str | None:
    if os.environ.get("COLETOR_API_KEY"):
        return os.environ["COLETOR_API_KEY"]
    caminho = os.path.join(os.path.dirname(__file__), "..", ".env")
    try:
        with open(caminho) as f:
            for linha in f:
                if linha.strip().startswith("COLETOR_API_KEY="):
                    return linha.strip().split("=", 1)[1]
    except FileNotFoundError:
        pass
    return None


HEADERS = {"X-API-Key": chave_api()} if chave_api() else {}
