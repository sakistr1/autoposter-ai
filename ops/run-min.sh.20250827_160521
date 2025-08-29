#!/usr/bin/env bash
set -euo pipefail
cd /home/smartpark/autoposter-ai-restored
source .venv/bin/activate
export PYTHONPATH=/home/smartpark/autoposter-ai-restored
exec python -m uvicorn main:app \
  --host 0.0.0.0 --port 8000 \
  --workers 2 \
  --proxy-headers \
  --no-server-header
