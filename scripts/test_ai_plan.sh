#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000}"
: "${TOKEN:?Set TOKEN first (export TOKEN=...)}"
AUTHZ="Authorization: Bearer $TOKEN"

echo "== /ai/plan (demo url) =="
jq -n '{"product_url":"https://example.com/demo/outfit1","platform":"instagram","ratio":"4:5"}' \
| curl -sS -H "$AUTHZ" -H "Content-Type: application/json" \
  --data-binary @- "$BASE/ai/plan" | tee /tmp/ai_plan_demo.json | jq '{absolute_url, plan}'

echo "== /ai/plan (static) =="
jq -n '{"product_url":"/static/demo/outfit1.webp","platform":"instagram","ratio":"4:5"}' \
| curl -sS -H "$AUTHZ" -H "Content-Type: application/json" \
  --data-binary @- "$BASE/ai/plan" | tee /tmp/ai_plan_static.json | jq '{absolute_url, plan}'

echo "== open last =="
URL=$(jq -r '.absolute_url // empty' /tmp/ai_plan_static.json)
[ -z "$URL" ] && URL=$(jq -r '.absolute_url // empty' /tmp/ai_plan_demo.json)
[ -n "$URL" ] && (xdg-open "$URL" >/dev/null 2>&1 || gio open "$URL" >/dev/null 2>&1 || true)
