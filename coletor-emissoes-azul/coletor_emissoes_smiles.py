"""Coletor de Emissões (Smiles) — primeira versão, escopo pequeno de
propósito (decisão do usuário, 17/09, mesmo espírito da Azul em 21/08).

Vive junto do coletor da Azul (mesmo diretório, mesmo venv) porque os dois
usam a mesma ferramenta (`SeleniumBase`, modo `uc=True`) e o mesmo padrão de
"ler o HTML já renderizado" — não há coletor-nativo separado ainda porque
a Smiles é só essas duas rotas por ora (ver seed_smiles.py no backend).

Achado de 09-17/09: a busca cai num spinner ("Aguarde enquanto buscamos os
melhores voos") na primeira navegação de uma sessão nova — não é erro, só
demora mais que o normal; resolve sozinho em ~15-20s. Diferente da Azul, a
API de busca da Smiles nunca foi viável de forma alguma (Akamai bloqueia
até com fingerprint de navegador real, achado de 09/09), então aqui não há
alternativa por API nem crua nem com refetch — é HTML renderizado desde o
início.

Uso manual: ./venv/bin/python3 coletor_emissoes_smiles.py [--limite N]
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import date, timedelta

import httpx
from seleniumbase import Driver

from parsing_smiles import extrair_ofertas_smiles_dom

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("garimpo.coletor_emissoes_smiles")

API_ROTAS_URL = "http://localhost:8000/api/v1/emissoes/rotas?programa_nome=Smiles"
API_OFERTAS_URL = "http://localhost:8000/api/v1/emissoes/ofertas"

DIAS_A_FRENTE = 30
CLASSE = "ECONOMY"  # valor gravado em ofertas_emissao.classe, junto da Azul
_CABIN_NA_URL = "ECONOMIC"  # a Smiles usa essa palavra na URL, não "ECONOMY"

# Tempo de resposta da busca é bem inconsistente (achado de 09-17/09): a
# mesma rota levou 6s numa tentativa e 24s noutra. O texto do spinner por
# si só não é um sinal confiável de "terminou" — visto ele desaparecer e
# reaparecer no meio de uma busca ainda em andamento. Por isso o critério
# de "terminou" é ter pelo menos um cartão de resultado, não o spinner
# ausente; e há um recurso a mais, imitando o que resolvia manualmente
# (seção 5 do HANDOFF): se a página toda não sair do zero depois do
# primeiro bloco de tentativas, um `reload()` e mais um bloco de tentativas.
TENTATIVAS_POR_BLOCO = 8
SEGUNDOS_POR_TENTATIVA = 4


def _url_busca(origem: str, destino: str, data_ida: date) -> str:
    """Busca só-ida: `tripType=2` com `returnDate` vazio devolve resultado
    de ida sozinha (achado de 17/09 — parece contraintuitivo, `tripType=2`
    normalmente seria "ida e volta", mas testado ao vivo e confirmado)."""
    timestamp_ms = int(time.mktime(data_ida.timetuple()) * 1000)
    return (
        "https://www.smiles.com.br/mfe/emissao-passagem/?"
        f"adults=1&cabin={_CABIN_NA_URL}&children=0&departureDate={timestamp_ms}"
        "&infants=0&isElegible=false&isFlexibleDateChecked=false&returnDate="
        f"&searchType=g3&segments=1&tripType=2&originAirport={origem}&originCity="
        f"&originCountry=&originAirportIsAny=false&destinationAirport={destino}"
        "&destinCity=&destinCountry=&destinAirportIsAny=false"
    )


def buscar_smiles(driver: Driver, origem: str, destino: str) -> tuple[dict, date]:
    """Devolve (`{"direto": oferta | None, "com_parada": oferta | None}`,
    data efetivamente buscada).
    """
    data_ida = date.today() + timedelta(days=DIAS_A_FRENTE)
    url = _url_busca(origem, destino, data_ida)
    logger.info("Smiles: buscando %s -> %s (%s)", origem, destino, data_ida)
    driver.get(url)
    cartoes = _esperar_cartoes(driver)

    if not cartoes:
        # `driver.refresh()` foi tentado aqui e piorou: a MFE da Smiles não
        # reidrata sozinha num reload de verdade, fica em branco pra
        # sempre (achado de 17/09) — uma navegação nova pra mesma URL
        # (bootstrap completo do app de novo) é o equivalente que funciona.
        logger.info("Smiles: sem cartões após o primeiro bloco de tentativas, navegando de novo (%s -> %s)", origem, destino)
        driver.get(url)
        cartoes = _esperar_cartoes(driver)

    resultado = extrair_ofertas_smiles_dom(cartoes)
    return resultado, data_ida


def _esperar_cartoes(driver: Driver) -> list[str]:
    """Espera até `TENTATIVAS_POR_BLOCO` vezes por pelo menos um cartão de
    resultado. Não confia no texto do spinner como sinal de "terminou" —
    ver comentário de `TENTATIVAS_POR_BLOCO`.
    """
    for _ in range(TENTATIVAS_POR_BLOCO):
        cartoes = driver.execute_script("""
            return Array.from(document.querySelectorAll('.select-flight-list-accordion-item'))
                .map(el => el.outerHTML);
        """)
        if cartoes:
            return cartoes
        time.sleep(SEGUNDOS_POR_TENTATIVA)
    return []


def buscar_rotas(client: httpx.Client, limite: int) -> list[dict]:
    resposta = client.get(API_ROTAS_URL)
    resposta.raise_for_status()
    return resposta.json()[:limite]


def enviar_oferta(client: httpx.Client, rota: dict, data_ida: date, oferta: dict) -> bool:
    payload = {
        "programa_nome": "Smiles",
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
            "  %s -> %s: %s milhas, %s parada(s), gravado.",
            rota["origem"], rota["destino"], oferta["pontos"], oferta.get("paradas"),
        )
        return True

    logger.warning(
        "Falha ao enviar %s -> %s: HTTP %s - %s",
        rota["origem"], rota["destino"], resposta.status_code, resposta.text[:200],
    )
    return False


def main(limite: int) -> None:
    with httpx.Client(timeout=15.0) as client:
        rotas = buscar_rotas(client, limite)

        if not rotas:
            logger.error("Nenhuma rota Smiles encontrada em rotas_emissao — rode o seed_smiles antes.")
            return

        logger.info("Rodando %d rota(s): %s", len(rotas), [f"{r['origem']}->{r['destino']}" for r in rotas])

        gravadas, sem_oferta, falhas = 0, 0, 0

        # Diferente da Azul (que encadeia buscas na mesma sessão sem
        # problema), a Smiles trava a segunda busca em diante dentro do
        # mesmo navegador — achado de 17/09: mesma URL, mesmo driver, que
        # funciona isolado (~24s) nunca resolve como segunda busca da
        # sessão, mesmo com um orçamento de espera bem maior. Um navegador
        # novo por rota custa uns segundos extras de startup, mas é o que
        # funciona de verdade.
        for rota in rotas:
            driver = Driver(uc=True, headless=False)
            try:
                try:
                    ofertas, data_ida = buscar_smiles(driver, rota["origem"], rota["destino"])
                except Exception:
                    logger.exception("Falha buscando %s -> %s (Smiles)", rota["origem"], rota["destino"])
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
    parser.add_argument("--limite", type=int, default=2, help="Rotas Smiles a buscar (padrão: 2)")
    args = parser.parse_args()
    main(args.limite)
