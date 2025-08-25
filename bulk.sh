#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000}"
TOKEN="${TOKEN:-}"
[ -z "${TOKEN}" ] && { echo "Δώσε TOKEN: export TOKEN=..."; exit 1; }
AUTH="Authorization: Bearer ${TOKEN}"

INPUT="${1:-bulk.json}"
RESULTS="bulk_results_$(date +%s).jsonl"
SLEEP_SEC="${SLEEP_SEC:-0}"   # βάλε π.χ. 0.2 αν τρως 429

command -v jq >/dev/null || { echo "χρειάζεται jq"; exit 1; }

DEFAULTS=$(jq -c '.defaults' "$INPUT")
RATIOS=$(echo "$DEFAULTS" | jq -r '.ratios[]')
ITEMS=$(jq -c '.items[]' "$INPUT")

echo "# bulk run -> $RESULTS"
: > "$RESULTS"

for IT in $ITEMS; do
  for R in $RATIOS; do
    PAYLOAD=$(jq -cn --argjson d "$DEFAULTS" --argjson it "$IT" --arg r "$R" '$d + $it + {ratio:$r} | del(.ratios)')
    TITLE=$(echo "$PAYLOAD" | jq -r '.title // ""')
    PRICE=$(echo "$PAYLOAD" | jq -r '.price // ""')

    # 1) preview
    PREVIEW_URL=$(curl -s -X POST "$BASE/tengine/preview" -H "$AUTH" -H "Content-Type: application/json" -d "$PAYLOAD" | jq -r .preview_url)
    if [[ -z "$PREVIEW_URL" || "$PREVIEW_URL" == "null" ]]; then
      echo "{\"ok\":false,\"step\":\"preview\",\"ratio\":\"$R\",\"title\":$(jq -Rn --arg t "$TITLE" '$t'),\"error\":\"no preview_url\"}" | tee -a "$RESULTS" >/dev/null
      sleep "$SLEEP_SEC"
      continue
    fi

    # 2) caption preset
    CAPTION=$(jq -Rn --arg t "$TITLE" --arg p "$PRICE" '$t + " — " + $p + "  #promo #deals"')

    # 3) commit
    BODY=$(jq -cn --arg p "$PREVIEW_URL" --arg c "$CAPTION" '{preview_url:$p, caption:$c}')
    COMMIT=$(curl -s -X POST "$BASE/tengine/commit" -H "$AUTH" -H "Content-Type: application/json" -d "$BODY")
    OK=$(echo "$COMMIT" | jq -r 'has("post_id")')
    if [[ "$OK" != "true" ]]; then
      echo "{\"ok\":false,\"step\":\"commit\",\"ratio\":\"$R\",\"title\":$(jq -Rn --arg t "$TITLE" '$t'),\"preview_url\":\"$PREVIEW_URL\",\"resp\":$COMMIT}" | tee -a "$RESULTS" >/dev/null
      sleep "$SLEEP_SEC"
      continue
    fi

    PNG=$(echo "$COMMIT" | jq -r '.media_urls[0]')
    POST_ID=$(echo "$COMMIT" | jq -r '.post_id')
    echo "{\"ok\":true,\"ratio\":\"$R\",\"title\":$(jq -Rn --arg t "$TITLE" '$t'),\"post_id\":$POST_ID,\"png\":\"$PNG\"}" | tee -a "$RESULTS" >/dev/null
    sleep "$SLEEP_SEC"
  done
done

echo "# Τέλος. Αποτελέσματα σε: $RESULTS"
