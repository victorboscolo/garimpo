#!/usr/bin/env bash
# Backup em camadas — GAR-1100 Cap. 7 / Decisão Arquitetural 067.
# Camada 1 (produção) já é o volume Docker. Este script cuida das
# Camadas 2 (HD externo) e 3 (nuvem criptografada).
set -euo pipefail

DATA=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR_LOCAL="${GARIMPO_BACKUP_HD:-/Volumes/BackupGarimpo}/postgres"
BACKUP_DIR_NUVEM="${GARIMPO_BACKUP_NUVEM:-$HOME/Google Drive/GarimpoBackups}/postgres"
ARQUIVO="garimpo_${DATA}.sql.gz"

mkdir -p "$BACKUP_DIR_LOCAL" "$BACKUP_DIR_NUVEM"

echo "[$(date)] Gerando dump do Postgres..."
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-garimpo}" "${POSTGRES_DB:-garimpo}" \
  | gzip > "${BACKUP_DIR_LOCAL}/${ARQUIVO}"

echo "[$(date)] Copiando para camada externa (nuvem)..."
# TODO: adicionar criptografia (ex.: gpg --symmetric) antes de copiar para a nuvem.
cp "${BACKUP_DIR_LOCAL}/${ARQUIVO}" "${BACKUP_DIR_NUVEM}/${ARQUIVO}"

echo "[$(date)] Backup concluído: ${ARQUIVO}"
echo "  Camada 2 (HD externo): ${BACKUP_DIR_LOCAL}/${ARQUIVO}"
echo "  Camada 3 (nuvem):      ${BACKUP_DIR_NUVEM}/${ARQUIVO}"

# TODO: registrar status (sucesso/falha + timestamp) em local lido pelo
# futuro Painel de Saúde (cartão "🟢 Backup" mencionado na auditoria original).
