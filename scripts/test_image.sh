#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8000}"
TOKEN="${TOKEN:?βάλε TOKEN: export TOKEN='...'}"
AUTHZ="Authorization: Bearer $TOKEN"

IMG="${1:-/static/demo/outfit1.webp}"
BODY=$(jq -n --arg img "$IMG" '{platform:"instagram", mode:"normal", image_url:$img}')
echo "$BODY" | curl -sS -H "$AUTHZ" -H "Content-Type: application/json" \
  --data-binary @- "$BASE/previews/render" | tee /tmp/r_img.json | jq

PREV=$(jq -r '.preview_url // .url // .path // empty' /tmp/r_img.json)
jq -n --arg u "$PREV" '{preview_url:$u}' \
| curl -sS -H "$AUTHZ" -H "Content-Type: application/json" \
  --data-binary @- "$BASE/previews/commit?wait=true&timeout=60" | tee /tmp/c_img.json | jq

URL=$(jq -r '.absolute_url // .url // empty' /tmp/c_img.json)
[ -n "$URL" ] && (xdg-open "$URL" >/dev/null 2>&1 || gio open "$URL" >/dev/null 2>&1 || true) &
