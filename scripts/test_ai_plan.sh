#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000}"
TOKEN="${TOKEN:?βάλε TOKEN: export TOKEN='...'}"
AUTHZ="Authorization: Bearer $TOKEN"

PRODUCT_URL="${1:-https://example.com/your-product-page}"
PLATFORM="${PLATFORM:-instagram}"
EXECUTE="${EXECUTE:-true}"

BODY=$(jq -n \
  --arg url "$PRODUCT_URL" \
  --arg platform "$PLATFORM" \
  --argjson execute $EXECUTE \
  '{product_url:$url, platform:$platform, execute:$execute}')

echo "$BODY" | curl -sS -H "$AUTHZ" -H "Content-Type: application/json" \
  --data-binary @- "$BASE/ai/plan" | tee /tmp/ai_plan.json | jq

URL=$(jq -r '.committed_url // empty' /tmp/ai_plan.json)
if [ -n "$URL" ]; then
  echo "Committed URL: $URL"
  if command -v xdg-open >/dev/null; then xdg-open "$URL" & fi
  if command -v gio >/dev/null; then gio open "$URL" & fi
fi
