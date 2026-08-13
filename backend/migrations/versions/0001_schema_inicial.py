"""Schema inicial — GAR-1100 Cap. 3 (Rev. 2)

Revision ID: 0001
Revises:
Create Date: 2026-08-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')  # gen_random_uuid()

    op.create_table(
        "dominios",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("codigo", sa.BigInteger, sa.Identity(), unique=True, nullable=False),
        sa.Column("nome", sa.String(50), nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "marcas",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("codigo", sa.BigInteger, sa.Identity(), unique=True, nullable=False),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_marcas_nome", "marcas", ["nome"])

    op.create_table(
        "categorias",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("codigo", sa.BigInteger, sa.Identity(), unique=True, nullable=False),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("categoria_pai_id", pg.UUID(as_uuid=True), sa.ForeignKey("categorias.id"), nullable=True),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_categorias_pai", "categorias", ["categoria_pai_id"])

    op.create_table(
        "programas",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("codigo", sa.BigInteger, sa.Identity(), unique=True, nullable=False),
        sa.Column("dominio_id", pg.UUID(as_uuid=True), sa.ForeignKey("dominios.id"), nullable=False),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_programas_dominio", "programas", ["dominio_id"])

    op.create_table(
        "parceiros",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("codigo", sa.BigInteger, sa.Identity(), unique=True, nullable=False),
        sa.Column("marca_id", pg.UUID(as_uuid=True), sa.ForeignKey("marcas.id"), nullable=False),
        sa.Column("categoria_id", pg.UUID(as_uuid=True), sa.ForeignKey("categorias.id"), nullable=True),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("nome_normalizado", sa.String(200), nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_parceiros_marca", "parceiros", ["marca_id"])
    op.create_index("idx_parceiros_categoria", "parceiros", ["categoria_id"])

    op.create_table(
        "parceiro_aliases",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("parceiro_id", pg.UUID(as_uuid=True), sa.ForeignKey("parceiros.id"), nullable=False),
        sa.Column("alias", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_parceiro_aliases_parceiro", "parceiro_aliases", ["parceiro_id"])

    op.create_table(
        "usuarios",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("codigo", sa.BigInteger, sa.Identity(), unique=True, nullable=False),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("email", sa.String(200), unique=True, nullable=False),
        sa.Column("senha_hash", sa.Text, nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "perfis",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("nome", sa.String(100), nullable=False),
    )

    op.create_table(
        "usuario_perfis",
        sa.Column("usuario_id", pg.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), primary_key=True),
        sa.Column("perfil_id", pg.UUID(as_uuid=True), sa.ForeignKey("perfis.id"), primary_key=True),
    )

    op.create_table(
        "configuracoes",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("chave", sa.String(200), nullable=False),
        sa.Column("dominio_id", pg.UUID(as_uuid=True), sa.ForeignKey("dominios.id"), nullable=True),
        sa.Column("programa_id", pg.UUID(as_uuid=True), sa.ForeignKey("programas.id"), nullable=True),
        sa.Column("parceiro_id", pg.UUID(as_uuid=True), sa.ForeignKey("parceiros.id"), nullable=True),
        sa.Column("valor", pg.JSONB, nullable=False),
        sa.Column("descricao", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("chave", "dominio_id", "programa_id", "parceiro_id", name="uq_configuracoes_escopo"),
    )
    op.create_index("idx_configuracoes_chave", "configuracoes", ["chave"])

    op.create_table(
        "promocoes",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("codigo", sa.BigInteger, sa.Identity(), unique=True, nullable=False),
        sa.Column("codigo_amigavel", sa.String(50), unique=True, nullable=True),
        sa.Column("programa_id", pg.UUID(as_uuid=True), sa.ForeignKey("programas.id"), nullable=False),
        sa.Column("parceiro_id", pg.UUID(as_uuid=True), sa.ForeignKey("parceiros.id"), nullable=False),
        sa.Column("titulo", sa.String(300), nullable=False),
        sa.Column("descricao", sa.Text, nullable=True),
        sa.Column("url_origem", sa.Text, nullable=False),
        sa.Column("regulamento_texto", sa.Text, nullable=True),
        sa.Column("regulamento_resumo", sa.Text, nullable=True),
        sa.Column("data_inicio", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_fim", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pontuacao", sa.Numeric(10, 2), nullable=False),
        sa.Column("unidade_pontuacao", sa.String(50), nullable=False),
        sa.Column("requer_clube", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("qual_clube", sa.String(100), nullable=True),
        sa.Column("requer_cupom", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("cupom", sa.String(100), nullable=True),
        sa.Column("marketplace_status", sa.String(20), nullable=True),
        sa.Column("abrangencia", sa.Text, nullable=True),
        sa.Column("restricoes", sa.Text, nullable=True),
        sa.Column("disponibilidade", sa.String(20), nullable=False, server_default="PUBLICA"),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDENTE"),
        sa.Column("motivo_rejeicao", sa.Text, nullable=True),
        sa.Column("parametros_utilizados", pg.JSONB, nullable=True),
        sa.Column("origem", sa.String(50), nullable=False),
        sa.Column("origem_detalhe", sa.String(100), nullable=True),
        sa.Column("hash_promocao", sa.String(128), nullable=False),
        sa.Column("criada_por", pg.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("aprovada_por", pg.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("aprovada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_promocoes_programa", "promocoes", ["programa_id"])
    op.create_index("idx_promocoes_parceiro", "promocoes", ["parceiro_id"])
    op.create_index("idx_promocoes_status", "promocoes", ["status"])
    op.create_index("idx_promocoes_datas", "promocoes", ["data_inicio", "data_fim"])
    op.create_index("idx_promocoes_hash", "promocoes", ["hash_promocao"])

    op.create_table(
        "categorias_promocao",
        sa.Column("promocao_id", pg.UUID(as_uuid=True), sa.ForeignKey("promocoes.id"), primary_key=True),
        sa.Column("categoria_id", pg.UUID(as_uuid=True), sa.ForeignKey("categorias.id"), primary_key=True),
    )

    op.create_table(
        "arquivos",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entidade_tipo", sa.String(20), nullable=False),
        sa.Column("entidade_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("tipo", sa.String(50), nullable=False),
        sa.Column("arquivo_url", sa.Text, nullable=False),
        sa.Column("hash_arquivo", sa.String(128), nullable=True),
        sa.Column("texto_extraido", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_arquivos_entidade", "arquivos", ["entidade_tipo", "entidade_id"])

    op.create_table(
        "classificacoes",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("codigo", sa.BigInteger, sa.Identity(), unique=True, nullable=False),
        sa.Column("entidade_tipo", sa.String(20), nullable=False),
        sa.Column("entidade_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("versao_motor", sa.String(50), nullable=False),
        sa.Column("nota", sa.Numeric(5, 2), nullable=False),
        sa.Column("categoria", sa.String(50), nullable=False),
        sa.Column("criterios_avaliados", pg.JSONB, nullable=False),
        sa.Column("confianca_historica", sa.String(20), nullable=False),
        sa.Column("confiabilidade_dados", sa.Numeric(5, 2), nullable=False),
        sa.Column("justificativa", sa.Text, nullable=False),
        sa.Column("ativa", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("processada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_classificacoes_entidade", "classificacoes", ["entidade_tipo", "entidade_id"])
    op.create_index("idx_classificacoes_ativa", "classificacoes", ["ativa"])
    op.create_index("idx_classificacoes_nota", "classificacoes", ["nota"])

    op.create_table(
        "publicacoes",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entidade_tipo", sa.String(20), nullable=False),
        sa.Column("entidade_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("canal", sa.String(50), nullable=False, server_default="TELEGRAM"),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDENTE"),
        sa.Column("erro_resumido", sa.Text, nullable=True),
        sa.Column("data_envio", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_publicacoes_entidade", "publicacoes", ["entidade_tipo", "entidade_id"])
    op.create_index("idx_publicacoes_status", "publicacoes", ["status"])
    op.create_index("idx_publicacoes_data_envio", "publicacoes", ["data_envio"])

    op.create_table(
        "auditoria",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("usuario_id", pg.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("entidade", sa.String(100), nullable=False),
        sa.Column("entidade_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("acao", sa.String(100), nullable=False),
        sa.Column("dados_anteriores", pg.JSONB, nullable=True),
        sa.Column("dados_novos", pg.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_auditoria_entidade", "auditoria", ["entidade", "entidade_id"])


def downgrade():
    op.drop_table("auditoria")
    op.drop_table("publicacoes")
    op.drop_table("classificacoes")
    op.drop_table("arquivos")
    op.drop_table("categorias_promocao")
    op.drop_table("promocoes")
    op.drop_table("configuracoes")
    op.drop_table("usuario_perfis")
    op.drop_table("perfis")
    op.drop_table("usuarios")
    op.drop_table("parceiro_aliases")
    op.drop_table("parceiros")
    op.drop_table("programas")
    op.drop_table("categorias")
    op.drop_table("marcas")
    op.drop_table("dominios")
