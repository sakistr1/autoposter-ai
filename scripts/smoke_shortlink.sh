#!/usr/bin/env bash
# Smoke test: shortlinks > (302 ����, ����� follow) > render �� QR > commit > ��������

set -Eeuo pipefail
trap 'echo; echo "ERROR ��� ������ $LINENO: $BASH_COMMAND"; exit 1' ERR

# === ���� �� ������ TOKEN ��� ===
TOKEN='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZW1vMTBAZ21haWwuY29tIiwiZXhwIjoxNzU2NzUwNTMxfQ.xpvmIjAnmjFi7Nudqmgo3ltNyBmcU5SzhasBYbDE96k'

# === ��������� backend / demo ��������� ===
BASE="http://127.0.0.1:8000"
IMG="/static/uploads/products/123.jpg"
PRODUCT_URL="https://shop.example.com/p/sku-777"   # demo URL � ��� ���������� �� ����� DNS

need() { command -v "$1" >/dev/null || { echo "������: $1"; exit 1; }; }
need curl
need jq

[[ -z "${TOKEN:-}" ]] && { echo "��� ����� ������ TOKEN"; exit 1; }

echo "== 1) ���������� shortlink =="; echo
SL=$(
  curl -sS -X POST "$BASE/shortlinks" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"url\":\"$PRODUCT_URL\"}"
)
echo "$SL" | jq .
CODE=$(echo "$SL" | jq -r .code)
[[ "$CODE" == "null" || -z "$CODE" ]] && { echo "������� ���������� shortlink (������ token)"; exit 1; }
echo "CODE=$CODE"

echo; echo "== 2) ������� redirect ����� follow =="; echo
# ��������� ���� �� ����� response (302). ��� ����������� redirs > ��� ������� DNS resolve ��� demo domain.
HDRS=$(curl -sS -D - -o /dev/null --max-redirs 0 "$BASE/go/$CODE" || true)
echo "$HDRS" | sed -n '1,12p'
HTTP302=$(echo "$HDRS" | awk 'NR==1{print $2}')
if [[ "$HTTP302" != "302" ]]; then
  echo "�������� 302, ����: $HTTP302"; exit 1
fi
LOCATION=$(echo "$HDRS" | awk '/^location:/I{print $2}')
echo "Location header: $LOCATION"

echo; echo "== 3) Render ������� �� QR (������������ shortlink) =="; echo
R=$(
  curl -sS -X POST "$BASE/previews/render" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"type\":\"image\",
      \"ratio\":\"4:5\",
      \"platform\":\"instagram\",
      \"mode\":\"��������\",
      \"title\":\"Shortlink QR Test\",
      \"target_url\":\"$PRODUCT_URL\",
      \"qr\":true,
      \"product_image_url\":\"$IMG\"
    }"
)
echo "$R" | jq .
RAW_PREV=$(echo "$R" | jq -r .preview_url)
PREV_URL=$(echo "$R" | jq -r '.absolute_url // ("'"$BASE"'" + .preview_url)')
[[ "$RAW_PREV" == "null" || -z "$RAW_PREV" ]] && { echo "������� render"; exit 1; }
echo "Preview URL: $PREV_URL"

echo; echo "== 4) Commit preview =="; echo
C=$(
  curl -sS -X POST "$BASE/previews/commit" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"preview_url\":\"$RAW_PREV\"}"
)
echo "$C" | jq .

echo; echo "== 5) �������� (��������� 5) =="; echo
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$BASE/previews/committed?limit=5&offset=0" | jq .

echo; echo "? �����. ������: $PREV_URL"

# ��� �� ��� ������� �������� �� �� ������� �� ����� ����:
read -rp "���� Enter ��� ����� " _ || true
