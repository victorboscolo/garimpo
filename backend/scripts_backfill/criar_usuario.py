"""Cria (ou atualiza a senha de) um usuário do painel.

Cada pessoa loga com a própria conta — decisão do usuário (18/09), mesmo
padrão do Guardião Financeiro. Sem tela de cadastro no painel de propósito:
criar usuário é ato raro (1-2 pessoas), não vale a superfície extra de uma
tela por onde qualquer sessão logada poderia criar outra conta.

Uso:
    docker compose exec backend python -m scripts_backfill.criar_usuario \
        --nome "Victor" --email victor@example.com

Sem --senha, pede a senha de forma oculta (getpass) — evita que ela fique
no histórico do shell. Se o e-mail já existe, atualiza nome e senha em vez
de falhar (útil pra trocar senha).
"""
import argparse
import asyncio
import getpass
import sys

from sqlalchemy import select

from application.auth_service import gerar_hash_senha
from domain.governanca import Usuario
from infrastructure.db.session import AsyncSessionLocal


async def executar(nome: str, email: str, senha: str) -> None:
    email = email.strip().lower()
    async with AsyncSessionLocal() as db:
        resultado = await db.execute(select(Usuario).filter_by(email=email))
        usuario = resultado.scalar_one_or_none()

        if usuario is None:
            usuario = Usuario(nome=nome, email=email, senha_hash=gerar_hash_senha(senha), ativo=True)
            db.add(usuario)
            print(f"Criando usuário novo: {nome} <{email}>")
        else:
            usuario.nome = nome
            usuario.senha_hash = gerar_hash_senha(senha)
            usuario.ativo = True
            print(f"Usuário já existia — nome e senha atualizados: {nome} <{email}>")

        await db.commit()
        print("Concluído.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--nome", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--senha", help="Se omitido, pede de forma oculta.")
    args = parser.parse_args()

    senha = args.senha or getpass.getpass("Senha: ")
    if len(senha) < 8:
        print("Senha precisa ter pelo menos 8 caracteres.", file=sys.stderr)
        sys.exit(1)

    asyncio.run(executar(args.nome, args.email, senha))
