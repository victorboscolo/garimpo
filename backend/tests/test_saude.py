"""Testes de lógica pura da avaliação de saúde dos jobs.

`avaliar_saude` decide, a partir da última execução de cada job e do horário
atual, se está tudo bem, atrasado ou nunca rodou. Não toca banco — quem busca
a última execução de cada job é `application/saude_service.py::obter_saude`,
testado à parte (integração).
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from application.saude_service import JANELA_POR_JOB, avaliar_saude

AGORA = datetime(2026, 8, 18, 23, 0, tzinfo=timezone.utc)


def _execucao(job, horas_atras, status="SUCESSO", **campos):
    return SimpleNamespace(
        job=job,
        status=status,
        criadas=campos.get("criadas"),
        descartadas=campos.get("descartadas"),
        falhas=campos.get("falhas"),
        erro=campos.get("erro"),
        created_at=AGORA - timedelta(hours=horas_atras),
    )


def test_execucao_recente_e_bem_sucedida_esta_ok():
    resultado = avaliar_saude("coletor_livelo", _execucao("coletor_livelo", 2), agora=AGORA)
    assert resultado["situacao"] == "OK"


def test_execucao_falhou_fica_em_falha_mesmo_recente():
    resultado = avaliar_saude("coletor_livelo", _execucao("coletor_livelo", 1, status="FALHA", erro="timeout"), agora=AGORA)
    assert resultado["situacao"] == "FALHA"


def test_execucao_alem_da_janela_fica_atrasada():
    janela = JANELA_POR_JOB["coletor_livelo"]
    execucao = _execucao("coletor_livelo", janela.total_seconds() / 3600 + 1)
    resultado = avaliar_saude("coletor_livelo", execucao, agora=AGORA)
    assert resultado["situacao"] == "ATRASADA"


def test_execucao_dentro_da_janela_nao_fica_atrasada():
    janela = JANELA_POR_JOB["coletor_livelo"]
    execucao = _execucao("coletor_livelo", janela.total_seconds() / 3600 - 1)
    resultado = avaliar_saude("coletor_livelo", execucao, agora=AGORA)
    assert resultado["situacao"] == "OK"


def test_sem_nenhuma_execucao_nunca_rodou():
    resultado = avaliar_saude("coletor_livelo", None, agora=AGORA)
    assert resultado["situacao"] == "NUNCA_RODOU"


def test_job_sem_janela_configurada_usa_padrao():
    """Um job novo, ainda sem entrada em JANELA_POR_JOB, não pode quebrar —
    cai num padrão conservador em vez de nunca marcar como atrasado."""
    resultado = avaliar_saude("job_desconhecido", _execucao("job_desconhecido", 1000), agora=AGORA)
    assert resultado["situacao"] == "ATRASADA"
