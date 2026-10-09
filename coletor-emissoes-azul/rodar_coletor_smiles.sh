#!/bin/bash
# Wrapper do coletor de Emissões — Smiles — usado tanto para rodar
# manualmente quanto pelo agendamento automático via launchd.
#
# Uso manual: ./rodar_coletor_smiles.sh
set -euo pipefail

# Segura o Mac acordado até o script terminar. Achado de 09/10: em repouso
# (pior na bateria), o macOS acorda sozinho por ~30s e volta a dormir por
# 2 a 5 minutos, em ciclo — a coleta rodava nesses intervalos, cada envio
# pego no meio ficava sem resposta, e uma rodada de 5 minutos chegou a
# levar 7 horas (26/09). Não altera nenhuma configuração do sistema: vale
# só enquanto este processo existir. Com a tampa fechada e fora da tomada
# o macOS dorme assim mesmo.
if [ -z "${GARIMPO_ACORDADO:-}" ]; then
  exec env GARIMPO_ACORDADO=1 /usr/bin/caffeinate -is "$0" "$@"
fi

DIR_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR_SCRIPT"

source venv/bin/activate
python3 coletor_emissoes_smiles.py
