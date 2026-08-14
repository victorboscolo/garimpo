"""Testes da decisão de publicar e da montagem das mensagens.

Duas regras de produto guiam tudo aqui:

- A categoria é o produto — é a opinião que o sistema entrega — e vai nas duas
  mensagens. A nota numérica e as notas por critério **não vão**: são a máquina
  por trás da opinião e ficam no painel, onde a validação interna acontece.
- A publicação nunca precede a aprovação humana, em nenhum modo.
"""
from decimal import Decimal
from types import SimpleNamespace

from application.publicacao_service import CONFIG_PADRAO, deve_publicar
from application.telegram.mensagens import montar_mensagem


def _promocao(**ajustes):
    padrao = dict(
        parceiro_nome="Renner",
        pontuacao=Decimal("10"),
        unidade_pontuacao="pontos_por_real",
        pontuacao_base=Decimal("2"),
        pontuacao_clube=None,
        pontuacao_e_teto=False,
        valor_condicionado=True,
        requer_cupom=False,
        cupom=None,
        data_fim=None,
        marketplace_status="PERMITIDO",
        regulamento_texto=(
            "Campanha válida de 14/08/2026 a 16/08/2026. Ganhe 10 pontos por real na "
            "categoria Básicos e 2 pontos demais produtos. Consulte o regulamento."
        ),
        url_origem="https://livelo.com.br/juntar-pontos/parceiros/renner/RNN",
        status="APROVADA",
    )
    padrao.update(ajustes)
    return SimpleNamespace(**padrao)


def _classificacao(categoria="EXCEPCIONAL", nota="94.8"):
    return SimpleNamespace(categoria=categoria, nota=Decimal(nota))


# --- decisão de publicar -----------------------------------------------------

def test_publica_quando_atinge_a_categoria_minima():
    assert deve_publicar(_classificacao("EXCELENTE"), "PUBLICO", CONFIG_PADRAO) is True


def test_nao_publica_abaixo_da_categoria_minima():
    assert deve_publicar(_classificacao("BOA"), "PUBLICO", CONFIG_PADRAO) is False


def test_canal_avancado_recebe_mais_que_o_publico():
    """Os validadores precisam ver também o que o motor avaliou como mediano —
    é onde mora a crítica de que ele errou para baixo.
    """
    boa = _classificacao("BOA")
    assert deve_publicar(boa, "AVANCADO", CONFIG_PADRAO) is True
    assert deve_publicar(boa, "PUBLICO", CONFIG_PADRAO) is False


def test_sem_classificacao_nao_publica():
    assert deve_publicar(None, "AVANCADO", CONFIG_PADRAO) is False


def test_canal_desconhecido_nao_publica():
    """Errar para o lado de não publicar: mandar para um canal não configurado
    é pior que não mandar.
    """
    assert deve_publicar(_classificacao(), "INEXISTENTE", CONFIG_PADRAO) is False


# --- mensagens ---------------------------------------------------------------

def test_categoria_aparece_nas_duas_mensagens():
    for tipo in ("PUBLICO", "AVANCADO"):
        texto = montar_mensagem(_promocao(), _classificacao(), tipo)
        assert "EXCEPCIONAL" in texto.upper()


def test_nota_numerica_nunca_aparece():
    """A nota é interna. Publicá-la convida a discutir o número em vez da
    oferta, e o número é a máquina, não o produto.
    """
    for tipo in ("PUBLICO", "AVANCADO"):
        texto = montar_mensagem(_promocao(), _classificacao(nota="94.8"), tipo)
        assert "94" not in texto
        assert "nota" not in texto.lower()


def test_condicao_aparece_nas_duas():
    """Uma oferta condicionada precisa avisar em qualquer canal: é o que separa
    informar de iludir.
    """
    for tipo in ("PUBLICO", "AVANCADO"):
        texto = montar_mensagem(_promocao(valor_condicionado=True), _classificacao(), tipo)
        assert "ondicionada" in texto or "ategoria Básicos" in texto


def test_avancado_traz_a_pontuacao_base_e_o_regulamento():
    texto = montar_mensagem(_promocao(), _classificacao(), "AVANCADO")
    assert "2" in texto and "regulamento" in texto.lower()


def test_publico_nao_traz_o_regulamento_inteiro():
    texto = montar_mensagem(_promocao(), _classificacao(), "PUBLICO")
    assert "Consulte o regulamento" not in texto


def test_cupom_aparece_com_destaque_quando_exigido():
    """Sem o cupom o leitor não pontua — é a informação que mais muda o
    resultado de seguir a oferta.
    """
    texto = montar_mensagem(_promocao(requer_cupom=True, cupom="LIVELO"), _classificacao(), "PUBLICO")
    assert "LIVELO" in texto


def test_link_da_oferta_sempre_presente():
    for tipo in ("PUBLICO", "AVANCADO"):
        texto = montar_mensagem(_promocao(), _classificacao(), tipo)
        assert "livelo.com.br" in texto


def test_singular_quando_e_um_ponto():
    """"1 pontos por R$ 1" denuncia texto gerado por máquina e tira a
    credibilidade da mensagem inteira.
    """
    texto = montar_mensagem(
        _promocao(pontuacao=Decimal("1"), pontuacao_base=Decimal("1")),
        _classificacao(), "PUBLICO",
    )
    assert "1 ponto por R$ 1" in texto
    assert "1 pontos" not in texto


def test_mensagem_nao_usa_marcacao():
    """Markdown do Telegram quebra com `_` ou `*` soltos, e o regulamento vem
    de fonte externa — um nome de parceiro com underscore derrubaria o envio.
    Sem marcação não há o que escapar nem o que quebrar, e nada de símbolo
    aparecendo cru na mensagem.
    """
    for tipo in ("PUBLICO", "AVANCADO"):
        texto = montar_mensagem(_promocao(), _classificacao(), tipo)
        assert "*" not in texto
        assert "_" not in texto


def test_marketplace_so_e_mencionado_quando_o_texto_o_menciona():
    """PERMITIDO é inferido do silêncio do regulamento. Publicar "vale também
    para o marketplace" a partir disso afirma que o parceiro TEM marketplace —
    e o Consórcio Embracon não tem. Ausência de restrição não é existência de
    canal de venda.
    """
    texto = montar_mensagem(
        _promocao(marketplace_status="PERMITIDO"), _classificacao(), "AVANCADO"
    )
    assert "marketplace" not in texto.lower()


def test_restricao_de_marketplace_declarada_no_texto_aparece():
    """PROIBIDO e PARCIAL vêm de menção explícita no regulamento — aí a
    informação é do parceiro, não nossa inferência, e é decisiva na compra.
    """
    proibido = montar_mensagem(
        _promocao(marketplace_status="PROIBIDO"), _classificacao(), "AVANCADO"
    )
    parcial = montar_mensagem(
        _promocao(marketplace_status="PARCIAL"), _classificacao(), "AVANCADO"
    )
    assert "vendidos e entregues" in proibido.lower()
    assert "marketplace" in parcial.lower()


def test_regulamento_curto_mas_informativo_e_publicado():
    """"Não pontua medicamentos." tem 24 caracteres e muda a decisão de compra.
    Qualquer filtro que venha a ser aplicado ao regulamento não pode descartar
    texto curto pelo tamanho — o que decide é o conteúdo.
    """
    texto = montar_mensagem(
        _promocao(regulamento_texto="Não pontua medicamentos."), _classificacao(), "AVANCADO"
    )
    assert "Não pontua medicamentos." in texto


def test_regulamento_informativo_seguido_de_boilerplate_mantem_o_util():
    texto = montar_mensagem(
        _promocao(regulamento_texto="Ganhe 10 pontos na categoria Básicos. Consulte o regulamento."),
        _classificacao(), "AVANCADO",
    )
    assert "categoria Básicos" in texto
