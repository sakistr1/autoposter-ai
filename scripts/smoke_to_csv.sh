#!/bin/bash
set -euo pipefail

: "${BASE:?Set BASE, e.g. http://127.0.0.1:8000}"
: "${TOKEN:?Set TOKEN (Bearer ...)}"

OUT="smoke_results.csv"
OUT_PLAIN="smoke_results_plain.csv"

# Headers
echo '"timestamp","ratio","caption","preview_url","committed_url","remaining_credits"' > "$OUT"
# Write UTF-8 BOM for Excel + header plain
printf '\xEF\xBB\xBF' > "$OUT_PLAIN"
echo 'timestamp,ratio,caption,preview_url,committed_url,remaining_credits' >> "$OUT_PLAIN"

# Ratios (override με --ratios "1:1,4:5,9:16" αν θέλεις)
RATIOS="1:1,4:5,9:16"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --ratios) RATIOS="$2"; shift 2;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

IFS=',' read -r -a RLIST <<< "$RATIOS"

for R in "${RLIST[@]}"; do
  TS=$(date +%Y-%m-%dT%H:%M:%S)
  >&2 echo "== Running ratio $R =="

  cat >/tmp/p_ai.json <<JSON
{
  "template_id": 12,
  "image_url": "$BASE/static/uploads/demo.jpg",
  "platform": "instagram",
  "ratio": "$R",
  "mode": "normal",
  "use_renderer": true,
  "use_ai_plan": true,
  "watermark": true,
  "return_absolute_url": true
}
JSON

  PREV=$(curl -sS -X POST "$BASE/tengine/preview" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    --data-binary @/tmp/p_ai.json)

  PREV_ID=$(echo "$PREV" | jq -r '.preview_id')
  PREV_URL=$(echo "$PREV" | jq -r '.preview_url')
  CAPTION=$(echo "$PREV" | jq -r '.caption')

  COMM=$(curl -sS -X POST "$BASE/tengine/commit" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"preview_id\":\"$PREV_ID\"}")

  COMM_URL=$(echo "$COMM" | jq -r '.committed_url')
  CREDITS=$(echo "$COMM" | jq -r '.remaining_credits')

  # Safe/quoted CSV
  printf '"%s","%s","%s","%s","%s","%s"\n' \
    "$TS" "$R" "$CAPTION" "$PREV_URL" "$COMM_URL" "$CREDITS" >> "$OUT"

  # Plain για Excel: καθάρισμα quotes, κόμματα -> ·
  CAP_PLAIN=$(printf '%s' "$CAPTION" | tr -d '"' | sed 's/,/·/g')
  printf '%s,%s,%s,%s,%s,%s\n' \
    "$TS" "$R" "$CAP_PLAIN" "$PREV_URL" "$COMM_URL" "$CREDITS" >> "$OUT_PLAIN"
done

echo "✅ Γράφτηκαν: $OUT  και  $OUT_PLAIN"
