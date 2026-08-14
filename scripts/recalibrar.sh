#!/bin/bash
# Reprocessa todas as promoções com a versão atual do motor.
#
# Existe porque a base de comparação envelhece: a cada semana entram ~100
# ofertas novas, parceiros ganham histórico próprio e a distribuição do mercado
# muda. Uma classificação feita quando havia 30 aprovadas foi julgada contra
# outro mercado — reprocessar é o que mantém todas na mesma régua.
#
# Roda pelo launchd (ver com.garimpo.recalibrar.plist), e não pelo scheduler do
# Docker: aquele perde execuções quando o Mac dorme, enquanto o launchd as
# recupera ao acordar.
#
# Ao final consulta as divergências. Reprocessar pode mudar a categoria de algo
# já publicado, e o Telegram não tem como despublicar — registrar no log é o que
# permite descobrir isso sem depender de abrir o painel.

set -u

API="http://127.0.0.1:8000/api/v1"
AGORA=$(date "+%Y-%m-%d %H:%M:%S")

echo "===================================================================="
echo "[$AGORA] Iniciando recalibração"

if ! curl -sf -o /dev/null --max-time 10 "$API/promocoes?status=PENDENTE"; then
  echo "[$AGORA] ERRO: a API não respondeu. O Docker está no ar?"
  echo "         Nada foi reprocessado — as classificações seguem as de antes."
  exit 1
fi

echo "Reprocessando..."
RESULTADO=$(curl -s --max-time 600 -X POST "$API/promocoes/reclassificar-todas")
echo "Resultado: $RESULTADO"

echo "Conferindo divergências com o que já foi publicado..."
DIVERGENCIAS=$(curl -s --max-time 30 "$API/publicacoes/divergencias")
echo "Divergências: $DIVERGENCIAS"

case "$DIVERGENCIAS" in
  *'"total":0'*)
    echo "Nenhuma publicação ficou desatualizada."
    ;;
  *)
    echo "ATENÇÃO: há publicações cuja categoria mudou desde o envio."
    echo "         O canal segue mostrando a avaliação antiga."
    echo "         Confira na aba Publicar do painel."
    ;;
esac

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Recalibração concluída"
