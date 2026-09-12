#!/usr/bin/env bash
# Uses the Power Platform CLI (pac) to help fill config.json:
#   1. authenticate (interactive, or with the app registration in config.json)
#   2. list environments so you can copy the environment URL
#   3. list model-driven apps via the Web API through pac's stored auth is not supported,
#      so the app list is produced by this utility (--list-apps) once config.json is filled.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v pac >/dev/null 2>&1; then
  echo "pac CLI not found. Install: dotnet tool install --global Microsoft.PowerApps.CLI.Tool" >&2
  exit 1
fi

ENV_URL="${DATAVERSE_URL:-}"
if [[ -z "$ENV_URL" && -f config.json ]]; then
  ENV_URL=$(python3 -c "import json;print(json.load(open('config.json')).get('environmentUrl',''))")
fi

echo "== pac auth profiles =="
pac auth list || true

if [[ -n "${DATAVERSE_CLIENT_ID:-}" && -n "${DATAVERSE_CLIENT_SECRET:-}" && -n "${DATAVERSE_TENANT_ID:-}" ]]; then
  echo "== creating app-only pac auth profile =="
  pac auth create --name app-documentor --applicationId "$DATAVERSE_CLIENT_ID" --clientSecret "$DATAVERSE_CLIENT_SECRET" --tenant "$DATAVERSE_TENANT_ID" ${ENV_URL:+--environment "$ENV_URL"}
else
  echo "== creating interactive pac auth profile (browser sign-in) =="
  pac auth create --name app-documentor ${ENV_URL:+--environment "$ENV_URL"}
fi

echo "== environments (copy the Environment URL into config.json -> environmentUrl) =="
pac org list

echo "== current org =="
pac org who || true

echo
echo "Next: fill config.json, then run:  .venv/bin/python document_app.py --list-apps"
