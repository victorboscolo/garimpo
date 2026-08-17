"""Coleta os parceiros da Esfera e envia para a API do Garimpo.

Ao contrário do coletor da Livelo, este roda com Python puro — a API da
Esfera não tem bloqueio anti-robô (ver esfera_api.py), então não precisa de
Chromium nem de disfarce de navegador. Continua rodando fora do Docker, via
launchd: não porque precise, mas para manter um único padrão operacional de
agendamento (o scheduler dentro do Docker foi removido de propósito por ser
frágil — perdia execuções quando o Mac dormia; launchd tem a mesma limitação,
então rodar dentro do Docker não evitaria isso).

Só cria promoções PENDENTES, nunca aprova sozinho — a aprovação continua
manual, no painel, como em qualquer outra fonte.
"""
from __future__ import annotations

import logging
import sys

import httpx

from esfera_api import ParceiroEsfera, buscar_parceiros, parceiro_para_bruta

API_INGERIR_URL = "http://localhost:8000/api/v1/promocoes/ingerir"
PROGRAMA_NOME = "Esfera"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("garimpo.coletor_esfera")


def coletar() -> list[ParceiroEsfera]:
    itens = buscar_parceiros()
    logger.info("Recebidos %d parceiros ativos da API da Esfera.", len(itens))
    return [parceiro_para_bruta(item) for item in itens]


def enviar_para_api(parceiros: list[ParceiroEsfera]) -> None:
    enviados, falhas, descartados = 0, 0, 0

    with httpx.Client(timeout=30.0) as client:
        for p in parceiros:
            payload = {
                "programa_nome": PROGRAMA_NOME,
                "parceiro_nome_bruto": p.nome_exibicao,
                "titulo": p.nome_exibicao,
                "url_origem": p.url_origem,
                "pontuacao": str(p.pontuacao),
                "unidade_pontuacao": p.unidade_pontuacao,
                "regulamento_texto": p.regulamento_texto,
                "requer_clube": False,
                "qual_clube": None,
                "requer_cupom": False,
                "cupom": None,
                "pontuacao_e_teto": p.pontuacao_e_teto,
                "pontuacao_clube": None,
                "codigo_externo": p.codigo_externo,
                "nome_exibicao": p.nome_exibicao,
                "pontuacao_base": None,
                "categorias": p.categorias,
                "pontuacao_anterior": None,
                "em_promocao": False,
                "data_inicio": None,
                "data_fim": None,
                "origem_detalhe": "COLETOR_ESFERA",
            }
            try:
                resposta = client.post(API_INGERIR_URL, json=payload)
                if resposta.status_code == 200:
                    corpo = resposta.json()
                    if corpo is None:
                        descartados += 1
                    else:
                        enviados += 1
                else:
                    falhas += 1
                    logger.warning(
                        "Falha ao enviar '%s': HTTP %s - %s",
                        p.nome_exibicao, resposta.status_code, resposta.text[:200],
                    )
            except httpx.RequestError as e:
                falhas += 1
                logger.error("Erro de conexão ao enviar '%s': %s", p.nome_exibicao, e)

    logger.info(
        "Envio concluído: %d criadas, %d descartadas (duplicata/parceiro não cadastrado), %d falhas.",
        enviados, descartados, falhas,
    )


def main():
    parceiros = coletar()
    if not parceiros:
        logger.warning("Nenhum parceiro coletado — verifique se a API da Esfera está acessível.")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"AMOSTRA (10 primeiros de {len(parceiros)}):")
    print(f"{'='*70}")
    for item in parceiros[:10]:
        teto = "até " if item.pontuacao_e_teto else ""
        print(f"  {item.nome_exibicao:30s} {teto}{item.pontuacao:>6} {item.unidade_pontuacao}")
    print()

    enviar_para_api(parceiros)


if __name__ == "__main__":
    main()
