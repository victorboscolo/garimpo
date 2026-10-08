"""Testes do coeficiente de variação usado pra decidir se o histórico
próprio do parceiro é coerente o bastante pra comparar contra ele.

Achado do usuário (02/09): o Magalu tinha 2 ofertas aprovadas (1 e 7
pontos) — já passava do mínimo de quantidade (`MINIMO_PARA_USAR_FAMILIA`),
mas a dispersão entre elas era tão grande que comparar uma oferta de 5
pontos contra esse "histórico" rendeu 50º percentil por coincidência
aritmética, não por sinal real. Quantidade sozinha não bastava.
"""
from decimal import Decimal

from application.motor.historico import _coeficiente_variacao


def test_amostra_dispersa_tem_cv_alto():
    """Magalu: 1 e 7 pontos — média 4, CV = 75%."""
    cv = _coeficiente_variacao([Decimal("1"), Decimal("7")])
    assert cv == 0.75


def test_amostra_coerente_tem_cv_baixo():
    """5 e 6 pontos — variação pequena em torno da média."""
    cv = _coeficiente_variacao([Decimal("5"), Decimal("6")])
    assert cv < 0.1


def test_amostra_moderada_fica_no_meio():
    """3, 4 e 5 pontos — dispersão razoável, mas não extrema."""
    cv = _coeficiente_variacao([Decimal("3"), Decimal("4"), Decimal("5")])
    assert 0.1 < cv < 0.3


def test_valores_identicos_tem_cv_zero():
    assert _coeficiente_variacao([Decimal("5"), Decimal("5"), Decimal("5")]) == 0.0


def test_lista_vazia_tem_cv_zero():
    """Sem amostra, não há dispersão a medir — o gatilho de quantidade
    (`MINIMO_PARA_USAR_FAMILIA`) já teria barrado esse caso antes, mas a
    função não deve quebrar se chamada assim.
    """
    assert _coeficiente_variacao([]) == 0.0


def test_media_zero_nao_quebra():
    """Pontuação zero não deveria acontecer na prática, mas a divisão por
    média não pode estourar.
    """
    assert _coeficiente_variacao([Decimal("0"), Decimal("0")]) == 0.0


def test_amostra_pequena_e_dispersa_nao_serve_de_regua():
    """O caso que criou o corte (Magalu, 02/09): duas ofertas, 1 e 7."""
    from application.motor.historico import _familia_serve_de_regua

    assert _familia_serve_de_regua([Decimal("1"), Decimal("7")], minimo=2, cv_maximo=0.5) is False
    assert _familia_serve_de_regua([Decimal("5"), Decimal("6")], minimo=2, cv_maximo=0.5) is True
    assert _familia_serve_de_regua([Decimal("5")], minimo=2, cv_maximo=0.5) is False


def test_amostra_grande_serve_de_regua_mesmo_dispersa():
    """Petlove Saúde, valores reais de 08/10: treze ofertas de 6 a 50
    pontos. A dispersão é o parceiro alternando base e campanha — com essa
    amostra dá pra dizer que 50 é o topo dele, e o motor descartava isso.
    """
    from application.motor.historico import _coeficiente_variacao, _familia_serve_de_regua

    valores = [Decimal(v) for v in (6, 6, 8, 8, 20, 20, 25, 30, 30, 40, 40, 45, 50)]
    assert _coeficiente_variacao(valores) > 0.5
    assert _familia_serve_de_regua(valores, minimo=2, cv_maximo=0.5) is True
    # Quatro ofertas dispersas ainda caem no corte.
    assert _familia_serve_de_regua(valores[::4], minimo=2, cv_maximo=0.5) is False
