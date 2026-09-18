"""Coleta os parceiros da Esfera e envia para a API do Garimpo.

Ao contrário do coletor da Livelo, este roda com Python puro — a API da
Esfera não tem bloqueio anti-robô (ver esfera_api.py), então não precisa de
Chromium nem de disfarce de navegador. Continua rodando fora do Docker, via
launchd: não porque precise, mas para manter um único padrão operacional de
agendamento (o scheduler dentro do Docker foi removido de propósito por ser
frágil — perdia execuções quando o Mac dormia; launchd tem a mesma limitação,
então rodar dentro do Docker não evitaria isso).

Só cria promoções PENDENTES, nunca aprova sozinho — a aprovação continua
manual, no painel, como em qualquer outra fonte.
"""
from __future__ import annotations

import logging
import os
import sys

import httpx

from esfera_api import ParceiroEsfera, buscar_parceiros, parceiro_para_bruta

PROGRAMA_NOME = "Esfera"
JOB = "coletor_esfera"


def _ler_env(nome: str, padrao: str | None = None) -> str | None:
    """Lê uma variável do .env na raiz do repo — o painel passou a exigir
    autenticação em toda rota (18/09), e o coletor roda em venv próprio,
    fora do Docker, sem env_file pra herdar a variável."""
    if os.environ.get(nome):
        return os.environ[nome]
    caminho = os.path.join(os.path.dirname(__file__), "..", ".env")
    try:
        with open(caminho) as f:
            for linha in f:
                if linha.strip().startswith(f"{nome}="):
                    return linha.strip().split("=", 1)[1]
    except FileNotFoundError:
        pass
    return padrao


HEADERS = {"X-API-Key": _ler_env("COLETOR_API_KEY")} if _ler_env("COLETOR_API_KEY") else {}

# A partir de 18/09 a nuvem (Render), não mais o Docker local — ver .env.example.
API_BASE_URL = _ler_env("API_BASE_URL", "http://localhost:8000")
API_INGERIR_URL = f"{API_BASE_URL}/api/v1/promocoes/ingerir"
API_EXECUCOES_URL = f"{API_BASE_URL}/api/v1/execucoes"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("garimpo.coletor_esfera")


def _aquecer(tentativas: int = 3, espera_segundos: float = 20.0) -> None:
    """Acorda o backend antes da coleta de verdade — o Render (plano
    grátis) dorme depois de 15 min sem acesso, e o cold start pode passar
    de qualquer timeout individual de requisição do coletor."""
    with httpx.Client(timeout=espera_segundos) as client:
        for tentativa in range(1, tentativas + 1):
            try:
                if client.get(f"{API_BASE_URL}/health").status_code == 200:
                    return
            except httpx.RequestError as e:
                logger.info("Aquecendo o backend (tentativa %d/%d): %s", tentativa, tentativas, e)
    logger.warning("Backend não respondeu ao aquecimento — seguindo mesmo assim.")


def coletar() -> list[ParceiroEsfera]:
    itens = buscar_parceiros()
    logger.info("Recebidos %d parceiros ativos da API da Esfera.", len(itens))
    return [parceiro_para_bruta(item) for item in itens]


def enviar_para_api(parceiros: list[ParceiroEsfera]) -> dict:
    enviados, falhas, descartados = 0, 0, 0

    with httpx.Client(timeout=30.0, headers=HEADERS) as client:
        for p in parceiros:
            payload = {
                "programa_nome": PROGRAMA_NOME,
                "parceiro_nome_bruto": p.nome_exibicao,
                "titulo": p.nome_exibicao,
                "url_origem": p.url_origem,
                "pontuacao": str(p.pontuacao),
                "unidade_pontuacao": p.unidade_pontuacao,
                "regulamento_texto": p.regulamento_texto,
                "requer_clube": False,
                "qual_clube": None,
                "requer_cupom": False,
                "cupom": None,
                "pontuacao_e_teto": p.pontuacao_e_teto,
                "pontuacao_clube": None,
                "codigo_externo": p.codigo_externo,
                "nome_exibicao": p.nome_exibicao,
                "pontuacao_base": None,
                "categorias": p.categorias,
                "pontuacao_anterior": None,
                "em_promocao": False,
                "data_inicio": None,
                "data_fim": None,
                "origem_detalhe": "COLETOR_ESFERA",
            }
            try:
                resposta = client.post(API_INGERIR_URL, json=payload)
                if resposta.status_code == 200:
                    corpo = resposta.json()
                    if corpo is None:
                        descartados += 1
                    else:
                        enviados += 1
                else:
                    falhas += 1
                    logger.warning(
                        "Falha ao enviar '%s': HTTP %s - %s",
                        p.nome_exibicao, resposta.status_code, resposta.text[:200],
                    )
            except httpx.RequestError as e:
                falhas += 1
                logger.error("Erro de conexão ao enviar '%s': %s", p.nome_exibicao, e)

    logger.info(
        "Envio concluído: %d criadas, %d descartadas (duplicata/parceiro não cadastrado), %d falhas.",
        enviados, descartados, falhas,
    )
    return {"criadas": enviados, "descartadas": descartados, "falhas": falhas}


def _reportar_execucao(status: str, **campos) -> None:
    """Registra o resultado desta execução pro Painel de Saúde.

    Nunca deve derrubar a coleta: se a própria API estiver fora do ar, é
    exatamente o cenário que o painel deveria estar avisando, então uma falha
    aqui só é logada, não propagada.
    """
    try:
        with httpx.Client(timeout=10.0, headers=HEADERS) as client:
            client.post(API_EXECUCOES_URL, json={"job": JOB, "status": status, **campos})
    except httpx.RequestError as e:
        logger.warning("Não foi possível registrar a execução no Painel de Saúde: %s", e)


def main():
    _aquecer()
    try:
        parceiros = coletar()
    except Exception as e:
        logger.exception("Coleta falhou.")
        _reportar_execucao("FALHA", erro=str(e)[:500])
        sys.exit(1)

    if not parceiros:
        logger.warning("Nenhum parceiro coletado — verifique se a API da Esfera está acessível.")
        _reportar_execucao("FALHA", erro="Nenhum parceiro coletado")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"AMOSTRA (10 primeiros de {len(parceiros)}):")
    print(f"{'='*70}")
    for item in parceiros[:10]:
        teto = "até " if item.pontuacao_e_teto else ""
        print(f"  {item.nome_exibicao:30s} {teto}{item.pontuacao:>6} {item.unidade_pontuacao}")
    print()

    resultado = enviar_para_api(parceiros)
    _reportar_execucao("SUCESSO", **resultado)


if __name__ == "__main__":
    main()
