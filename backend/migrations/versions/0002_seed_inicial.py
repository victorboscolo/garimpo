"""Seed inicial — GAR-1100 Cap. 5

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-07
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.sql import table, column

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    dominios_t = table("dominios", column("id", pg.UUID), column("nome", sa.String), column("ativo", sa.Boolean))
    perfis_t = table("perfis", column("id", pg.UUID), column("nome", sa.String))
    programas_t = table(
        "programas", column("id", pg.UUID), column("dominio_id", pg.UUID),
        column("nome", sa.String), column("ativo", sa.Boolean),
    )
    categorias_t = table("categorias", column("id", pg.UUID), column("nome", sa.String), column("ativo", sa.Boolean))
    configuracoes_t = table(
        "configuracoes", column("id", pg.UUID), column("chave", sa.String),
        column("valor", pg.JSONB), column("descricao", sa.Text),
    )

    dominio_promocoes_id = uuid.uuid4()
    dominio_emissoes_id = uuid.uuid4()

    op.bulk_insert(dominios_t, [
        {"id": dominio_promocoes_id, "nome": "PROMOCOES", "ativo": True},
        {"id": dominio_emissoes_id, "nome": "EMISSOES", "ativo": False},
    ])

    op.bulk_insert(perfis_t, [
        {"id": uuid.uuid4(), "nome": "ADMIN"},
        {"id": uuid.uuid4(), "nome": "OPERADOR"},
    ])

    op.bulk_insert(programas_t, [
        {"id": uuid.uuid4(), "dominio_id": dominio_promocoes_id, "nome": "Livelo", "ativo": True},
        {"id": uuid.uuid4(), "dominio_id": dominio_promocoes_id, "nome": "Esfera", "ativo": True},
    ])

    op.bulk_insert(categorias_t, [
        {"id": uuid.uuid4(), "nome": nome, "ativo": True}
        for nome in [
            "Moda", "Eletrônicos", "Supermercado", "Farmácia",
            "Viagens", "Casa", "Esportes", "Livros",
        ]
    ])

    op.bulk_insert(configuracoes_t, [
        {
            "id": uuid.uuid4(),
            "chave": "pesos_motor_v1",
            "valor": {
                "historico": 25, "atratividade": 25, "amplitude": 20,
                "facilidade": 10, "exclusividade": 10, "confiabilidade_dados": 10,
            },
            "descricao": "Pesos dos 6 pilares do Motor V1. Soma deve ser 100.",
        },
        {
            "id": uuid.uuid4(),
            "chave": "faixas_classificacao",
            "valor": {
                "excepcional": {"min": 90, "max": 100},
                "excelente": {"min": 75, "max": 89},
                "boa": {"min": 55, "max": 74},
                "comum": {"min": 35, "max": 54},
                "pouco_atrativa": {"min": 0, "max": 34},
            },
            "descricao": "Faixas de nota que definem a categoria final exibida ao usuário.",
        },
        {
            "id": uuid.uuid4(),
            "chave": "historico_suficiente",
            "valor": {"min_campanhas": 3, "janela_dias": 365},
            "descricao": "Limiar para considerar o histórico da família (parceiro+programa) suficiente.",
        },
        {
            "id": uuid.uuid4(),
            "chave": "peso_temporal",
            "valor": {
                "recente_dias": 180, "recente_peso": 1.0,
                "medio_dias": 365, "medio_peso": 0.6,
                "antigo_peso": 0.3,
            },
            "descricao": "Peso decrescente por proximidade temporal das campanhas no histórico.",
        },
    ])


def downgrade():
    op.execute("DELETE FROM configuracoes WHERE chave IN "
               "('pesos_motor_v1', 'faixas_classificacao', 'historico_suficiente', 'peso_temporal')")
    op.execute("DELETE FROM categorias")
    op.execute("DELETE FROM programas")
    op.execute("DELETE FROM perfis")
    op.execute("DELETE FROM dominios")
