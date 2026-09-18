#!/bin/bash
# Wrapper do coletor de Emissões — LATAM — usado tanto para rodar
# manualmente quanto pelo agendamento automático via launchd.
#
# Depende de uma sessão já logada manualmente pelo usuário no
# perfil-latam-dedicado/ (ver coletor_emissoes_latam.py). Se a sessão
# expirar, a execução agendada falha com "sem oferta" pra tudo — o
# Painel de Saúde acusa isso como job atrasado/falho; a correção é logar
# de novo manualmente, não algo que este script resolva sozinho.
#
# Uso manual: ./rodar_coletor_latam.sh
set -euo pipefail

DIR_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR_SCRIPT"

source venv/bin/activate
python3 coletor_emissoes_latam.py
