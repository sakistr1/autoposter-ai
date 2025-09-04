#!/usr/bin/env bash
set -u  # να μην περνάνε άδεια vars (αλλά να μην σταματάει όλο το script)

BASE="http://127.0.0.1:8000"
DB="autoposter.db"

# ΦΡΕΣΚΟ TOKEN (από εσένα)
TOKEN='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZW1vMTBAZ21haWwuY29tIiwiZXhwIjoxNzU2MDMzMjAwfQ.hmJ4mgETlvQa_Mq6ZVVcTCx-4ci5pCU3dwk6eWRYn20'
export TOKEN
AHDR=(-H "Authorization: Bearer $TOKEN")

step(){ echo -e "\n### $1"; shift; bash -lc "$*" 2>&1 | sed 's/^/   /' || true; }

# 0) email από token (debug)
EMAIL=$(python3 - <<'PY'
import os, json, base64
tok=os.environ["TOKEN"]; p = tok.split('.')[1] + '=='
print(json.loads(base64.urlsafe_b64decode(p)).get('sub'))
PY
)
echo "EMAIL=$EMAIL"
echo "Token length=${#TOKEN}"

# 1) βασικά
step "healthz"          'curl -s "$BASE/healthz" | jq .'
step "openapi paths"    'curl -s "$BASE/openapi.json" | jq ".paths | keys"'
step "static HEADs"     'curl -sI "$BASE/auth.html" | sed -n "1,4p"; curl -sI "$BASE/dashboard.html" | sed -n "1,4p"'

# 2) templates -> λίστα
step "tengine/templates" 'curl -s "${AHDR[@]}" "$BASE/tengine/templates" | jq .'

# 3) render (χρησιμοποιώ template_id=1, ratio 4:5)
cat >/tmp/render.json <<'JSON'
{
  "template_id": 1,
  "ratio": "4:5",
  "data": {
    "title": "Demo Προϊόν — Ακουστικά",
    "price": "€39.90",
    "brand_color": "#0fbf91",
    "image_url": "https://picsum.photos/id/1062/1500/2000"
  }
}
JSON
step "previews/render"  'curl -s -X POST "$BASE/previews/render" "${AHDR[@]}" -H "Content-Type: application/json" -d @/tmp/render.json | tee /tmp/render_out.json | jq .'

# Απόσπαση preview_id (με fallback από url)
PID=$(jq -r '.preview_id // empty' /tmp/render_out.json)
if [ -z "$PID" ]; then
  PURL=$(jq -r '.preview_url // .url // empty' /tmp/render_out.json)
  [ -n "$PURL" ] && PID=$(basename "$PURL" .png)
fi
echo "PID=$PID"

# 4) commit αν υπάρχει PID
if [ -n "$PID" ]; then
  jq -n --arg pid "$PID" --arg c "ok!" '{preview_id:$pid, caption:$c}' >/tmp/commit.json
  step "previews/commit" 'curl -s -X POST "$BASE/previews/commit" "${AHDR[@]}" -H "Content-Type: application/json" -d @/tmp/commit.json | tee /tmp/commit_out.json | jq .'
  FINAL=$(jq -r '(.final_url // .urls[0] // .image_url // .media_urls[0] // empty)' /tmp/commit_out.json)
  echo "FINAL=$FINAL"
  [ -n "$FINAL" ] && curl -sI "$BASE$FINAL" | sed -n '1,5p'
else
  echo "SKIP commit: no preview_id"
fi

# 5) credits / debit (στον server σου είναι GET)
step "me/credits (before)" 'curl -s "${AHDR[@]}" "$BASE/me/credits" | jq .'
step "me/use-credit"       'curl -s "${AHDR[@]}" "$BASE/me/use-credit" | jq .'
step "me/credits (after)"  'curl -s "${AHDR[@]}" "$BASE/me/credits" | jq .'

# 6) uploads (logo + product images)
curl -sL https://picsum.photos/seed/logo/300/300 -o /tmp/logo.png
curl -sL https://picsum.photos/seed/p1/800/800  -o /tmp/img1.jpg
curl -sL https://picsum.photos/seed/p2/800/800  -o /tmp/img2.jpg

step "upload_logo" 'curl -s -X POST "$BASE/upload_logo" "${AHDR[@]}" -F "file=@/tmp/logo.png" | jq .'

DB_UID=$(sqlite3 "$DB" "SELECT id FROM users WHERE email='$EMAIL' LIMIT 1;")
PROD_ID=$(sqlite3 "$DB" "INSERT INTO products (name, owner_id, price) VALUES ('CLI Demo', $DB_UID, '€9.99'); SELECT last_insert_rowid();")
echo "PROD_ID=$PROD_ID"

step "upload_product_images" 'curl -s -X POST "$BASE/upload_product_images" "${AHDR[@]}" -F "product_id='"$PROD_ID"'" -F "files=@/tmp/img1.jpg" -F "files=@/tmp/img2.jpg" | jq .'

# 7) mapping resolve (προαιρετικό)
cat >/tmp/resolve.json <<'JSON'
{ "node": "image_left" }
JSON
step "tengine/mapping/resolve" 'curl -s -X POST "$BASE/tengine/mapping/resolve" "${AHDR[@]}" -H "Content-Type: application/json" -d @/tmp/resolve.json | jq .'

echo -e "\n=== DONE ==="
