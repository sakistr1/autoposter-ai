#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8000}"
: "${TOKEN:?Set TOKEN env var (e.g. TOKEN='Bearer eyJ...')}"
AUTHZ="Authorization: $TOKEN"; CT="Content-Type: application/json"

echo "== /health"; curl -sS "$BASE/health" | jq .

echo "== Normal OK -> preview"; 
R=$(curl -sS -X POST "$BASE/previews/render" -H "$AUTHZ" -H "$CT" \
  -d '{"mode":"Κανονικό","ratio":"4:5","image_url":"static/demo/laptop.jpg"}')
echo "$R" | jq .
PREV=$(echo "$R" | jq -r .preview_id)

echo "== commit"; curl -sS -X POST "$BASE/previews/commit" -H "$AUTHZ" -H "$CT" \
  -d "{\"preview_id\":\"$PREV\"}" | jq .

echo "== regenerate"; curl -sS -X POST "$BASE/previews/regenerate" -H "$AUTHZ" -H "$CT" \
  -d "{\"preview_id\":\"$PREV\",\"max_passes\":1}" | jq .

echo "== video OK (>=2)"; 
RV=$(curl -sS -X POST "$BASE/previews/render" -H "$AUTHZ" -H "$CT" \
  -d '{"mode":"video","ratio":"9:16","images":["static/demo/img_9_16.jpg","static/demo/laptop.jpg"]}')
echo "$RV" | jq .
PV=$(echo "$RV" | jq -r .preview_id)

echo "== carousel OK (>=2)";
RC=$(curl -sS -X POST "$BASE/previews/render" -H "$AUTHZ" -H "$CT" \
  -d '{"mode":"carousel","ratio":"1:1","images":["static/demo/img_1_1.jpg","static/demo/shoes3.jpg"]}')
echo "$RC" | jq .
PC=$(echo "$RC" | jq -r .preview_id)

echo "== cleanup (delete)"; 
for X in "$PREV" "$PV" "$PC"; do
  curl -sS -X POST "$BASE/previews/delete" -H "$AUTHZ" -H "$CT" \
    -d "{\"preview_id\":\"$X\"}" | jq .
done
