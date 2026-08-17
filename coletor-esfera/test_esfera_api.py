"""Testes da leitura da API pública de parceiros da Esfera.

A Esfera expõe `GET /bff-product/ehcs/products?categoryId=esf02163` sem
nenhuma proteção — nem cookie, nem sessão, nem anti-robô. Confirmado com
`curl` puro em 17/08/2026: HTTP 200 direto. Isso dispensa navegador (nada de
Playwright aqui, ao contrário da Livelo) e dispensa rodar fora do Docker.

Os objetos abaixo são recortes reais dessa resposta, reduzidos aos campos que
importam — a resposta completa de um parceiro tem ~200 campos, a maioria
metadado de e-commerce (imagens, frete, SKU) que não interessa ao Garimpo.
"""
from __future__ import annotations

from decimal import Decimal

from esfera_api import parceiro_para_bruta

# Renner, capturado em 17/08/2026: prefixo "Até" com É maiúsculo, unidade Real.
ITEM_RENNER = {
    "id": "e000100180",
    "displayName": "Renner",
    "active": True,
    "esf_accumulationValue": "3",
    "esf_accumulationPrefix": "Até",
    "esf_accumulationFactorDescription": "Real em compra",
    "esf_campaignId": None,
    "route": "/p/renner/e000100180",
    "esf_accumulationGeneralRules": (
        "<p><strong>* Ganhe 3 pontos a cada R$ 1,00 em compras no site "
        "parceiro.</strong></p>\n<p><strong>* Condições válidas para compras "
        "efetuadas de 00h00min do dia 17/08/2026 até 23h59min do dia "
        "21/08/2026.</strong></p>"
    ),
    "parentCategories": [
        {"repositoryId": "newModaCalcadosAcessorios"},
        {"repositoryId": "new02163"},
        {"repositoryId": "esf02163"},
    ],
}

# C&A: prefixo em minúsculo ("até") — o parser não pode depender de caixa.
ITEM_CEA = {
    "id": "e000100476",
    "displayName": "C&A",
    "active": True,
    "esf_accumulationValue": "7",
    "esf_accumulationPrefix": "até",
    "esf_accumulationFactorDescription": "Real em Compra",
    "esf_campaignId": "ESFCE17086",
    "route": "/p/cea/e000100476",
    "esf_accumulationGeneralRules": "<p>Ganhe 7 pontos a cada R$ 1,00.</p>",
    "parentCategories": [{"repositoryId": "new02163"}],
}

# Booking.com: pontuação por dólar, sem prefixo "até" (valor fixo).
ITEM_BOOKING = {
    "id": "e000100296",
    "displayName": "Booking.com",
    "active": True,
    "esf_accumulationValue": "4",
    "esf_accumulationPrefix": None,
    "esf_accumulationFactorDescription": "dólar em compra",
    "esf_campaignId": None,
    "route": "/p/booking-com/e000100296",
    "esf_accumulationGeneralRules": "<p>Ganhe 4 pontos a cada dólar.</p>",
    "parentCategories": [{"repositoryId": "new02163"}],
}

# New Balance: o único dos 168 parceiros ativos sem
# esf_accumulationFactorDescription — precisa de um padrão sem quebrar.
ITEM_NEW_BALANCE = {
    "id": "e000100555",
    "displayName": "New Balance",
    "active": True,
    "esf_accumulationValue": "1",
    "esf_accumulationPrefix": None,
    "esf_accumulationFactorDescription": None,
    "esf_campaignId": None,
    "route": "/p/new-balance/e000100555",
    "esf_accumulationGeneralRules": None,
    "parentCategories": [{"repositoryId": "new02163"}],
}


def test_campos_basicos():
    bruta = parceiro_para_bruta(ITEM_RENNER)
    assert bruta.codigo_externo == "e000100180"
    assert bruta.nome_exibicao == "Renner"
    assert bruta.pontuacao == Decimal("3")
    assert bruta.unidade_pontuacao == "pontos_por_real"


def test_prefixo_ate_marca_teto_independente_de_caixa():
    """"Até" na Renner e "até" na C&A precisam virar o mesmo teto=True — o
    site não é consistente com maiúsculas.
    """
    assert parceiro_para_bruta(ITEM_RENNER).pontuacao_e_teto is True
    assert parceiro_para_bruta(ITEM_CEA).pontuacao_e_teto is True


def test_sem_prefixo_nao_e_teto():
    assert parceiro_para_bruta(ITEM_BOOKING).pontuacao_e_teto is False


def test_unidade_dolar_reconhecida_no_texto_livre():
    """"dólar em compra" (Booking.com) tem que virar pontos_por_dolar — a
    Esfera não separa unidade em campo próprio como a Livelo faz com
    `currency`, é só um texto descritivo.
    """
    bruta = parceiro_para_bruta(ITEM_BOOKING)
    assert bruta.pontuacao == Decimal("4")
    assert bruta.unidade_pontuacao == "pontos_por_dolar"


def test_sem_descricao_de_unidade_cai_no_padrao_real():
    """New Balance é o único dos 168 parceiros ativos sem
    esf_accumulationFactorDescription — não pode quebrar a coleta inteira.
    """
    bruta = parceiro_para_bruta(ITEM_NEW_BALANCE)
    assert bruta.unidade_pontuacao == "pontos_por_real"


def test_regulamento_vem_limpo_de_html():
    bruta = parceiro_para_bruta(ITEM_RENNER)
    assert bruta.regulamento_texto.startswith("* Ganhe 3 pontos a cada R$ 1,00")
    assert "<p>" not in bruta.regulamento_texto
    assert "<strong>" not in bruta.regulamento_texto


def test_categoria_container_e_taxonomia_antiga_sao_descartadas():
    """new02163 é "Lojas Parceiras" — o contêiner que todo parceiro carrega,
    equivalente ao "todos" da Livelo. E esf02163 é a taxonomia antiga, que a
    Esfera está migrando: escolhida a "new_" porque ela precisa dialogar com
    as categorias da Livelo na camada canônica, e a sigla "esf_" amarra o
    dado à fonte de um jeito que a "new_" não amarra.
    """
    bruta = parceiro_para_bruta(ITEM_RENNER)
    assert bruta.categorias == ["newModaCalcadosAcessorios"]


def test_sem_pontuacao_base_nem_datas_por_ora():
    """A Esfera não expõe campo limpo equivalente ao `parityBau` (piso fora
    de campanha) nem a `dateStart`/`dateEnd` da Livelo — o período e o valor
    padrão só aparecem em texto livre, com redação diferente por parceiro
    (a Casas Bahia, por exemplo, tem duas taxas diferentes na mesma frase).
    Tentar extrair por regex arriscava inventar dado a partir de um padrão
    que só bate em ~20% dos casos. Fica de fora até haver fonte confiável.
    """
    bruta = parceiro_para_bruta(ITEM_RENNER)
    assert bruta.pontuacao_base is None
    assert bruta.data_inicio is None
    assert bruta.data_fim is None


def test_url_origem_a_partir_da_rota():
    bruta = parceiro_para_bruta(ITEM_RENNER)
    assert bruta.url_origem == "https://esfera.com.vc/p/renner/e000100180"
