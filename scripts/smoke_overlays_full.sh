#!/usr/bin/env bash
set -euo pipefail

# Reqs: BASE, AUTHZ (Authorization: Bearer ...)

IMG_URL_1_1="${IMG_URL_1_1:-/static/demo/img_1_1.jpg}"
IMG_URL_4_5="${IMG_URL_4_5:-/static/demo/img_4_5.jpg}"
IMG_URL_9_16="${IMG_URL_9_16:-/static/demo/img_9_16.jpg}"
BRAND_LOGO="${BRAND_LOGO:-/static/demo/logo.png}"

OUT="smoke_overlays_full.csv"
LOG="smoke_overlays_full.log"
echo "ratio,preview_status,commit_status,preview_url,committed_url,meta_width,meta_height,overlay_applied,logo_applied,discount_badge_applied,cta_applied,slots_json,err" > "$OUT"
: > "$LOG"

pick_img () {
  case "$1" in
    "1:1")  echo "$IMG_URL_1_1" ;;
    "4:5")  echo "$IMG_URL_4_5" ;;
    "9:16") echo "$IMG_URL_9_16" ;;
    *)      echo "$IMG_URL_4_5" ;;
  esac
}

for R in "1:1" "4:5" "9:16"; do
  IMG="$(pick_img "$R")"

  DATA=$(jq -n --arg r "$R" --arg img "$IMG" --arg logo "$BRAND_LOGO" '
  {
    use_renderer: true,
    ratio: $r,
    mode: "normal",
    image_url: $img,
    mapping: {
      title: "Demo Product",
      price: "19.90",
      old_price: "29.90",
      cta: "ΑΓΟΡΑ ΤΩΡΑ",
      logo_url: $logo,
      discount_badge: true
    }
  }')

  # Render
  RES=$(curl -s -X POST "$BASE/previews/render" -H "$AUTHZ" -H "Content-Type: application/json" -d "$DATA" || true)
  {
    echo "===== $(date -Iseconds) RATIO=$R RENDER ====="
    echo "$RES"
  } >> "$LOG"

  # Robust parsing: treat OK if preview_id exists (fallback if status missing)
  PST=$(echo "$RES" | jq -r 'if has("status") then .status else (if (.preview_id // "") != "" then "ok" else "ERR" end) end')
  PID=$(echo "$RES" | jq -r '.preview_id // empty')
  PURL=$(echo "$RES" | jq -r '.absolute_url // .url // .preview_url // empty')
  MW=$(echo "$RES" | jq -r '.meta.width  // .meta["width"]  // empty')
  MH=$(echo "$RES" | jq -r '.meta.height // .meta["height"] // empty')
  OA=$(echo "$RES" | jq -r '(.overlay_applied // false) | tostring')
  LA=$(echo "$RES" | jq -r '(.logo_applied // false) | tostring')
  DA=$(echo "$RES" | jq -r '(.discount_badge_applied // false) | tostring')
  CA=$(echo "$RES" | jq -r '(.cta_applied // false) | tostring')
  SLOTS=$(echo "$RES" | jq -c '.slots_used // {}')
  ERR=""

  # Commit
  CST="na"
  CURL=""
  if [ -n "$PID" ]; then
    CREQ=$(jq -n --arg id "$PID" '{preview_id: $id}')
    CRES=$(curl -s -X POST "$BASE/previews/commit" -H "$AUTHZ" -H "Content-Type: application/json" -d "$CREQ" || true)
    {
      echo "===== $(date -Iseconds) RATIO=$R COMMIT($PID) ====="
      echo "$CRES"
    } >> "$LOG"
    CST=$(echo "$CRES" | jq -r 'if has("status") then .status else (if (.committed_url // .url // "") != "" then "ok" else "ERR" end) end')
    CURL=$(echo "$CRES" | jq -r '.absolute_url // .url // .committed_url // empty')
  else
    ERR="no_preview_id"
  fi

  echo "$R,$PST,$CST,$PURL,$CURL,$MW,$MH,$OA,$LA,$DA,$CA,\"$SLOTS\",$ERR" >> "$OUT"
done

echo "Wrote $OUT (log: $LOG)"
