import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ClassificacaoResumoOut(BaseModel):
    """Classificação ativa embutida na listagem, para o painel não precisar de
    uma requisição por promoção só para mostrar a nota.
    """
    model_config = ConfigDict(from_attributes=True)

    nota: Decimal
    categoria: str
    criterios_avaliados: dict
    confianca_historica: str
    confiabilidade_dados: Decimal
    justificativa: str


class PromocaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    codigo_amigavel: str | None
    programa_id: uuid.UUID
    programa_nome: str
    parceiro_id: uuid.UUID
    parceiro_nome: str
    titulo: str
    pontuacao: Decimal
    unidade_pontuacao: str
    disponibilidade: str
    status: str
    motivo_rejeicao: str | None = None
    origem: str
    origem_detalhe: str | None = None
    url_origem: str
    data_inicio: datetime | None
    data_fim: datetime | None
    created_at: datetime

    # Campos que já existiam no banco mas não chegavam ao painel.
    regulamento_texto: str | None = None
    regulamento_resumo: str | None = None
    marketplace_status: str | None = None
    abrangencia: str | None = None
    restricoes: str | None = None
    requer_clube: bool = False
    qual_clube: str | None = None
    requer_cupom: bool = False
    cupom: str | None = None

    classificacao_ativa: ClassificacaoResumoOut | None = None


class PromocaoRejeitarIn(BaseModel):
    motivo_rejeicao: str


class PromocaoAprovarLoteIn(BaseModel):
    ids: list[uuid.UUID]


class PromocaoRejeitarLoteIn(BaseModel):
    ids: list[uuid.UUID]
    motivo_rejeicao: str


class LoteIgnoradaOut(BaseModel):
    id: uuid.UUID
    motivo: str


class LoteResultadoOut(BaseModel):
    """Lote é tolerante a falha parcial: uma promoção que saiu de PENDENTE
    entre o carregamento da tela e o clique não derruba as demais.
    """
    solicitadas: int
    processadas: int
    ignoradas: list[LoteIgnoradaOut]


class ClassificacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    versao_motor: str
    nota: Decimal
    categoria: str
    criterios_avaliados: dict
    confianca_historica: str
    confiabilidade_dados: Decimal
    justificativa: str
    ativa: bool
    processada_em: datetime


class PromocaoIngerirIn(BaseModel):
    """Payload usado por coletores externos (ex: coletor nativo do Mac) para
    enviar uma promoção bruta via HTTP, sem acesso direto ao banco.
    """
    programa_nome: str
    parceiro_nome_bruto: str
    titulo: str
    url_origem: str
    pontuacao: Decimal
    unidade_pontuacao: str
    regulamento_texto: str | None = None
    requer_clube: bool = False
    qual_clube: str | None = None
    requer_cupom: bool = False
    cupom: str | None = None
    origem_detalhe: str
