#!/usr/bin/env bash
# Quality gate do PoC: lint + tipos + testes (CLAUDE.md secao 4).
# Uso:  ./scripts/gate.sh   (Linux / WSL)
set -euo pipefail

echo "== check_licoes =="
python scripts/check_licoes.py

echo "== ruff =="
python -m ruff check .

echo "== mypy --strict =="
python -m mypy

echo "== pytest =="
python -m pytest -q

echo "GATE OK"
