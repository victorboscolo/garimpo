"""Emissões: guarda a duração do voo, como texto

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-17

Achado do usuário (17/09): a tabela de ofertas precisa mostrar a duração
total do voo. Guardada como texto ("11h25", "02h50min"), exatamente como os
dois sites mostram — decisão do usuário, pra não perder precisão nem criar
uma conversão que a fonte não garante (ex: "11h25" vira 685 min, mas não dá
pra saber se o site já arredonda segundos por baixo dos panos).

`taxa_reais` deixa de ser preenchido pelos coletores a partir de agora
(decisão do usuário: só milhas) — a coluna fica no banco sem uso por ora,
não é removida porque descreve um conceito genuíno (taxa/tarifa em reais)
que pode voltar a ser usado se um dado de taxa de embarque separado da
tarifa completa em dinheiro for encontrado depois.
"""
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ofertas_emissao", sa.Column("duracao_texto", sa.String(20), nullable=True))


def downgrade():
    op.drop_column("ofertas_emissao", "duracao_texto")
