"""Monta o texto publicado em cada canal.

A diferença entre os formatos é **quanto detalhe da oferta** cada um dá, e não
quanto do motor cada um expõe. A categoria — "Excepcional", "Excelente" — vai
nos dois, porque é a opinião que o sistema entrega e é o produto. Já a nota
numérica e as notas por critério não vão a canal nenhum: são a máquina por trás
da opinião, ficam no painel, e publicá-las convidaria a discutir o número em vez
da oferta.

O AVANCADO acrescenta o que permite julgar a oferta a fundo: a pontuação fora da
campanha, o regulamento na íntegra, o alcance no marketplace e a validade
completa.

Sem marcação de formatação, de propósito. O Markdown do Telegram quebra quando o
texto contém `_` ou `*` desbalanceados, e tanto o nome do parceiro quanto o
regulamento vêm de fonte externa — um underscore no lugar errado derrubaria o
envio ou faria o símbolo aparecer cru na mensagem. Emoji e quebra de linha dão
a hierarquia visual necessária sem nada para escapar.
"""
from decimal import Decimal

CATEGORIA_ROTULO = {
    "EXCEPCIONAL": "🔥 EXCEPCIONAL",
    "EXCELENTE": "⭐ EXCELENTE",
    "BOA": "👍 BOA",
    "COMUM": "⚠️ COMUM",
    "POUCO_ATRATIVA": "❌ POUCO ATRATIVA",
}

UNIDADE_MOEDA = {
    "pontos_por_real": "R$ 1",
    "pontos_por_dolar": "U$ 1",
}

# PERMITIDO não aparece aqui de propósito. Ele é inferido do silêncio do
# regulamento — serve ao motor para entender que a oferta não é restrita, mas
# publicá-lo afirmaria que o parceiro TEM marketplace. O Consórcio Embracon não
# tem, e a mensagem dizia "vale também para o marketplace". Ausência de
# restrição não é existência de canal de venda.
MARKETPLACE_ROTULO = {
    "PROIBIDO": "🏪 Só vale para produtos vendidos e entregues pela loja",
    "PARCIAL": "🏪 Compras no marketplace pontuam menos",
}


def _numero(valor: Decimal | None) -> str:
    """Sem casas decimais quando são zeros: "10" lê melhor que "10.00"."""
    if valor is None:
        return ""
    inteiro = int(valor)
    return str(inteiro) if Decimal(inteiro) == valor else str(valor)


def _pontos(valor: Decimal | None, unidade: str) -> str:
    """"1 ponto por R$ 1", não "1 pontos": concordância errada denuncia texto
    de máquina e tira a credibilidade da mensagem inteira.
    """
    moeda = UNIDADE_MOEDA.get(unidade, unidade)
    numero = _numero(valor)
    palavra = "ponto" if valor is not None and abs(valor) == 1 else "pontos"
    return f"{numero} {palavra} por {moeda}"


def _formatar_data(data) -> str:
    return data.strftime("%d/%m") if data else ""


# A Livelo nunca passou de 484 caracteres de regulamento (17/08/2026, 364
# promoções na base). A Esfera tem mediana de 1106 e quase todo mundo (166 de
# 167) passa de 500 — o texto ali não é regulamento específico da oferta, é a
# explicação genérica de como o programa funciona (esvaziar carrinho, CPF
# cadastrado, prazo de crédito), igual em toda oferta. 500 dá folga sobre o
# maior caso real da Livelo sem deixar a Esfera virar parede de texto.
LIMITE_REGULAMENTO = 500


def _regulamento_truncado(texto: str) -> str:
    """Corta pelo tamanho, nunca pelo conteúdo — não julga o que é útil, só
    limita quanto cabe na mensagem. O texto completo continua salvo no banco
    e a um clique de distância, no link que toda mensagem já traz.
    """
    if len(texto) <= LIMITE_REGULAMENTO:
        return texto
    corte = texto.rfind(" ", 0, LIMITE_REGULAMENTO)
    if corte <= 0:
        corte = LIMITE_REGULAMENTO
    return texto[:corte].rstrip(" .,;") + "… (regulamento completo no link abaixo)"


def montar_mensagem(promocao, classificacao, tipo: str) -> str:
    """Tópicos pré-determinados para o que já é dado limpo — Pontuação,
    Validade, Cupom — em vez de bullets soltos. "Escopo" fica de fora de
    propósito: não existe campo confiável para isso, só texto livre com
    redação inconsistente por parceiro, e rotular uma leitura que o dado não
    sustenta é pior que não ter o tópico. O regulamento (truncado, ver
    `_regulamento_truncado`) continua como fonte crua de reserva no AVANÇADO,
    nunca como um tópico "Escopo".
    """
    linhas = [CATEGORIA_ROTULO.get(classificacao.categoria, classificacao.categoria), ""]

    linhas.append(f"{promocao.parceiro_nome} ({promocao.programa_nome})")

    unidade = promocao.unidade_pontuacao
    teto = "até " if promocao.pontuacao_e_teto else ""
    # Clube e "fora da campanha" são fatos sobre a mesma coisa — quanto a
    # oferta paga — por isso vivem dentro do tópico Pontuação, não espalhados
    # em linhas soltas com ícones próprios.
    pontuacao_partes = [f"{teto}{_pontos(promocao.pontuacao, unidade)}"]
    if promocao.pontuacao_clube:
        pontuacao_partes.append(f"{_pontos(promocao.pontuacao_clube, unidade)} para assinantes do Clube")
    if (
        tipo == "AVANCADO"
        and promocao.pontuacao_base is not None
        and promocao.pontuacao_base < promocao.pontuacao
    ):
        pontuacao_partes.append(f"fora da campanha: {_pontos(promocao.pontuacao_base, unidade)}")
    linhas.append(f"💰 Pontuação: {' — '.join(pontuacao_partes)}")

    if promocao.data_fim:
        linhas.append(f"🗓 Validade: até {_formatar_data(promocao.data_fim)}")

    if promocao.requer_cupom and promocao.cupom:
        linhas.append(f"🎫 Cupom: {promocao.cupom}")

    # A condição vai nos dois canais: avisar que o valor não vale para a compra
    # inteira é o que separa informar de iludir.
    if promocao.valor_condicionado:
        linhas.append("⚠️ Oferta condicionada — confira as regras antes de comprar")

    if tipo == "AVANCADO":
        if promocao.marketplace_status in MARKETPLACE_ROTULO:
            linhas.append(MARKETPLACE_ROTULO[promocao.marketplace_status])
        if promocao.regulamento_texto:
            linhas += ["", _regulamento_truncado(promocao.regulamento_texto)]

    linhas += ["", f"🔗 {promocao.url_origem}"]
    return "\n".join(linhas)
