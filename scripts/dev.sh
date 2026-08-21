#!/usr/bin/env bash
# Local product development: API on :8000, Vite UI on :5173.
# Does not start Qdrant Docker (embedded local mode is the default) or Ollama.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${1:-}" == "api" ]]; then
  exec python -m research_assistant serve --host 127.0.0.1 --port 8000
fi
if [[ "${1:-}" == "ui" ]]; then
  exec npm --prefix web run dev
fi
if [[ "${1:-}" == "check" ]]; then
  exec python scripts/check_environment.py
fi

echo "Usage:"
echo "  Terminal A:  ./scripts/dev.sh api"
echo "  Terminal B:  ./scripts/dev.sh ui"
echo "  Optional:    ./scripts/dev.sh check"
echo "Then open http://127.0.0.1:5173"
echo
echo "Prerequisites: pip install -e '.[dev]', npm --prefix web install,"
echo "Ollama with qwen2.5-coder:7b for generation, optional docker compose for the API image."
exit 1
