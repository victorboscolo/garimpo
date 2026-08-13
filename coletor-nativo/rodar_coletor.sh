#!/bin/bash
# Wrapper do coletor nativo Livelo — usado tanto para rodar manualmente
# quanto pelo agendamento automático via launchd.
#
# Uso manual: ./rodar_coletor.sh
set -euo pipefail

DIR_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR_SCRIPT"

source venv/bin/activate
python3 coletor_livelo_nativo.py
