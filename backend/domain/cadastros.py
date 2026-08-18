"""Entidades de cadastro: Domínio, Marca, Categoria, Programa, Parceiro.

Fonte da verdade do schema físico: GAR-1100 Cap. 3 (Rev. 2).
"""
import uuid
from datetime import datetime

from sqlalchemy import UniqueConstraint, BigInteger, Boolean, DateTime, ForeignKey, Identity, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.base import Base


class Dominio(Base):
    __tablename__ = "dominios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    nome: Mapped[str] = mapped_column(String(50), nullable=False)  # 'PROMOCOES' | 'EMISSOES'
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Marca(Base):
    __tablename__ = "marcas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    categoria_pai_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categorias.id"), nullable=True
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Programa(Base):
    __tablename__ = "programas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    dominio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dominios.id"), nullable=False)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)  # Livelo, Esfera, Smiles...
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CategoriaOrigem(Base):
    """Categoria como o programa de origem a informa, sem tradução.

    A Livelo classifica parceiros em 38 slugs ("modaebeleza", "seguroviagem").
    Guardar o valor exato mantém o dado fiel e evita conflito quando outro
    programa trouxer vocabulário próprio.

    `categoria_id` é o agrupamento canônico que nós decidimos, e nasce nulo: só
    é preenchido por curadoria, o que mantém sempre distinguível o que veio da
    fonte do que foi decisão nossa.
    """
    __tablename__ = "categorias_origem"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    programa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("programas.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("categorias.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("programa_id", "slug", name="uq_categoria_origem_programa_slug"),)


class ParceiroCategoria(Base):
    """N:N — a Livelo dá várias categorias ao mesmo parceiro.

    `categoria_id` é a curadoria canônica **deste parceiro** neste slug —
    não do slug em geral. Um slug largo como "casaedecoracao" mistura
    parceiros de natureza bem diferente; a curadoria real mostrou isso
    distribuindo um mesmo slug em até 7 categorias canônicas diferentes,
    a depender do parceiro. Por isso o vínculo, não o slug
    (`categorias_origem.categoria_id`), é o nível certo pra essa decisão.
    Nulo até que alguém classifique; o motor cai no slug bruto até lá.
    """
    __tablename__ = "parceiro_categorias"

    parceiro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parceiros.id"), primary_key=True)
    categoria_origem_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("categorias_origem.id"), primary_key=True)
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("categorias.id"), index=True)


class Parceiro(Base):
    __tablename__ = "parceiros"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    marca_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("marcas.id"), nullable=False)
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("categorias.id"), nullable=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    nome_normalizado: Mapped[str] = mapped_column(String(200), nullable=False)
    # Código da variante no programa de origem. Um mesmo slug da Livelo pode
    # ter ofertas distintas (beach-park/BPK são os Hotéis, /BHP os Ingressos):
    # sem isso, as duas viram um parceiro só e o motor usa o histórico de uma
    # como se fosse da outra.
    codigo_externo: Mapped[str | None] = mapped_column(String(20), index=True)
    # Nome legível para a tela, separado de `nome` de propósito: `nome` entra na
    # identidade usada na ingestão e no hash de dedup, então renomear ali faria
    # a próxima coleta não reconhecer o parceiro e duplicar o histórico.
    nome_exibicao: Mapped[str | None] = mapped_column(String(200))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ParceiroAlias(Base):
    __tablename__ = "parceiro_aliases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parceiro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parceiros.id"), nullable=False)
    alias: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
