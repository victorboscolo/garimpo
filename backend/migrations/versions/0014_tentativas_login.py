"""Login por usuário: tabela de tentativas para bloqueio temporário

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-18

O painel deixa de rodar só em 127.0.0.1 (vai para hospedagem na nuvem —
Render + Neon) e passa a exigir login por usuário, um por pessoa, mesmo
padrão do Guardião Financeiro. A tabela `usuarios` já existia desde a
migration 0001 (nunca usada); esta migration só acrescenta o controle de
tentativas, que não fazia parte do schema original.
"""
import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tentativas_login",
        sa.Column("email", sa.String(200), primary_key=True),
        sa.Column("tentativas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bloqueado_ate", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("tentativas_login")
