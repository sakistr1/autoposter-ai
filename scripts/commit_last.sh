#!/usr/bin/env bash
set -euo pipefail

BASE=${BASE:-"http://127.0.0.1:8000"}
AUTHZ=${AUTHZ:-"Authorization: Bearer ${TOKEN:-}"}
MODE=${1:-video}   # image | carousel | video

# ---- Build render payload ανά mode ----
case "$MODE" in
  image)
    PAYLOAD='{
      "use_renderer": true, "ratio": "4:5", "mode": "normal",
      "image_url": "/static/demo/img_4_5.jpg",
      "mapping": {
        "title":"Demo","price":"19.90€","old_price":"29.90€",
        "cta":"ΑΓΟΡΑ ΤΩΡΑ","logo_url":"/static/demo/logo.png",
        "discount_badge": true
      }
    }'
    ;;
  carousel)
    PAYLOAD='{
      "node":"carousel",
      "images":[
        {"image":"/static/demo/img_1_1.jpg"},
        {"image":"/static/demo/img_4_5.jpg"},
        {"image":"/static/demo/img_9_16.jpg"}
      ]
    }'
    ;;
  video)
    PAYLOAD='{
      "node":"video","ratio":"4:5","fps":30,"duration_sec":6,
      "images":[
        {"image":"/static/demo/img_1_1.jpg"},
        {"image":"/static/demo/img_4_5.jpg"}
      ]
    }'
    ;;
  *)
    echo "Usage: $0 [image|carousel|video]" >&2; exit 2;;
esac

# ---- Render ----
RENDER_RESP=$(curl -s -X POST "$BASE/previews/render" \
  -H "$AUTHZ" -H "Content-Type: application/json" -d "$PAYLOAD")

echo "=== render ==="
echo "$RENDER_RESP" | jq

# Πάρε preview url ανά τύπο (image: preview_url, carousel: sheet_url, video: mp4_url)
PREVIEW_URL=$(echo "$RENDER_RESP" | jq -r '.preview_url // .sheet_url // .mp4_url // empty')
if [[ -z "$PREVIEW_URL" ]]; then
  echo "❌ No preview_url/sheet_url/mp4_url found in render response" >&2
  exit 1
fi
echo "✅ Using preview: $PREVIEW_URL"

# ---- Commit ----
COMMIT_RESP=$(jq -Rn --arg p "$PREVIEW_URL" '{preview_url:$p}' |
  curl -s -X POST "$BASE/previews/commit" \
       -H "$AUTHZ" -H "Content-Type: application/json" \
       -d @-)

echo "=== commit ==="
echo "$COMMIT_RESP" | jq
