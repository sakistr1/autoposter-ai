#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8000}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: χρειάζεται $1"; exit 1; }; }
need jq

get_token() {
  if [[ -z "${TOKEN:-}" ]]; then
    echo "== LOGIN -> TOKEN (demo10)"
    TOKEN="$(curl -sS -X POST "$BASE/login" -H "Content-Type: application/json" \
      -d '{"email":"demo10@gmail.com","password":"demo10"}' | jq -r '.access_token')"
    [[ -z "$TOKEN" || "$TOKEN" == "null" ]] && { echo "ERROR: δεν πήραμε token"; exit 1; }
    export TOKEN
  fi
}

render() {
  local body="$1" out="$2" ; shift 2
  curl -sS -X POST "$BASE/previews/render" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "$body" | tee "$out" >/dev/null
  local ok status; status=$(jq -r '.status // empty' "$out")
  [[ "$status" != "ok" ]] && { echo "RENDER FAIL: $(cat "$out")"; exit 1; }
}

commit() {
  local prev="$1"
  curl -sS -X POST "$BASE/previews/commit" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "{\"preview_url\":\"$prev\"}" | jq .
}

echo "== Smoke ALL (image/carousel/video + shortlink)"
get_token

echo "== Credits πριν"
curl -sS -H "Authorization: Bearer $TOKEN" "$BASE/previews/me/credits" | jq .

# 1) IMAGE με AI BG + shortlink
echo "== IMAGE"
render '{
  "mode":"normal","ratio":"4:5","ai_bg":"remove",
  "qr": true,
  "target_url":"https://shop.example.com/p/sku-777",
  "image_url":"/static/demo/outfit1.webp",
  "mapping":{"title":"Image Test","price":"49.90","cta":"Αγορά τώρα"}
}' /tmp/pr_img.json
jq -r '.short_url, .preview_url' /tmp/pr_img.json
commit "$(jq -r '.preview_url' /tmp/pr_img.json)"

# 2) CAROUSEL (3 frames)
echo "== CAROUSEL"
render '{
  "mode":"carousel","ratio":"4:5","ai_bg":"remove",
  "qr": true,
  "target_url":"https://shop.example.com/p/sku-888",
  "meta":{"images":["/static/demo/outfit1.webp","/static/demo/shoes1.webp","/static/demo/shoes2.jpg"]},
  "mapping":{"title":"Carousel Test","price":"69.00","cta":"Δες τα"}
}' /tmp/pr_car.json
jq -r '.short_url, .preview_url, .sheet_url, .first_frame_url' /tmp/pr_car.json
commit "$(jq -r '.preview_url' /tmp/pr_car.json)"

# 3) VIDEO (6s / 30fps)
echo "== VIDEO"
render '{
  "mode":"video","ratio":"4:5","ai_bg":"remove",
  "qr": true,
  "target_url":"https://shop.example.com/p/sku-999",
  "meta":{"images":["/static/demo/outfit1.webp","/static/demo/shoes1.webp"],"fps":30,"duration_sec":6},
  "mapping":{"title":"Video Test","price":"149.00","cta":"Δες το"}
}' /tmp/pr_vid.json
jq -r '.short_url, .preview_url, .plan.video_url' /tmp/pr_vid.json
commit "$(jq -r '.preview_url' /tmp/pr_vid.json)"

echo "== Credits μετά"
curl -sS -H "Authorization: Bearer $TOKEN" "$BASE/previews/me/credits" | jq .

echo "OK ✅"
