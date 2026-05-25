#!/usr/bin/env bash
# Register Azure MCP and GitHub MCP servers with Claude Code.
# Run this once, after `claude` CLI is on PATH and Docker Desktop is running.
# After this, future Claude Code sessions on this repo can interact with Azure
# and GitHub via rich MCP tools instead of bash CLI shellouts.
#
# Prereqs:
#   - Docker Desktop running (`docker ps` succeeds)
#   - `az` already authenticated (Azure MCP uses ambient `az` credentials)
#   - A fine-grained GitHub PAT scoped to ashtad63/amos-bolt-iq with:
#     Contents (R/W), Metadata (R), Pull requests (R/W)
#     Export it as $GITHUB_PERSONAL_ACCESS_TOKEN before running this script.

set -euo pipefail

if ! command -v claude >/dev/null 2>&1; then
  echo "claude CLI not on PATH. Install Claude Code first." >&2
  exit 1
fi

# 1. Azure MCP — uses ambient `az login` credentials, no token needed.
echo "Registering Azure MCP server..."
claude mcp add azure -- npx -y @azure/mcp@latest server start

# 2. GitHub MCP — official Docker container, requires PAT.
if [[ -z "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" ]]; then
  echo "Set GITHUB_PERSONAL_ACCESS_TOKEN env var first." >&2
  exit 1
fi
echo "Registering GitHub MCP server..."
claude mcp add github \
  -e GITHUB_PERSONAL_ACCESS_TOKEN="$GITHUB_PERSONAL_ACCESS_TOKEN" \
  -- docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN ghcr.io/github/github-mcp-server

echo ""
echo "Verify:"
echo "  claude mcp list"
