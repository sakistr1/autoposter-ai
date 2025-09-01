#!/usr/bin/env bash
set -euo pipefail

BASE=${BASE:-http://127.0.0.1:8000}
TOKEN=${TOKEN:?TOKEN env required}
AUTHZ="Authorization: Bearer $TOKEN"
JSON="Content-Type: application/json"
OUT="${1:-smoke_renderer_results.csv}"

echo "ratio,caption,preview_url,committed_url,width,height,credits" > "$OUT"

for R in "1:1" "4:5" "9:16"; do
  cat > /tmp/p_smoke.json <<JSON
{
  "template_id": 12,
  "image_url": "$BASE/static/uploads/demo.jpg",
  "platform": "instagram",
  "ratio": "$R",
  "mode": "normal",
  "use_renderer": true,
  "use_ai_plan": true,
  "watermark": true,
  "return_absolute_url": true
}
JSON

  PLAN=$(curl -s -X POST "$BASE/ai/plan" -H "$AUTHZ" -H "$JSON" \
         -d "{\"platform\":\"instagram\",\"ratio\":\"$R\"}")
  CAP=$(jq -r '.caption' <<<"$PLAN")
  MAP=$(jq -c '.preview_payload.mapping' <<<"$PLAN")

  echo "$(jq -c --argjson m "$MAP" '.mapping=$m' /tmp/p_smoke.json)" > /tmp/p_smoke.json

  PREV=$(curl -s -X POST "$BASE/tengine/preview" -H "$AUTHZ" -H "$JSON" \
         --data-binary @/tmp/p_smoke.json)
  PURL=$(jq -r '.preview_url' <<<"$PREV")
  PID=$(jq -r '.preview_id // .id' <<<"$PREV")
  WIDTH=$(jq -r '.meta.width // empty' <<<"$PREV")
  HEIGHT=$(jq -r '.meta.height // empty' <<<"$PREV")

  COM=$(curl -s -X POST "$BASE/tengine/commit" -H "$AUTHZ" -H "$JSON" \
        -d "{\"preview_id\":\"$PID\"}")
  CURL=$(jq -r '.committed_url' <<<"$COM")
  CRED=$(jq -r '.remaining_credits' <<<"$COM")

  echo "\"$R\",\"$CAP\",\"$PURL\",\"$CURL\",$WIDTH,$HEIGHT,$CRED" >> "$OUT"
  echo "✔ $R → $CURL"
done

echo "CSV → $OUT"
