#!/usr/bin/env bash
set -euo pipefail
METHOD="$1"; PATHN="$2"; BODY="$3"

do_call() {
  curl -s -w "\n%{http_code}" -X "$METHOD" "$BASE$PATHN" \
    -H "$AUTHZ" -H "Content-Type: application/json" -d "$BODY"
}

RESP=$(do_call)
CODE=$(echo "$RESP" | tail -n1)
BODY=$(echo "$RESP" | sed '$d')

# Αν 401, ξαναστήσε AUTHZ (π.χ. με νέο TOKEN) και δοκίμασε ξανά
if [ "$CODE" = "401" ]; then
  echo "Got 401, retrying once..." >&2
  # εδώ βάλε λογική ανανέωσης TOKEN αν χρειάζεται
  RESP=$(do_call)
  CODE=$(echo "$RESP" | tail -n1)
  BODY=$(echo "$RESP" | sed '$d')
fi

echo "$BODY"
exit 0
