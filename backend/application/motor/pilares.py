"""Os 6 pilares do Motor de Análise V1.

Cada função recebe os dados necessários e retorna uma nota 0-100.
Critérios são independentes entre si (RN da auditoria — a nota de um
pilar nunca é ajustada em função de outro; cruzamentos narrativos ficam
só na camada de Interpretação/justificativa, fora daqui).
"""
from decimal import Decimal

from application.motor.historico import HistoricoFamilia
from application.motor.percentil import percentil, valor_comparavel
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


def pilar_historico_com_base(promocao: Promocao, base) -> float:
    """Posição da oferta dentro da base resolvida em cascata.

    A base pode ser o histórico do próprio parceiro, o segmento ou o mercado —
    qual delas fica em `base.nivel` e reflete na confianca_historica, para que a
    nota nunca esconda em que se apoiou.

    A nota é o percentil, não a razão com a média. A razão saturava: com média
    de segmento em 2 pontos, qualquer oferta acima de 4 valia 100, e 38
    classificações estavam nesse teto.

    Usa `valor_comparavel`, não `promocao.pontuacao` direto (achado do
    usuário, 09/09) — `base.distribuicao` já vem construída com o piso das
    ofertas condicionadas (ver `historico.py`), então esta oferta precisa
    ser posicionada na mesma régua, não com o número anunciado.
    """
    if not base.distribuicao:
        return 50.0
    return percentil(valor_comparavel(promocao), base.distribuicao)


def pilar_atratividade(promocao: Promocao, mercado: list | None) -> float:
    """Posição da oferta no mercado inteiro do programa.

    Independe do histórico do parceiro: mede quão boa a oferta é em termos
    absolutos, não relativos ao próprio passado dele.

    Pela mesma razão do pilar Histórico, a nota é o percentil. A média de
    mercado (5,48) é puxada pelos consórcios de 40 e 100 enquanto a mediana é 2,
    e comparar contra a média numa distribuição assim era severo no meio —
    uma oferta de 5 pontos supera 75% do mercado e tirava 46 — e cego no topo,
    onde 33 classificações empatavam em 100.

    Usa `valor_comparavel`, mesma razão do pilar Histórico: `mercado` já
    vem construído com o piso das ofertas condicionadas.
    """
    if not mercado:
        return 50.0
    return percentil(valor_comparavel(promocao), mercado)


def pilar_amplitude(promocao: Promocao, quantidade_categorias: int, segmento_varejo: bool = False) -> float:
    """Mede o alcance da promoção no catálogo.

    Heurística inicial: marketplace_status e quantidade de categorias
    associadas. Texto livre em `abrangencia` não é parseado automaticamente
    nesta versão — fica registrado como contexto para o admin, mas não
    influencia a nota até termos um padrão estruturado de captura.

    `segmento_varejo` suaviza a penalidade de `marketplace_status=PARCIAL`
    (decisão do usuário, 01/09, caso real: Magalu/Esfera a 7 pontos, só
    reduzido pra 1 ponto em produto vendido por loja parceira). Restrição de
    **canal** de venda pesa bem menos que restrição de **tipo de produto**
    pra um parceiro de varejo com catálogo próprio já muito amplo — não
    vale no marketplace não reduz o alcance na prática, porque a loja
    própria já cobre a maior parte do que se compra ali. PROIBIDO continua
    penalizado igual em qualquer segmento: é bloqueio de verdade, não
    redução de taxa.
    """
    nota = 50.0

    # O valor anunciado não vale para a compra inteira — a Renner anuncia 10
    # pontos que só valem na categoria Básicos, e o resto do catálogo rende 2
    # (80% de queda). É redução de alcance, e é aqui que deve doer: a
    # Confiabilidade mede se o dado está completo e a Facilidade mede
    # barreiras para aproveitar, que são outras coisas.
    #
    # A penalidade escala pela queda relativa (decisão do usuário, 01/09,
    # caso real: Magalu/Esfera cai de 7 pra 6 pontos pra quem não é Clube —
    # só 14% de queda, bem menos restritivo que os 80% da Renner, mas os
    # dois recebiam a mesma penalidade fixa de -25). Sem piso conhecido no
    # texto (caso do "Até X" sem segunda pontuação no regulamento — a queda
    # existe mas o tamanho dela não é lido em lugar nenhum), a penalidade
    # plena só se aplica quando a razão do "até" continua desconhecida.
    #
    # Achado do usuário (08/09), caso real: Camicado/Esfera a 10 pontos,
    # marcada "até" pela Esfera mas sem nenhum degrau de Clube/categoria no
    # regulamento — a única restrição no texto inteiro é a de marketplace
    # (`marketplace_status=PROIBIDO`), já penalizada abaixo. Sem esse
    # ajuste, a mesma restrição contava duas vezes: uma como marketplace,
    # outra como "condição desconhecida". Quando o marketplace já é
    # PARCIAL/PROIBIDO e não há piso, a magnitude não é desconhecida — já
    # está explicada ali, então a penalidade extra não se aplica.
    if getattr(promocao, "valor_condicionado", False):
        piso = getattr(promocao, "valor_condicionado_piso", None)
        if piso is not None and promocao.pontuacao > 0:
            queda_relativa = float((promocao.pontuacao - piso) / promocao.pontuacao)
            nota -= 25 * min(max(queda_relativa, 0.0), 1.0)
        elif promocao.marketplace_status not in ("PARCIAL", "PROIBIDO"):
            nota -= 25

    if promocao.marketplace_status == "PERMITIDO":
        nota += 20
    elif promocao.marketplace_status == "PROIBIDO":
        nota -= 20
    elif promocao.marketplace_status == "PARCIAL":
        nota -= 1 if segmento_varejo else 5

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


# Um recorde na faixa Clube Livelo é real — o cliente pode assinar e
# receber. Começou em 0.2 (14/09, caso Centauro), mas o caso da Insider
# Store (15/09: piso real de 1 ponto, recorde de Clube batendo 20 contra
# 13) mostrou que esse peso baixo praticamente anulava o recorde na nota
# final — decisão do usuário: subir pra peso igual ao do recorde sem
# clube, pra que bater um recorde de clube pese de verdade.
PESO_RECORDE_CLUBE = 0.5


def _nota_recorde(valor: Decimal, recorde: Decimal) -> float:
    if valor > recorde:
        return 100.0  # novo recorde
    if valor == recorde:
        return 85.0  # empatou o recorde
    razao = float(valor) / float(recorde)
    return _clamp(razao * 70.0)


def pilar_exclusividade(promocao: Promocao, historico: HistoricoFamilia) -> float:
    """Mede o quão raro/recorde é o valor desta promoção.

    Recorrência não penaliza diretamente a nota (decisão da conversa
    original) — este pilar mede RARIDADE em relação ao próprio histórico,
    não frequência de publicação.
    """
    if historico.maior_valor_historico is None:
        return 50.0

    # valor_comparavel: `maior_valor_historico` já vem do piso das ofertas
    # condicionadas (ver `historico.py`), então o "recorde" a bater é o
    # valor real garantido, não o anunciado (achado do usuário, 09/09).
    nota = _nota_recorde(valor_comparavel(promocao), historico.maior_valor_historico)

    # Se esta oferta também tem faixa Clube, o recorde dessa faixa conta
    # com o mesmo peso do recorde sem clube — ver `PESO_RECORDE_CLUBE`.
    # Sem recorde anterior na faixa Clube pra comparar, a primeira
    # observação já vale como recorde (100), mesmo tratamento que o
    # histórico geral daria à primeira campanha.
    pontuacao_clube = getattr(promocao, "pontuacao_clube", None)
    if pontuacao_clube is not None:
        recorde_clube = historico.maior_valor_historico_clube
        nota_clube = 100.0 if recorde_clube is None else _nota_recorde(pontuacao_clube, recorde_clube)
        nota = nota * (1 - PESO_RECORDE_CLUBE) + nota_clube * PESO_RECORDE_CLUBE

    return nota


def pilar_confiabilidade_dados(promocao: Promocao) -> float:
    """Mede completude/clareza dos dados desta campanha específica —
    independe de `confianca_historica` (RN separada da auditoria).
    """
    nota = 100.0

    # "Até X pontos" é um teto: o valor real da oferta pode ser qualquer coisa
    # abaixo dele, e as condições ficam na página de detalhe do parceiro, que o
    # coletor ainda não visita. A pontuação não é ajustada (decisão de produto:
    # o valor anunciado é o que se apresenta) — o que cai é a confiança de que
    # o dado descreve a oferta por inteiro.
    if promocao.pontuacao_e_teto:
        nota -= 20

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
