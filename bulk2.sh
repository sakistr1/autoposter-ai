#!/usr/bin/env bash
set -euo pipefail

: "${BASE:=http://127.0.0.1:8000}"
: "${TOKEN:?export TOKEN=... πρώτα}"
AUTH="Authorization: Bearer ${TOKEN}"
INPUT="${1:-bulk.json}"
RESULTS="bulk_results_$(date +%s).jsonl"
: "${SLEEP_SEC:=0}"   # π.χ. 0.25 αν πέσεις σε 429

command -v jq >/dev/null || { echo "χρειάζεται jq"; exit 1; }
jq empty "$INPUT" >/dev/null

echo "# bulk run -> $RESULTS"
: > "$RESULTS"

# Το jq εδώ εκπέμπει ΕΝΑ payload ανά γραμμή (defaults + item + ratio)
jq -c '
  . as $root
  | .items[] as $it
  | $root.defaults.ratios[] as $r
  | ($root.defaults + $it + {ratio:$r} | del(.ratios))
' "$INPUT" | while IFS= read -r PAYLOAD; do
  TITLE=$(echo "$PAYLOAD" | jq -r '.title // ""')
  PRICE=$(echo "$PAYLOAD" | jq -r '.price // ""')

  # 1) preview
  PREVIEW_URL=$(curl -s -X POST "$BASE/tengine/preview" \
    -H "$AUTH" -H "Content-Type: application/json" \
    -d "$PAYLOAD" | jq -r '.preview_url // empty')

  if [[ -z "$PREVIEW_URL" ]]; then
    jq -n --arg t "$TITLE" --arg err "no preview_url" \
      '{ok:false, step:"preview", title:$t, error:$err}' \
      | tee -a "$RESULTS" >/dev/null
    sleep "$SLEEP_SEC"; continue
  fi

  # 2) caption preset
  CAPTION=$(jq -Rn --arg t "$TITLE" --arg p "$PRICE" '$t + " — " + $p + "  #promo #deals"')
  BODY=$(jq -cn --arg p "$PREVIEW_URL" --arg c "$CAPTION" '{preview_url:$p, caption:$c}')

  # 3) commit
  COMMIT=$(curl -s -X POST "$BASE/tengine/commit" \
    -H "$AUTH" -H "Content-Type: application/json" \
    -d "$BODY")

  if [[ "$(echo "$COMMIT" | jq -r 'has("post_id")')" != "true" ]]; then
    jq -n --arg t "$TITLE" --arg p "$PREVIEW_URL" --arg resp "$COMMIT" \
      '{ok:false, step:"commit", title:$t, preview_url:$p, resp_raw:$resp}' \
      | tee -a "$RESULTS" >/dev/null
    sleep "$SLEEP_SEC"; continue
  fi

  PNG=$(echo "$COMMIT"   | jq -r '.media_urls[0]')
  PID=$(echo "$COMMIT"   | jq -r '.post_id')
  RATIO=$(echo "$PAYLOAD"| jq -r '.ratio')

  jq -n --arg t "$TITLE" --arg r "$RATIO" --arg p "$PNG" --arg id "$PID" \
    '{ok:true, title:$t, ratio:$r, post_id:($id|tonumber), png:$p}' \
    | tee -a "$RESULTS" >/dev/null

  sleep "$SLEEP_SEC"
done

echo "# Τέλος. Αποτελέσματα σε: $RESULTS"
