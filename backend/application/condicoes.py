"""Decide se o valor de pontuação exibido é condicionado.

A pergunta prática: os pontos que o painel mostra valem para a compra inteira,
ou só para uma fatia dela?

O regulamento da Livelo costuma descrever uma escada — "10 pontos na categoria
Básicos e 2 pontos demais produtos". Quando o valor que guardamos é o degrau de
cima e existe um degrau abaixo, ele é condicionado: a maior parte da loja rende
menos. Quando o valor guardado já é o piso (caso comum das ofertas com Clube,
em que a pontuação maior é a do assinante e a nossa é a de qualquer cliente),
não há condição a alertar — é o mínimo garantido.

A comparação é feita sobre os números do próprio texto, sem palavra-chave e sem
fator arbitrário: o critério é a escada que o regulamento declara.
"""
import re
from decimal import Decimal, InvalidOperation

# "10 pontos", "2 pontos", "1 ponto" — sempre acompanhados da palavra ponto(s),
# o que evita ler datas ("14 a 16/08/2026") ou percentuais como pontuação.
PADRAO_PONTOS_NO_TEXTO = re.compile(r"(\d+)\s*pontos?\b", re.IGNORECASE)

# A frase que o coletor antigo escrevia sobre si mesmo em `regulamento_texto`.
# Não diz nada sobre a oferta e não pode ser lida como regulamento — registros
# gravados antes de 14/08/2026 ainda a contêm.
PADRAO_FRASE_DO_COLETOR = re.compile(r"^Coletado do site oficial", re.IGNORECASE)

# "produtos vendidos e entregues por X" — a oferta se limita ao estoque próprio
# da loja, deixando de fora os vendedores terceiros.
PADRAO_ESTOQUE_PROPRIO = re.compile(r"vendid[oa]s?\s+e\s+entregu", re.IGNORECASE)

PADRAO_MARKETPLACE = re.compile(r"marketplace", re.IGNORECASE)


def _valores_citados(regulamento: str) -> list[Decimal]:
    valores = []
    for bruto in PADRAO_PONTOS_NO_TEXTO.findall(regulamento):
        try:
            valores.append(Decimal(bruto))
        except InvalidOperation:
            continue
    return valores


def valor_e_condicionado(
    pontuacao: Decimal, regulamento_texto: str | None, pontuacao_e_teto: bool
) -> bool:
    """True quando o valor exibido não vale para a compra inteira.

    Duas evidências, ambas ancoradas no que a fonte declara:

    1. O card anuncia "Até X" — o próprio anunciante diz que é um limite.
    2. O regulamento cita uma pontuação menor que a exibida — logo a exibida é
       o degrau de cima de uma escada.

    Restrição escrita apenas em palavras, sem segunda pontuação ("válido apenas
    para produtos vendidos e entregues por"), não é detectada aqui. Nesse caso
    quem informa é o texto do regulamento exibido no card.
    """
    if pontuacao_e_teto:
        return True
    if not regulamento_texto:
        return False

    valores = _valores_citados(regulamento_texto)
    if not valores:
        return False

    return pontuacao > min(valores)


def resolver_marketplace(regulamento_texto: str | None) -> str | None:
    """Diz se compras de vendedores terceiros pontuam, lendo o regulamento.

    Marketplaces vendem estoque próprio e de terceiros, e onde a compra é feita
    muda quanto se pontua — algo que o cliente costuma descobrir tarde demais.
    Os três valores já existiam no schema e o pilar Amplitude do motor já reage
    a eles; faltava alguém preenchê-los.

    - PARCIAL: o texto dá uma taxa própria ao marketplace. Terceiros pontuam,
      só que menos ("3 pontos vendidos e entregues por Magalu e 2 pontos para
      marketplace").
    - PROIBIDO: o texto limita a oferta ao estoque próprio e não oferece taxa
      alguma a terceiros ("10 pontos em produtos vendidos e entregues por
      Quero-Quero").
    - PERMITIDO: há regulamento e ele não restringe. Silêncio num texto que
      existe é evidência de que vale para a compra inteira.
    - None: não há regulamento algum. Sem texto não se lê nada, e isso é
      ausência de leitura, não ausência de restrição — afirmar "permitido"
      aqui seria inventar.
    """
    if not regulamento_texto or PADRAO_FRASE_DO_COLETOR.match(regulamento_texto.strip()):
        return None

    # A ordem importa: um texto pode citar as duas coisas, e nesse caso o que
    # vale é haver taxa para o marketplace — ele pontua, ainda que menos.
    if PADRAO_MARKETPLACE.search(regulamento_texto):
        return "PARCIAL"
    if PADRAO_ESTOQUE_PROPRIO.search(regulamento_texto):
        return "PROIBIDO"
    return "PERMITIDO"
