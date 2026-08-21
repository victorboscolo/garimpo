"""Emissões: rastreia por perna (ida), não por pacote ida+volta

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-21

Decisão do usuário (21/08): uma promoção de ida sozinha tem mais alcance de
público e dá liberdade pro usuário — uma "oferta de volta" é só outra
`OfertaEmissao` na direção oposta, não um par amarrado na mesma linha. Ver
domain/emissoes.py.

Remove `data_volta` (não existe mais pacote). Troca `voo_direto` (bool) por
`paradas` (int) — estritamente mais informativo. Adiciona
`assentos_restantes`, sinal de escassez que o site principal já expõe.

Só existia 1 linha de teste em `ofertas_emissao` no momento desta migration
(o teste manual de ponta a ponta do dia anterior) — nenhum dado de produção
real perdido.
"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("ofertas_emissao", "data_volta")
    op.drop_column("ofertas_emissao", "voo_direto")
    op.add_column("ofertas_emissao", sa.Column("paradas", sa.Integer(), nullable=True))
    op.add_column("ofertas_emissao", sa.Column("assentos_restantes", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("ofertas_emissao", "assentos_restantes")
    op.drop_column("ofertas_emissao", "paradas")
    op.add_column("ofertas_emissao", sa.Column("voo_direto", sa.Boolean(), nullable=True))
    op.add_column("ofertas_emissao", sa.Column("data_volta", sa.Date(), nullable=True))
