#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000}"

# ---- Πηγή TOKEN: env > .token > 1ο arg ----
if [[ -z "${TOKEN:-}" ]]; then
  if [[ -f .token ]]; then
    TOKEN="$(< .token)"
  elif [[ $# -ge 1 ]]; then
    TOKEN="$1"
  else
    echo "Δώσε TOKEN: είτε με env (TOKEN=...), είτε αποθήκευσέ το σε ./.token, είτε ως 1ο arg."
    echo "Παράδειγμα: TOKEN=eyJ... ./scripts/smoke_e2e.sh"
    exit 1
  fi
fi

AHDR=(-H "Authorization: Bearer $TOKEN")

# ---- 1) RENDER ----
cat >/tmp/render.json <<'JSON'
{
  "platform": "instagram",
  "ratio": "1:1",
  "mode": "normal",
  "template": "clean",
  "title": "Demo Προϊόν",
  "new_price": "29.90",
  "old_price": "49.90",
  "image_url": "http://127.0.0.1:8000/static/demo/shoes1.webp",
  "brand_logo_url": "",
  "purchase_url": "https://example.com/p/123",
  "cta_label": "Αγορά τώρα"
}
JSON

echo "== 1) POST /previews/render"
curl -sS -o /tmp/render.out.json -w "HTTP %{http_code}\n" \
  -X POST "$BASE/previews/render" "${AHDR[@]}" \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/render.json

PREVIEW_ID=$(jq -r '.preview_id // .id // empty' /tmp/render.out.json)
PREVIEW_URL_ABS=$(jq -r '.absolute_url // .preview_url // .url // empty' /tmp/render.out.json)
[[ -z "$PREVIEW_URL_ABS" ]] && { echo "Render απέτυχε: /tmp/render.out.json"; cat /tmp/render.out.json; exit 2; }

PREVIEW_URL_REL=$(echo "$PREVIEW_URL_ABS" | sed -E 's@^https?://[^/]+@@')
echo "PREVIEW_ID=$PREVIEW_ID"
echo "PREVIEW_URL_REL=$PREVIEW_URL_REL"

echo "== HEAD preview"
curl -sI "$PREVIEW_URL_ABS" | head -n1

# ---- 2) COMMIT (πάντα relative url) ----
if [[ -n "$PREVIEW_ID" ]]; then
  cat > /tmp/commit.json <<EOF
{ "preview_id": "$PREVIEW_ID", "preview_url": "$PREVIEW_URL_REL" }
EOF
else
  cat > /tmp/commit.json <<EOF
{ "preview_url": "$PREVIEW_URL_REL" }
EOF
fi

echo "== 2) POST /previews/commit"
curl -sS -o /tmp/commit.out.json -w "HTTP %{http_code}\n" \
  -X POST "$BASE/previews/commit" "${AHDR[@]}" \
  -H "Content-Type: application/json" \
  --data-binary @/tmp/commit.json

COMMITTED_URL=$(jq -r '.absolute_url // .committed_url // empty' /tmp/commit.out.json)
[[ -z "$COMMITTED_URL" ]] && { echo "Commit απέτυχε: /tmp/commit.out.json"; cat /tmp/commit.out.json; exit 3; }
echo "COMMITTED_URL=$COMMITTED_URL"

echo "== HEAD committed"
curl -sI "$COMMITTED_URL" | head -n1

# ---- 3) Ιστορικό ----
echo "== 3) GET /previews/committed?limit=5"
curl -s "${AHDR[@]}" "$BASE/previews/committed?limit=5" \
  | jq '.count, .images[0] // .results[0] // .items[0].urls[0]'
