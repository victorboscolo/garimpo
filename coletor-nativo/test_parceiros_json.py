"""Testes da leitura do JSON estruturado embutido na listagem da Livelo.

A página traz, para cada parceiro, um objeto com os dados já tipados — o que
substitui o regex sobre texto renderizado e dispensa visitar a página de regras
de cada campanha. Estrutura capturada do site real em 14/08/2026.

`parityBau` é o dado mais valioso da estrutura: a pontuação fora de campanha,
ou seja, o que a oferta vale quando a promoção acabar. Nada no texto renderizado
expõe isso.
"""
from __future__ import annotations

import json
from decimal import Decimal

from parceiros_json import extrair_parceiros, parceiro_para_bruta

# Objeto real da Decolar, reduzido ao que interessa. O texto do regulamento é o
# que confirmou a restrição de aluguel de carros que o card nunca mencionou.
HTML_DECOLAR = '''<html><body><script>{"foo":1,"details":{
 "id":"DCR","name":"Decolar","categories":"todos alugueldecarros viagemeservicos",
 "link":"https://livelo.com.br/juntar-pontos/parceiros/decolar/DCR",
 "partnerDetailsPage":"https://livelo.com.br/juntar-pontos/parceiros/decolar/DCR",
 "parity":{"currency":"U$","currencyValue":1,"parity":12,"parityClub":12,
  "legalTerms":"<p><span>Campanha v\\u00e1lida de 12 a 17/08/2026. 12 pontos por d\\u00f3lar gasto para todos os clientes, v\\u00e1lido apenas para aluguel de carros.</span></p>",
  "separator":"=","parityBau":6,"promotion":true,"separatorSlug":"IGUAL",
  "dateStart":"2026-08-12-00:00:00 GMT-03:00","dateEnd":"2026-08-17-23:59:00 GMT-03:00",
  "activeCampaign":"PROMOTION","categoryParities":[]}}}</script></body></html>'''

HTML_BEACH_PARK = '''<script>{"details":{
 "id":"BHP","name":"Beach Park Ingressos","categories":"todos ingressosepasseios",
 "partnerDetailsPage":"https://livelo.com.br/juntar-pontos/parceiros/beach-park/BHP",
 "parity":{"currency":"R$","currencyValue":1,"parity":1,"parityClub":1,
  "legalTerms":"<p><br></p>","separator":"=","parityBau":1,"promotion":false,
  "separatorSlug":"IGUAL","activeCampaign":"BAU","categoryParities":[]}}}</script>'''

# A Livelo já serviu o id da Bankei em minúscula pelo JSON num dia, e em
# maiúscula (via URL) noutro — mesmo parceiro virou dois `Parceiro` no banco.
HTML_BANKEI_MINUSCULA = '''<script>{"details":{
 "id":"ban","name":"Bankei","categories":"todos servicos",
 "partnerDetailsPage":"https://livelo.com.br/juntar-pontos/parceiros/bankei/ban",
 "parity":{"currency":"R$","currencyValue":1,"parity":2,"parityClub":2,
  "legalTerms":"<p><br></p>","separator":"=","parityBau":2,"promotion":false,
  "separatorSlug":"IGUAL","activeCampaign":"BAU","categoryParities":[]}}}</script>'''


def test_extrai_parceiro_da_pagina():
    parceiros = extrair_parceiros(HTML_DECOLAR)
    assert "DCR" in parceiros
    assert parceiros["DCR"]["name"] == "Decolar"


def test_pagina_sem_json_devolve_vazio():
    """Se a Livelo mudar a estrutura, o coletor precisa perceber e cair no
    parsing de texto, não quebrar.
    """
    assert extrair_parceiros("<html><body>sem json aqui</body></html>") == {}


def test_codigo_do_json_em_minuscula_e_normalizado_para_maiuscula():
    """O código não tem significado semântico na caixa, só identifica — e a
    busca por parceiro no backend é exata. Sem normalizar aqui, um "id" em
    minúscula no JSON vira um segundo `Parceiro` para quem já existe com o
    código em maiúscula (achado real: Bankei, "ban" vs "BAN").
    """
    parceiros = extrair_parceiros(HTML_BANKEI_MINUSCULA)
    assert "BAN" in parceiros
    assert "ban" not in parceiros

    bruta = parceiro_para_bruta(parceiros["BAN"])
    assert bruta.codigo_externo == "BAN"


def test_campos_tipados_dispensam_regex():
    bruta = parceiro_para_bruta(extrair_parceiros(HTML_DECOLAR)["DCR"])
    assert bruta.pontuacao == Decimal("12")
    assert bruta.unidade_pontuacao == "pontos_por_dolar"
    assert bruta.codigo_externo == "DCR"
    assert bruta.nome_exibicao == "Decolar"
    assert bruta.em_promocao is True


def test_pontuacao_base_capturada():
    """`parityBau` é quanto a oferta vale fora da campanha. A Decolar anuncia
    12 e volta a 6 quando a promoção acabar — informação que o texto
    renderizado nunca expôs.
    """
    bruta = parceiro_para_bruta(extrair_parceiros(HTML_DECOLAR)["DCR"])
    assert bruta.pontuacao_base == Decimal("6")


def test_separator_slug_marca_o_teto():
    """O "Até" vira campo em vez de regex: separatorSlug == "ATE"."""
    bruta = parceiro_para_bruta(extrair_parceiros(HTML_DECOLAR)["DCR"])
    assert bruta.pontuacao_e_teto is False

    com_teto = json.loads(json.dumps(extrair_parceiros(HTML_DECOLAR)["DCR"]))
    com_teto["parity"]["separatorSlug"] = "ATE"
    assert parceiro_para_bruta(com_teto).pontuacao_e_teto is True


def test_datas_com_fuso_viram_data_de_calendario():
    bruta = parceiro_para_bruta(extrair_parceiros(HTML_DECOLAR)["DCR"])
    assert (bruta.data_inicio.day, bruta.data_inicio.month) == (12, 8)
    assert (bruta.data_fim.day, bruta.data_fim.month) == (17, 8)


def test_regulamento_vem_limpo_de_html():
    bruta = parceiro_para_bruta(extrair_parceiros(HTML_DECOLAR)["DCR"])
    assert bruta.regulamento_texto.startswith("Campanha válida de 12 a 17/08/2026.")
    assert "<span>" not in bruta.regulamento_texto
    assert "aluguel de carros" in bruta.regulamento_texto


def test_categorias_vem_da_fonte():
    """Categoria é classificação do parceiro, vinda da Livelo — não inferida
    por heurística nem preenchida à mão.
    """
    bruta = parceiro_para_bruta(extrair_parceiros(HTML_DECOLAR)["DCR"])
    assert bruta.categorias == ["alugueldecarros", "viagemeservicos"]


def test_categoria_todos_e_descartada():
    """"todos" aparece em 263 dos 265 parceiros: não classifica nada."""
    bruta = parceiro_para_bruta(extrair_parceiros(HTML_BEACH_PARK)["BHP"])
    assert bruta.categorias == ["ingressosepasseios"]


def test_oferta_sem_campanha_nao_tem_datas_nem_regulamento():
    """activeCampaign BAU é a taxa estável do parceiro: legalTerms vazio e sem
    período. Não se inventa validade para ela.
    """
    bruta = parceiro_para_bruta(extrair_parceiros(HTML_BEACH_PARK)["BHP"])
    assert bruta.em_promocao is False
    assert bruta.data_inicio is None and bruta.data_fim is None
    assert bruta.regulamento_texto is None


def test_clube_igual_a_pontuacao_normal_nao_e_oferta_de_clube():
    """`parityClub` vem preenchido em todos os parceiros, quase sempre igual à
    pontuação normal. Gravar isso como "oferta de clube" seria ruído — e, como
    o campo entra no hash de deduplicação, mudaria o hash de toda a base.
    """
    obj = json.loads(json.dumps(extrair_parceiros(HTML_BEACH_PARK)["BHP"]))
    assert obj["parity"]["parity"] == obj["parity"]["parityClub"]
    assert parceiro_para_bruta(obj).pontuacao_clube is None


def test_clube_maior_que_a_normal_e_oferta_de_clube():
    obj = json.loads(json.dumps(extrair_parceiros(HTML_BEACH_PARK)["BHP"]))
    obj["parity"]["parityClub"] = 5
    assert parceiro_para_bruta(obj).pontuacao_clube == Decimal("5")
