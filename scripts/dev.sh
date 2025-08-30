#!/usr/bin/env bash
set -euo pipefail
source .venv/bin/activate
uvicorn main:app --reload --host 127.0.0.1 --port 8000
