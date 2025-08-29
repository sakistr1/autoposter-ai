#!/usr/bin/env bash
set -u  # μην περνάνε άδεια vars

BASE="http://127.0.0.1:8000"
DB="autoposter.db"

# Φρέσκο token (από εσένα)
TOKEN='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZW1vMTBAZ21haWwuY29tIiwiZXhwIjoxNzU2MDMzMjAwfQ.hmJ4mgETlvQa_Mq6ZVVcTCx-4ci5pCU3dwk6eWRYn20'
export TOKEN
AHDR=(-H "Authorization: Bearer $TOKEN")

# Μικρός helper: τρέξε εντολή και τύπωσε ωραία
step(){ echo -e "\n### $1"; shift; bash -lc "$*" 2>&1 | sed 's/^/   /' || true; }

# Email από token (debug)
EMAIL=$(python3 - <<'PY'
import os, json, base64
tok=os.environ["TOKEN"]; p=tok.split('.')[1]+'=='
print(json.loads(base64.urlsafe_b64decode(p)).get('sub'))
PY
)
echo "EMAIL=$EMAIL | token_len=${#TOKEN}"

# Basic checks
step "healthz"          'curl -s "$BASE/healthz" | jq .'
step "openapi paths"    'curl -s "$BASE/openapi.json" | jq ".paths | keys"'
step "static HEADs"     'curl -sI "$BASE/auth.html" | sed -n "1,4p"; echo; curl -sI "$BASE/dashboard.html" | sed -n "1,4p"'

# Templates (idempotent)
step "tengine/templates/register" 'curl -s -X POST "$BASE/tengine/templates/register" "${AHDR[@]}" | jq .'
step "tengine/templates"          'curl -s "$BASE/tengine/templates" "${AHDR[@]}" | jq .'

# -------- Render --------
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

# Πιάσε JSON & HTTP code ΧΩΡΙΣ να χαλάει το output
echo -e "\n### previews/render (raw)"
CODE=$(curl -sS -o /tmp/render.out.json -w "%{http_code}" -X POST "$BASE/previews/render" "${AHDR[@]}" -H "Content-Type: application/json" -d @/tmp/render.json)
cat /tmp/render.out.json | jq . 2>/dev/null || cat /tmp/render.out.json
echo "HTTP=$CODE"

if [ "$CODE" != "200" ]; then
  echo "Render FAILED (HTTP $CODE). STOP."
  exit 0
fi

PID=$(jq -r '.preview_id // empty' /tmp/render.out.json)
if [ -z "$PID" ]; then
  PURL=$(jq -r '.preview_url // .url // empty' /tmp/render.out.json)
  [ -n "$PURL" ] && PID=$(basename "$PURL" .png)
fi
echo "PID=$PID"
[ -z "$PID" ] && echo "No preview_id → STOP." && exit 0

# -------- Commit --------
jq -n --arg pid "$PID" --arg c "ok!" '{preview_id:$pid, caption:$c}' >/tmp/commit.json
echo -e "\n### previews/commit (raw)"
CODE=$(curl -sS -o /tmp/commit.out.json -w "%{http_code}" -X POST "$BASE/previews/commit" "${AHDR[@]}" -H "Content-Type: application/json" -d @/tmp/commit.json)
cat /tmp/commit.out.json | jq . 2>/dev/null || cat /tmp/commit.out.json
echo "HTTP=$CODE"

FINAL=$(jq -r '(.final_url // .urls[0] // .image_url // .media_urls[0] // empty)' /tmp/commit.out.json)
[ -n "$FINAL" ] && echo -e "\nHEAD $FINAL" && curl -sI "$BASE$FINAL" | sed -n '1,5p'

# -------- Credits --------
step "me/credits (before)" 'curl -s "${AHDR[@]}" "$BASE/me/credits" | jq .'
step "me/use-credit"       'curl -s "${AHDR[@]}" "$BASE/me/use-credit" | jq .'
step "me/credits (after)"  'curl -s "${AHDR[@]}" "$BASE/me/credits" | jq .'

# -------- Uploads --------
curl -sL https://picsum.photos/seed/logo/300/300 -o /tmp/logo.png
curl -sL https://picsum.photos/seed/p1/800/800  -o /tmp/img1.jpg
curl -sL https://picsum.photos/seed/p2/800/800  -o /tmp/img2.jpg

step "upload_logo" 'curl -s -X POST "$BASE/upload_logo" "${AHDR[@]}" -F "file=@/tmp/logo.png" | jq .'

DB_UID=$(sqlite3 "$DB" "SELECT id FROM users WHERE email='$EMAIL' LIMIT 1;")
echo "DB_UID=$DB_UID"
if [ -z "$DB_UID" ]; then
  echo "!!! ΔΕΝ βρέθηκε χρήστης στη $DB για $EMAIL. Δείξε μου:"
  echo "  pwd; ls -l autoposter.db; sqlite3 autoposter.db \"SELECT id,email FROM users;\""
  echo "STOP uploads."
  exit 0
fi

PROD_ID=$(sqlite3 "$DB" "INSERT INTO products (name, owner_id, price) VALUES ('CLI Demo', $DB_UID, '€9.99'); SELECT last_insert_rowid();")
echo "PROD_ID=$PROD_ID"

step "upload_product_images" \
  'curl -s -X POST "$BASE/upload_product_images" "${AHDR[@]}" -F "product_id='"$PROD_ID"'" -F "files=@/tmp/img1.jpg" -F "files=@/tmp/img2.jpg" | jq .'

# -------- mapping resolve (optional) --------
cat >/tmp/resolve.json <<'JSON'
{ "node": "image_left" }
JSON
step "tengine/mapping/resolve" 'curl -s -X POST "$BASE/tengine/mapping/resolve" "${AHDR[@]}" -H "Content-Type: application/json" -d @/tmp/resolve.json | jq .'

echo -e "\n=== DONE ==="
