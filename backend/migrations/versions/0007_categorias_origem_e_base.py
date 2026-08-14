"""Categorias de origem, vínculo N:N com parceiro, e pontuação base

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-14

Duas coisas que a listagem da Livelo entrega e ninguém estava lendo, descobertas
ao inspecionar o JSON que a página embute.

## `promocoes.pontuacao_base`

O `parityBau` da Livelo: quanto a oferta vale fora da campanha. É o piso real, e
ele muda o entendimento de várias ofertas — a Liga Vitória Consórcio anuncia
"até 100 pontos" e volta a 1 quando a promoção acabar; o Renner anuncia 10 e
volta a 2, o que casa exatamente com o "e 2 pontos demais produtos" do
regulamento. Nada no texto renderizado da página expunha isso.

Fica fora do hash de deduplicação: descreve o contexto da oferta, não seus
termos, e mudança de base sem mudança de pontuação não é oferta nova.

## `categorias_origem` e `parceiro_categorias`

A Livelo classifica cada parceiro em uma ou mais de 38 categorias
("modaebeleza", "calcados", "seguroviagem"). São o insumo que faltava para o
motor comparar uma oferta com as do mesmo segmento em vez de com o programa
inteiro — hoje 223 dos 249 parceiros não têm histórico próprio e o pilar
Histórico devolve neutro para eles.

O modelo tem duas camadas de propósito:

- `categorias_origem` guarda o slug **exato como a fonte informa**, por programa.
  É fiel e nunca inventado. Quando a Esfera entrar, terá o vocabulário dela
  aqui, sem conflito.
- `categorias` (que já existia, com 8 registros do seed e nenhum uso) passa a
  ser a camada **canônica**: o agrupamento que nós decidimos, ligado por
  `categorias_origem.categoria_id`, que nasce nulo.

Assim o agrupamento é uma operação de dados feita quando houver vontade — não
exige recoletar nem altera o histórico —, e permanece distinguível do que veio
da fonte. Nada do seed é apagado: as 8 categorias existentes viram o ponto de
partida da camada canônica.

O vínculo com o parceiro é N:N porque a Livelo dá várias categorias ao mesmo
parceiro (Renner é "modaebeleza" e "modaeacessorios").
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("promocoes", sa.Column("pontuacao_base", sa.Numeric(10, 2), nullable=True))

    op.create_table(
        "categorias_origem",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("programa_id", pg.UUID(as_uuid=True), sa.ForeignKey("programas.id"), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        # Agrupamento canônico, preenchido por curadoria. Nulo = ainda não agrupado.
        sa.Column("categoria_id", pg.UUID(as_uuid=True), sa.ForeignKey("categorias.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("programa_id", "slug", name="uq_categoria_origem_programa_slug"),
    )
    op.create_index("ix_categorias_origem_categoria_id", "categorias_origem", ["categoria_id"])

    op.create_table(
        "parceiro_categorias",
        sa.Column("parceiro_id", pg.UUID(as_uuid=True), sa.ForeignKey("parceiros.id"), primary_key=True),
        sa.Column("categoria_origem_id", pg.UUID(as_uuid=True), sa.ForeignKey("categorias_origem.id"), primary_key=True),
    )


def downgrade():
    op.drop_table("parceiro_categorias")
    op.drop_index("ix_categorias_origem_categoria_id", table_name="categorias_origem")
    op.drop_table("categorias_origem")
    op.drop_column("promocoes", "pontuacao_base")
