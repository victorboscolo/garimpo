import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


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


class PromocaoRejeitarIn(BaseModel):
    motivo_rejeicao: str


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
