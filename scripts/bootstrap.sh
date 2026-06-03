#!/usr/bin/env bash
# Bootstrap do ambiente local (IaC local) — recria tudo do zero.
# Uso:  ./scripts/bootstrap.sh   (Linux / WSL)
set -euo pipefail

if [ ! -d ".venv" ]; then
  echo "Criando venv..."
  python -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Instalando dependencias (deps + dev)..."
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

if [ ! -f ".env" ]; then
  echo "Criando .env a partir do exemplo (preencha as chaves)..."
  cp .env.example .env
fi

echo "Rodando quality gate..."
ruff check .
mypy
pytest -q

echo "BOOTSTRAP OK — ambiente pronto."
