"""Categoria canônica por parceiro, não só por slug de origem

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-18

A curadoria real (423 parceiros classificados à mão) mostrou que a categoria
canônica precisa viver no vínculo parceiro↔slug, não no slug sozinho: o mesmo
slug de origem (`casaedecoracao`, `modaebeleza`, `new02156`...) reúne
parceiros de natureza bem diferente — a Livelo e a Esfera usam poucos slugs
largos, não um por segmento fino. Em `casaedecoracao`, por exemplo, a curadoria
distribuiu os parceiros entre 7 categorias canônicas diferentes.

`categorias_origem.categoria_id` (0007) não sustenta isso: é um valor só por
slug, compartilhado por todo mundo que carrega aquele slug. Forçar a curadoria
ali faria a decisão de um parceiro vencer a de outro no mesmo slug.

`parceiro_categorias.categoria_id` guarda a decisão por parceiro. Continua
nulo por padrão — sem curadoria, o motor cai no slug bruto como segmento,
igual sempre fez. `categorias_origem.categoria_id` não é removido: fica como
fallback de nível de slug para quando não há decisão por parceiro (hoje
nenhuma linha usa isso, mas não custa preservar o caminho).
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "parceiro_categorias",
        sa.Column("categoria_id", pg.UUID(as_uuid=True), sa.ForeignKey("categorias.id"), nullable=True),
    )
    op.create_index("ix_parceiro_categorias_categoria_id", "parceiro_categorias", ["categoria_id"])


def downgrade():
    op.drop_index("ix_parceiro_categorias_categoria_id", table_name="parceiro_categorias")
    op.drop_column("parceiro_categorias", "categoria_id")
