"""Valor condicionado: guarda o piso do degrau

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-01

`valor_condicionado` (migration 0006) diz *que* o valor exibido não vale
para a compra inteira, mas não *o quanto* ele cai — um degrau de 10 para 2
(Renner, 80% de queda) e um de 7 para 6 (Magalu/Esfera, 14% de queda) eram
penalizados exatamente igual no pilar Amplitude, uma penalidade fixa de -25.
Decisão do usuário (01/09), a partir do caso real do Magalu: o tamanho do
degrau importa — a penalidade deve escalar com a queda relativa, não ser
plana.

`valor_condicionado_piso` guarda o menor valor citado no regulamento (o
mesmo que `application/condicoes.valor_e_condicionado` já calcula pra
decidir o booleano, só que descartava o número). Nulo quando não há piso
extraível do texto — caso do "Até X" sem nenhuma segunda pontuação no
regulamento, onde não há magnitude conhecida pra escalar; o pilar cai de
volta na penalidade plena nesse caso.

Mesmo raciocínio da 0006: derivado de `pontuacao` e `regulamento_texto`,
não entra no hash de deduplicação.
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "promocoes",
        sa.Column("valor_condicionado_piso", sa.Numeric(10, 2), nullable=True),
    )


def downgrade():
    op.drop_column("promocoes", "valor_condicionado_piso")
