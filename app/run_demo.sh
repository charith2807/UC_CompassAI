#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export COMPASS_DEMO=1
exec .venv/bin/python -m streamlit run app/streamlit_app.py \
  --server.address 127.0.0.1 --server.port 8501 \
  --server.headless true --browser.gatherUsageStats false
