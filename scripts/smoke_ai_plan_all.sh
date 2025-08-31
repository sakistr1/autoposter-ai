#!/bin/bash
set -euo pipefail

# -------- Config --------
BASE="${BASE:-http://127.0.0.1:8000}"
HDR_JSON="Content-Type: application/json"

# AUTH header: είτε από AUTHZ, είτε από TOKEN
if [[ -n "${AUTHZ:-}" ]]; then
  HDR_AUTH="$AUTHZ"
else
  : "${TOKEN:?Set TOKEN env var or AUTHZ header}"
  HDR_AUTH="Authorization: Bearer ${TOKEN}"
fi

# Απλή helper για καθαρή κλήση (χωρίς να περνάμε ποτέ echo -> jq)
call_json() {
  local method="$1" url="$2" data="${3:-}"
  if [[ -n "$data" ]]; then
    curl -s -X "$method" "$url" -H "$HDR_AUTH" -H "$HDR_JSON" --data-binary "$data"
  else
    curl -s -X "$method" "$url" -H "$HDR_AUTH" -H "$HDR_JSON"
  fi
}

for R in "1:1" "4:5" "9:16"; do
  echo "========== Ratio $R =========="

  # 1) AI plan μόνο του
  call_json POST "$BASE/ai/plan" "{\"platform\":\"instagram\",\"ratio\":\"$R\"}" \
    | jq '.caption, .preview_payload.ratio'

  # 2) Preview με use_ai_plan (χρησιμοποιούμε inline JSON ώστε να επεκταθεί το $R
  PAYLOAD=$(cat <<JSON
{
  "template_id": 12,
  "image_url": "http://127.0.0.1:8000/static/uploads/demo.jpg",
  "platform": "instagram",
  "ratio": "$R",
  "mode": "normal",
  "use_renderer": true,
  "use_ai_plan": true,
  "watermark": true,
  "return_absolute_url": true
}
JSON
)
  call_json POST "$BASE/tengine/preview" "$PAYLOAD" \
    | tee /tmp/_prev.json | jq '.preview_url, .caption, .meta'

  # 3) Commit
  PREV_ID=$(jq -r '.preview_id // .id // empty' /tmp/_prev.json)
  call_json POST "$BASE/tengine/commit" "{\"preview_id\":\"$PREV_ID\"}" \
    | jq '.committed_url, .remaining_credits'

  echo
done
