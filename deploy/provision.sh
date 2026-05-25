#!/usr/bin/env bash
# Idempotent Azure provisioning for Amos.
# Creates: Resource Group, ACR, Storage, App Insights, ACA Environment, two ACA apps.
# Re-running is safe — every "create" is preceded by a "show" check.

set -euo pipefail

# --- Config ---------------------------------------------------------------
REGION="${REGION:-eastus2}"
RG="${RG:-rg-amos-demo-eus2}"
ACR="${ACR:-cramosprodeus2}"           # ACR names: lowercase, alphanumeric, 5–50 chars, globally unique
STORAGE="${STORAGE:-stamosprodeus2}"   # Storage names: lowercase, alphanumeric, 3–24 chars, globally unique
APPINSIGHTS="${APPINSIGHTS:-ai-amos-prod-eus2}"
ACA_ENV="${ACA_ENV:-cae-amos-prod-eus2}"
ACA_PUBLIC="${ACA_PUBLIC:-ca-amos-public-eus2}"
ACA_INTERNAL="${ACA_INTERNAL:-ca-amos-internal-eus2}"

# --- Helpers --------------------------------------------------------------
log() { printf '\033[1;36m[provision]\033[0m %s\n' "$*"; }

exists_rg()      { az group show --name "$RG" >/dev/null 2>&1; }
exists_acr()     { az acr show --name "$ACR" --resource-group "$RG" >/dev/null 2>&1; }
exists_storage() { az storage account show --name "$STORAGE" --resource-group "$RG" >/dev/null 2>&1; }
exists_ai()      { az monitor app-insights component show --app "$APPINSIGHTS" --resource-group "$RG" >/dev/null 2>&1; }
exists_env()     { az containerapp env show --name "$ACA_ENV" --resource-group "$RG" >/dev/null 2>&1; }

# --- Resource Group -------------------------------------------------------
if exists_rg; then
  log "RG $RG exists"
else
  log "Creating RG $RG in $REGION"
  az group create --name "$RG" --location "$REGION" -o none
fi

# --- ACR ------------------------------------------------------------------
if exists_acr; then
  log "ACR $ACR exists"
else
  log "Creating ACR $ACR (Basic SKU)"
  az acr create --name "$ACR" --resource-group "$RG" --sku Basic --admin-enabled true -o none
fi

# --- Storage --------------------------------------------------------------
if exists_storage; then
  log "Storage $STORAGE exists"
else
  log "Creating Storage $STORAGE (Standard_LRS)"
  az storage account create --name "$STORAGE" --resource-group "$RG" \
    --location "$REGION" --sku Standard_LRS --kind StorageV2 --allow-blob-public-access false -o none
fi

# Ensure containers exist
STORAGE_KEY=$(az storage account keys list --resource-group "$RG" --account-name "$STORAGE" --query '[0].value' -o tsv)
for c in amos-wiki amos-conversations; do
  if az storage container show --name "$c" --account-name "$STORAGE" --account-key "$STORAGE_KEY" >/dev/null 2>&1; then
    log "Container $c exists"
  else
    log "Creating container $c"
    az storage container create --name "$c" --account-name "$STORAGE" --account-key "$STORAGE_KEY" --public-access off -o none
  fi
done
STORAGE_CONN=$(az storage account show-connection-string --resource-group "$RG" --name "$STORAGE" --query connectionString -o tsv)

# --- Application Insights -------------------------------------------------
if exists_ai; then
  log "App Insights $APPINSIGHTS exists"
else
  log "Creating App Insights $APPINSIGHTS"
  az monitor app-insights component create --app "$APPINSIGHTS" --resource-group "$RG" \
    --location "$REGION" --application-type web -o none
fi
AI_CONN=$(az monitor app-insights component show --app "$APPINSIGHTS" --resource-group "$RG" --query connectionString -o tsv)

# --- Container Apps Environment -------------------------------------------
if exists_env; then
  log "ACA Env $ACA_ENV exists"
else
  log "Creating ACA Env $ACA_ENV"
  az containerapp env create --name "$ACA_ENV" --resource-group "$RG" --location "$REGION" -o none
fi

# --- Echo back the values the deploy script needs -------------------------
cat <<EOF

=== Provisioned ===
REGION=$REGION
RG=$RG
ACR=$ACR
STORAGE=$STORAGE
APPINSIGHTS=$APPINSIGHTS
ACA_ENV=$ACA_ENV
ACA_PUBLIC=$ACA_PUBLIC
ACA_INTERNAL=$ACA_INTERNAL

# Save these (export and source in deploy.sh):
STORAGE_CONN="$STORAGE_CONN"
AI_CONN="$AI_CONN"
EOF
