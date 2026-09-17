"""Garimpo Emissões: disponibilidade de assento por milhas, rota e data.

Natureza diferente do Promoções (domain/promocoes.py): não é "ganhe pontos"
num parceiro, é "quanto custa em milhas hoje" para uma combinação de
rota+data+classe — por isso não reaproveita `Promocao`. Reaproveita sim
`Programa`/`Dominio` (o schema já antecipava um `Dominio` "EMISSOES", ver
cadastros.py) e o princípio geral de imutabilidade: cada coleta grava uma
`OfertaEmissao` nova, nunca sobrescreve a anterior — é o que sustenta o sinal
futuro de "queda de preço ao longo do tempo" (precisa do histórico, não só do
valor mais recente).

Sem motor, sem classificação automática: decisão de produto (18/08) — o
sistema ainda não tem histórico suficiente para calibrar isso, e a
experiência pessoal do usuário em milhas vale mais que uma heurística nova.
Aprovação e publicação, quando existirem, são manuais.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.base import Base


class RotaEmissao(Base):
    """Uma combinação origem→destino que o coletor monitora.

    Catálogo curado à mão (seção 5 do HANDOFF tem a lista completa e o
    critério de cada uma) — não é dado que os usuários submetem. `fonte`
    existe porque a Azul precisa de dois sistemas de busca diferentes: a
    malha própria dela (site principal, inclui Flórida/Lisboa/Paris) e o
    portal `azulpelomundo` para o resto do internacional via parceiro —
    achado técnico de 20/08, ver HANDOFF seção 5.
    """
    __tablename__ = "rotas_emissao"
    __table_args__ = (UniqueConstraint("programa_id", "origem", "destino", name="uq_rota_emissao_programa_od"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    programa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("programas.id"), nullable=False)
    origem: Mapped[str] = mapped_column(String(3), nullable=False)
    destino: Mapped[str] = mapped_column(String(3), nullable=False)
    fonte: Mapped[str] = mapped_column(String(30), nullable=False)  # SITE_PRINCIPAL | AZUL_PELO_MUNDO
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OfertaEmissao(Base):
    """O preço em milhas mais barato encontrado para uma perna (trecho de
    ida, uma direção só) numa rota+data+classe, numa coleta. Só o mais
    barato — decisão do usuário (19/08): buscar traz várias opções de
    horário/conexão, mas o sinal que importa aqui é "qual o menor preço
    hoje", não a lista inteira.

    Por perna, não por pacote ida+volta — decisão do usuário (21/08): uma
    promoção de ida sozinha tem mais alcance de público e dá liberdade pro
    usuário não ficar preso a uma data de volta específica. Uma "oferta de
    volta" é só outra `OfertaEmissao`, na direção oposta — não um par
    amarrado na mesma linha. Por isso a busca também precisa ser só-ida de
    verdade, não ida-e-volta com a volta descartada: o preço da ida dentro
    de um pacote combinado pode ser mais barato do que comprá-la sozinha.

    Imutável: cada coleta cria uma linha nova, nunca atualiza uma existente
    — mesmo princípio do Promoções, e aqui é ainda mais essencial, porque o
    histórico de preço ao longo do tempo é o dado, não um efeito colateral.
    """
    __tablename__ = "ofertas_emissao"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rota_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rotas_emissao.id"), nullable=False)

    data_ida: Mapped[date] = mapped_column(Date, nullable=False)
    classe: Mapped[str] = mapped_column(String(20), nullable=False)  # ECONOMY | BUSINESS

    pontos: Mapped[int] = mapped_column(Integer, nullable=False)
    # Não populado pelos coletores desde 17/09 (decisão do usuário: só
    # milhas) — o valor que existia aqui vinha de um produto diferente da
    # oferta em pontos (a opção 100%-dinheiro ou milhas+dinheiro, que os
    # sites mostram ao lado, não uma taxa sobre a própria oferta em
    # pontos). Fica no schema porque o conceito "taxa em reais separada da
    # tarifa" ainda pode voltar a ter uso — ver migration 0013.
    taxa_reais: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    companhia_operadora: Mapped[str | None] = mapped_column(String(100))
    # Texto tal qual o site mostra ("11h25", "02h50min") — decisão do
    # usuário (17/09): não converter pra minutos, pra não supor uma
    # precisão que a fonte não garante.
    duracao_texto: Mapped[str | None] = mapped_column(String(20))
    # 0 = voo direto, 1+ = número de conexões. Substituiu um `voo_direto`
    # booleano (decisão do usuário, 21/08) — estritamente mais informativo,
    # direto vira só `paradas == 0`.
    paradas: Mapped[int | None] = mapped_column(Integer)
    # Sinal de escassez, quando a fonte expõe (site principal expõe a
    # contagem exata; azulpelomundo só um booleano — nesse caso fica None
    # aqui e o booleano vira sinal à parte, não inventado como número).
    assentos_restantes: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
