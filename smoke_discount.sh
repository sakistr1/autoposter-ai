#!/usr/bin/env bash
set -euo pipefail

BASE="http://127.0.0.1:8000"
AUTHZ="Authorization: Bearer $TOKEN"

echo "== Render (image 4:5 με discount/CTA/QR) =="

RENDER_PAYLOAD=$(cat <<'JSON'
{
  "type": "image",
  "ratio": "4:5",
  "platform": "instagram",
  "mode": "Επαγγελματικό",
  "title": "Ασύρματα ακουστικά Pro",
  "price": "€79",
  "old_price": "€129",
  "new_price": "€79",
  "cta_text": "Δες το τώρα",
  "target_url": "https://shop.example.com/p/123?src=ig",
  "qr": true
}
JSON
)

R=$(curl -s -X POST "$BASE/previews/render" \
      -H "$AUTHZ" -H "Content-Type: application/json" \
      -d "$RENDER_PAYLOAD")

echo "$R" | jq .

PREVIEW_ID=$(echo "$R" | jq -r '.preview_id // .id // .preview.id // empty')
PREVIEW_URL=$(echo "$R" | jq -r '.preview_url // .url // .preview_url // empty')

if [ -z "$PREVIEW_ID" ]; then
  echo "!! Δεν βρέθηκε preview_id στην απόκριση."
  exit 2
fi

echo "Preview ID: $PREVIEW_ID"
[ -n "$PREVIEW_URL" ] && echo "Preview URL: $PREVIEW_URL"

echo "== Commit (θα χρεώσει credits) =="
C=$(curl -s -X POST "$BASE/previews/commit" \
      -H "$AUTHZ" -H "Content-Type: application/json" \
      -d "{\"preview_id\":\"$PREVIEW_ID\"}")

echo "$C" | jq .

COMMITTED_URL=$(echo "$C" | jq -r '.committed_url // .url // .absolute_url // empty')
[ -n "$COMMITTED_URL" ] && echo "Committed URL: $COMMITTED_URL"

echo "== Τελευταία committed =="
curl -s -H "$AUTHZ" "$BASE/previews/committed?limit=5&offset=0" | jq .
