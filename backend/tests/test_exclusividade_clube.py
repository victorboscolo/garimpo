"""Recorde na faixa Clube Livelo entra no pilar Exclusividade, com o
mesmo peso do recorde sem clube.

Caso real que motivou a mudança (14/09): a Centauro anunciou "até 10
pontos", mas quem tem Clube Livelo ganhava 15 — o maior valor que a
Centauro já ofereceu (o recorde anterior, sem clube, nunca passou de 6).
O peso começou em 0.2 (recorde de clube conta bem menos), mas o caso da
Insider Store (15/09) mostrou que isso praticamente anulava o recorde na
nota final — o usuário pediu pra subir o peso do recorde de clube até
ficar igual ao do recorde sem clube (`PESO_RECORDE_CLUBE = 0.5`).
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


def test_recorde_de_clube_pesa_igual_ao_recorde_sem_clube():
    """Sem o recorde de clube, a oferta empataria o recorde sem-clube
    (85). Com um novo recorde de clube (15 > 11), os dois pesam igual.
    """
    promocao = _promocao(pontuacao_clube=Decimal("15"))
    historico = HistoricoFamilia(
        media_ponderada=Decimal("2"), maior_valor_historico=Decimal("2"),
        total_campanhas_janela=3, confianca_historica="MEDIA",
        maior_valor_historico_clube=Decimal("11"),
    )
    # sem-clube: piso 2 empata o recorde de 2 -> 85. clube: 15 > 11 -> 100.
    # 85*0.5 + 100*0.5 = 92.5
    assert pilar_exclusividade(promocao, historico) == 92.5


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


def test_recorde_de_clube_fraco_puxa_a_nota_pra_baixo_tambem():
    """Com peso igual, um desempenho fraco na faixa clube não é mais
    diluído: bater o recorde geral (100) mas ficar longe do recorde de
    clube (52,5) puxa a média pro meio, não perto de 100.
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
    # 100*0.5 + 52.5*0.5 = 76.25
    assert pilar_exclusividade(promocao, historico) == 76.25


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
    # 85*0.5 + 100*0.5 = 92.5
    assert pilar_exclusividade(promocao, historico) == 92.5
