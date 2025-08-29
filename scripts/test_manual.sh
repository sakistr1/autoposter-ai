#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8000}"
TOKEN="${TOKEN:?βάλε TOKEN: export TOKEN='...'}"
AUTHZ="Authorization: Bearer $TOKEN"

TITLE="${TITLE:-Κοντομάνικο μπλουζάκι}"
PRICE="${PRICE:-19,90€}"
IMG1="${IMG1:-$BASE/static/demo/outfit1.webp}"

BODY=$(jq -n \
  --arg t "$TITLE" \
  --arg p "$PRICE" \
  --arg i1 "$IMG1" \
  '{
    platform:"instagram",
    ratio:"4:5",
    title:$t,
    price:$p,
    images:[$i1],
    execute:true
  }')

echo "$BODY" | curl -sS -H "$AUTHZ" -H "Content-Type: application/json" \
  --data-binary @- "$BASE/manual/plan" | tee /tmp/manual_plan.json | jq

URL=$(jq -r '.committed_url // empty' /tmp/manual_plan.json)
[ -n "$URL" ] && (xdg-open "$URL" >/dev/null 2>&1 || gio open "$URL" >/dev/null 2>&1 || echo "$URL")
