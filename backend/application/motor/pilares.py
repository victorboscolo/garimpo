"""Os 6 pilares do Motor de Análise V1.

Cada função recebe os dados necessários e retorna uma nota 0-100.
Critérios são independentes entre si (RN da auditoria — a nota de um
pilar nunca é ajustada em função de outro; cruzamentos narrativos ficam
só na camada de Interpretação/justificativa, fora daqui).
"""
from decimal import Decimal

from application.motor.historico import HistoricoFamilia
from domain.promocoes import Promocao


def _clamp(valor: float, minimo: float = 0, maximo: float = 100) -> float:
    return max(minimo, min(maximo, valor))


def pilar_historico(promocao: Promocao, historico: HistoricoFamilia) -> float:
    """Compara a pontuação atual com a média ponderada do histórico da família.

    Sem histórico suficiente, retorna uma nota neutra (50) — a falta de
    informação não deve penalizar nem beneficiar a promoção; é a
    confianca_historica que sinaliza essa limitação, não a nota do pilar.
    """
    if historico.media_ponderada is None or historico.media_ponderada == 0:
        return 50.0

    razao = float(promocao.pontuacao) / float(historico.media_ponderada)
    # 1.0x da média = 50 pontos; 2.0x da média = 100 pontos; 0.5x = 25 pontos (linear)
    nota = razao * 50.0
    return _clamp(nota)


def pilar_atratividade(promocao: Promocao, media_mercado: Decimal | None) -> float:
    """Compara a pontuação com a média de mercado (todo o domínio/programa),
    independente do histórico específico deste parceiro — mede quão boa é
    a oferta em termos absolutos, não relativos ao próprio passado dele.
    """
    if media_mercado is None or media_mercado == 0:
        return 50.0

    razao = float(promocao.pontuacao) / float(media_mercado)
    nota = razao * 50.0
    return _clamp(nota)


def pilar_amplitude(promocao: Promocao, quantidade_categorias: int) -> float:
    """Mede o alcance da promoção no catálogo.

    Heurística inicial: marketplace_status e quantidade de categorias
    associadas. Texto livre em `abrangencia` não é parseado automaticamente
    nesta versão — fica registrado como contexto para o admin, mas não
    influencia a nota até termos um padrão estruturado de captura.
    """
    nota = 50.0

    if promocao.marketplace_status == "PERMITIDO":
        nota += 20
    elif promocao.marketplace_status == "PROIBIDO":
        nota -= 20
    elif promocao.marketplace_status == "PARCIAL":
        nota -= 5

    if quantidade_categorias == 0:
        nota += 15  # nenhuma categoria = presumidamente todo o catálogo
    elif quantidade_categorias == 1:
        nota -= 10
    else:
        nota -= 5 * min(quantidade_categorias, 5)

    return _clamp(nota)


def pilar_facilidade(promocao: Promocao) -> float:
    """Quanto menos barreiras para o usuário aproveitar, maior a nota."""
    nota = 100.0

    if promocao.requer_clube:
        nota -= 30
    if promocao.requer_cupom:
        nota -= 15
    if promocao.restricoes:
        nota -= 15
    if promocao.disponibilidade != "PUBLICA":
        nota -= 20

    return _clamp(nota)


def pilar_exclusividade(promocao: Promocao, historico: HistoricoFamilia) -> float:
    """Mede o quão raro/recorde é o valor desta promoção.

    Recorrência não penaliza diretamente a nota (decisão da conversa
    original) — este pilar mede RARIDADE em relação ao próprio histórico,
    não frequência de publicação.
    """
    if historico.maior_valor_historico is None:
        return 50.0

    if promocao.pontuacao > historico.maior_valor_historico:
        return 100.0  # novo recorde
    if promocao.pontuacao == historico.maior_valor_historico:
        return 85.0  # empatou o recorde

    razao = float(promocao.pontuacao) / float(historico.maior_valor_historico)
    return _clamp(razao * 70.0)


def pilar_confiabilidade_dados(promocao: Promocao) -> float:
    """Mede completude/clareza dos dados desta campanha específica —
    independe de `confianca_historica` (RN separada da auditoria).
    """
    nota = 100.0

    if not promocao.regulamento_texto:
        nota -= 25
    if promocao.data_inicio is None:
        nota -= 10
    if promocao.data_fim is None:
        nota -= 10
    if not promocao.unidade_pontuacao:
        nota -= 20
    if promocao.marketplace_status is None:
        nota -= 10
    if promocao.requer_clube and not promocao.qual_clube:
        nota -= 10
    if promocao.requer_cupom and not promocao.cupom:
        nota -= 10

    return _clamp(nota)
