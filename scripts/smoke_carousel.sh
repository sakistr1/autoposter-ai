#!/usr/bin/env bash
set -euo pipefail

: "${BASE:?set BASE}"
: "${AUTHZ:?set AUTHZ}"

OUT="smoke_carousel.csv"
LOG="smoke_carousel.log"
: > "$LOG"

echo "status,frame_count,sheet_url,first_frame_url,commit_status,committed_url,err" > "$OUT"

read -r -d '' PAYLOAD <<'JSON'
{
  "mode": "carousel",
  "images": [
    {"image": "/static/demo/img_1_1.jpg"},
    {"image": "/static/demo/img_4_5.jpg"},
    {"image": "/static/demo/img_9_16.jpg"}
  ]
}
JSON

RESP=$(curl -sS -X POST "$BASE/previews/render" \
  -H "$AUTHZ" -H "Content-Type: application/json" \
  -d "$PAYLOAD" || true)

printf '%s\n' "$RESP" >> "$LOG"

STATUS=$(jq -r '.status // "ERR"' <<<"$RESP")
# Διάβασε sheet/preview URL (διαφορετικά backends μπορεί να δίνουν άλλα κλειδιά)
SHEET=$(jq -r '(.sheet_url // .preview_url // "")' <<<"$RESP")
# frames: προτίμησε frames array, αλλιώς count
COUNT=$(jq -r '((.frames|length) // .count // 0)' <<<"$RESP")
FIRST=$(jq -r '(.frames[0] // "")' <<<"$RESP")

if [[ "$STATUS" != "ok" || -z "$SHEET" ]]; then
  echo "$STATUS,0,,,ERR,,render failed" >> "$OUT"
  exit 0
fi

CRESP=$(curl -sS -X POST "$BASE/previews/commit" \
  -H "$AUTHZ" -H "Content-Type: application/json" \
  -d "{\"preview_url\":\"$SHEET\"}" || true)

printf '%s\n' "$CRESP" >> "$LOG"
CSTAT=$(jq -r '.status // "ERR"' <<<"$CRESP")
CURL=$(jq -r '.committed_url // ""' <<<"$CRESP")

echo "$STATUS,$COUNT,$SHEET,$FIRST,$CSTAT,$CURL," >> "$OUT"
