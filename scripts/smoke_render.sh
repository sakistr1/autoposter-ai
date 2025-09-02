#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000}"
: "${TOKEN:?Set TOKEN first: export TOKEN=...}"
AUTHZ="Authorization: Bearer $TOKEN"

echo "== healthz & credits =="
curl -s -H "$AUTHZ" "$BASE/healthz"          | jq -r .
curl -s -H "$AUTHZ" "$BASE/me/credits"       | jq -r .

echo "== render 4:5 =="
RID_JSON=$(
  curl -s -X POST "$BASE/previews/render" \
    -H "$AUTHZ" -H "Content-Type: application/json" \
    -d '{
      "use_renderer": true, "ratio":"4:5", "mode":"normal",
      "image_url": "/static/demo/img_4_5.jpg",
      "mapping": {
        "title": "Demo",
        "price": "19.90€",
        "old_price": "29.90€",
        "cta": "ΑΓΟΡΑ ΤΩΡΑ",
        "logo_url": "/static/demo/logo.png",
        "discount_badge": true
      }
    }'
)

echo "$RID_JSON" | jq '{status,overlay_applied,logo_applied,discount_badge_applied,cta_applied,slots_used,preview_url}'
PREVIEW_ID=$(echo "$RID_JSON" | jq -r '.preview_id // empty')
if [[ -z "$PREVIEW_ID" ]]; then
  echo "Render failed (no preview_id)"; exit 1
fi

echo "== commit =="
CMT=$(
  curl -s -X POST "$BASE/previews/commit" \
    -H "$AUTHZ" -H "Content-Type: application/json" \
    -d "{\"preview_id\":\"$PREVIEW_ID\"}"
)
echo "$CMT" | jq -r '{status,ok,preview_id,committed_url,absolute_url,remaining_credits}'

echo "== render video (2 frames) =="
VID=$(
  curl -s -X POST "$BASE/previews/render" \
    -H "$AUTHZ" -H "Content-Type: application/json" \
    -d "{
      \"mode\":\"video\",\"fps\":30,\"duration_sec\":6,
      \"images\":[
        {\"image\":\"/static/demo/img_1_1.jpg\"},
        {\"image\":\"/static/demo/img_4_5.jpg\"}
      ]
    }"
)
echo "$VID" | jq '{status,mode,preview_url,poster_url}'
