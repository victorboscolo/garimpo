"""Pontuação do Clube Livelo

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-13

15 dos 248 cards da Livelo anunciam duas pontuações: uma para qualquer cliente
e outra, maior, para assinantes do Clube Livelo. O coletor capturava só a
primeira (a de qualquer cliente, que é a correta para `pontuacao`) e descartava
a segunda.

Guardar as duas serve ao painel — a oferta maior é uma informação real, desde
que fique claro que é condicionada a assinatura. `pontuacao` continua sendo
sempre a de qualquer cliente, e `requer_clube` continua falso: a oferta base
está disponível para todos.

O preenchimento dos registros existentes e o recálculo dos hashes (a coluna
entra na fórmula de deduplicação) ficam em `scripts_backfill/backfill_0004.py`.
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("promocoes", sa.Column("pontuacao_clube", sa.Numeric(10, 2), nullable=True))


def downgrade():
    op.drop_column("promocoes", "pontuacao_clube")
