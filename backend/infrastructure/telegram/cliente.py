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


async def diagnosticar(tipo: str) -> dict:
    """Verifica a configuração sem publicar nada.

    Existe porque um erro de configuração no Telegram se manifesta de formas
    pouco óbvias — token errado, bot não adicionado, bot sem permissão de
    publicar e ID de canal errado dão mensagens diferentes e igualmente
    crípticas. Melhor descobrir aqui do que com uma mensagem torta chegando
    aos validadores.

    Nenhum valor de token aparece no retorno.
    """
    token, canal = _token(), canal_de(tipo)

    resultado = {
        "canal": tipo,
        "token_configurado": bool(token),
        "canal_configurado": bool(canal),
        "bot": None,
        "canal_nome": None,
        "pode_publicar": None,
        "erro": None,
    }
    if not token or not canal:
        resultado["erro"] = motivo_nao_configurado(tipo)
        return resultado

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            # 1. O token é válido? getMe é a forma mais barata de saber.
            resposta = await client.get(f"{API_BASE}/bot{token}/getMe")
            dados = resposta.json()
            if not dados.get("ok"):
                resultado["erro"] = (
                    "O Telegram recusou o token. Confira se copiou a linha inteira "
                    f"do BotFather. ({dados.get('description', 'sem detalhe')})"
                )
                return resultado
            bot = dados["result"]
            resultado["bot"] = f"@{bot.get('username')}"

            # 2. O bot enxerga o canal? Falha aqui costuma ser ID errado ou bot
            #    não adicionado.
            resposta = await client.get(f"{API_BASE}/bot{token}/getChat", params={"chat_id": canal})
            dados = resposta.json()
            if not dados.get("ok"):
                resultado["erro"] = (
                    "O bot não encontrou o canal. Verifique se o ID está correto "
                    "(inclusive o sinal de menos) e se o bot foi adicionado como "
                    f"administrador. ({dados.get('description', 'sem detalhe')})"
                )
                return resultado
            resultado["canal_nome"] = dados["result"].get("title")

            # 3. Tem permissão de publicar? Ser membro não basta.
            resposta = await client.get(
                f"{API_BASE}/bot{token}/getChatMember",
                params={"chat_id": canal, "user_id": bot["id"]},
            )
            dados = resposta.json()
            if dados.get("ok"):
                membro = dados["result"]
                administrador = membro.get("status") in ("administrator", "creator")
                resultado["pode_publicar"] = bool(
                    administrador and membro.get("can_post_messages", administrador)
                )
                if not resultado["pode_publicar"]:
                    resultado["erro"] = (
                        "O bot está no canal mas não pode publicar. Em Administradores, "
                        "habilite a permissão de publicar mensagens."
                    )
        except httpx.RequestError as e:
            resultado["erro"] = f"Não foi possível falar com o Telegram: {e}"

    return resultado
