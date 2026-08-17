"""Testes de `_completar_dados_da_campanha` e `_tem_regulamento_real`.

O gatilho: no painel, a Esfera nunca mostrava o bloco de regulamento em
destaque no card — só a Livelo. A causa não era falta de dado (167 dos 168
parceiros da Esfera têm regulamento real e completo), era um detector
específico demais: `_tem_regulamento_real` (e a cópia em JS do painel)
verificava se o texto continha "campanha válida" — frase que a Livelo usa e a
Esfera nunca usa (0 dos 168 regulamentos reais dela contêm isso).

O detector deveria checar o oposto: não é regulamento real quando bate o
placeholder que o coletor antigo escrevia sobre si mesmo ("Coletado do site
oficial..."), não quando falta uma frase específica de uma única fonte.
"""
from decimal import Decimal
from types import SimpleNamespace

from application.ingestao_service import (
    PromocaoBrutaIn,
    _completar_dados_da_campanha,
    _tem_regulamento_real,
)

REGULAMENTO_ESFERA = (
    "Ganhe 6 pontos a cada R$ 1,00 em compras no site parceiro. Condições "
    "válidas para compras efetuadas de 00h00min do dia 17/08/2026 até "
    "23h59min do dia 19/08/2026."
)
REGULAMENTO_LIVELO = "Campanha válida de 14/08/2026 a 16/08/2026. Ganhe 10 pontos por real."
PLACEHOLDER_ANTIGO = "Coletado do site oficial da Livelo."


def _bruta(**ajustes) -> PromocaoBrutaIn:
    padrao = dict(
        programa_nome="Esfera",
        parceiro_nome_bruto="Beleza na Web",
        titulo="Beleza na Web",
        url_origem="https://esfera.com.vc/p/beleza-na-web/e000100477",
        pontuacao=Decimal("6"),
        unidade_pontuacao="pontos_por_real",
    )
    padrao.update(ajustes)
    return PromocaoBrutaIn(**padrao)


def _existente(**ajustes) -> SimpleNamespace:
    padrao = dict(
        regulamento_texto=None,
        data_inicio=None,
        data_fim=None,
        pontuacao_base=None,
        pontuacao_anterior=None,
        em_promocao=False,
        # Recalculados sempre que o regulamento muda — não fazem parte do que
        # este teste examina, mas `_completar_dados_da_campanha` sempre lê.
        pontuacao=Decimal("6"),
        pontuacao_e_teto=False,
        valor_condicionado=False,
        marketplace_status=None,
    )
    padrao.update(ajustes)
    return SimpleNamespace(**padrao)


def test_regulamento_da_esfera_e_reconhecido_como_real():
    """Sem "campanha válida" em lugar nenhum, mas é regulamento de verdade."""
    assert _tem_regulamento_real(REGULAMENTO_ESFERA) is True


def test_regulamento_da_livelo_continua_reconhecido():
    assert _tem_regulamento_real(REGULAMENTO_LIVELO) is True


def test_placeholder_antigo_nao_e_regulamento_real():
    assert _tem_regulamento_real(PLACEHOLDER_ANTIGO) is False


def test_regulamento_esfera_ja_gravado_nao_e_sobrescrito_a_toa():
    """Antes do fix: toda coleta duplicada da Esfera reescrevia o regulamento
    (e marcava `mudou=True`) porque o texto já salvo "não parecia real" —
    ruído em todo log, todo dia, para 167 parceiros.

    `marketplace_status` já vem "PERMITIDO" porque é o que este texto resolve
    (silêncio sobre marketplace) — do contrário o teste pegaria uma mudança
    legítima desse campo e erraria a causa.
    """
    existente = _existente(regulamento_texto=REGULAMENTO_ESFERA, marketplace_status="PERMITIDO")
    bruta = _bruta(regulamento_texto=REGULAMENTO_ESFERA)

    mudou = _completar_dados_da_campanha(existente, bruta)

    assert mudou is False
    assert existente.regulamento_texto == REGULAMENTO_ESFERA


def test_placeholder_antigo_e_substituido_pelo_regulamento_real():
    existente = _existente(regulamento_texto=PLACEHOLDER_ANTIGO)
    bruta = _bruta(regulamento_texto=REGULAMENTO_ESFERA)

    mudou = _completar_dados_da_campanha(existente, bruta)

    assert mudou is True
    assert existente.regulamento_texto == REGULAMENTO_ESFERA


def test_regulamento_vazio_e_preenchido():
    existente = _existente(regulamento_texto=None)
    bruta = _bruta(regulamento_texto=REGULAMENTO_ESFERA)

    mudou = _completar_dados_da_campanha(existente, bruta)

    assert mudou is True
    assert existente.regulamento_texto == REGULAMENTO_ESFERA
