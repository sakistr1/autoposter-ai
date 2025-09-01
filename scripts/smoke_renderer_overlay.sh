#!/usr/bin/env bash
set -euo pipefail

# --- Config via env ---
: "${BASE:=http://127.0.0.1:8000}"
: "${TOKEN:?Set TOKEN env, e.g. export TOKEN='...'}"
: "${IMAGE:=$BASE/static/uploads/demo.jpg}"   # μπορείς να αλλάξεις εικόνα
: "${QUALITY:=}"                              # π.χ. QUALITY=95 (προαιρετικό)

AUTHZ="Authorization: Bearer ${TOKEN}"
JSON="Content-Type: application/json"

# Έξοδος CSV
OUT="smoke_renderer_overlay_results.csv"
echo "ratio,caption,preview_url,overlay_applied,width,height,committed_url,remaining_credits" > "$OUT"

# Helper: τρέξε ένα ratio
run_one() {
  local ratio="$1"
  local tmp="/tmp/p_renderer_overlay_${ratio//:/}.json"
  local prev="/tmp/prev_${ratio//:/}.json"

  # payload (βάζουμε mapping για να ανάψει το overlay)
  cat > "$tmp" <<JSON
{
  "template_id": 12,
  "image_url": "$IMAGE",
  "platform": "instagram",
  "ratio": "$ratio",
  "mode": "normal",
  "use_renderer": true,
  "use_ai_plan": false,
  "watermark": true,
  "return_absolute_url": true,
  "mapping": {
    "title": "🔥 Overlay test $ratio"
  }
  $( [[ -n "$QUALITY" ]] && printf ', "quality": %s' "$QUALITY" )
}
JSON

  # preview
  curl -sS -X POST "$BASE/tengine/preview" \
    -H "$AUTHZ" -H "$JSON" \
    --data-binary @"$tmp" \
    | tee "$prev" >/dev/null

  # pick fields
  local preview_url caption overlay width height preview_id
  preview_url=$(jq -r '.preview_url' "$prev")
  caption=$(jq -r '.caption // ""' "$prev")
  overlay=$(jq -r '.overlay_applied // false' "$prev")
  width=$(jq -r '.meta.width // empty' "$prev")
  height=$(jq -r '.meta.height // empty' "$prev")
  preview_id=$(jq -r '.preview_id // .id // empty' "$prev")

  # commit
  local commit
  commit=$(curl -sS -X POST "$BASE/tengine/commit" \
    -H "$AUTHZ" -H "$JSON" \
    -d "{\"preview_id\":\"$preview_id\"}")

  local committed_url credits
  committed_url=$(jq -r '.committed_url' <<<"$commit")
  credits=$(jq -r '.remaining_credits' <<<"$commit")

  # CSV line
  printf '%q,%q,%q,%q,%q,%q,%q,%q\n' \
    "$ratio" "$caption" "$preview_url" "$overlay" "$width" "$height" "$committed_url" "$credits" \
    >> "$OUT"

  # ωραία εμφάνιση στη κονσόλα
  echo "=== Ratio $ratio ==="
  echo "caption: $caption"
  echo "overlay_applied: $overlay"
  echo "preview:  $preview_url"
  echo "size:     ${width}x${height}"
  echo "committed:$committed_url"
  echo "credits:  $credits"
  echo
}

# Τρέξε και τα 3 ratios
for r in "1:1" "4:5" "9:16"; do
  run_one "$r"
done

echo "✅ Αποτελέσματα γραμμένα στο $OUT"
# μικρό preview του CSV (πρώτες 10 γραμμές), αν υπάρχει 'column'
if command -v column >/dev/null 2>&1; then
  echo
  echo "---- CSV preview ----"
  column -s, -t "$OUT" | sed -n '1,10p'
fi
