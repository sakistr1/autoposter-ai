#!/usr/bin/env bash
set -euo pipefail

: "${BASE:=http://127.0.0.1:8000}"
: "${TOKEN:?export TOKEN=... πρώτα}"
AUTH="Authorization: Bearer ${TOKEN}"
INPUT="${1:-bulk.json}"
RESULTS="bulk_results_$(date +%s).jsonl"

# Ρυθμίσεις backoff (μπορείς να τις αλλάξεις με env)
: "${BASE_SLEEP:=0.25}"   # αρχικό delay (δευτερόλεπτα)
: "${MAX_RETRIES:=6}"     # μέγιστες επαναλήψεις σε 429 (έως ~2s sleep)

command -v jq >/dev/null || { echo "χρειάζεται jq"; exit 1; }
jq empty "$INPUT" >/dev/null

echo "# bulk run -> $RESULTS"
: > "$RESULTS"

call_http() { # method url [json]
  local method="$1" url="$2" body="${3:-}"
  if [[ -n "$body" ]]; then
    curl -sS -w '\n%{http_code}' -H "$AUTH" -H 'Content-Type: application/json' -X "$method" "$url" -d "$body"
  else
    curl -sS -w '\n%{http_code}' -H "$AUTH" -X "$method" "$url"
  fi
}

call_with_retry429() { # method url [json] -> prints "body\nstatus"
  local method="$1" url="$2" body="${3:-}"
  local attempt=0 sleep_s="$BASE_SLEEP"
  while :; do
    local resp; resp=$(call_http "$method" "$url" "$body")
    local status; status=$(echo "$resp" | tail -n1)
    local payload; payload=$(echo "$resp" | sed '$d')
    if [[ "$status" == "429" ]]; then
      ((attempt++))
      if (( attempt > MAX_RETRIES )); then
        echo "$payload"; echo "$status"; return 0
      fi
      # exponential-ish backoff μέχρι 2.00s
      sleep "$sleep_s"
      sleep_s=$(awk -v s="$sleep_s" 'BEGIN{n=s*1.7; if(n>2.0)n=2.0; printf "%.2f", n}')
      continue
    fi
    echo "$payload"; echo "$status"; return 0
  done
}

# Δημιουργεί payload ανά (item, ratio) με jq
jq -c '
  . as $root
  | .items[] as $it
  | $root.defaults.ratios[] as $r
  | ($root.defaults + $it + {ratio:$r} | del(.ratios))
' "$INPUT" | while IFS= read -r PAYLOAD; do
  TITLE=$(echo "$PAYLOAD" | jq -r '.title // ""')
  PRICE=$(echo "$PAYLOAD" | jq -r '.price // ""')
  RATIO=$(echo "$PAYLOAD" | jq -r '.ratio')

  # 1) PREVIEW (με retry/backoff σε 429)
  PREVIEW_CALL=$(call_with_retry429 POST "$BASE/tengine/preview" "$PAYLOAD")
  PREVIEW_STATUS=$(echo "$PREVIEW_CALL" | tail -n1)
  PREVIEW_BODY=$(echo "$PREVIEW_CALL" | sed '$d')

  if [[ "$PREVIEW_STATUS" != "200" ]]; then
    jq -n --arg step preview --arg t "$TITLE" --arg r "$RATIO" \
         --arg st "$PREVIEW_STATUS" --arg resp "$PREVIEW_BODY" \
         '{ok:false, step:$step, title:$t, ratio:$r, status:$st, resp_raw:$resp}' \
      | tee -a "$RESULTS" >/dev/null
    continue
  fi

  PREVIEW_URL=$(echo "$PREVIEW_BODY" | jq -r '.preview_url // empty')
  if [[ -z "$PREVIEW_URL" ]]; then
    jq -n --arg step preview --arg t "$TITLE" --arg r "$RATIO" \
         --arg resp "$PREVIEW_BODY" \
         '{ok:false, step:$step, title:$t, ratio:$r, error:"no preview_url", resp_raw:$resp}' \
      | tee -a "$RESULTS" >/dev/null
    continue
  fi

  # 2) Caption preset
  CAPTION=$(jq -Rn --arg t "$TITLE" --arg p "$PRICE" '$t + " — " + $p + "  #promo #deals"')
  BODY=$(jq -cn --arg p "$PREVIEW_URL" --arg c "$CAPTION" '{preview_url:$p, caption:$c}')

  # 3) COMMIT (δεν περιμένω 429 εδώ, αλλά κρατάμε το ίδιο wrapper)
  COMMIT_CALL=$(call_with_retry429 POST "$BASE/tengine/commit" "$BODY")
  COMMIT_STATUS=$(echo "$COMMIT_CALL" | tail -n1)
  COMMIT_BODY=$(echo "$COMMIT_CALL" | sed '$d')

  if [[ "$COMMIT_STATUS" != "200" ]] || [[ "$(echo "$COMMIT_BODY" | jq -r 'has("post_id")')" != "true" ]]; then
    jq -n --arg step commit --arg t "$TITLE" --arg r "$RATIO" \
         --arg st "$COMMIT_STATUS" --arg resp "$COMMIT_BODY" \
         --arg p "$PREVIEW_URL" \
         '{ok:false, step:$step, title:$t, ratio:$r, status:$st, preview_url:$p, resp_raw:$resp}' \
      | tee -a "$RESULTS" >/dev/null
    continue
  fi

  PNG=$(echo "$COMMIT_BODY" | jq -r '.media_urls[0]')
  PID=$(echo "$COMMIT_BODY" | jq -r '.post_id')

  jq -n --arg t "$TITLE" --arg r "$RATIO" --arg p "$PNG" --arg id "$PID" \
    '{ok:true, title:$t, ratio:$r, post_id:($id|tonumber), png:$p}' \
    | tee -a "$RESULTS" >/dev/null
done

echo "# Τέλος. Αποτελέσματα σε: $RESULTS"
