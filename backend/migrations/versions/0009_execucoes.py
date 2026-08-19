"""Registro de execução de jobs (coletores, recalibração, backup)

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-18

Suporte ao Painel de Saúde: hoje, se um coletor para de rodar (Mac desligado,
site mudou de estrutura, anti-robô passou a bloquear), ninguém percebe até
notar a ausência de ofertas novas — não há sinal ativo de falha. Este registro
é escrito por quem executa o job (coletor Livelo, coletor Esfera, recalibração
semanal, backup), uma linha por execução, para o painel poder mostrar a última
execução de cada um e destacar quando está atrasada ou falhou.

Tabela de log — sem `codigo` Identity nem `updated_at`, no mesmo estilo de
`auditoria` (nunca é atualizada, só inserida).
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "execucoes",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        # `codigo` (não `created_at`) é o critério de "mais recente": dentro de
        # uma mesma transação Postgres, now() devolve sempre o mesmo valor —
        # duas execuções registradas na mesma transação empatariam em
        # created_at. Identity() é sequencial de verdade, sem esse risco.
        sa.Column("codigo", sa.BigInteger(), sa.Identity(), unique=True, nullable=False),
        sa.Column("job", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("criadas", sa.Integer(), nullable=True),
        sa.Column("descartadas", sa.Integer(), nullable=True),
        sa.Column("falhas", sa.Integer(), nullable=True),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_execucoes_job_codigo", "execucoes", ["job", "codigo"])


def downgrade():
    op.drop_index("ix_execucoes_job_created_at", table_name="execucoes")
    op.drop_table("execucoes")
