"""Entidade central: Promoção. Imutável no conteúdo (RN-001, Cap. 3).

Fonte da verdade do schema físico: GAR-1100 Cap. 3 (Rev. 2).
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Identity, Numeric, String, Text, and_, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from infrastructure.db.base import Base
from domain.cadastros import Parceiro, Programa
from domain.motor import ENTIDADE_PROMOCAO, Classificacao


class Promocao(Base):
    __tablename__ = "promocoes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    codigo_amigavel: Mapped[str | None] = mapped_column(String(50), unique=True)

    programa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("programas.id"), nullable=False)
    parceiro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parceiros.id"), nullable=False)

    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    url_origem: Mapped[str] = mapped_column(Text, nullable=False)

    regulamento_texto: Mapped[str | None] = mapped_column(Text)
    regulamento_resumo: Mapped[str | None] = mapped_column(Text)

    data_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    pontuacao: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unidade_pontuacao: Mapped[str] = mapped_column(String(50), nullable=False)

    requer_clube: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    qual_clube: Mapped[str | None] = mapped_column(String(100))
    requer_cupom: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cupom: Mapped[str | None] = mapped_column(String(100))

    marketplace_status: Mapped[str | None] = mapped_column(String(20))  # PERMITIDO|PROIBIDO|PARCIAL
    abrangencia: Mapped[str | None] = mapped_column(Text)
    restricoes: Mapped[str | None] = mapped_column(Text)
    disponibilidade: Mapped[str] = mapped_column(String(20), default="PUBLICA", nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="PENDENTE", nullable=False)
    motivo_rejeicao: Mapped[str | None] = mapped_column(Text)
    parametros_utilizados: Mapped[dict | None] = mapped_column(JSONB)

    origem: Mapped[str] = mapped_column(String(50), nullable=False)  # MANUAL|COLETOR|IMPORTACAO
    origem_detalhe: Mapped[str | None] = mapped_column(String(100))
    hash_promocao: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    criada_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    aprovada_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    aprovada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos (lazy="joined" carrega automaticamente num único SELECT
    # com JOIN, sem precisar de query extra — importante para a tela admin
    # não fazer 1 query por promoção só para mostrar o nome do parceiro).
    parceiro: Mapped["Parceiro"] = relationship("Parceiro", lazy="joined", foreign_keys=[parceiro_id])
    programa: Mapped["Programa"] = relationship("Programa", lazy="joined", foreign_keys=[programa_id])

    # Classificação ativa do Motor de Análise. `classificacoes` usa referência
    # polimórfica sem FK (ver domain/motor.py), então o join é declarado à mão.
    # viewonly=True: este lado nunca escreve — quem cria/desativa classificação
    # é o motor, e a integridade da referência polimórfica é responsabilidade
    # da aplicação (RN-013), não do ORM.
    # lazy="joined" evita lazy load: em sessão async, carregar sob demanda na
    # hora de serializar estouraria MissingGreenlet.
    classificacao_ativa: Mapped["Classificacao | None"] = relationship(
        "Classificacao",
        primaryjoin=lambda: and_(
            foreign(Classificacao.entidade_id) == Promocao.id,
            Classificacao.entidade_tipo == ENTIDADE_PROMOCAO,
            Classificacao.ativa.is_(True),
        ),
        viewonly=True,
        uselist=False,
        lazy="joined",
    )

    @property
    def parceiro_nome(self) -> str:
        return self.parceiro.nome

    @property
    def programa_nome(self) -> str:
        return self.programa.nome


class CategoriaPromocao(Base):
    """Associação N:N — uma promoção pode abranger mais de uma categoria."""
    __tablename__ = "categorias_promocao"

    promocao_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("promocoes.id"), primary_key=True)
    categoria_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("categorias.id"), primary_key=True)
