"""Pontuação anterior e selo de promoção

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-14

Dois dados que o card da Livelo sempre trouxe e o coletor descartava:

- `pontuacao_anterior` — o "Eram 1 ponto" que acompanha as ofertas em campanha.
  Diz de onde a oferta saiu, e é o tamanho do salto que faz a notícia: o
  Consórcio da Liga Vitória foi de 1 para 100 pontos. Esse valor vivia dentro
  de uma frase que o coletor escrevia em `regulamento_texto`, e passou a ser
  perdido quando essa frase começou a ser substituída pelo regulamento real da
  campanha — esta coluna recupera o dado em lugar próprio.

- `em_promocao` — o selo "Promoção" do card. Mede eixo diferente da nota: a
  nota diz se a oferta é boa, o selo diz que ela é temporária e vai expirar.

Nenhuma das duas entra no hash de deduplicação. Elas descrevem o contexto da
oferta, não seus termos: uma campanha que recalcula a base de comparação, ou
que sai do selo mantendo a mesma pontuação, não é uma oferta diferente. Manter
fora do hash também evita invalidar os hashes já gravados.
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("promocoes", sa.Column("pontuacao_anterior", sa.Numeric(10, 2), nullable=True))
    op.add_column(
        "promocoes",
        sa.Column("em_promocao", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("promocoes", "em_promocao")
    op.drop_column("promocoes", "pontuacao_anterior")
