"""Variantes de parceiro e pontuação como teto

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-13

Duas lacunas encontradas ao inspecionar os cards reais da Livelo:

1. `promocoes.pontuacao_e_teto` — 33 dos 248 cards anunciam "Até X pontos".
   O coletor gravava X como valor fixo, e essas ofertas subiam ao topo do
   ranking como se fossem garantidas. O valor em `pontuacao` continua sendo X
   (decisão de produto: o valor anunciado é o que se apresenta); esta coluna
   registra que ele é um limite, e o motor reduz a confiabilidade dos dados.

2. `parceiros.codigo_externo` — um mesmo slug pode ter ofertas distintas:
   beach-park/BPK são os Hotéis e beach-park/BHP os Ingressos. Como o parceiro
   era resolvido só pelo nome, as duas viravam um registro só e o motor usava
   o histórico de uma como se fosse da outra.

3. `parceiros.nome_exibicao` — nome legível para a tela. Fica separado de
   `nome` de propósito: `nome` participa da identidade usada na ingestão e no
   hash de deduplicação, então renomear para "Beach Park Hotéis" ali faria a
   próxima coleta não reconhecer o parceiro e duplicar o histórico.

Esta migration só altera o schema. O preenchimento dos dados existentes (e o
recálculo dos hashes, que a mudança de fórmula invalida) fica no script
`scripts/backfill_0003.py`, que roda em Python para usar exatamente a mesma
função `calcular_hash` da aplicação.
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "promocoes",
        sa.Column("pontuacao_e_teto", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("parceiros", sa.Column("codigo_externo", sa.String(20), nullable=True))
    op.add_column("parceiros", sa.Column("nome_exibicao", sa.String(200), nullable=True))
    op.create_index("ix_parceiros_codigo_externo", "parceiros", ["codigo_externo"])


def downgrade():
    op.drop_index("ix_parceiros_codigo_externo", table_name="parceiros")
    op.drop_column("parceiros", "nome_exibicao")
    op.drop_column("parceiros", "codigo_externo")
    op.drop_column("promocoes", "pontuacao_e_teto")
