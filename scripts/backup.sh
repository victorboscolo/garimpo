#!/usr/bin/env bash
# Backup em camadas — GAR-1100 Cap. 7 / Decisão Arquitetural 067.
# Camada 1 (produção) já é o volume Docker. Este script cuida das
# Camadas 2 (HD externo, opcional) e 3 (Google Drive, sempre).
#
# Sem criptografia por decisão (18/08/2026): o banco não guarda credencial
# nem dado pessoal de terceiros, só inteligência de negócio (parceiros,
# pontuação, categorias) — o ganho não pareceu justificar a complexidade
# agora. Revisitar se isso for para um servidor externo algum dia.
set -uo pipefail

API="http://127.0.0.1:8000/api/v1"
AGORA=$(date "+%Y-%m-%d %H:%M:%S")
DATA=$(date +%Y%m%d_%H%M%S)
ARQUIVO="garimpo_${DATA}.sql.gz"

# Área de trabalho local só para o dump desta execução — nunca é o destino
# final. Existir sempre (não depende de HD nem de nuvem montados) evita o
# script falhar por causa de uma camada opcional.
STAGING="${GARIMPO_BACKUP_STAGING:-$HOME/GarimpoBackups/staging}"
mkdir -p "$STAGING"

# Camada 2, opcional: só grava se o ponto de montagem já existir DE VERDADE —
# nunca faz `mkdir -p` nele. Um HD desconectado não aparece em /Volumes; criar
# a pasta ali criaria silenciosamente um backup "externo" dentro do disco
# interno, dando falsa confiança de que existe uma cópia fora da máquina.
BACKUP_DIR_HD="${GARIMPO_BACKUP_HD:-/Volumes/BackupGarimpo}/postgres"

# Camada 3: pasta sincronizada pelo Google Drive para computador. O caminho
# muda por conta com as versões atuais do app (não é mais `~/Google Drive`) —
# por isso é sempre conferido, nunca criado, no diretório pai.
BACKUP_DIR_NUVEM_BASE="${GARIMPO_BACKUP_NUVEM:-$HOME/Library/CloudStorage/GoogleDrive-victorboscolo@gmail.com/Meu Drive}"
BACKUP_DIR_NUVEM="${BACKUP_DIR_NUVEM_BASE}/GarimpoBackups/postgres"

# Quantos backups manter na nuvem — o dump é pequeno (poucas dezenas de MB),
# mas sem limite a pasta cresceria pra sempre. 30 cobre um mês de histórico.
RETER_NA_NUVEM=30

echo "===================================================================="
echo "[$AGORA] Iniciando backup"

reportar_execucao() {
  # Nunca deve derrubar o script: se a API estiver fora do ar, é o próprio
  # Painel de Saúde que vai acusar isso pela ausência de execução recente.
  curl -s --max-time 10 -X POST "$API/execucoes" \
    -H "Content-Type: application/json" \
    -d "$1" > /dev/null 2>&1 || true
}

echo "[$(date)] Gerando dump do Postgres..."
if ! docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-garimpo}" "${POSTGRES_DB:-garimpo}" \
    | gzip > "${STAGING}/${ARQUIVO}"; then
  echo "[$(date)] ERRO: pg_dump falhou."
  reportar_execucao '{"job":"backup","status":"FALHA","erro":"pg_dump falhou"}'
  exit 1
fi

HD_OK=0
if [ -d "$(dirname "$BACKUP_DIR_HD")" ]; then
  mkdir -p "$BACKUP_DIR_HD"
  if cp "${STAGING}/${ARQUIVO}" "${BACKUP_DIR_HD}/${ARQUIVO}"; then
    echo "[$(date)] Camada 2 (HD externo): ${BACKUP_DIR_HD}/${ARQUIVO}"
    HD_OK=1
  else
    echo "[$(date)] AVISO: HD externo presente, mas a cópia falhou."
  fi
else
  echo "[$(date)] Camada 2 (HD externo) pulada — não está conectado."
fi

if [ ! -d "$BACKUP_DIR_NUVEM_BASE" ]; then
  echo "[$(date)] ERRO: pasta do Google Drive não encontrada em '$BACKUP_DIR_NUVEM_BASE'."
  echo "         O app está instalado, logado e sincronizando?"
  reportar_execucao "{\"job\":\"backup\",\"status\":\"FALHA\",\"erro\":\"pasta do Google Drive nao encontrada\"}"
  exit 1
fi

mkdir -p "$BACKUP_DIR_NUVEM"
if ! cp "${STAGING}/${ARQUIVO}" "${BACKUP_DIR_NUVEM}/${ARQUIVO}"; then
  echo "[$(date)] ERRO: cópia para o Google Drive falhou."
  reportar_execucao '{"job":"backup","status":"FALHA","erro":"copia para o Google Drive falhou"}'
  exit 1
fi
echo "[$(date)] Camada 3 (Google Drive): ${BACKUP_DIR_NUVEM}/${ARQUIVO}"

# Retenção: mantém os N mais recentes, apaga o resto.
ls -t "${BACKUP_DIR_NUVEM}"/garimpo_*.sql.gz 2>/dev/null | tail -n +$((RETER_NA_NUVEM + 1)) | xargs -r rm -f

rm -f "${STAGING}/${ARQUIVO}"

echo "[$(date)] Backup concluído: ${ARQUIVO}"
[ $HD_OK -eq 0 ] && echo "[$(date)] (camada HD pulada nesta execução, nuvem está ok)"
reportar_execucao '{"job":"backup","status":"SUCESSO"}'
