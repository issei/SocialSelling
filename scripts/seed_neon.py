"""Seed do banco Neon: cria tabelas + insere uma operadora de teste.

Uso:
    py scripts/seed_neon.py

O código de acesso gerado é impresso no terminal — guarde-o para fazer login.
Idempotente: rodar duas vezes não duplica a operadora (ON CONFLICT DO NOTHING).
"""

from __future__ import annotations

import hashlib
import os
import sys
import uuid
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
if not DATABASE_URL:
    print("ERRO: DATABASE_URL não definida no .env")
    sys.exit(1)

try:
    import psycopg  # type: ignore[import-untyped]
except ImportError:
    print("ERRO: psycopg não instalado. Execute: pip install -e '.[portal]'")
    sys.exit(1)

# DDL (mesmo do dao_postgres.py — idempotente via IF NOT EXISTS)
_DDL = """
CREATE TABLE IF NOT EXISTS snapshots (
    profile_id   TEXT        NOT NULL,
    run_id       TEXT        NOT NULL,
    payload      JSONB       NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (profile_id, run_id)
);

CREATE TABLE IF NOT EXISTS feedback_events (
    id          BIGSERIAL PRIMARY KEY,
    operator_id TEXT        NOT NULL,
    profile_id  TEXT        NOT NULL,
    entity_id   TEXT        NOT NULL,
    run_id      TEXT        NOT NULL,
    kind        TEXT        NOT NULL CHECK (kind IN ('status', 'reaction')),
    status_id   TEXT,
    reaction    TEXT        CHECK (reaction IN ('like', 'dislike')),
    note        TEXT        NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS operators (
    operator_id TEXT PRIMARY KEY,
    nome        TEXT NOT NULL,
    code_hash   TEXT NOT NULL,
    profile_id  TEXT NOT NULL
);
"""

# Dados da operadora de teste
OPERATOR_NOME = "Talita"
OPERATOR_ID = "op-talita"
PROFILE_ID = "talita"          # deve bater com o ICP usado no motor
ACCESS_CODE = "talita-2026"    # código de acesso para login (altere se quiser)

code_hash = hashlib.sha256(ACCESS_CODE.encode()).hexdigest()

_INSERT_OPERATOR = """
INSERT INTO operators (operator_id, nome, code_hash, profile_id)
VALUES (%s, %s, %s, %s)
ON CONFLICT (operator_id) DO NOTHING;
"""

print(f"Conectando ao Neon...")
with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        print("Criando tabelas (IF NOT EXISTS)...")
        cur.execute(_DDL)

        print(f"Inserindo operadora '{OPERATOR_NOME}' (idempotente)...")
        cur.execute(_INSERT_OPERATOR, (OPERATOR_ID, OPERATOR_NOME, code_hash, PROFILE_ID))
        inserted = cur.rowcount == 1

    conn.commit()

print()
print("=" * 50)
print("  Seed concluído!")
print(f"  Operadora:     {OPERATOR_NOME} ({OPERATOR_ID})")
print(f"  Profile ID:    {PROFILE_ID}")
if inserted:
    print(f"  Codigo login:  {ACCESS_CODE}   << use na tela /login")
else:
    print(f"  Operadora ja existia - codigo nao alterado")
    print(f"  Codigo login:  {ACCESS_CODE}   (se ainda nao foi trocado)")
print("=" * 50)
