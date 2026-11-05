#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose up -d db
python -m venv services/api/.venv
if [[ -f services/api/.venv/Scripts/activate ]]; then
  # Windows
  source services/api/.venv/Scripts/activate
else
  source services/api/.venv/bin/activate
fi
pip install -e "services/api[dev]"
(
  cd services/api
  alembic upgrade head
  python -m app.seed
)
echo "API database is ready. Copy .env.example files and fill provider keys before the voice worker."
