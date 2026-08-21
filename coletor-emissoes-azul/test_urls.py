"""Testes de montagem de URL do coletor de Emissões (Azul), busca só-ida.

Ambos os padrões abaixo validados empiricamente em 21/08/2026, depois da
mudança pra busca só-ida (decisão do usuário, 21/08): buscas reais
encadeadas na mesma sessão, e a URL de cada teste é exatamente a que o
próprio site gerou (capturada de `window.location.href` depois da busca).
"""
from datetime import date

from urls import url_azul_pelo_mundo, url_site_principal

# Capturada de verdade em 21/08/2026, depois de uma busca real GRU->LIS,
# só-ida:
# https://azulpelomundo.voeazul.com.br/flights/OW/GRU/LIS/-/-/2026-08-25/-/1/0/0/0/0/ALL/F/ECONOMY/-/-/-/-/A/-
URL_REAL_CAPTURADA = (
    "https://azulpelomundo.voeazul.com.br/flights/OW/GRU/LIS/-/-/"
    "2026-08-25/-/1/0/0/0/0/ALL/F/ECONOMY/-/-/-/-/A/-"
)


def test_url_bate_com_a_capturada_de_verdade():
    url = url_azul_pelo_mundo(
        origem="GRU", destino="LIS", data_ida=date(2026, 8, 25), classe="ECONOMY",
    )
    assert url == URL_REAL_CAPTURADA


def test_classe_business_vai_maiuscula():
    url = url_azul_pelo_mundo(
        origem="GRU", destino="JFK", data_ida=date(2026, 10, 16), classe="business",
    )
    assert "/BUSINESS/" in url


def test_data_no_formato_iso():
    url = url_azul_pelo_mundo(
        origem="GIG", destino="MAD", data_ida=date(2026, 12, 1), classe="ECONOMY",
    )
    assert "/2026-12-01/-/" in url


def test_origem_e_destino_ficam_no_lugar_certo():
    url = url_azul_pelo_mundo(
        origem="SDU", destino="CWB", data_ida=date(2026, 9, 1), classe="ECONOMY",
    )
    assert "/flights/OW/SDU/CWB/" in url


# Capturada de verdade em 21/08/2026, depois de uma busca real GIG->MCO,
# só-ida, com "Usar pontos Azul" marcado:
# https://www.voeazul.com.br/br/pt/home/selecao-voo?c[0].ds=GIG&c[0].std=08/22/2026&c[0].as=MCO&p[0].t=ADT&p[0].c=1&p[0].cp=false&f.dl=3&f.dr=3&cc=PTS
URL_SITE_PRINCIPAL_REAL = (
    "https://www.voeazul.com.br/br/pt/home/selecao-voo?"
    "c[0].ds=GIG&c[0].std=08/22/2026&c[0].as=MCO&"
    "p[0].t=ADT&p[0].c=1&p[0].cp=false&f.dl=3&f.dr=3&cc=PTS"
)


def test_url_site_principal_bate_com_a_capturada_de_verdade():
    url = url_site_principal(origem="GIG", destino="MCO", data_ida=date(2026, 8, 22))
    assert url == URL_SITE_PRINCIPAL_REAL


def test_url_site_principal_nao_tem_parametro_de_classe():
    """Achado real (20/08): a busca no site principal já traz Economy e
    Business juntas no mesmo resultado — classe não é parâmetro de busca
    aqui, é atributo de cada opção retornada. Guarda de regressão pra não
    reintroduzir um parâmetro de classe que não existe de verdade.
    """
    url = url_site_principal(origem="GIG", destino="LIS", data_ida=date(2026, 10, 1))
    assert "classe" not in url.lower()
    assert "cabin" not in url.lower()


def test_url_site_principal_nao_tem_parametro_de_volta():
    """Achado real (21/08): busca só-ida no site principal larga os
    parâmetros `c[1].*` (perna de volta) por completo, não os deixa vazios.
    """
    url = url_site_principal(origem="GIG", destino="LIS", data_ida=date(2026, 10, 1))
    assert "c[1]" not in url
