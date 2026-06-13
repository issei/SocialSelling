"""Entrypoint local do portal da operadora.

Usa PostgresDAO se DATABASE_URL estiver no .env; cai em InMemoryDAO caso contrário.
Carrega o .env automaticamente — não precisa ativar variáveis manualmente.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), val)


ROOT = Path(__file__).resolve().parent.parent
_load_dotenv(ROOT / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-CHANGE-IN-PROD")
PUBLISH_TOKEN = os.environ.get("PUBLISH_TOKEN", "dev-token")

os.environ.setdefault("SECRET_KEY", SECRET_KEY)
os.environ.setdefault("PUBLISH_TOKEN", PUBLISH_TOKEN)

if DATABASE_URL:
    try:
        import psycopg  # type: ignore[import-untyped]
    except ImportError:
        print("ERRO: psycopg não instalado. Execute: pip install -e '.[portal]'")
        sys.exit(1)

    try:
        conn = psycopg.connect(DATABASE_URL, autocommit=False)
    except Exception as exc:
        print(f"ERRO ao conectar ao Neon: {exc}")
        sys.exit(1)

    from socialselling.portal.dao_postgres import PostgresDAO

    dao = PostgresDAO(conn)
    mode = "PostgresDAO → Neon"
else:
    from socialselling.portal.dao_memory import InMemoryDAO

    dao = InMemoryDAO()
    mode = "InMemoryDAO (dados perdidos ao reiniciar)"

from socialselling.portal.app import create_portal_app
import uvicorn

app = create_portal_app(dao, https_only=False)

print("=" * 50)
print(f"  Modo:          {mode}")
print(f"  PUBLISH_TOKEN: {PUBLISH_TOKEN[:8]}...")
print(f"  Portal:        http://localhost:8000")
print(f"  Login:         http://localhost:8000/login")
print(f"  Health:        http://localhost:8000/healthz")
print("=" * 50)
print("  Ctrl+C para parar\n")

uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
