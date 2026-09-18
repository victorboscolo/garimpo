#!/bin/bash
# Checagem periódica do Painel de Saúde: atraso não é evento como falha —
# ninguém "avisa" sozinho que um job ficou atrasado, ele só fica assim
# conforme o tempo passa sem ninguém reportar. Este script existe só pra
# bater aqui de tempos em tempos e deixar o backend decidir se avisa
# (ver application/saude_service.py::verificar_atrasados_e_alertar).
#
# Roda via launchd (com.garimpo.verificar-saude.plist), em intervalo fixo
# (StartInterval), não em horário de calendário — não importa a que hora do
# dia roda, só que rode com regularidade.
GARIMPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COLETOR_API_KEY=$(grep -E '^COLETOR_API_KEY=' "$GARIMPO_ROOT/.env" 2>/dev/null | cut -d '=' -f2-)

# A partir de 18/09 a nuvem (Render), não mais o Docker local. --max-time
# sobe de 30 pra 90s: o Render (plano grátis) dorme depois de 15 min sem
# acesso, e o cold start pode passar dos 30s de antes.
API_BASE=$(grep -E '^API_BASE_URL=' "$GARIMPO_ROOT/.env" 2>/dev/null | cut -d '=' -f2-)
API_BASE="${API_BASE:-http://127.0.0.1:8000}"

curl -s --max-time 90 -X POST -H "X-API-Key: $COLETOR_API_KEY" \
  "$API_BASE/api/v1/saude/verificar-atrasados" > /dev/null
