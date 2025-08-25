#!/usr/bin/env bash
set -u  # όχι -e, για να μην σταματάει μεμονωμένο βήμα

BASE="http://127.0.0.1:8000"

# === ΦΡΕΣΚΟ TOKEN ===
TOKEN='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZW1vMTBAZ21haWwuY29tIiwiZXhwIjoxNzU2MDQwNDAxfQ.Vs0e_LR1vSZ2O2_w4pjmzNAR9BxDdFZmSetqZrBpjPk'
export TOKEN
AHDR=(-H "Authorization: Bearer $TOKEN")

step(){ echo -e "\n### $1"; shift; bash -lc "$*" 2>&1 | sed 's/^/   /' || true; }

# --- Βρες το σωστό DB που χρησιμοποιεί ο uvicorn (fallback στο project) ---
PID_UV=$(pgrep -f 'uvicorn.*main:app' | head -1 || true)
DB_PATH=""
[ -n "${PID_UV:-}" ] && DB_PATH=$(lsof -p "$PID_UV" 2>/dev/null | awk '/autoposter\.db$/ {print $9; exit}')
[ -z "$DB_PATH" ] && DB_PATH="$HOME/autoposter-ai/autoposter.db"

step "DB used by server" 'echo "$DB_PATH"; sqlite3 "$DB_PATH" ".tables"'

# --- Email από token (για lookups στο DB) ---
EMAIL=$(python3 - <<'PY'
import os, json, base64
tok=os.environ['TOKEN']; p = tok.split('.')[1] + '=='
print(json.loads(base64.urlsafe_b64decode(p)).get('sub'))
PY
)
echo "EMAIL=$EMAIL"

# --- Υγεία/API ---
step "healthz"         'curl -s "$BASE/healthz" | jq .'
step "openapi paths"   'curl -s "$BASE/openapi.json" | jq ".paths | keys | length"'
step "templates list"  'curl -s "${AHDR[@]}" "$BASE/tengine/templates" | jq .'

# --- PREVIEW: render ---
cat >/tmp/render.json <<'JSON'
{
  "template_id": 1,
  "ratio": "4:5",
  "data": {
    "title": "Demo Product - Headphones",
    "price": "EUR 39.90",
    "brand_color": "#0fbf91",
    "image_url": "https://picsum.photos/id/1062/1500/2000"
  }
}
JSON

step "previews/render" '
  curl -sS -X POST "$BASE/previews/render" "${AHDR[@]}" -H "Content-Type: application/json" -d @/tmp/render.json | tee /tmp/render_resp.json | jq .
'
PID=$(jq -r '.preview_id // empty' /tmp/render_resp.json)
PURL=$(jq -r '.preview_url // empty' /tmp/render_resp.json)
echo "PID=$PID | PURL=$PURL"
if [ -z "$PID" ]; then
  echo "!! No preview_id — stop."; exit 0
fi

# --- CREDITS: δες, αν είναι 0 κάνε top-up (+5) από sqlite ---
step "me/credits (before)" 'curl -s "${AHDR[@]}" "$BASE/me/credits" | jq .'
DB_UID=$(sqlite3 "$DB_PATH" "SELECT id FROM users WHERE email='$EMAIL' LIMIT 1;")
if [ -n "$DB_UID" ]; then
  sqlite3 "$DB_PATH" "UPDATE users SET credits=MAX(5, COALESCE(credits,0)) WHERE id=$DB_UID;"
fi
step "me/credits (after +topup if needed)" 'curl -s "${AHDR[@]}" "$BASE/me/credits" | jq .'

# --- COMMIT (καταναλώνει 1 credit) ---
printf '{"preview_id":"%s","caption":"ok!"}\n' "$PID" >/tmp/commit.json
step "previews/commit" '
  curl -sS -X POST "$BASE/previews/commit" "${AHDR[@]}" -H "Content-Type: application/json" -d @/tmp/commit.json | tee /tmp/commit_resp.json | jq .
'
step "previews/committed (last 5)" 'curl -s "${AHDR[@]}" "$BASE/previews/committed?limit=5" | jq .'

# --- UPLOADS: sample εικόνες ---
step "download sample images" '
  curl -sL "https://picsum.photos/seed/brand/800/800" -o /tmp/logo.png ;
  curl -sL "https://picsum.photos/seed/p2/800/800"   -o /tmp/img1.jpg ;
  curl -sL "https://picsum.photos/seed/p3/800/800"   -o /tmp/img2.jpg ;
  ls -lh /tmp/logo.png /tmp/img1.jpg /tmp/img2.jpg
'

# --- UPLOAD logo ---
step "upload_logo" '
  curl -sS -X POST "$BASE/upload_logo" "${AHDR[@]}" \
       -F "file=@/tmp/logo.png" | tee /tmp/logo_resp.json | jq .
'

# --- Product row στο DB (αν λείπει) ---
DB_UID=$(sqlite3 "$DB_PATH" "SELECT id FROM users WHERE email='$EMAIL' LIMIT 1;")
if [ -z "$DB_UID" ]; then
  echo "!! Δεν βρέθηκε user για $EMAIL στο DB ($DB_PATH) — σταματάω τα product uploads."
  echo "   Δείξε μου: sqlite3 \"$DB_PATH\" 'SELECT id,email,credits FROM users;'"
  exit 0
fi

PROD_ID=$(sqlite3 "$DB_PATH" "
  SELECT id FROM products WHERE owner_id=$DB_UID ORDER BY id DESC LIMIT 1;
")
if [ -z "$PROD_ID" ]; then
  PROD_ID=$(sqlite3 "$DB_PATH" "
    INSERT INTO products (name, owner_id, price) VALUES ('Smoke Demo', $DB_UID, '€9.99');
    SELECT last_insert_rowid();
  ")
fi
echo "PROD_ID=$PROD_ID"

# --- UPLOAD product images ---
step "upload_product_images" '
  curl -sS -X POST "$BASE/upload_product_images" "${AHDR[@]}" \
       -F "product_id='"$PROD_ID"'" -F "files=@/tmp/img1.jpg" -F "files=@/tmp/img2.jpg" \
  | jq .
'

echo -e "\n=== DONE ==="
