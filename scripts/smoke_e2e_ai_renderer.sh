#!/usr/bin/env bash
set -euo pipefail

: "${BASE:?missing BASE}"
: "${AUTHZ:?missing AUTHZ}"
: "${JSON:?missing JSON}"

OUT_CSV="smoke_e2e_results.csv"
TMP_REQ="/tmp/p_e2e.json"
DEMO_URL="$BASE/static/uploads/demo.jpg"

echo "ratio,caption,preview_url,overlay_applied,width,height,committed_url,remaining_credits" > "$OUT_CSV"

run_one() {
  local R="$1"

  # 1) Ζήτα AI plan (caption + mapping)
  CAPTION=$(curl -s -X POST "$BASE/ai/plan" \
    -H "$AUTHZ" -H "$JSON" \
    -d "{\"platform\":\"instagram\",\"ratio\":\"$R\"}" \
    | jq -r '.caption // ""')

  MAPPING=$(curl -s -X POST "$BASE/ai/plan" \
    -H "$AUTHZ" -H "$JSON" \
    -d "{\"platform\":\"instagram\",\"ratio\":\"$R\"}" \
    | jq -c '.preview_payload.mapping // {}')

  # safety: αν αποτύχει το ai/plan
  if [[ -z "$CAPTION" || "$CAPTION" == "null" ]]; then
    echo "AI plan failed for ratio $R" >&2
    CAPTION=""
    MAPPING="{}"
  fi

  # 2) Φτιάξε tengine payload
  cat > "$TMP_REQ" <<JSON
{
  "template_id": 12,
  "image_url": "${DEMO_URL}",
  "platform": "instagram",
  "ratio": "${R}",
  "mode": "normal",
  "use_renderer": true,
  "use_ai_plan": true,
  "watermark": true,
  "return_absolute_url": true,
  "mapping": ${MAPPING}
}
JSON

  # 3) Preview
  PREV_JSON="/tmp/prev_${R//:/}.json"
  curl -s -X POST "$BASE/tengine/preview" \
    -H "$AUTHZ" -H "$JSON" \
    --data-binary @"$TMP_REQ" \
    | tee "$PREV_JSON" >/dev/null

  PREVIEW_URL=$(jq -r '.preview_url // ""' "$PREV_JSON")
  OVERLAY=$(jq -r '.meta.overlay_applied // false' "$PREV_JSON")
  WIDTH=$(jq -r '.meta.width // 0' "$PREV_JSON")
  HEIGHT=$(jq -r '.meta.height // 0' "$PREV_JSON")
  PREV_ID=$(jq -r '.preview_id // .id // empty' "$PREV_JSON")

  if [[ -z "$PREVIEW_URL" || -z "$PREV_ID" ]]; then
    echo "Preview failed for ratio $R" >&2
    PREVIEW_URL=""
    OVERLAY="false"
    WIDTH=0
    HEIGHT=0
    PREV_ID=""
  fi

  # 4) Commit
  COMMIT_JSON="/tmp/commit_${R//:/}.json"
  if [[ -n "$PREV_ID" ]]; then
    curl -s -X POST "$BASE/tengine/commit" \
      -H "$AUTHZ" -H "$JSON" \
      -d "{\"preview_id\":\"$PREV_ID\"}" \
      | tee "$COMMIT_JSON" >/dev/null
  else
    echo '{"committed_url":"","remaining_credits":null}' > "$COMMIT_JSON"
  fi

  COMMITTED_URL=$(jq -r '.committed_url // ""' "$COMMIT_JSON")
  CREDITS=$(jq -r '.remaining_credits // ""' "$COMMIT_JSON")

  # 5) Γράψε CSV (escape caption διπλά quotes)
  SAFE_CAP=${CAPTION//\"/\"\"}
  echo "\"$R\",\"$SAFE_CAP\",\"$PREVIEW_URL\",$OVERLAY,$WIDTH,$HEIGHT,\"$COMMITTED_URL\",\"$CREDITS\"" >> "$OUT_CSV"

  # echo mini log
  echo "[$R] overlay=$OVERLAY ${WIDTH}x${HEIGHT}"
  echo "     caption: $CAPTION"
  echo "     preview: $PREVIEW_URL"
  echo "     commit : $COMMITTED_URL (credits: $CREDITS)"
}

# Τρέξε 1:1, 4:5, 9:16
for R in "1:1" "4:5" "9:16"; do
  run_one "$R"
done

echo "✅ Αποτελέσματα => $OUT_CSV"
