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

# Chave fixa de coletores/scripts (18/09) — o painel agora exige
# autenticação em toda rota, e um script não tem sessão de usuário.
GARIMPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COLETOR_API_KEY=$(grep -E '^COLETOR_API_KEY=' "$GARIMPO_ROOT/.env" 2>/dev/null | cut -d '=' -f2-)

# A partir de 18/09 a nuvem (Render), não mais o Docker local.
API_BASE=$(grep -E '^API_BASE_URL=' "$GARIMPO_ROOT/.env" 2>/dev/null | cut -d '=' -f2-)
API_BASE="${API_BASE:-http://127.0.0.1:8000}"
API="$API_BASE/api/v1"
AGORA=$(date "+%Y-%m-%d %H:%M:%S")

echo "===================================================================="
echo "[$AGORA] Iniciando recalibração"

# O Render (plano grátis) dorme depois de 15 min sem acesso — a primeira
# requisição do dia pode demorar até ~1 min pra responder (cold start).
# Sem isso, o teste de saúde abaixo (10s de timeout) falsamente acusaria
# a API como fora do ar.
for tentativa in 1 2 3 4 5; do
  curl -sf -o /dev/null --max-time 20 "$API_BASE/health" && break
  echo "Aquecendo o backend (tentativa $tentativa/5)..."
  sleep 10
done

if ! curl -sf -o /dev/null --max-time 10 -H "X-API-Key: $COLETOR_API_KEY" "$API/promocoes?status=PENDENTE"; then
  echo "[$AGORA] ERRO: a API não respondeu. Ela está no ar?"
  echo "         Nada foi reprocessado — as classificações seguem as de antes."
  exit 1
fi

echo "Reprocessando..."
RESULTADO=$(curl -sf --max-time 600 -X POST -H "X-API-Key: $COLETOR_API_KEY" "$API/promocoes/reclassificar-todas")
if [ $? -ne 0 ]; then
  echo "[$AGORA] ERRO: reclassificar-todas falhou."
  curl -s --max-time 10 -X POST "$API/execucoes" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $COLETOR_API_KEY" \
    -d '{"job":"recalibracao","status":"FALHA","erro":"reclassificar-todas falhou ou expirou"}' > /dev/null
  exit 1
fi
echo "Resultado: $RESULTADO"

# Extração simples por regex, no mesmo espírito do case abaixo — não é um
# parser de JSON de verdade, só pega os dois números que interessam pro painel.
PROCESSADAS=$(echo "$RESULTADO" | grep -o '"processadas":[0-9]*' | grep -o '[0-9]*')
ERROS=$(echo "$RESULTADO" | grep -o '"erros":[0-9]*' | grep -o '[0-9]*')
curl -s --max-time 10 -X POST "$API/execucoes" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $COLETOR_API_KEY" \
  -d "{\"job\":\"recalibracao\",\"status\":\"SUCESSO\",\"criadas\":${PROCESSADAS:-null},\"falhas\":${ERROS:-null}}" > /dev/null

echo "Conferindo divergências com o que já foi publicado..."
DIVERGENCIAS=$(curl -s --max-time 30 -H "X-API-Key: $COLETOR_API_KEY" "$API/publicacoes/divergencias")
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
