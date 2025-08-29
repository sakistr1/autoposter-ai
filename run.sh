#!/usr/bin/env bash
cd /home/smartpark/autoposter-ai-restored
source .venv/bin/activate
export PYTHONPATH=/home/smartpark/autoposter-ai-restored
exec python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
