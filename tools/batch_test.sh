#!/usr/bin/env bash
set -euo pipefail

BASE=${BASE:-http://127.0.0.1:8000}
: "${TOKEN:?Set TOKEN env var: export TOKEN='JWT'}"

to_abs() { local u="$1"; case "$u" in http*) echo "$u";; /*) echo "$BASE$u";; *) echo "$BASE/$u";; esac; }

OUT="run_$(date +%Y%m%d_%H%M)"; mkdir -p "$OUT"

TEMPLATES=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE/tengine/templates" \
 | jq -r '[.[]|select(.type=="image")|.name]|unique|.[0:6][]')

for PID in 84 85 86; do
  for MODE in "Κανονικό" "Επαγγελματικό" "Χιουμοριστικό"; do
    for TKEY in $TEMPLATES; do
      RJSON=$(curl -s -X POST "$BASE/previews/render" \
        -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
        -d "{\"product_id\":$PID,\"template_key\":\"$TKEY\",\"mode\":\"$MODE\"}")

      RID=$(jq -r '.id // .preview_id // .render_id // empty' <<<"$RJSON")
      PURL=$(jq -r '.preview_url // (.urls[0] // (.urls_json[0] // empty))' <<<"$RJSON")
      [ -z "$RID" ] && { echo "WARN: no preview id for PID=$PID T=$TKEY MODE=$MODE"; continue; }

      AURL=$(to_abs "$PURL")
      CJSON=$(curl -s -X POST $BASE/previews/commit \
      -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
      -d "{\"preview_id\":\"$RID\"}")


      CID=$(jq -r '.post_id // empty' <<<"$CJSON")
      REM=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE/me/credits" | jq -r '.credits')
      echo "$(date +%F\ %T),$PID,$MODE,$TKEY,$RID,$AURL,$CID,$REM" >> "$OUT/results.csv"
      echo "OK: PID=$PID T=$TKEY MODE=$MODE → post_id=$CID credits=$REM"
    done
  done
done

echo "Αποτελέσματα στο $OUT/results.csv"
