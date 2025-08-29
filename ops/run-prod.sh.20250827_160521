#!/usr/bin/env bash
set -euo pipefail
cd /home/smartpark/autoposter-ai-restored
export PYTHONPATH=/home/smartpark/autoposter-ai-restored
mkdir -p logs
exec /home/smartpark/autoposter-ai-restored/.venv/bin/python -m uvicorn main:app \
  --host 0.0.0.0 --port 8000 \
  --workers 1 \
  --proxy-headers --no-server-header \
  --log-level info >> logs/uvicorn.out 2>&1
