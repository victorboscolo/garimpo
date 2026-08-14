"""Decide o que publicar, para qual canal, e registra cada envio.

Fronteira do Cap. 6: o módulo Telegram nunca toca em `promocoes` — consome este
serviço. Adicionar um público novo é acrescentar um canal na configuração e um
template de mensagem, sem mexer aqui.

## Modo de publicação

A configuração vive em `configuracoes`, chave `publicacao`, com a mesma
hierarquia GLOBAL → DOMÍNIO → PROGRAMA → PARCEIRO usada pelos pesos e faixas do
motor. Trocar o comportamento é editar dado, não código.

`modo` admite dois valores:

- MANUAL: as aprovadas entram numa fila e um humano dispara o lote. É o modo de
  hoje, escolhido enquanto o motor amadurece e as notas ainda merecem curadoria.
- AUTOMATICO: **arquitetura prevista, ainda não implementada**. A intenção é que
  aprovar uma oferta acima do limiar já dispare a publicação. Quando for
  implementado, o gancho é uma chamada em `aprovar_promocao` — o resto (limiar
  por canal, montagem da mensagem, registro em `publicacoes`) já existe e é o
  mesmo. Configurar AUTOMATICO hoje registra um aviso e se comporta como MANUAL,
  para que ninguém suponha que está ligado.

Em nenhum dos modos a publicação precede a aprovação humana. AUTOMATICO
significa "publica sozinho depois que você aprovou", nunca "publica sem você" —
publicar sem aprovação seria outra decisão, de produto, e não está contemplada.
"""
import logging

logger = logging.getLogger("garimpo.application.publicacao")

# Da pior para a melhor. A comparação é por posição, não por nome, para que
# mudar os rótulos das faixas não quebre silenciosamente o limiar.
ORDEM_CATEGORIAS = ["POUCO_ATRATIVA", "COMUM", "BOA", "EXCELENTE", "EXCEPCIONAL"]

CONFIG_PADRAO = {
    "modo": "MANUAL",
    "canais": {
        # Os validadores recebem mais: é preciso ver também o que o motor achou
        # mediano para poder criticar que ele errou para baixo.
        "AVANCADO": {"categoria_minima": "BOA"},
        "PUBLICO": {"categoria_minima": "EXCELENTE"},
    },
}


def deve_publicar(classificacao, tipo: str, config: dict) -> bool:
    """A oferta atinge o limiar do canal?

    Sem classificação, ou com canal fora da configuração, devolve False: mandar
    para um canal não configurado é pior que não mandar.
    """
    if classificacao is None:
        return False

    canal = (config.get("canais") or {}).get(tipo)
    if not canal:
        return False

    minima = canal.get("categoria_minima")
    if minima not in ORDEM_CATEGORIAS or classificacao.categoria not in ORDEM_CATEGORIAS:
        return False

    return ORDEM_CATEGORIAS.index(classificacao.categoria) >= ORDEM_CATEGORIAS.index(minima)


def modo_efetivo(config: dict) -> str:
    """MANUAL ou AUTOMATICO, avisando quando o segundo ainda não existe."""
    modo = (config or {}).get("modo", "MANUAL")
    if modo == "AUTOMATICO":
        logger.warning(
            "Modo de publicação AUTOMATICO está configurado, mas o disparo na aprovação "
            "ainda não foi implementado. Tratando como MANUAL."
        )
        return "MANUAL"
    return "MANUAL"
