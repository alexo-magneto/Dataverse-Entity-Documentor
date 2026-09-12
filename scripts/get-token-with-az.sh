#!/usr/bin/env bash
# Alternative to an app registration: use your own signed-in Azure CLI identity.
#   az login
#   source scripts/get-token-with-az.sh https://yourorg.crm.dynamics.com
#   .venv/bin/python document_app.py --app "Sales Hub"
ENV_URL="${1:-${DATAVERSE_URL:-}}"
if [[ -z "$ENV_URL" ]]; then echo "usage: source $0 https://yourorg.crm.dynamics.com" >&2; return 1 2>/dev/null || exit 1; fi
export DATAVERSE_URL="$ENV_URL"
export DATAVERSE_ACCESS_TOKEN="$(az account get-access-token --resource "$ENV_URL" --query accessToken -o tsv)"
export DATAVERSE_AUTH_MODE=accessToken
echo "DATAVERSE_ACCESS_TOKEN exported for $ENV_URL (valid ~1 hour)."
