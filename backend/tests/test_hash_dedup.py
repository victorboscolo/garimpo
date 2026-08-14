"""Testes do hash de deduplicação de promoções.

O hash decide se uma oferta coletada é "a mesma de ontem" (descartada) ou uma
mudança real (novo registro, preservando o histórico). Se ele ignorar um campo
que distingue duas ofertas, uma delas some em silêncio; se incluir ruído, o
banco enche de duplicatas.
"""
from decimal import Decimal

from application.ingestao_service import PromocaoBrutaIn, calcular_hash


def _bruta(**ajustes) -> PromocaoBrutaIn:
    padrao = dict(
        programa_nome="Livelo",
        parceiro_nome_bruto="Beach Park",
        titulo="Beach Park - 2 pontos por R$ 1",
        url_origem="https://livelo.com.br/juntar-pontos/parceiros/beach-park/BPK",
        pontuacao=Decimal("2"),
        unidade_pontuacao="pontos_por_real",
    )
    padrao.update(ajustes)
    return PromocaoBrutaIn(**padrao)


def test_ofertas_identicas_tem_o_mesmo_hash():
    assert calcular_hash(_bruta()) == calcular_hash(_bruta())


def test_variantes_do_mesmo_parceiro_tem_hashes_diferentes():
    """Beach Park Hotéis (BPK) e Ingressos (BHP) são ofertas distintas. Se
    tivessem a mesma pontuação e o código não entrasse no hash, uma seria
    descartada como duplicata da outra.
    """
    hoteis = _bruta(codigo_externo="BPK")
    ingressos = _bruta(codigo_externo="BHP")
    assert calcular_hash(hoteis) != calcular_hash(ingressos)


def test_mudar_de_valor_fixo_para_teto_gera_hash_diferente():
    """Um card que passa de '6 pontos' para 'Até 6 pontos' mudou de significado
    mesmo com o número igual — tem que virar registro novo, não ser descartado.
    """
    fixo = _bruta(pontuacao_e_teto=False)
    teto = _bruta(pontuacao_e_teto=True)
    assert calcular_hash(fixo) != calcular_hash(teto)


def test_mudanca_na_pontuacao_do_clube_gera_hash_diferente():
    """Se a oferta do Clube sobe de 10 para 15 e o resto fica igual, a oferta
    mudou — tem que virar registro novo em vez de ser descartada como duplicata.
    """
    antes = _bruta(pontuacao_clube=Decimal("10"))
    depois = _bruta(pontuacao_clube=Decimal("15"))
    assert calcular_hash(antes) != calcular_hash(depois)


def test_pontuacao_diferente_gera_hash_diferente():
    assert calcular_hash(_bruta(pontuacao=Decimal("2"))) != calcular_hash(_bruta(pontuacao=Decimal("3")))


def test_campos_irrelevantes_nao_afetam_o_hash():
    """Título e regulamento são texto gerado pelo coletor; variação neles não
    significa oferta nova.
    """
    assert calcular_hash(_bruta(titulo="outro título")) == calcular_hash(_bruta())
