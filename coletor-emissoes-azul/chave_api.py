"""Config compartilhada pelos três coletores de Emissões (Azul, Smiles,
LATAM): chave de API, URL base do backend, e o "aquecimento" antes da
primeira chamada real.

Cada coletor roda no seu próprio processo, fora do Docker, sem env_file
pra herdar a variável — por isso lê direto do `.env` na raiz do repo
quando ela não está no ambiente.
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger("garimpo.chave_api")


def _ler_env(nome: str, padrao: str | None = None) -> str | None:
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


def chave_api() -> str | None:
    return _ler_env("COLETOR_API_KEY")


HEADERS = {"X-API-Key": chave_api()} if chave_api() else {}

# A partir de 18/09 a nuvem (Render), não mais o Docker local — ver .env.example.
API_BASE_URL = _ler_env("API_BASE_URL", "http://localhost:8000")


def aquecer(tentativas: int = 3, espera_segundos: float = 20.0) -> None:
    """Acorda o backend antes da coleta de verdade.

    O Render (plano grátis) "dorme" o serviço depois de 15 min sem acesso —
    a primeira requisição depois disso demora até ~1 min pra responder
    (cold start), tempo maior que o timeout de qualquer chamada individual
    do coletor. Sem isso, a primeira busca do dia falharia por timeout
    mesmo com o backend saudável, só lento pra acordar.
    """
    with httpx.Client(timeout=espera_segundos) as client:
        for tentativa in range(1, tentativas + 1):
            try:
                resposta = client.get(f"{API_BASE_URL}/health")
                if resposta.status_code == 200:
                    return
            except httpx.RequestError as e:
                logger.info("Aquecendo o backend (tentativa %d/%d): %s", tentativa, tentativas, e)
    logger.warning("Backend não respondeu ao aquecimento — seguindo mesmo assim.")


def reportar_execucao(job: str, status: str, **campos) -> None:
    """Registra o resultado desta execução pro Painel de Saúde — igual ao
    que os coletores de Promoções (Livelo/Esfera) já fazem. Sem isso, uma
    falha agendada de Azul/Smiles/LATAM nunca aparece pra quem não estiver
    olhando o log local na hora.

    Nunca deve derrubar a coleta: se a própria API estiver fora do ar, é
    exatamente o cenário que o painel deveria estar avisando, então uma
    falha aqui só é logada, não propagada.
    """
    try:
        with httpx.Client(timeout=10.0, headers=HEADERS) as client:
            client.post(f"{API_BASE_URL}/api/v1/execucoes", json={"job": job, "status": status, **campos})
    except httpx.RequestError as e:
        logger.warning("Não foi possível registrar a execução no Painel de Saúde: %s", e)
