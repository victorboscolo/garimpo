"""Testes de montagem de URL do coletor de Emissões (Azul).

O padrão da URL do azulpelomundo foi validado empiricamente em 20/08/2026
— 6 buscas internacionais reais encadeadas na mesma sessão (Londres, JFK,
Madrid, Roma, Miami, Los Angeles), todas retornando resultado, e a URL
abaixo é exatamente a que o próprio site gerou (capturada de
`window.location.href` depois de uma busca real GRU->LHR).

O do site principal (voeazul.com.br) ainda NÃO foi revalidado nesta sessão
— por isso não tem função aqui ainda. Não vale a pena arriscar codificar de
memória de uma investigação anterior sem conferir de novo.
"""
from datetime import date

from urls import url_azul_pelo_mundo, url_site_principal

# Capturada de verdade em 20/08/2026, depois de uma busca real GRU->LHR:
# https://azulpelomundo.voeazul.com.br/flights/RT/GRU/LHR/-/-/2026-08-30/2026-08-31/1/0/0/0/0/ALL/F/ECONOMY/-/-/-/-/A/-
URL_REAL_CAPTURADA = (
    "https://azulpelomundo.voeazul.com.br/flights/RT/GRU/LHR/-/-/"
    "2026-08-30/2026-08-31/1/0/0/0/0/ALL/F/ECONOMY/-/-/-/-/A/-"
)


def test_url_bate_com_a_capturada_de_verdade():
    url = url_azul_pelo_mundo(
        origem="GRU", destino="LHR",
        data_ida=date(2026, 8, 30), data_volta=date(2026, 8, 31),
        classe="ECONOMY",
    )
    assert url == URL_REAL_CAPTURADA


def test_classe_business_vai_maiuscula():
    url = url_azul_pelo_mundo(
        origem="GRU", destino="JFK",
        data_ida=date(2026, 10, 16), data_volta=date(2026, 10, 24),
        classe="business",
    )
    assert "/BUSINESS/" in url


def test_datas_no_formato_iso():
    url = url_azul_pelo_mundo(
        origem="GIG", destino="MAD",
        data_ida=date(2026, 12, 1), data_volta=date(2026, 12, 8),
        classe="ECONOMY",
    )
    assert "/2026-12-01/2026-12-08/" in url


def test_origem_e_destino_ficam_no_lugar_certo():
    url = url_azul_pelo_mundo(
        origem="SDU", destino="CWB",
        data_ida=date(2026, 9, 1), data_volta=date(2026, 9, 5),
        classe="ECONOMY",
    )
    assert "/flights/RT/SDU/CWB/" in url


# Capturada de verdade em 20/08/2026, depois de uma busca real GIG->MCO
# ida e volta, com "Usar pontos Azul" marcado:
# https://www.voeazul.com.br/br/pt/home/selecao-voo?c[0].ds=GIG&c[0].std=08/23/2026&c[0].as=MCO&c[1].ds=MCO&c[1].std=09/07/2026&c[1].as=GIG&p[0].t=ADT&p[0].c=1&p[0].cp=false&f.dl=3&f.dr=3&cc=PTS
URL_SITE_PRINCIPAL_REAL = (
    "https://www.voeazul.com.br/br/pt/home/selecao-voo?"
    "c[0].ds=GIG&c[0].std=08/23/2026&c[0].as=MCO&"
    "c[1].ds=MCO&c[1].std=09/07/2026&c[1].as=GIG&"
    "p[0].t=ADT&p[0].c=1&p[0].cp=false&f.dl=3&f.dr=3&cc=PTS"
)


def test_url_site_principal_bate_com_a_capturada_de_verdade():
    url = url_site_principal(
        origem="GIG", destino="MCO",
        data_ida=date(2026, 8, 23), data_volta=date(2026, 9, 7),
    )
    assert url == URL_SITE_PRINCIPAL_REAL


def test_url_site_principal_nao_tem_parametro_de_classe():
    """Achado real (20/08): a busca no site principal já traz Economy e
    Business juntas no mesmo resultado — classe não é parâmetro de busca
    aqui, é atributo de cada opção retornada. Guarda de regressão pra não
    reintroduzir um parâmetro de classe que não existe de verdade.
    """
    url = url_site_principal(origem="GIG", destino="LIS", data_ida=date(2026, 10, 1), data_volta=date(2026, 10, 8))
    assert "classe" not in url.lower()
    assert "cabin" not in url.lower()
