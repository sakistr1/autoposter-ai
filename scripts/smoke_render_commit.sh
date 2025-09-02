#!/usr/bin/env bash
set -euo pipefail

# --- Config / defaults ---
BASE="${BASE:-http://127.0.0.1:8000}"
AUTHZ="${AUTHZ:-}"
RATIO="${RATIO:-4:5}"
MODE="${MODE:-normal}"
IMAGE_URL="${IMAGE_URL:-/static/demo/img_4_5.jpg}"

# mapping (override με env αν θέλεις)
TITLE="${TITLE:-Demo}"
PRICE="${PRICE:-19.90€}"
OLD_PRICE="${OLD_PRICE:-29.90€}"
CTA="${CTA:-ΑΓΟΡΑ ΤΩΡΑ}"
LOGO_URL="${LOGO_URL:-/static/demo/logo.png}"
DISCOUNT_BADGE="${DISCOUNT_BADGE:-true}"

# --- Helpers ---
need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing dependency: $1" >&2; exit 1; }; }

need curl
need jq

if [[ -z "$AUTHZ" ]]; then
  echo "AUTHZ header is empty. Κάνε: export AUTHZ=\"Authorization: Bearer <TOKEN>\"" >&2
  exit 1
fi

echo "== Render =="
RENDER_JSON=$(
  curl -s -X POST "$BASE/previews/render" \
    -H "$AUTHZ" -H "Content-Type: application/json" \
    -d @- <<JSON
{
  "use_renderer": true,
  "ratio": "${RATIO}",
  "mode": "${MODE}",
  "image_url": "${IMAGE_URL}",
  "mapping": {
    "title": "${TITLE}",
    "price": "${PRICE}",
    "old_price": "${OLD_PRICE}",
    "cta": "${CTA}",
    "logo_url": "${LOGO_URL}",
    "discount_badge": ${DISCOUNT_BADGE}
  }
}
JSON
)

echo "$RENDER_JSON" | jq '{status,overlay_applied,logo_applied,discount_badge_applied,cta_applied,slots_used,preview_url}'

PREVIEW_URL=$(echo "$RENDER_JSON" | jq -r '.preview_url // empty')

if [[ -z "$PREVIEW_URL" || "$PREVIEW_URL" == "null" ]]; then
  echo "❌ Δεν βρέθηκε preview_url στην απόκριση." >&2
  exit 2
fi

echo
echo "== Commit =="
COMMIT_JSON=$(
  curl -s -X POST "$BASE/previews/commit" \
    -H "$AUTHZ" -H "Content-Type: application/json" \
    -d "{\"preview_url\":\"${PREVIEW_URL}\"}"
)

echo "$COMMIT_JSON" | jq '{ok,status,preview_id,committed_url,absolute_url,remaining_credits}'

echo
echo "== Summary =="
echo "Preview : $PREVIEW_URL"
echo "Committed: $(echo "$COMMIT_JSON" | jq -r '.committed_url // empty')"
