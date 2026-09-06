#!/bin/sh
set -eu
PORT="${PORT:-8000}"
exec python -m uvicorn app:app --host 0.0.0.0 --port "$PORT"
