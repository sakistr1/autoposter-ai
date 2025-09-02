#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   TOKEN="eyJ..." scripts/smoke_shortlink.sh
# �
#   scripts/smoke_shortlink.sh --login           # �� ����� token �� demo user
#
# ������������: jq

BASE="${BASE:-http://127.0.0.1:8000}"
TMP="${TMPDIR:-/tmp}"
PR_JSON="$TMP/pr_short.json"

need_jq() { command -v jq >/dev/null 2>&1 || { echo "ERROR: ���������� 'jq'"; exit 1; }; }

get_token_via_login() {
  echo "== LOGIN -> TOKEN (demo10)"
  TOKEN="$(curl -sS -X POST "$BASE/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"demo10@gmail.com","password":"demo10"}' | jq -r '.access_token')"
  if [[ -z "${TOKEN:-}" || "$TOKEN" == "null" ]]; then
    echo "ERROR: ��� ������ access_token ��� /login"; exit 1
  fi
  export TOKEN
}

if [[ "${1:-}" == "--login" ]]; then
  need_jq
  get_token_via_login
fi

if [[ -z "${TOKEN:-}" ]]; then
  echo "ERROR: ���� TOKEN (�.�. TOKEN=\"...\" scripts/smoke_shortlink.sh) � ����� �� --login"
  exit 1
fi

need_jq

echo "== 1) RENDER �� QR + auto-shortlink"
curl -sS -X POST "$BASE/previews/render" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "mode":"normal","ratio":"4:5",
        "ai_bg":"remove",
        "qr": true,
        "target_url":"https://shop.example.com/p/sku-777",
        "image_url":"/static/demo/outfit1.webp",
        "mapping":{"title":"Shortlink Test","price":"99.90","cta":"�������"}
      }' \
  | tee "$PR_JSON" >/dev/null

SHORT_URL="$(jq -r '.short_url // empty' "$PR_JSON")"
PREVIEW_URL="$(jq -r '.preview_url // .url // empty' "$PR_JSON")"

if [[ -z "$SHORT_URL" ]]; then
  echo "ERROR: ��� ����������� short_url ��� render"; exit 1
fi
if [[ -z "$PREVIEW_URL" ]]; then
  echo "ERROR: ��� ������� preview_url ��� render"; exit 1
fi

CODE="${SHORT_URL##*/go/}"

echo "   short_url: $SHORT_URL"
echo "   preview_url: $PREVIEW_URL"

echo "== 2) ������� 302 (redirect) ��� /go/$CODE"
curl -sS -D - -o /dev/null --max-redirs 0 "$BASE/go/$CODE" | sed -n '1,5p'

echo "== 3) COMMIT (�� ������� credits)"
curl -sS -X POST "$BASE/previews/commit" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"preview_url\":\"$PREVIEW_URL\"}" \
  | tee "$TMP/commit_short.json" >/dev/null

echo "== 4) CREDITS"
curl -sS -H "Authorization: Bearer $TOKEN" "$BASE/previews/me/credits" | jq .

echo "OK ?  (render>shortlink>302>commit>credits)"
