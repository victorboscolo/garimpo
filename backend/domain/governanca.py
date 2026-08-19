"""Usuários/perfis, parâmetros calibráveis (configuracoes) e auditoria.

Fonte da verdade do schema físico: GAR-1100 Cap. 3 (Rev. 2).
"""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Identity, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.base import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    senha_hash: Mapped[str] = mapped_column(Text, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Perfil(Base):
    __tablename__ = "perfis"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)  # ADMIN | OPERADOR


class UsuarioPerfil(Base):
    __tablename__ = "usuario_perfis"

    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"), primary_key=True)
    perfil_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("perfis.id"), primary_key=True)


class Configuracao(Base):
    __tablename__ = "configuracoes"
    __table_args__ = (
        UniqueConstraint("chave", "dominio_id", "programa_id", "parceiro_id", name="uq_configuracoes_escopo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chave: Mapped[str] = mapped_column(String(200), nullable=False)

    dominio_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("dominios.id"))
    programa_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("programas.id"))
    parceiro_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("parceiros.id"))

    valor: Mapped[dict] = mapped_column(JSONB, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Auditoria(Base):
    __tablename__ = "auditoria"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    entidade: Mapped[str] = mapped_column(String(100), nullable=False)
    entidade_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    acao: Mapped[str] = mapped_column(String(100), nullable=False)
    dados_anteriores: Mapped[dict | None] = mapped_column(JSONB)
    dados_novos: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Execucao(Base):
    """Uma linha por execução de um job de infraestrutura (coletor, recalibração,
    backup) — quem executa registra o resultado ao terminar.

    Suporte ao Painel de Saúde: sem isso, um coletor que parou de rodar (Mac
    desligado, site mudou, anti-robô passou a bloquear) só é percebido quando
    alguém nota a ausência de ofertas novas. `job` não é FK de propósito: o
    conjunto de jobs é pequeno e fixo (coletor_livelo, coletor_esfera,
    recalibracao, backup), não um cadastro que cresce.
    """
    __tablename__ = "execucoes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Critério de "mais recente" — não created_at: dentro de uma mesma
    # transação Postgres, now() é sempre o mesmo valor, então duas execuções
    # registradas na mesma transação empatariam. Identity() é sequencial de
    # verdade.
    codigo: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    job: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # SUCESSO | FALHA
    criadas: Mapped[int | None] = mapped_column(Integer)
    descartadas: Mapped[int | None] = mapped_column(Integer)
    falhas: Mapped[int | None] = mapped_column(Integer)
    erro: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
