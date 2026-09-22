#!/bin/sh
set -eu

APP_DIR=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
export PYTHONPATH="$APP_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
cd "$APP_DIR"

if [ "${RAGTRUST_SERVICE:-ui}" = "api" ]; then
  exec uvicorn ragtrust.api:app --host 0.0.0.0 --port "${PORT:-8000}"
fi

exec streamlit run src/ragtrust/app.py \
  --server.address 0.0.0.0 \
  --server.port "${PORT:-8000}" \
  --server.headless true \
  --browser.gatherUsageStats false
