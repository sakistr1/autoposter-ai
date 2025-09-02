#!/usr/bin/env bash
set -euo pipefail

# --- config ---
BASE="${BASE:-http://127.0.0.1:8000}"
: "${TOKEN:?Set TOKEN env first}"
AUTHZ="Authorization: Bearer ${TOKEN}"

# Είσοδοι (προεπιλογές)
IMG1="${1:-/static/demo/img_1_1.jpg}"
IMG2="${2:-/static/demo/img_4_5.jpg}"
DUR="${3:-6}"         # συνολικά δευτερόλεπτα video
FPS="${FPS:-30}"      # frames per second

OUTCSV="smoke_video.csv"
TMP_JSON="$(mktemp)"

# Header CSV αν δεν υπάρχει
if [[ ! -f "$OUTCSV" ]]; then
  echo "status,mode,mp4_url,poster_url,commit_status,committed_url,err" > "$OUTCSV"
fi

# --- render ---
VID=$(
  curl -s -X POST "$BASE/previews/render" \
    -H "$AUTHZ" -H "Content-Type: application/json" \
    -d "{
      \"mode\": \"video\",
      \"fps\": ${FPS},
      \"duration_sec\": ${DUR},
      \"images\": [
        {\"image\": \"${IMG1}\"},
        {\"image\": \"${IMG2}\"}
      ]
    }"
)

echo "$VID" > "$TMP_JSON"

STATUS=$(jq -r '.status // "ERR"' "$TMP_JSON")
MODE=$(jq -r '.mode // ""' "$TMP_JSON")
MP4=$(jq -r '.preview_url // ""' "$TMP_JSON")
POSTER=$(jq -r '.poster_url // ""' "$TMP_JSON")

# Αν κόπηκε το render
if [[ "$STATUS" != "ok" || -z "$MP4" ]]; then
  ERR=$(jq -r '.detail? // .error? // "render failed"' "$TMP_JSON")
  echo "$STATUS,$MODE,,,$(printf "ERR"),,${ERR//,/;}" >> "$OUTCSV"
  column -s, -t "$OUTCSV" | sed -n '1,20p'
  exit 1
fi

# --- commit ---
CMT=$(
  curl -s -X POST "$BASE/previews/commit" \
    -H "$AUTHZ" -H "Content-Type: application/json" \
    -d "{\"preview_url\":\"${MP4}\"}"
)

CSTAT=$(echo "$CMT" | jq -r '.status // .ok // "ERR"' | sed 's/true/ok/; s/false/ERR/')
CURL=$(echo "$CMT" | jq -r '.committed_url // .absolute_url // ""')
ERR=$(echo "$CMT" | jq -r '.detail? // .error? // ""')

# Γράψε γραμμή CSV
echo "ok,video,${MP4},${POSTER},${CSTAT},${CURL},${ERR//,/;}" >> "$OUTCSV"

# Εμφάνισε γρήγορο report
echo "== VIDEO =="
column -s, -t "$OUTCSV" | sed -n '1,20p'
