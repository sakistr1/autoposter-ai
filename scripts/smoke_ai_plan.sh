#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8000}"
TOKEN="${TOKEN:?export TOKEN=...}"
AUTHZ="Authorization: Bearer $TOKEN"
JSON="Content-Type: application/json; charset=utf-8"

# 1) AI Plan
printf '%s' '{
  "product_url": "https://example.com/product/123",
  "platform": "instagram",
  "ratio": "4:5",
  "mode": "κανονικό"
}' | curl -s -X POST "$BASE/ai/plan" -H "$AUTHZ" -H "$JSON" --data-binary @- \
| tee /tmp/ai_plan.json | jq .

# 2) Render
jq -r '.preview_payload' /tmp/ai_plan.json > /tmp/preview_payload.json
curl -s -X POST "$BASE/previews/render" -H "$AUTHZ" -H "$JSON" \
  --data-binary @/tmp/preview_payload.json | tee /tmp/preview.json | jq .

# 3) Commit (JSON body με preview_id)
PREVIEW_ID=$(jq -r '.preview_id // .id // empty' /tmp/preview.json)
curl -s -X POST "$BASE/previews/commit" -H "$AUTHZ" -H "Content-Type: application/json" \
  -d "{\"preview_id\":\"$PREVIEW_ID\"}" | tee /tmp/commit.json | jq .

# 4) Ιστορικό + Credits
curl -s -H "$AUTHZ" "$BASE/previews/committed?limit=5&offset=0" | jq .
curl -s -H "$AUTHZ" "$BASE/me/credits" | jq .
