#!/usr/bin/env bash
set -euo pipefail
BASE=${BASE:-http://127.0.0.1:8000}
: "${TOKEN:?Set TOKEN env var: export TOKEN='JWT'}"

OUT="run_car_$(date +%Y%m%d_%H%M)"; mkdir -p "$OUT"

# Πάρε ΜΟΝΟ carousel templates (τους 3 πρώτους)
TEMPLATES=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE/tengine/templates" \
 | jq -r '[.[]|select(.type=="carousel")|.name]|unique|.[0:3][]')

if [ -z "$TEMPLATES" ]; then
  echo "Δεν βρέθηκαν carousel templates."
  exit 0
fi

to_abs_list() { jq -r --arg BASE "$BASE" -c 'map(
  if test("^https?://") then .
  else ( if startswith("/") then ($BASE + .) else ($BASE + "/" + .) end )
  end
)'; }

for PID in 84 85 86; do
  for MODE in "Κανονικό"; do
    for TKEY in $TEMPLATES; do
      RJSON=$(curl -s -X POST "$BASE/previews/render" \
        -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
        -d "{\"product_id\":$PID,\"template_key\":\"$TKEY\",\"mode\":\"$MODE\"}")

      RID=$(jq -r '.id // .preview_id // .render_id // empty' <<<"$RJSON")
      # Συνένωση πιθανών πηγών: urls, urls_json, preview_url
      URLS=$(jq -c '[ (.urls? // [] )[], (.urls_json? // [] )[], (.preview_url? // empty) ]
                    | map(select(.!=null))' <<<"$RJSON")
      [ "$URLS" = "[]" ] && { echo "WARN: no URLs for PID=$PID T=$TKEY"; continue; }

      URLS_ABS=$(echo "$URLS" | to_abs_list)

      CJSON=$(curl -s -X POST "$BASE/previews/commit" \
        -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
        -d "{\"preview_id\":\"$RID\",\"urls\":$URLS_ABS}")

      CID=$(jq -r '.post_id // empty' <<<"$CJSON")
      REM=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE/me/credits" | jq -r '.credits')
      echo "$(date +%F\ %T),$PID,$MODE,$TKEY,$RID,$URLS_ABS,$CID,$REM" >> "$OUT/results.csv"
      echo "OK(carousel): PID=$PID T=$TKEY → post_id=$CID credits=$REM"
    done
  done
done

echo "Αποτελέσματα: $OUT/results.csv"
