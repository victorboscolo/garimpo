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
        programa_nome="Livelo",
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


def test_programa_aparece_nas_duas_mensagens():
    """Com mais de um programa (Livelo e Esfera) publicando no mesmo canal, o
    link deixa de ser a única forma de saber de onde é a oferta — quem lê
    precisa disso antes de abrir a mensagem, não só ao clicar.
    """
    for tipo in ("PUBLICO", "AVANCADO"):
        texto = montar_mensagem(_promocao(programa_nome="Esfera"), _classificacao(), tipo)
        assert "Esfera" in texto


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


def test_regulamento_muito_longo_e_truncado():
    """A Livelo nunca passou de 484 caracteres de regulamento (17/08/2026,
    364 promoções). A Esfera tem mediana de 1106 e 166 dos 167 parceiros
    passam de 500 — o "regulamento na íntegra" do AVANÇADO virava uma parede
    de texto genérico sobre como o programa funciona (esvaziar carrinho, CPF
    cadastrado, prazo de crédito), sem nada específico desta oferta depois do
    início. O início — onde mora o que muda por oferta (taxa, validade,
    restrição de categoria) — precisa sobreviver inteiro.
    """
    cabeca = "Ganhe 6 pontos a cada R$ 1,00 em compras no site parceiro. Condições válidas de 17/08/2026 até 19/08/2026. "
    cauda_generica = "Lembre-se que você precisa acessar a loja parceira através deste link. " * 20
    texto_bruto = cabeca + cauda_generica

    texto = montar_mensagem(
        _promocao(regulamento_texto=texto_bruto, programa_nome="Esfera"),
        _classificacao(), "AVANCADO",
    )

    assert cabeca in texto
    assert texto_bruto not in texto
    assert "regulamento completo" in texto.lower()
    # A mensagem inteira, não só o regulamento, precisa ficar num tamanho
    # legível no Telegram — bem abaixo do limite de 4096 da plataforma.
    assert len(texto) < 1000


def test_regulamento_dentro_do_limite_nao_e_truncado():
    """O maior regulamento real da Livelo (484 caracteres) não pode ser
    tocado — o limite precisa ter folga sobre o que já existe hoje.
    """
    texto_484 = "Campanha válida de 12 a 17/08/2026. " + "Ganhe pontos em compras selecionadas. " * 11
    assert len(texto_484) <= 484

    texto = montar_mensagem(
        _promocao(regulamento_texto=texto_484), _classificacao(), "AVANCADO",
    )
    assert texto_484 in texto
    assert "regulamento completo" not in texto.lower()


# --- tópicos pré-determinados --------------------------------------------------
#
# Pontuação, Validade e Cupom viram tópicos rotulados porque já são dado limpo
# — vêm de campo próprio, não de texto livre. Escopo fica de fora de propósito:
# não existe campo para isso, e extrair de texto livre por regex arriscaria
# rotular "sem restrição" numa oferta que na verdade tem uma — pior que não
# ter o tópico. Ver a conversa que resolveu isso: o regulamento truncado
# continua sendo a fonte crua de reserva, nunca rotulado como Escopo.

def test_topico_pontuacao_aparece_rotulado():
    texto = montar_mensagem(_promocao(pontuacao_e_teto=True), _classificacao(), "PUBLICO")
    assert "Pontuação: até 10 pontos por R$ 1" in texto


def test_topico_validade_so_aparece_quando_ha_data_fim():
    from datetime import date
    com_data = montar_mensagem(
        _promocao(data_fim=date(2026, 8, 16)), _classificacao(), "PUBLICO"
    )
    assert "Validade: até 16/08" in com_data

    sem_data = montar_mensagem(_promocao(data_fim=None), _classificacao(), "PUBLICO")
    assert "Validade" not in sem_data


def test_topico_cupom_aparece_rotulado():
    texto = montar_mensagem(
        _promocao(requer_cupom=True, cupom="LIVELO"), _classificacao(), "PUBLICO"
    )
    assert "Cupom: LIVELO" in texto


def test_clube_e_base_se_juntam_ao_topico_pontuacao_no_avancado():
    """Clube e "fora da campanha" são fatos sobre a mesma coisa — quanto a
    oferta paga — e por isso vivem dentro do tópico Pontuação, não espalhados
    em linhas soltas.
    """
    texto = montar_mensagem(
        _promocao(pontuacao_clube=Decimal("15"), pontuacao_base=Decimal("2")),
        _classificacao(), "AVANCADO",
    )
    linha_pontuacao = next(l for l in texto.splitlines() if l.startswith("💰"))
    assert "15 pontos por R$ 1" in linha_pontuacao
    assert "fora da campanha" in linha_pontuacao
    assert "2 pontos por R$ 1" in linha_pontuacao


def test_escopo_nunca_e_rotulado():
    """Não existe fonte confiável para "escopo" (só texto livre inconsistente
    por parceiro) — inventar o rótulo afirmaria uma leitura que o dado não
    sustenta. Guarda de regressão: se alguém tentar adicionar de novo, este
    teste avisa.
    """
    for tipo in ("PUBLICO", "AVANCADO"):
        texto = montar_mensagem(_promocao(), _classificacao(), tipo)
        assert "Escopo" not in texto
