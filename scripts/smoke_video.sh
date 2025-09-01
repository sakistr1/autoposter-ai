#!/usr/bin/env bash
set -euo pipefail

: "${BASE:?set BASE}"
: "${AUTHZ:?set AUTHZ}"

OUT="smoke_video.csv"
LOG="smoke_video.log"
: > "$LOG"

echo "status,mode,mp4_url,poster_url,commit_status,committed_url,err" > "$OUT"

read -r -d '' PAYLOAD <<'JSON'
{
  "mode": "video",
  "fps": 30,
  "duration_sec": 12,
  "images": [
    {"image": "/static/demo/img_1_1.jpg"},
    {"image": "/static/demo/img_4_5.jpg"}
  ]
}
JSON

RESP=$(curl -sS -X POST "$BASE/previews/render" \
  -H "$AUTHZ" -H "Content-Type: application/json" \
  -d "$PAYLOAD" || true)

printf '%s\n' "$RESP" >> "$LOG"

STATUS=$(jq -r '.status // "ERR"' <<<"$RESP")
MODE=$(jq -r '.mode // ""' <<<"$RESP")
MP4=$(jq -r '(.mp4_url // .preview_url // "")' <<<"$RESP")
POSTER=$(jq -r '(.poster_url // "")' <<<"$RESP")

if [[ "$STATUS" != "ok" || -z "$MP4" ]]; then
  echo "$STATUS,$MODE,,,ERR,,render failed" >> "$OUT"
  exit 0
fi

CRESP=$(curl -sS -X POST "$BASE/previews/commit" \
  -H "$AUTHZ" -H "Content-Type: application/json" \
  -d "{\"preview_url\":\"$MP4\"}" || true)

printf '%s\n' "$CRESP" >> "$LOG"
CSTAT=$(jq -r '.status // "ERR"' <<<"$CRESP")
CURL=$(jq -r '.committed_url // ""' <<<"$CRESP")

echo "$STATUS,$MODE,$MP4,$POSTER,$CSTAT,$CURL," >> "$OUT"
