#!/usr/bin/env bash
# Smoke test: shortlinks > (302 μόνο, χωρίς follow) > render με QR > commit > ιστορικό

set -Eeuo pipefail
trap 'echo; echo "ERROR στη γραμμή $LINENO: $BASH_COMMAND"; exit 1' ERR

# === ΒΑΛΕ ΤΟ ΦΡΕΣΚΟ TOKEN ΣΟΥ ===
TOKEN='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZW1vMTBAZ21haWwuY29tIiwiZXhwIjoxNzU2NzUwNTMxfQ.xpvmIjAnmjFi7Nudqmgo3ltNyBmcU5SzhasBYbDE96k'

# === Ρυθμίσεις backend / demo προϊόντος ===
BASE="http://127.0.0.1:8000"
IMG="/static/uploads/products/123.jpg"
PRODUCT_URL="https://shop.example.com/p/sku-777"   # demo URL — δεν χρειάζεται να λύνει DNS

need() { command -v "$1" >/dev/null || { echo "Λείπει: $1"; exit 1; }; }
need curl
need jq

[[ -z "${TOKEN:-}" ]] && { echo "Δεν έχεις ορίσει TOKEN"; exit 1; }

echo "== 1) Δημιουργία shortlink =="; echo
SL=$(
  curl -sS -X POST "$BASE/shortlinks" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"url\":\"$PRODUCT_URL\"}"
)
echo "$SL" | jq .
CODE=$(echo "$SL" | jq -r .code)
[[ "$CODE" == "null" || -z "$CODE" ]] && { echo "Απέτυχε δημιουργία shortlink (μάλλον token)"; exit 1; }
echo "CODE=$CODE"

echo; echo "== 2) Έλεγχος redirect ΧΩΡΙΣ follow =="; echo
# Παίρνουμε ΜΟΝΟ το πρώτο response (302). Δεν ακολουθούμε redirs > δεν γίνεται DNS resolve στο demo domain.
HDRS=$(curl -sS -D - -o /dev/null --max-redirs 0 "$BASE/go/$CODE" || true)
echo "$HDRS" | sed -n '1,12p'
HTTP302=$(echo "$HDRS" | awk 'NR==1{print $2}')
if [[ "$HTTP302" != "302" ]]; then
  echo "Περίμενα 302, πήρα: $HTTP302"; exit 1
fi
LOCATION=$(echo "$HDRS" | awk '/^location:/I{print $2}')
echo "Location header: $LOCATION"

echo; echo "== 3) Render εικόνας με QR (χρησιμοποιεί shortlink) =="; echo
R=$(
  curl -sS -X POST "$BASE/previews/render" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"type\":\"image\",
      \"ratio\":\"4:5\",
      \"platform\":\"instagram\",
      \"mode\":\"Κανονικό\",
      \"title\":\"Shortlink QR Test\",
      \"target_url\":\"$PRODUCT_URL\",
      \"qr\":true,
      \"product_image_url\":\"$IMG\"
    }"
)
echo "$R" | jq .
RAW_PREV=$(echo "$R" | jq -r .preview_url)
PREV_URL=$(echo "$R" | jq -r '.absolute_url // ("'"$BASE"'" + .preview_url)')
[[ "$RAW_PREV" == "null" || -z "$RAW_PREV" ]] && { echo "Απέτυχε render"; exit 1; }
echo "Preview URL: $PREV_URL"

echo; echo "== 4) Commit preview =="; echo
C=$(
  curl -sS -X POST "$BASE/previews/commit" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"preview_url\":\"$RAW_PREV\"}"
)
echo "$C" | jq .

echo; echo "== 5) Ιστορικό (τελευταία 5) =="; echo
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$BASE/previews/committed?limit=5&offset=0" | jq .

echo; echo "? Τέλος. Άνοιξε: $PREV_URL"

# Για να μην κλείνει παράθυρο αν το τρέξεις με διπλό κλικ:
read -rp "Πάτα Enter για έξοδο… " _ || true
