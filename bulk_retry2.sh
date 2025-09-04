#!/usr/bin/env bash
set -euo pipefail

: "${BASE:=http://127.0.0.1:8000}"
: "${TOKEN:?export TOKEN=... πρώτα}"
AUTH="Authorization: Bearer ${TOKEN}"
INPUT="${1:-bulk.json}"
RESULTS="bulk_results_$(date +%s).jsonl"

# Backoff ρυθμίσεις (override με env αν θες)
: "${BASE_SLEEP:=0.6}"     # αρχικό delay
: "${MAX_RETRIES:=12}"     # μέγιστες προσπάθειες
: "${MAX_SLEEP:=5.0}"      # upper bound για backoff
: "${GAP_PREVIEW:=0.2}"    # σταθερό κενό μετά από επιτυχημένο preview
: "${GAP_COMMIT:=0.4}"     # σταθερό κενό μετά από επιτυχημένο commit

command -v jq >/dev/null || { echo "χρειάζεται jq"; exit 1; }
jq empty "$INPUT" >/dev/null

echo "# bulk run -> $RESULTS"
: > "$RESULTS"

call_with_retry429() { # method url [json] -> stdout: body | last line: HTTP code
  local method="$1" url="$2" body="${3:-}"
  local attempt=0 sleep_s="$BASE_SLEEP"

  while :; do
    local hdr bodyf
    hdr=$(mktemp) ; bodyf=$(mktemp)
    if [[ -n "$body" ]]; then
      code=$(curl -sS -D "$hdr" -o "$bodyf" -H "$AUTH" -H 'Content-Type: application/json' -X "$method" "$url" -d "$body" -w '%{http_code}')
    else
      code=$(curl -sS -D "$hdr" -o "$bodyf" -H "$AUTH" -X "$method" "$url" -w '%{http_code}')
    fi
    if [[ "$code" == "429" ]]; then
      ((attempt++))
      if (( attempt > MAX_RETRIES )); then
        cat "$bodyf"; echo "$code"
        rm -f "$hdr" "$bodyf"
        return 0
      fi
      # Διάβασε Retry-After (δευτ.) αν υπάρχει
      ra=$(awk 'BEGIN{IGNORECASE=1} /^Retry-After:/ {gsub("\r",""); print $2; exit}' "$hdr")
      if [[ "$ra" =~ ^[0-9]+$ ]]; then
        sleep_s="$ra"
      fi
      sleep "$sleep_s"
      # εκθετική αύξηση με όριο
      sleep_s=$(python3 - <<PY
s=float("$sleep_s"); m=float("$MAX_SLEEP")
n=s*1.7
print(n if n<m else m)
PY
)
      rm -f "$hdr" "$bodyf"
      continue
    fi
    cat "$bodyf"; echo "$code"
    rm -f "$hdr" "$bodyf"
    return 0
  done
}

# Παράγει payloads (defaults + item + ratio)
jq -c '. as $root | .items[] as $it | $root.defaults.ratios[] as $r | ($root.defaults + $it + {ratio:$r} | del(.ratios))' "$INPUT" \
| while IFS= read -r PAYLOAD; do
  TITLE=$(echo "$PAYLOAD" | jq -r '.title // ""')
  PRICE=$(echo "$PAYLOAD" | jq -r '.price // ""')
  RATIO=$(echo "$PAYLOAD" | jq -r '.ratio')

  # 1) PREVIEW
  PREVIEW_CALL=$(call_with_retry429 POST "$BASE/tengine/preview" "$PAYLOAD")
  PREVIEW_STATUS=$(echo "$PREVIEW_CALL" | tail -n1)
  PREVIEW_BODY=$(echo "$PREVIEW_CALL" | sed '$d')

  if [[ "$PREVIEW_STATUS" != "200" ]]; then
    jq -n --arg step preview --arg t "$TITLE" --arg r "$RATIO" --arg st "$PREVIEW_STATUS" --arg resp "$PREVIEW_BODY" \
      '{ok:false, step:$step, title:$t, ratio:$r, status:$st, resp_raw:$resp}' \
      | tee -a "$RESULTS" >/dev/null
    continue
  fi

  PREVIEW_URL=$(echo "$PREVIEW_BODY" | jq -r '.preview_url // empty')
  if [[ -z "$PREVIEW_URL" ]]; then
    jq -n --arg step preview --arg t "$TITLE" --arg r "$RATIO" --arg resp "$PREVIEW_BODY" \
      '{ok:false, step:$step, title:$t, ratio:$r, error:"no preview_url", resp_raw:$resp}' \
      | tee -a "$RESULTS" >/dev/null
    continue
  fi
  sleep "$GAP_PREVIEW"

  # 2) Caption
  CAPTION=$(jq -Rn --arg t "$TITLE" --arg p "$PRICE" '$t + " — " + $p + "  #promo #deals"')
  BODY=$(jq -cn --arg p "$PREVIEW_URL" --arg c "$CAPTION" '{preview_url:$p, caption:$c}')

  # 3) COMMIT (με retry)
  COMMIT_CALL=$(call_with_retry429 POST "$BASE/tengine/commit" "$BODY")
  COMMIT_STATUS=$(echo "$COMMIT_CALL" | tail -n1)
  COMMIT_BODY=$(echo "$COMMIT_CALL" | sed '$d')

  if [[ "$COMMIT_STATUS" != "200" ]] || [[ "$(echo "$COMMIT_BODY" | jq -r 'has("post_id")')" != "true" ]]; then
    jq -n --arg step commit --arg t "$TITLE" --arg r "$RATIO" --arg st "$COMMIT_STATUS" --arg p "$PREVIEW_URL" --arg resp "$COMMIT_BODY" \
      '{ok:false, step:$step, title:$t, ratio:$r, status:$st, preview_url:$p, resp_raw:$resp}' \
      | tee -a "$RESULTS" >/dev/null
    continue
  fi

  PNG=$(echo "$COMMIT_BODY" | jq -r '.media_urls[0]')
  PID=$(echo "$COMMIT_BODY" | jq -r '.post_id')

  jq -n --arg t "$TITLE" --arg r "$RATIO" --arg p "$PNG" --arg id "$PID" \
    '{ok:true, title:$t, ratio:$r, post_id:($id|tonumber), png:$p}' \
    | tee -a "$RESULTS" >/dev/null

  sleep "$GAP_COMMIT"
done

echo "# Τέλος. Αποτελέσματα σε: $RESULTS"
