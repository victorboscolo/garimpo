"""Saída do Motor de Análise, arquivos de evidência e publicações.

IMPORTANTE: estas 3 tabelas usam referência polimórfica (entidade_tipo +
entidade_id) em vez de FK nativa, para servirem tanto ao domínio Promoções
quanto ao futuro domínio Emissões sem redesenho de schema (RN-012, Cap. 3
Rev. 2). A validação de que entidade_id existe na tabela correspondente ao
entidade_tipo é responsabilidade da camada de aplicação (RN-013) — ver
application/validators.py.
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Identity, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.base import Base

ENTIDADE_PROMOCAO = "PROMOCAO"
ENTIDADE_EMISSAO = "EMISSAO"  # reservado para o futuro Garimpo Emissões


class Classificacao(Base):
    __tablename__ = "classificacoes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)

    entidade_tipo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    entidade_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    versao_motor: Mapped[str] = mapped_column(String(50), nullable=False)
    nota: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    categoria: Mapped[str] = mapped_column(String(50), nullable=False)

    criterios_avaliados: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confianca_historica: Mapped[str] = mapped_column(String(20), nullable=False)  # ALTA|MEDIA|BAIXA
    confiabilidade_dados: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    justificativa: Mapped[str] = mapped_column(Text, nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    processada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Arquivo(Base):
    __tablename__ = "arquivos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entidade_tipo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    entidade_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    tipo: Mapped[str] = mapped_column(String(50), nullable=False)  # PDF|REGULAMENTO|ANEXO
    arquivo_url: Mapped[str] = mapped_column(Text, nullable=False)
    hash_arquivo: Mapped[str | None] = mapped_column(String(128))
    texto_extraido: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Publicacao(Base):
    __tablename__ = "publicacoes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entidade_tipo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    entidade_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    canal: Mapped[str] = mapped_column(String(50), default="TELEGRAM", nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)  # ADMIN|PUBLICO|AVANCADO
    status: Mapped[str] = mapped_column(String(20), default="PENDENTE", nullable=False)
    erro_resumido: Mapped[str | None] = mapped_column(Text)
    data_envio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
