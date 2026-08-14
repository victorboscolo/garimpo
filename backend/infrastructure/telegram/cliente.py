"""Envio de mensagens ao Telegram. Só transporte — não decide o que enviar.

Lê o token e os IDs de canal do ambiente. Nenhum valor é registrado em log:
token em log vira token vazado.

Enquanto as variáveis não existirem, `esta_configurado` devolve False e o
serviço de publicação recusa o disparo com uma mensagem clara, em vez de falhar
no meio do lote com metade das mensagens enviadas.
"""
import logging
import os

import httpx

logger = logging.getLogger("garimpo.infrastructure.telegram")

API_BASE = "https://api.telegram.org"

# Um canal por tipo de publicação, como previsto no Cap. 6.
VARIAVEL_DE_CANAL = {
    "PUBLICO": "TELEGRAM_CANAL_PUBLICO_ID",
    "AVANCADO": "TELEGRAM_CANAL_AVANCADO_ID",
}


def _token() -> str | None:
    return os.environ.get("TELEGRAM_BOT_TOKEN") or None


def canal_de(tipo: str) -> str | None:
    variavel = VARIAVEL_DE_CANAL.get(tipo)
    return os.environ.get(variavel) if variavel else None


def esta_configurado(tipo: str) -> bool:
    return bool(_token() and canal_de(tipo))


def motivo_nao_configurado(tipo: str) -> str:
    """Texto para a API devolver ao painel, dizendo o que falta preencher."""
    faltando = []
    if not _token():
        faltando.append("TELEGRAM_BOT_TOKEN")
    if not canal_de(tipo):
        faltando.append(VARIAVEL_DE_CANAL.get(tipo, f"canal de {tipo}"))
    return f"Configuração ausente no .env: {', '.join(faltando)}."


async def enviar(tipo: str, texto: str) -> None:
    """Publica no canal do tipo. Levanta exceção em qualquer falha, para que o
    chamador registre FALHA em `publicacoes` com o motivo.
    """
    token, canal = _token(), canal_de(tipo)
    if not token or not canal:
        raise RuntimeError(motivo_nao_configurado(tipo))

    async with httpx.AsyncClient(timeout=20.0) as client:
        resposta = await client.post(
            f"{API_BASE}/bot{token}/sendMessage",
            json={
                "chat_id": canal,
                "text": texto,
                "parse_mode": "Markdown",
                # O link já aparece no texto; a prévia automática ocuparia a
                # tela toda e enterraria as mensagens seguintes.
                "disable_web_page_preview": True,
            },
        )
    if resposta.status_code != 200:
        # A resposta do Telegram descreve o erro, mas a URL contém o token —
        # por isso só o corpo é propagado.
        raise RuntimeError(f"Telegram devolveu HTTP {resposta.status_code}: {resposta.text[:200]}")
