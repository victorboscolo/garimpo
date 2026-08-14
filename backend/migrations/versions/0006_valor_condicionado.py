"""Valor condicionado

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-14

Marca as ofertas cujo valor exibido não vale para a compra inteira.

Até aqui o painel sinalizava isso apenas quando o card dizia "Até X", o que
deixava passar os casos mais graves: o Renner anuncia "10 pontos" sem qualquer
ressalva, e só o regulamento revela que os 10 valem na categoria Básicos
enquanto o resto da loja rende 2. A Decolar anuncia 12 pontos por dólar válidos
apenas para aluguel de carros.

O critério está em application/condicoes.py e compara o valor exibido com a
escada declarada pelo próprio regulamento. Fica em coluna porque é consultável,
e porque o pilar Amplitude do motor — hoje 65 fixo para todos por falta de
qualquer sinal de alcance — pode passar a usá-lo.

Derivado de `pontuacao`, `regulamento_texto` e `pontuacao_e_teto`, então não
entra no hash de deduplicação: não é fato novo sobre a oferta, é leitura dos
fatos que já estão lá.
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "promocoes",
        sa.Column("valor_condicionado", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("promocoes", "valor_condicionado")
