"""Coletor de Emissões (Azul) — segunda versão, migrado pra SeleniumBase.

Playwright (mesmo com `--disable-blink-features=AutomationControlled`, Chrome
real, perfil aged, stealth) sempre bateu no bloqueio "Ops! Só um momento" do
Akamai — confirmado de novo em 17/09 com testes de controle isolando IP,
fingerprint e reputação de sessão. `SeleniumBase` no modo `uc=True` (patch em
tempo de execução no binário do Chrome, remove os ganchos que o Akamai
detecta do CDP) passa direto, sem aquecimento de sessão nenhum — cada busca é
uma navegação direta e independente, testado 2x seguidas (GRU→LIS, GRU→JFK).

**`SITE_PRINCIPAL` continua bloqueado** e por isso fica fora desta versão: a
home passa pelo SeleniumBase, mas a API de busca de verdade
(`b2c-api.voeazul.com.br/.../v6/availability`) devolve 403 mesmo assim —
proteção em duas camadas separadas, achado de 17/09. `SITE_PRINCIPAL` cobre
a malha própria da Azul (Brasil + Flórida/Lisboa/Paris); `AZUL_PELO_MUNDO`
(parceiros, +3.000 destinos) é a única fonte funcional por ora.

Não é loop assíncrono: SeleniumBase é uma API síncrona (Selenium por baixo),
e não vale a pena rodar isso numa thread só pra manter o resto em asyncio —
o script inteiro virou síncrono, `httpx.Client` no lugar do `AsyncClient`.

Uso manual: ./venv/bin/python3 coletor_emissoes_azul.py [--limite N]
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import date, timedelta

import httpx
from seleniumbase import Driver

from chave_api import API_BASE_URL, HEADERS, aquecer
from parsing import extrair_ofertas_azul_pelo_mundo_dom
from urls import url_azul_pelo_mundo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("garimpo.coletor_emissoes_azul")

API_ROTAS_URL = f"{API_BASE_URL}/api/v1/emissoes/rotas?programa_nome=Azul"
API_OFERTAS_URL = f"{API_BASE_URL}/api/v1/emissoes/ofertas"

DIAS_A_FRENTE = 30
CLASSE = "ECONOMY"

# Teto de buscas por sessão da versão Playwright (~10, "sessão aquecida") não
# se aplica mais: cada busca aqui já é uma navegação independente, sem
# aquecimento. O teto real da versão SeleniumBase ainda não foi caracterizado
# — comece pequeno (`--limite`) até ter mais dados.


def buscar_azul_pelo_mundo(driver: Driver, origem: str, destino: str) -> tuple[dict, date]:
    """Devolve (`{"direto": oferta | None, "com_parada": oferta | None}`,
    data efetivamente buscada).

    Navega direto pra URL de resultado (`urls.py`) — sem aquecimento de
    sessão, achado de 17/09. Lê o preço do HTML já renderizado
    (`.componentFlight`), não da API crua: a API exige um token de
    reCAPTCHA que só o JS da própria página sabe gerar, então refazer a
    chamada de fora (mesmo com os cookies certos) devolve 400
    `MISSING_TOKEN` — ver `parsing.py`.
    """
    data_ida = date.today() + timedelta(days=DIAS_A_FRENTE)
    url = url_azul_pelo_mundo(origem, destino, data_ida, CLASSE)
    logger.info("azulpelomundo: buscando %s -> %s (%s)", origem, destino, data_ida)
    driver.get(url)
    time.sleep(6)

    linhas = driver.execute_script("""
        return Array.from(document.querySelectorAll('.componentFlight')).map(el => el.outerHTML);
    """)
    if not linhas:
        # Rota fora do escopo do portal (ex: doméstica) devolve página em
        # branco, sem nenhuma linha de resultado — achado de 17/09, não é erro.
        return {"direto": None, "com_parada": None}, data_ida

    resultado = extrair_ofertas_azul_pelo_mundo_dom(linhas)
    return resultado, data_ida


def buscar_rotas(client: httpx.Client, limite: int) -> list[dict]:
    resposta = client.get(API_ROTAS_URL)
    resposta.raise_for_status()
    todas = resposta.json()

    # SITE_PRINCIPAL segue bloqueado (ver docstring do módulo) — só
    # AZUL_PELO_MUNDO é buscado nesta versão.
    do_azul_pelo_mundo = [r for r in todas if r["fonte"] == "AZUL_PELO_MUNDO"]
    return do_azul_pelo_mundo[:limite]


def enviar_oferta(client: httpx.Client, rota: dict, data_ida: date, oferta: dict) -> bool:
    payload = {
        "programa_nome": "Azul",
        "origem": rota["origem"],
        "destino": rota["destino"],
        "data_ida": data_ida.isoformat(),
        "classe": CLASSE,
        "pontos": oferta["pontos"],
        "companhia_operadora": oferta.get("companhia_operadora"),
        "paradas": oferta.get("paradas"),
        "assentos_restantes": oferta.get("assentos_restantes"),
        "duracao_texto": oferta.get("duracao_texto"),
    }
    try:
        resposta = client.post(API_OFERTAS_URL, json=payload, timeout=10.0)
    except httpx.RequestError as e:
        logger.error("Erro de conexão ao enviar %s -> %s: %s", rota["origem"], rota["destino"], e)
        return False

    if resposta.status_code == 200:
        logger.info(
            "  %s -> %s: %s pontos, %s parada(s), gravado.",
            rota["origem"], rota["destino"], oferta["pontos"], oferta.get("paradas"),
        )
        return True

    logger.warning(
        "Falha ao enviar %s -> %s: HTTP %s - %s",
        rota["origem"], rota["destino"], resposta.status_code, resposta.text[:200],
    )
    return False


def main(limite: int) -> None:
    aquecer()
    with httpx.Client(timeout=15.0, headers=HEADERS) as client:
        rotas = buscar_rotas(client, limite)

        if not rotas:
            logger.error("Nenhuma rota AZUL_PELO_MUNDO encontrada em rotas_emissao — rode o seed antes.")
            return

        logger.info("Rodando %d rota(s): %s", len(rotas), [f"{r['origem']}->{r['destino']}" for r in rotas])

        gravadas, sem_oferta, falhas = 0, 0, 0

        driver = Driver(uc=True, headless=False)
        try:
            for rota in rotas:
                try:
                    ofertas, data_ida = buscar_azul_pelo_mundo(driver, rota["origem"], rota["destino"])
                except Exception:
                    logger.exception("Falha buscando %s -> %s (AZUL_PELO_MUNDO)", rota["origem"], rota["destino"])
                    falhas += 1
                    continue

                # Duas categorias, cada uma sua própria linha (decisão do
                # usuário, 17/09) — uma pode existir sem a outra.
                if ofertas["direto"] is None and ofertas["com_parada"] is None:
                    logger.info("  %s -> %s: sem oferta disponível.", rota["origem"], rota["destino"])
                    sem_oferta += 1
                    continue

                for oferta in (ofertas["direto"], ofertas["com_parada"]):
                    if oferta is None:
                        continue
                    if enviar_oferta(client, rota, data_ida, oferta):
                        gravadas += 1
                    else:
                        falhas += 1
        finally:
            driver.quit()

        logger.info("Concluído: %d gravadas, %d sem oferta, %d falhas.", gravadas, sem_oferta, falhas)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, default=2, help="Rotas AZUL_PELO_MUNDO a buscar (padrão: 2)")
    args = parser.parse_args()
    main(args.limite)
