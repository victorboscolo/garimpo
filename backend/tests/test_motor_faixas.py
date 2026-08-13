"""Testes da resolução de categoria a partir da nota do Motor de Análise.

Contexto: as faixas são configuráveis via `configuracoes` e vêm do banco como
JSON, com limites inteiros (ex.: excelente 75-89, excepcional 90-100). As notas,
porém, são decimais — então existem vãos entre uma faixa e a seguinte
(89,01 a 89,99) onde uma nota válida não pertence a faixa nenhuma.
"""
from application.motor.servico import FAIXAS_DEFAULT, _resolver_categoria

# Como o JSONB do Postgres devolve as chaves: em ordem alfabética, não na ordem
# em que foram escritas. A resolução não pode depender da ordem do dicionário.
FAIXAS_COMO_VEM_DO_BANCO = {
    "boa": {"max": 74, "min": 55},
    "comum": {"max": 54, "min": 35},
    "excelente": {"max": 89, "min": 75},
    "excepcional": {"max": 100, "min": 90},
    "pouco_atrativa": {"max": 34, "min": 0},
}


def test_nota_no_vao_entre_faixas_cai_na_faixa_de_baixo():
    """Nota 89,5 está acima do teto de Excelente (89) e abaixo do piso de
    Excepcional (90). Deve ser Excelente — nunca o fallback Comum.
    """
    assert _resolver_categoria(89.5, FAIXAS_DEFAULT) == "EXCELENTE"


def test_todos_os_vaos_entre_faixas_resolvem_para_a_faixa_de_baixo():
    for nota, esperado in [
        (34.5, "POUCO_ATRATIVA"),
        (54.5, "COMUM"),
        (74.5, "BOA"),
        (89.5, "EXCELENTE"),
    ]:
        assert _resolver_categoria(nota, FAIXAS_DEFAULT) == esperado


def test_notas_exatamente_no_piso_da_faixa():
    assert _resolver_categoria(90.0, FAIXAS_DEFAULT) == "EXCEPCIONAL"
    assert _resolver_categoria(75.0, FAIXAS_DEFAULT) == "EXCELENTE"
    assert _resolver_categoria(55.0, FAIXAS_DEFAULT) == "BOA"
    assert _resolver_categoria(35.0, FAIXAS_DEFAULT) == "COMUM"
    assert _resolver_categoria(0.0, FAIXAS_DEFAULT) == "POUCO_ATRATIVA"


def test_resolucao_nao_depende_da_ordem_das_chaves():
    """O motor lê as faixas do banco, onde a ordem é alfabética."""
    assert _resolver_categoria(89.5, FAIXAS_COMO_VEM_DO_BANCO) == "EXCELENTE"
    assert _resolver_categoria(95.0, FAIXAS_COMO_VEM_DO_BANCO) == "EXCEPCIONAL"


def test_nota_maxima_e_minima():
    assert _resolver_categoria(100.0, FAIXAS_DEFAULT) == "EXCEPCIONAL"
    assert _resolver_categoria(0.0, FAIXAS_DEFAULT) == "POUCO_ATRATIVA"
