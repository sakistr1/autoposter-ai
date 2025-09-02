#!/usr/bin/env bash
# Smoke όλων των ροών: images (1:1, 4:5, 9:16), carousel, video
# Αποτελέσματα -> smoke_all.csv
set -u

BASE="${BASE:-http://127.0.0.1:8000}"
: "${TOKEN:?Missing TOKEN env (JWT)}"
AUTHZ="Authorization: Bearer ${TOKEN}"

OUT="smoke_all.csv"
TMP="$(mktemp -d)"
cleanup(){ rm -rf "$TMP"; }
trap cleanup EXIT

# Header CSV (αν δεν υπάρχει)
if [[ ! -f "$OUT" ]]; then
  echo "kind,status,detail,preview_or_sheet,first_frame,commit_status,committed_url,err" > "$OUT"
fi

jqval () { jq -r "$1 // empty"; }

commit_preview () {
  # $1 = preview_url (εικόνα, frame ή mp4)
  local purl="$1"
  if [[ -z "$purl" ]]; then
    echo "ERR|no preview_url"
    return 0
  fi
  local resp
  resp=$(curl -s -X POST "$BASE/previews/commit" \
    -H "$AUTHZ" -H "Content-Type: application/json" \
    -d "{\"preview_url\":\"$purl\"}")
  local ok detail curl_
  ok=$(echo "$resp" | jqval '.ok')
  detail=$(echo "$resp" | jqval '.detail')
  curl_=$(echo "$resp" | jqval '.committed_url')
  if [[ "$ok" == "true" || -n "$curl_" ]]; then
    echo "ok|$curl_|"
  else
    echo "ERR||${detail:-commit failed}"
  fi
}

smoke_image () {
  # $1 = ratio (e.g. 1:1 / 4:5 / 9:16)
  # $2 = demo image path
  local ratio="$1" img="$2"
  local resp status purl
  resp=$(curl -s -X POST "$BASE/previews/render" \
    -H "$AUTHZ" -H "Content-Type: application/json" \
    -d "{
      \"use_renderer\": true,
      \"ratio\": \"$ratio\",
      \"mode\": \"normal\",
      \"image_url\": \"$img\",
      \"mapping\": {
        \"title\":\"Demo\",
        \"price\":\"19.90€\",
        \"old_price\":\"29.90€\",
        \"cta\":\"ΑΓΟΡΑ ΤΩΡΑ\",
        \"logo_url\":\"/static/demo/logo.png\",
        \"discount_badge\": true
      }
    }")
  status=$(echo "$resp" | jqval '.status')
  purl=$(echo "$resp" | jqval '.preview_url')

  if [[ -n "$purl" ]]; then
    local cstat committed err
    IFS='|' read -r cstat committed err < <(commit_preview "$purl")
    echo "image,ok,$ratio,$purl,,${cstat},${committed},${err}" >> "$OUT"
  else
    local detail
    detail=$(echo "$resp" | jqval '.detail')
    echo "image,ERR,$ratio,,,ERR,,${detail:-render failed}" >> "$OUT"
  fi
}

smoke_carousel () {
  local resp sheet frames first
  resp=$(curl -s -X POST "$BASE/previews/render" \
    -H "$AUTHZ" -H "Content-Type: application/json" \
    -d "{
      \"mode\": \"carousel\",
      \"images\": [
        {\"image\":\"/static/demo/img_1_1.jpg\"},
        {\"image\":\"/static/demo/img_4_5.jpg\"},
        {\"image\":\"/static/demo/img_9_16.jpg\"}
      ]
    }")
  sheet=$(echo "$resp" | jqval '.preview_url // .sheet_url')
  # λίστα καρέ (αν υπάρχει)
  frames=$(echo "$resp" | jq -r '.frames[]? // empty')
  first=$(echo "$resp" | jq -r '.frames[0]? // empty')

  if [[ -n "$sheet" ]]; then
    # Κάνε commit το πρώτο frame (εικόνα)
    local cstat committed err
    IFS='|' read -r cstat committed err < <(commit_preview "$first")
    echo "carousel,ok,3-frames,$sheet,$first,${cstat},${committed},${err}" >> "$OUT"
  else
    local detail
    detail=$(echo "$resp" | jqval '.detail')
    echo "carousel,ERR,render,,,ERR,,${detail:-render failed}" >> "$OUT"
  fi
}

smoke_video () {
  local ratio="$1"   # π.χ. 4:5
  local resp purl
  resp=$(curl -s -X POST "$BASE/previews/render" \
    -H "$AUTHZ" -H "Content-Type: application/json" \
    -d "{
      \"mode\": \"video\",
      \"ratio\": \"$ratio\",
      \"fps\": 30,
      \"duration_sec\": 6,
      \"images\": [
        {\"image\":\"/static/demo/img_1_1.jpg\"},
        {\"image\":\"/static/demo/img_4_5.jpg\"}
      ],
      \"meta\": {\"fps\":30, \"duration_sec\":6}
    }")
  purl=$(echo "$resp" | jqval '.preview_url')
  if [[ -n "$purl" ]]; then
    local cstat committed err
    IFS='|' read -r cstat committed err < <(commit_preview "$purl")
    echo "video,ok,$ratio,$purl,,${cstat},${committed},${err}" >> "$OUT"
  else
    local detail
    detail=$(echo "$resp" | jqval '.detail')
    echo "video,ERR,$ratio,,,ERR,,${detail:-render failed}" >> "$OUT"
  fi
}

echo ">>> IMAGES ..."
smoke_image "1:1"  "/static/demo/img_1_1.jpg"
smoke_image "4:5"  "/static/demo/img_4_5.jpg"
smoke_image "9:16" "/static/demo/img_9_16.jpg"

echo ">>> CAROUSEL ..."
smoke_carousel

echo ">>> VIDEO ..."
smoke_video "4:5"

echo "Done. Results -> $OUT"
