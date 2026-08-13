"""Contrato que todo coletor de programa deve implementar.

Cada coletor roda isolado: uma exceção em um coletor nunca deve derrubar
os demais nem o sistema (decisão registrada na auditoria — Cap. 6).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PromocaoBruta:
    """Dado ainda não persistido, como veio da página de origem."""
    programa_nome: str
    parceiro_nome_bruto: str  # resolvido para parceiro_id via parceiro_aliases no pipeline
    titulo: str
    url_origem: str
    pontuacao: Decimal
    unidade_pontuacao: str
    regulamento_texto: str | None = None
    data_inicio: str | None = None
    data_fim: str | None = None
    requer_clube: bool = False
    qual_clube: str | None = None
    requer_cupom: bool = False
    cupom: str | None = None


class ColetorBase(ABC):
    """Toda implementação de coletor (Livelo, Esfera, ...) herda daqui."""

    origem_detalhe: str  # ex.: "COLETOR_LIVELO"

    @abstractmethod
    async def coletar(self) -> list[PromocaoBruta]:
        """Executa a coleta e retorna a lista de promoções brutas encontradas.

        Implementações devem deixar exceções de rede/parsing subirem —
        o tratamento de erro (log + retry) é responsabilidade do pipeline,
        não do coletor individual.
        """
        raise NotImplementedError
