#!/usr/bin/env bash
set -euo pipefail

REPO="/home/smartpark/autoposter-ai-restored"
GEN="$REPO/static/generated"
DAYS="${1:-3}"

# Σβήσε αρχεία (ασφαλές: δεν πειράζει άλλα paths, ούτε μπαίνει βαθιά)
find "$GEN" -maxdepth 1 -type d -name 'prev_*' -mtime +"$DAYS" -print0 \
  | xargs -0 -I{} bash -c 'rm -f "{}"/*.png "{}"/*.mp4 "{}"/*.webm "{}"/meta.json || true'

# Μάζεψε άδεια directories
find "$GEN" -maxdepth 1 -type d -name 'prev_*' -empty -print0 | xargs -0 -r rmdir

# Log για έλεγχο
du -sh "$GEN" || true
