"""Coletor de Emissões (LATAM) — primeira versão.

Diferente de Azul e Smiles, a LATAM nunca teve bloqueio Akamai — a
barreira sempre foi login (achado antigo, reconfirmado 17/09): sem
sessão autenticada, a busca com milhas nem carrega resultado. Por isso
este coletor **depende de uma sessão já logada manualmente pelo usuário**
num perfil de Chrome dedicado (`perfil-latam-dedicado/`, na raiz deste
diretório) — nunca automatizamos login, mesmo com credencial fornecida:
seria contornar a mesma barreira de acesso que a Azul/Smiles não têm.

Por isso mesmo, este é o único dos três coletores que usa **Playwright**,
não SeleniumBase: sem bloqueio anti-bot pra vencer, não há motivo pro
`uc=True` do SeleniumBase — e achado real (17/09), ele nem serve aqui:
abrir o mesmo `user_data_dir` com SeleniumBase não reconhece a sessão que
o Playwright gravou (perfis internos incompatíveis entre as duas
ferramentas), a busca volta a pedir login. Como o login foi feito com
Playwright (mesma ferramenta usada pros outros perfis dedicados,
Smiles/Azul), a leitura também precisa ser com Playwright.

Se a sessão tiver expirado (cookie de login vencido), a busca volta a
pedir login e a coleta falha "sem oferta" pra tudo — não é bug do
parser, é a sessão precisando de novo login manual.

Navega direto pra URL de resultado (`redemption=true` é o parâmetro que
ativa a busca por milhas), sem preencher formulário — testado 2x contra
rotas reais (GRU->MIA, GIG->SCL), sessão autenticada uma vez só.

## ⚠️ Suspeita real, não resolvida (21/09): navegação direta pode
## subestimar disponibilidade

Achado do usuário: buscando SCL->GRU pelo formulário de verdade do site
(digitando origem/destino, selecionando data, clicando "Procurar voos"),
ele encontrou oferta em milhas (33.130, direto) numa data em que a
navegação direta por URL deste coletor (mesma rota, mesma data, mesmo
perfil logado) devolvia "sem oferta" de forma consistente — confirmado
em buscas repetidas, inclusive ao vivo, sem mudança.

Investigação em 21/09: reproduzir o fluxo do formulário via automação
(preencher campos, clicar o botão de verdade — não navegação direta)
**deu timeout 3 de 3 vezes**, com a própria LATAM admitindo o problema
("A busca está demorando mais que o normal", página de erro
`/oferta-voos/erro/tempo-resultados-busca/`). Ou seja: passar pelo
formulário parece acionar uma busca "ao vivo" mais lenta e mais completa
no backend deles — é provavelmente isso que revela disponibilidade que a
navegação direta (rápida, ~10-12s, usada por este coletor) não enxerga.
Mas essa busca "ao vivo" não é confiável pra automação hoje (timeout
nas 3 tentativas).

**Conclusão prática, ainda em aberto**: os dados que este coletor traz
podem estar subestimando disponibilidade real da LATAM de forma
sistemática, não só num caso isolado. Não foi resolvido nesta sessão —
fica registrado pra retomar, não é hipótese descartada.

Uso manual: ./venv/bin/python3 coletor_emissoes_latam.py [--limite N]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import date, timedelta

import httpx
from playwright.async_api import async_playwright

from chave_api import API_BASE_URL, HEADERS, aquecer, reportar_execucao
from parsing_latam import extrair_ofertas_latam_dom

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("garimpo.coletor_emissoes_latam")

API_ROTAS_URL = f"{API_BASE_URL}/api/v1/emissoes/rotas?programa_nome=LATAM"
API_OFERTAS_URL = f"{API_BASE_URL}/api/v1/emissoes/ofertas"

DIAS_A_FRENTE = 30
CLASSE = "ECONOMY"

PERFIL_LATAM = os.path.join(os.path.dirname(__file__), "perfil-latam-dedicado")


def _url_busca(origem: str, destino: str, data_ida: date) -> str:
    """Busca só-ida por milhas (`redemption=true`, `trip=OW`) — capturada
    de verdade em 17/09/2026, depois de uma sessão autenticada
    manualmente pelo usuário buscar GRU->MIA e GIG->SCL.
    """
    timestamp_iso = f"{data_ida.isoformat()}T00%3A00%3A00.000Z"
    return (
        "https://www.latamairlines.com/br/pt/oferta-voos?"
        f"origin={origem}&outbound={timestamp_iso}&destination={destino}"
        "&adt=1&chd=0&inf=0&trip=OW&cabin=Economy&redemption=true&sort=RECOMMENDED"
    )


async def buscar_latam(page, origem: str, destino: str, data_ida: date | None = None) -> tuple[dict, date]:
    """Devolve (`{"direto": oferta | None, "com_parada": oferta | None}`,
    data efetivamente buscada).

    Sem `data_ida`, usa o padrão do coletor agendado (hoje + `DIAS_A_FRENTE`).
    Passar uma data explícita é o que `buscar_latam_intervalo.py` usa pra
    pesquisas pontuais fora da cadência diária (ex: pedido do usuário,
    21/09, segunda quinzena de julho/2027).
    """
    if data_ida is None:
        data_ida = date.today() + timedelta(days=DIAS_A_FRENTE)
    url = _url_busca(origem, destino, data_ida)
    logger.info("LATAM: buscando %s -> %s (%s)", origem, destino, data_ida)
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_timeout(9000)

    html = await page.content()
    # "Fazer login" por si só não serve de sinal — aparece em algum canto
    # da página mesmo com a sessão ativa (achado 17/09, falso positivo
    # confirmado com resultado real na tela ao mesmo tempo). O texto da
    # tela de login de verdade é mais específico.
    if "Insira seu usuário" in html and "card-expander-0" not in html:
        raise RuntimeError(
            "Sessão da LATAM não está logada (caiu na tela de login) — "
            "peça pro usuário logar de novo no perfil-latam-dedicado."
        )

    resultado = extrair_ofertas_latam_dom(html)
    return resultado, data_ida


async def buscar_rotas(client: httpx.AsyncClient, limite: int) -> list[dict]:
    resposta = await client.get(API_ROTAS_URL)
    resposta.raise_for_status()
    return resposta.json()[:limite]


async def enviar_oferta(client: httpx.AsyncClient, rota: dict, data_ida: date, oferta: dict) -> bool:
    payload = {
        "programa_nome": "LATAM",
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
        resposta = await client.post(API_OFERTAS_URL, json=payload, timeout=10.0)
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


JOB = "coletor_latam"


async def main(limite: int) -> None:
    aquecer()
    if not os.path.isdir(PERFIL_LATAM):
        logger.error(
            "Perfil %s não existe — o usuário precisa logar manualmente na LATAM "
            "nesse perfil antes de rodar o coletor.", PERFIL_LATAM,
        )
        reportar_execucao(JOB, "FALHA", erro="Perfil da LATAM não existe — precisa de login manual")
        return

    async with httpx.AsyncClient(timeout=15.0, headers=HEADERS) as client:
        rotas = await buscar_rotas(client, limite)

        if not rotas:
            logger.error("Nenhuma rota LATAM encontrada em rotas_emissao — rode o seed antes.")
            reportar_execucao(JOB, "FALHA", erro="Nenhuma rota LATAM cadastrada")
            return

        logger.info("Rodando %d rota(s): %s", len(rotas), [f"{r['origem']}->{r['destino']}" for r in rotas])

        gravadas, sem_oferta, falhas = 0, 0, 0

        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                PERFIL_LATAM, channel="chrome", headless=False,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1400, "height": 900}, locale="pt-BR",
            )
            page = context.pages[0] if context.pages else await context.new_page()

            for rota in rotas:
                try:
                    ofertas, data_ida = await buscar_latam(page, rota["origem"], rota["destino"])
                except Exception:
                    logger.exception("Falha buscando %s -> %s (LATAM)", rota["origem"], rota["destino"])
                    falhas += 1
                    continue

                if ofertas["direto"] is None and ofertas["com_parada"] is None:
                    logger.info("  %s -> %s: sem oferta disponível.", rota["origem"], rota["destino"])
                    sem_oferta += 1
                    continue

                for oferta in (ofertas["direto"], ofertas["com_parada"]):
                    if oferta is None:
                        continue
                    if await enviar_oferta(client, rota, data_ida, oferta):
                        gravadas += 1
                    else:
                        falhas += 1

            await context.close()

        logger.info("Concluído: %d gravadas, %d sem oferta, %d falhas.", gravadas, sem_oferta, falhas)
        reportar_execucao(JOB, "SUCESSO", criadas=gravadas, descartadas=sem_oferta, falhas=falhas)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, default=2, help="Rotas LATAM a buscar (padrão: 2)")
    args = parser.parse_args()
    asyncio.run(main(args.limite))
