"""Garimpo Emissões: rotas monitoradas e ofertas coletadas

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-20

Ver domain/emissoes.py para o raciocínio completo. Reaproveita `programas`/
`dominios` (o `Dominio` "EMISSOES" já era previsto no schema original) — só
as duas tabelas novas específicas de Emissões entram aqui.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rotas_emissao",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("programa_id", pg.UUID(as_uuid=True), sa.ForeignKey("programas.id"), nullable=False),
        sa.Column("origem", sa.String(3), nullable=False),
        sa.Column("destino", sa.String(3), nullable=False),
        sa.Column("fonte", sa.String(30), nullable=False),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("programa_id", "origem", "destino", name="uq_rota_emissao_programa_od"),
    )

    op.create_table(
        "ofertas_emissao",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("rota_id", pg.UUID(as_uuid=True), sa.ForeignKey("rotas_emissao.id"), nullable=False),
        sa.Column("data_ida", sa.Date(), nullable=False),
        sa.Column("data_volta", sa.Date(), nullable=True),
        sa.Column("classe", sa.String(20), nullable=False),
        sa.Column("pontos", sa.Integer(), nullable=False),
        sa.Column("taxa_reais", sa.Numeric(10, 2), nullable=True),
        sa.Column("companhia_operadora", sa.String(100), nullable=True),
        sa.Column("voo_direto", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ofertas_emissao_created_at", "ofertas_emissao", ["created_at"])
    op.create_index("ix_ofertas_emissao_rota_data_classe", "ofertas_emissao", ["rota_id", "data_ida", "classe"])


def downgrade():
    op.drop_index("ix_ofertas_emissao_rota_data_classe", table_name="ofertas_emissao")
    op.drop_index("ix_ofertas_emissao_created_at", table_name="ofertas_emissao")
    op.drop_table("ofertas_emissao")
    op.drop_table("rotas_emissao")
