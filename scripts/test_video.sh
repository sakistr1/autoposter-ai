#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8000}"
TOKEN="${TOKEN:?βάλε TOKEN: export TOKEN='...'}"
AUTHZ="Authorization: Bearer $TOKEN"

BODY=$(jq -n '{
  platform:"instagram",
  mode:"video",
  images:["/static/demo/outfit1.webp","/static/demo/outfit2.webp"],
  fps: 24,
  duration_sec: 8
}')
echo "$BODY" | curl -sS -H "$AUTHZ" -H "Content-Type: application/json" \
  --data-binary @- "$BASE/previews/render" | tee /tmp/r_vid.json | jq

PREV=$(jq -r '.preview_url // .url // .path // empty' /tmp/r_vid.json)
jq -n --arg u "$PREV" '{preview_url:$u}' \
| curl -sS -H "$AUTHZ" -H "Content-Type: application/json" \
  --data-binary @- "$BASE/previews/commit?wait=true&timeout=60" | tee /tmp/c_vid.json | jq

URL=$(jq -r '.absolute_url // .url // empty' /tmp/c_vid.json)
[ -n "$URL" ] && (xdg-open "$URL" >/dev/null 2>&1 || gio open "$URL" >/dev/null 2>&1 || true) &
