"""Recorde na faixa Clube Livelo entra no pilar Exclusividade, com peso
menor que o recorde sem clube.

Caso real que motivou a mudança (14/09): a Centauro anunciou "até 10
pontos", mas quem tem Clube Livelo ganhava 15 — o maior valor que a
Centauro já ofereceu (o recorde anterior, sem clube, nunca passou de 6).
O usuário decidiu: o recorde de clube é real e deve contar, mas pesa bem
menos que um recorde aberto a qualquer comprador.
"""
from decimal import Decimal
from types import SimpleNamespace

from application.motor.historico import HistoricoFamilia
from application.motor.pilares import pilar_exclusividade


def _promocao(**ajustes):
    padrao = dict(
        pontuacao=Decimal("10"), valor_condicionado=True,
        valor_condicionado_piso=Decimal("2"), pontuacao_clube=None,
    )
    padrao.update(ajustes)
    return SimpleNamespace(**padrao)


def test_recorde_de_clube_da_um_bonus_mas_nao_domina_a_nota():
    """Sem o recorde de clube, a oferta empataria o recorde sem-clube (85).
    Com um novo recorde de clube (15 > 11), o bônus empurra a nota pra
    cima, mas o peso do recorde sem clube (85) ainda domina.
    """
    promocao = _promocao(pontuacao_clube=Decimal("15"))
    historico = HistoricoFamilia(
        media_ponderada=Decimal("2"), maior_valor_historico=Decimal("2"),
        total_campanhas_janela=3, confianca_historica="MEDIA",
        maior_valor_historico_clube=Decimal("11"),
    )
    # sem-clube: piso 2 empata o recorde de 2 -> 85. clube: 15 > 11 -> 100.
    # 85*0.8 + 100*0.2 = 88.0
    assert pilar_exclusividade(promocao, historico) == 88.0


def test_sem_faixa_clube_comportamento_nao_muda():
    """Oferta sem `pontuacao_clube` continua exatamente como antes —
    sem nenhum ajuste.
    """
    promocao = _promocao(pontuacao_clube=None)
    historico = HistoricoFamilia(
        media_ponderada=Decimal("2"), maior_valor_historico=Decimal("2"),
        total_campanhas_janela=3, confianca_historica="MEDIA",
        maior_valor_historico_clube=Decimal("11"),
    )
    assert pilar_exclusividade(promocao, historico) == 85.0


def test_recorde_sem_clube_pesa_mais_que_recorde_de_clube():
    """Um recorde sem clube domina mesmo quando a faixa clube não é
    recorde nenhum: bater o recorde geral (100) com um clube mediano (70,
    abaixo do recorde de clube 20) ainda fica bem mais perto de 100 do
    que de 50-50.
    """
    promocao = _promocao(
        pontuacao=Decimal("10"), valor_condicionado=False, pontuacao_clube=Decimal("15"),
    )
    historico = HistoricoFamilia(
        media_ponderada=Decimal("5"), maior_valor_historico=Decimal("8"),
        total_campanhas_janela=3, confianca_historica="MEDIA",
        maior_valor_historico_clube=Decimal("20"),
    )
    # sem-clube: 10 > 8 -> 100 (novo recorde). clube: 15 < 20 -> razão*70 = 52.5
    # 100*0.8 + 52.5*0.2 = 90.5
    nota = pilar_exclusividade(promocao, historico)
    assert nota == 90.5
    assert nota > 85  # o recorde sem clube domina, mesmo com clube mediano


def test_primeira_oferta_com_clube_ja_conta_como_recorde_de_clube():
    """Sem nenhuma campanha anterior com faixa Clube pra comparar, a
    primeira observação já vale como recorde — mesmo tratamento dado ao
    histórico geral com amostra única.
    """
    promocao = _promocao(pontuacao_clube=Decimal("15"))
    historico = HistoricoFamilia(
        media_ponderada=Decimal("2"), maior_valor_historico=Decimal("2"),
        total_campanhas_janela=3, confianca_historica="MEDIA",
        maior_valor_historico_clube=None,
    )
    # sem-clube: 85 (empate). clube: sem recorde anterior -> 100.
    assert pilar_exclusividade(promocao, historico) == 88.0
