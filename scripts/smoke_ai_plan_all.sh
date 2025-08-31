#!/bin/bash
set -euo pipefail

# Defaults
BASE="${BASE:-http://127.0.0.1:8000}"
RATIOS="1:1,4:5,9:16"
IMAGE="http://127.0.0.1:8000/static/uploads/demo.jpg"
TEMPLATE_ID=12

usage() {
  cat <<USAGE
Usage: TOKEN=<jwt> $0 [--ratios "1:1,4:5"] [--image <url>] [--template <id>] [--base <url>]
Env:  TOKEN or AUTHZ (Authorization header). BASE/IMAGE/TEMPLATE_ID/RATIOS can also be set via env.
USAGE
}

# Parse flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --ratios)   RATIOS="$2"; shift 2;;
    --image)    IMAGE="$2"; shift 2;;
    --template) TEMPLATE_ID="$2"; shift 2;;
    --base)     BASE="$2"; shift 2;;
    -h|--help)  usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 2;;
  esac
done

HDR_JSON="Content-Type: application/json"
if [[ -n "${AUTHZ:-}" ]]; then
  HDR_AUTH="$AUTHZ"
else
  : "${TOKEN:?Set TOKEN env var or AUTHZ header}"
  HDR_AUTH="Authorization: Bearer ${TOKEN}"
fi

call_json() {
  local method="$1" url="$2" data="${3:-}"
  if [[ -n "$data" ]]; then
    curl -s -X "$method" "$url" -H "$HDR_AUTH" -H "$HDR_JSON" --data-binary "$data"
  else
    curl -s -X "$method" "$url" -H "$HDR_AUTH" -H "$HDR_JSON"
  fi
}

IFS=',' read -r -a RAT_ARR <<< "$RATIOS"

for R in "${RAT_ARR[@]}"; do
  R=$(echo "$R" | xargs)  # trim
  echo "========== Ratio $R =========="

  # 1) AI plan μόνο του
  call_json POST "$BASE/ai/plan" "{\"platform\":\"instagram\",\"ratio\":\"$R\"}" \
    | jq '.caption, .preview_payload.ratio'

  # 2) Preview με use_ai_plan
  PAYLOAD=$(cat <<JSON
{
  "template_id": ${TEMPLATE_ID},
  "image_url": "${IMAGE}",
  "platform": "instagram",
  "ratio": "${R}",
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
