#!/usr/bin/env bash
# Build and deploy a single variant ("public" or "full") to its Azure Container App.
# Assumes provision.sh has run and wiki-<variant>/ + chroma-<variant>/ exist.
#
# Usage: ./deploy.sh public        # builds amos-public, deploys to ca-amos-public-eus2
#        ./deploy.sh full          # builds amos-full,   deploys to ca-amos-internal-eus2

set -euo pipefail

VARIANT="${1:-}"
if [[ "$VARIANT" != "public" && "$VARIANT" != "full" ]]; then
  echo "usage: $0 {public|full}" >&2
  exit 1
fi

REGION="${REGION:-eastus2}"
RG="${RG:-rg-amos-demo-eus2}"
ACR="${ACR:-cramosprodeus2}"
ACA_ENV="${ACA_ENV:-cae-amos-prod-eus2}"

if [[ "$VARIANT" == "public" ]]; then
  IMAGE="amos-public"
  APP_NAME="${ACA_PUBLIC:-ca-amos-public-eus2}"
  ENABLE_PASSWORD="false"
else
  IMAGE="amos-full"
  APP_NAME="${ACA_INTERNAL:-ca-amos-internal-eus2}"
  ENABLE_PASSWORD="true"
fi

TAG="$(date -u +%Y%m%d%H%M%S)"
FULL_IMAGE="${ACR}.azurecr.io/${IMAGE}:${TAG}"

log() { printf '\033[1;32m[deploy:%s]\033[0m %s\n' "$VARIANT" "$*"; }

# Required env vars (set before running):
: "${OPENAI_API_KEY:?OPENAI_API_KEY must be set in env}"
: "${STORAGE_CONN:?STORAGE_CONN must be set in env (from provision.sh output)}"
: "${AI_CONN:?AI_CONN must be set in env (from provision.sh output)}"
if [[ "$VARIANT" == "full" ]]; then
  : "${AMOS_PASSWORD:?AMOS_PASSWORD must be set for the internal deployment}"
fi
: "${RATE_LIMIT_SALT:?RATE_LIMIT_SALT must be set (any random string)}"

# Sanity: variant artifacts must exist locally before we ship them into the image.
[[ -d "wiki-${VARIANT}" ]] || { echo "wiki-${VARIANT}/ missing — run ingest first" >&2; exit 1; }
[[ -d "chroma-${VARIANT}" ]] || { echo "chroma-${VARIANT}/ missing — run embed first" >&2; exit 1; }

log "Server-side ACR build: $FULL_IMAGE (VARIANT=$VARIANT)"
az acr build \
  --registry "$ACR" \
  --image "${IMAGE}:${TAG}" \
  --image "${IMAGE}:latest" \
  --build-arg VARIANT="$VARIANT" \
  --file Dockerfile \
  .

# Does the app already exist? If yes, update; if not, create.
if az containerapp show --name "$APP_NAME" --resource-group "$RG" >/dev/null 2>&1; then
  log "Updating existing app $APP_NAME"
  az containerapp update \
    --name "$APP_NAME" \
    --resource-group "$RG" \
    --image "$FULL_IMAGE" \
    --set-env-vars \
      "CORPUS_VARIANT=$VARIANT" \
      "ENABLE_PASSWORD_GATE=$ENABLE_PASSWORD" \
      "BUDGET_MONTHLY_USD=15" \
      "BUDGET_HARD_CAP_USD=20" \
      "APPLICATIONINSIGHTS_CONNECTION_STRING=secretref:appinsights-conn" \
      "AZURE_STORAGE_CONNECTION_STRING=secretref:storage-conn" \
      "OPENAI_API_KEY=secretref:openai-key" \
      "RATE_LIMIT_SALT=secretref:rate-limit-salt" \
      "AMOS_PASSWORD=secretref:amos-password" \
    -o none
else
  log "Creating new app $APP_NAME"
  ACR_USER=$(az acr credential show --name "$ACR" --query username -o tsv)
  ACR_PWD=$(az acr credential show --name "$ACR" --query 'passwords[0].value' -o tsv)
  az containerapp create \
    --name "$APP_NAME" \
    --resource-group "$RG" \
    --environment "$ACA_ENV" \
    --image "$FULL_IMAGE" \
    --target-port 8000 \
    --ingress external \
    --transport http \
    --min-replicas 1 \
    --max-replicas 2 \
    --cpu 0.5 \
    --memory 1.0Gi \
    --registry-server "${ACR}.azurecr.io" \
    --registry-username "$ACR_USER" \
    --registry-password "$ACR_PWD" \
    --secrets \
      "openai-key=$OPENAI_API_KEY" \
      "storage-conn=$STORAGE_CONN" \
      "appinsights-conn=$AI_CONN" \
      "rate-limit-salt=$RATE_LIMIT_SALT" \
      "amos-password=${AMOS_PASSWORD:-unused}" \
    --env-vars \
      "CORPUS_VARIANT=$VARIANT" \
      "ENABLE_PASSWORD_GATE=$ENABLE_PASSWORD" \
      "BUDGET_MONTHLY_USD=15" \
      "BUDGET_HARD_CAP_USD=20" \
      "APPLICATIONINSIGHTS_CONNECTION_STRING=secretref:appinsights-conn" \
      "AZURE_STORAGE_CONNECTION_STRING=secretref:storage-conn" \
      "OPENAI_API_KEY=secretref:openai-key" \
      "RATE_LIMIT_SALT=secretref:rate-limit-salt" \
      "AMOS_PASSWORD=secretref:amos-password" \
    -o none
fi

FQDN=$(az containerapp show --name "$APP_NAME" --resource-group "$RG" --query 'properties.configuration.ingress.fqdn' -o tsv)
log "Deployed → https://$FQDN"
