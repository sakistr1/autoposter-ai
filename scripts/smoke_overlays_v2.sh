#!/usr/bin/env bash
set -euo pipefail

: "${BASE:?missing BASE}"
: "${AUTHZ:?missing AUTHZ header}"

OUT="smoke_overlays_v2.csv"
echo "ratio,preview_status,commit_status,preview_url,committed_url,meta_width,meta_height,overlay_applied,err" > "$OUT"

# Demo images per ratio (μπορείς να αλλάξεις paths/URLs)
IMG_1_1="${IMG_1_1:-/static/demo/img_1_1.jpg}"
IMG_4_5="${IMG_4_5:-/static/demo/img_4_5.jpg}"
IMG_9_16="${IMG_9_16:-/static/demo/img_9_16.jpg}"

image_for_ratio() {
  case "$1" in
    "1:1")  echo "$IMG_1_1" ;;
    "4:5")  echo "$IMG_4_5" ;;
    "9:16") echo "$IMG_9_16" ;;
    *)      echo "$IMG_4_5" ;;
  esac
}

for R in "1:1" "4:5" "9:16"; do
  IMG_URL="$(image_for_ratio "$R")"

  DATA=$(jq -n --arg ratio "$R" --arg img "$IMG_URL" \
    '{
       ratio: $ratio,
       mode: "normal",
       image_url: $img,
       inputs: {
         title:"Demo",
         price:"19.90€",
         old_price:"29.90€",
         cta:"ΑΓΟΡΑ ΤΩΡΑ",
         logo_url:"/static/demo/logo.png"
       }
     }')

  # --- PREVIEW ---
  PREVIEW=$(curl -sS -X POST "$BASE/previews/render" \
    -H "$AUTHZ" -H "Content-Type: application/json" -d "$DATA" || true)

  PSTATUS=$(echo "$PREVIEW" | jq -r '.status // "ok"')
  PERR=$(echo "$PREVIEW" | jq -r '.detail // .error // .message // empty')
  PURL=$(echo "$PREVIEW" | jq -r '.absolute_url // .preview_url // .url // empty')
  PID=$(echo "$PREVIEW" | jq -r '.preview_id // empty')
  MW=$(echo "$PREVIEW" | jq -r '.meta.width // empty')
  MH=$(echo "$PREVIEW" | jq -r '.meta.height // empty')
  OVL=$(echo "$PREVIEW" | jq -r '.overlay_applied // false')

  if [ -z "$PID" ] || [ -z "$PURL" ]; then
    echo "$R,FAIL,NA,,,$MW,$MH,$OVL,\"$PERR\"" >> "$OUT"
    continue
  fi

  # --- COMMIT ---
  COMMIT=$(jq -n --arg pid "$PID" '{preview_id:$pid}')
  CRESP=$(curl -sS -X POST "$BASE/previews/commit" \
    -H "$AUTHZ" -H "Content-Type: application/json" -d "$COMMIT" || true)

  CSTATUS=$(echo "$CRESP" | jq -r '.status // "ok"')
  CERR=$(echo "$CRESP" | jq -r '.detail // .error // .message // empty')
  CURL=$(echo "$CRESP" | jq -r '.absolute_url // .committed_url // .url // empty')

  if [ -z "$CURL" ]; then
    echo "$R,ok,FAIL,$PURL,,$MW,$MH,$OVL,\"$CERR\"" >> "$OUT"
    continue
  fi

  echo "$R,ok,ok,$PURL,$CURL,$MW,$MH,$OVL," >> "$OUT"
done

echo "Wrote $OUT"
