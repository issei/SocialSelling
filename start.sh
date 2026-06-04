#!/usr/bin/env bash
# ============================================================================
#  SocialSelling - inicia a UI local (http://127.0.0.1:8000) em WSL/Linux/macOS.
#  Uso:  ./start.sh   (na 1a vez prepara o ambiente sozinho)
# ============================================================================
set -e
cd "$(dirname "$0")"

PY=".venv/bin/python"

# 1) venv
if [ ! -x "$PY" ]; then
  echo "[SocialSelling] Criando ambiente virtual .venv ..."
  python3 -m venv .venv
fi

# 2) dependencias da UI (primeira vez)
if ! "$PY" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "[SocialSelling] Instalando dependencias (so na primeira vez)..."
  "$PY" -m pip install --upgrade pip -q
  "$PY" -m pip install -e ".[web]" -q
fi

# 3) .env
if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "[SocialSelling] Criei o .env a partir do exemplo. Preencha TAVILY_API_KEY e GEMINI_API_KEY."
fi

# 4) abre o navegador depois de 3s e sobe o servidor
( sleep 3; (xdg-open http://127.0.0.1:8000 || open http://127.0.0.1:8000) >/dev/null 2>&1 || true ) &
echo "[SocialSelling] Abrindo http://127.0.0.1:8000  (Ctrl+C para encerrar)"
exec "$PY" -m socialselling.web
