#!/usr/bin/env bash
# Single-command refresh after adding documents.
# Ingests both variants, embeds both, builds both images, deploys both apps.
#
# Prereqs: .venv activated, OPENAI_API_KEY in env, provision.sh has run.

set -euo pipefail

log() { printf '\033[1;33m[refresh]\033[0m %s\n' "$*"; }

# --- 1. Wiki ingest (idempotent, --new-only) --------------------------------
log "Ingest: public manifest"
python -m ingest.ingest_agent \
  --manifest ingest/manifest_public.json \
  --data-root data/predictant \
  --wiki-out wiki-public \
  --new-only

log "Ingest: full manifest (auto-generated from data/predictant + data/academic)"
python -m ingest.ingest_agent \
  --manifest ingest/manifest_full.json \
  --data-root data/predictant \
  --wiki-out wiki-full \
  --new-only

# --- 2. RAG embedding (idempotent, --new-only) ------------------------------
log "Embed: public"
python -m rag.embed \
  --manifest ingest/manifest_public.json \
  --data-root data/predictant \
  --chroma-out chroma-public \
  --new-only

log "Embed: full"
python -m rag.embed \
  --manifest ingest/manifest_full.json \
  --data-root data/predictant \
  --chroma-out chroma-full \
  --new-only

# --- 3. Build + deploy both variants ----------------------------------------
log "Deploy: public"
bash deploy/deploy.sh public

log "Deploy: internal (full)"
bash deploy/deploy.sh full

log "All deployments refreshed."
