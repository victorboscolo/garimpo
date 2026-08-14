"""Testes da regra que decide se o valor exibido é condicionado.

Todos os textos vêm de regulamentos reais capturados da Livelo em 14/08/2026.

A pergunta que a regra responde: os pontos que mostramos valem para a compra
inteira, ou só para uma fatia dela? A resposta está na escada de valores do
próprio regulamento — se o número exibido é o degrau de cima e existe um degrau
abaixo, ele é condicionado; se já é o piso, todo mundo o recebe.
"""
from decimal import Decimal

from application.condicoes import valor_e_condicionado


def test_valor_exibido_e_o_degrau_de_cima():
    """Renner: os 10 pontos valem só na categoria Básicos; o resto da loja
    rende 2. Quem vê "10 pontos" precisa saber disso.
    """
    reg = ("Campanha válida de 14/08/2026 a 16/08/2026. Ganhe 10 pontos por real na "
           "categoria Básicos e 2 pontos demais produtos. Consulte o regulamento.")
    assert valor_e_condicionado(Decimal("10"), reg, pontuacao_e_teto=False) is True


def test_valor_exibido_e_o_piso():
    """Olympikus: os 15 pontos são para primeira compra, mas guardamos 5 — que
    é justamente o que vale para as demais. Marcar como condicionado diria que
    os 5 têm pegadinha, quando são o mínimo garantido.
    """
    reg = ("Campanha válida de 13 a 14/08/2026. Ganhe 15 pontos por real gasto exclusivo "
           "para primeira compra e 5 pontos por real nas demais compras. Utilize o cupom "
           "LIVELO. Consulte o regulamento.")
    assert valor_e_condicionado(Decimal("5"), reg, pontuacao_e_teto=False) is False


def test_clube_no_degrau_de_cima_nao_condiciona_o_piso():
    """Pontofrio: 4 no Clube, 3 para os demais. Guardamos 3."""
    reg = ("Campanha válida de 14 a 16/08/2026. Ganhe 4 pontos por real gasto exclusivo "
           "para assinantes Clube Livelo; 3 pontos por real para demais clientes.")
    assert valor_e_condicionado(Decimal("3"), reg, pontuacao_e_teto=False) is False


def test_ate_condiciona_mesmo_sem_escada_no_texto():
    """O "Até" do card já é prova de que o número é um limite, independente do
    que o regulamento detalhe.
    """
    reg = "Campanha válida de 14 a 16/08/2026. Ganhe 8 pontos por real gasto."
    assert valor_e_condicionado(Decimal("8"), reg, pontuacao_e_teto=True) is True


def test_sem_regulamento_vale_apenas_o_ate():
    assert valor_e_condicionado(Decimal("8"), None, pontuacao_e_teto=True) is True
    assert valor_e_condicionado(Decimal("8"), None, pontuacao_e_teto=False) is False


def test_valor_unico_no_texto_nao_condiciona():
    """Sem segundo degrau, não há o que comparar. Uma restrição escrita em
    palavras (sem outra pontuação) não é detectável por esta regra — quem
    informa nesse caso é o próprio texto exibido no card.
    """
    reg = "Campanha válida de 13 a 17/08/2026. Ganhe 11 pontos por real gasto. Utilize o cupom LIVELO."
    assert valor_e_condicionado(Decimal("11"), reg, pontuacao_e_teto=False) is False


def test_ignora_numeros_que_nao_sao_pontuacao():
    """A data no início do texto não pode ser lida como pontuação."""
    reg = "Campanha válida de 14 a 16/08/2026. Ganhe 6 pontos por real gasto."
    assert valor_e_condicionado(Decimal("6"), reg, pontuacao_e_teto=False) is False


# --- Alcance no marketplace ---------------------------------------------------
#
# Marketplaces vendem estoque próprio e de vendedores terceiros. Onde a compra
# é feita muda quanto se pontua, e o cliente descobre isso tarde demais.

from application.condicoes import resolver_marketplace


def test_marketplace_com_taxa_propria_e_parcial():
    """Magalu: 3 pontos no estoque próprio, 2 no marketplace. Terceiros
    pontuam, só que menos.
    """
    reg = ("Campanha válida de 14 a 16/08/2026. Ganhe 3 pontos por real gasto em produtos "
           "vendidos e entregues por Magalu e 2 pontos por real para marketplace.")
    assert resolver_marketplace(reg) == "PARCIAL"


def test_apenas_vendidos_e_entregues_e_proibido():
    """Quero-Quero limita a oferta ao estoque próprio e não dá taxa alguma ao
    marketplace: comprar de terceiro não pontua.
    """
    reg = ("Campanha válida de 14 a 16/08/2026. Ganhe 10 pontos a cada real gasto em "
           "produtos vendidos e entregues por Quero-Quero. Utilize o cupom LIVELO.")
    assert resolver_marketplace(reg) == "PROIBIDO"


def test_regulamento_que_nao_toca_no_assunto_e_permitido():
    """Havendo regulamento e ele não restringindo, vale para a compra toda —
    silêncio num texto que existe é evidência, não lacuna.
    """
    reg = "Campanha válida de 14 a 16/08/2026. Ganhe 11 pontos por real gasto. Utilize o cupom LIVELO."
    assert resolver_marketplace(reg) == "PERMITIDO"


def test_sem_regulamento_nao_se_conclui_nada():
    """Oferta sem campanha ativa não tem a página de regras visitada. Não é
    ausência de restrição — é ausência de leitura.
    """
    assert resolver_marketplace(None) is None
    assert resolver_marketplace("Coletado do site oficial da Livelo.") is None


def test_regulamento_sem_campanha_tambem_vale():
    """O JSON da Livelo traz condições gerais mesmo para parceiros sem campanha
    ativa — texto que nunca chegava pelo caminho antigo. A regra de "só vale se
    disser 'campanha válida'" existia para descartar a frase que o próprio
    coletor escrevia, e essa frase não existe mais.
    """
    reg = ("Para acumular Pontos Livelo, é necessário a inclusão do cupom LIVELO no "
           "carrinho de compras; produtos vendidos e entregues por Época Cosméticos.")
    assert resolver_marketplace(reg) == "PROIBIDO"


def test_frase_sintetica_do_coletor_antigo_nao_e_regulamento():
    """Registros antigos ainda têm essa frase gravada; ela não diz nada sobre a
    oferta e não pode ser lida como regulamento.
    """
    assert resolver_marketplace("Coletado do site oficial da Livelo.") is None
    assert resolver_marketplace(
        "Coletado do site oficial da Livelo. Base de comparacao anterior (Eram): 2 pontos."
    ) is None
