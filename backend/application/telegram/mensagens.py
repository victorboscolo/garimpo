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

MARKETPLACE_ROTULO = {
    "PROIBIDO": "🏪 Só vale para produtos vendidos e entregues pela loja",
    "PARCIAL": "🏪 Compras no marketplace pontuam menos",
    "PERMITIDO": "🏪 Vale também para o marketplace",
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


def montar_mensagem(promocao, classificacao, tipo: str) -> str:
    linhas = [CATEGORIA_ROTULO.get(classificacao.categoria, classificacao.categoria), ""]

    unidade = promocao.unidade_pontuacao
    teto = "até " if promocao.pontuacao_e_teto else ""
    linhas.append(f"*{promocao.parceiro_nome}* — {teto}{_pontos(promocao.pontuacao, unidade)}")

    if promocao.pontuacao_clube:
        linhas.append(f"💳 {_pontos(promocao.pontuacao_clube, unidade)} para assinantes do Clube")

    # A condição vai nos dois canais: avisar que o valor não vale para a compra
    # inteira é o que separa informar de iludir.
    if promocao.valor_condicionado:
        linhas.append("⚠️ Oferta condicionada — confira as regras antes de comprar")

    if promocao.requer_cupom and promocao.cupom:
        linhas.append(f"🎫 Use o cupom *{promocao.cupom}* no carrinho")

    if promocao.data_fim:
        linhas.append(f"🗓 Até {_formatar_data(promocao.data_fim)}")

    if tipo == "AVANCADO":
        if promocao.pontuacao_base is not None and promocao.pontuacao_base < promocao.pontuacao:
            linhas.append(f"📉 Fora da campanha esta loja rende {_pontos(promocao.pontuacao_base, unidade)}")
        if promocao.marketplace_status in MARKETPLACE_ROTULO:
            linhas.append(MARKETPLACE_ROTULO[promocao.marketplace_status])
        if promocao.regulamento_texto:
            linhas += ["", f"_{promocao.regulamento_texto}_"]

    linhas += ["", f"🔗 {promocao.url_origem}"]
    return "\n".join(linhas)
