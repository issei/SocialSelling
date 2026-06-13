"""Smoke pós-deploy do portal (ADR-010, SDD §8/§9) — ferramenta operacional.

ÚNICA peça que toca o portal real (cobre o risco residual do PostgresDAO, fora do gate).
NÃO roda no pytest/gate. Uso:

    py scripts/smoke_portal.py --base-url https://selling.issei.com.br --token <PUBLISH_TOKEN>

Sequência (SDD §9):
    GET  /healthz                       → 200
    POST /api/publish (snapshot smoke)  → 201
    POST /api/publish (mesmo snapshot)  → 409 (idempotente)
    GET  /api/feedback?since=0          → 200

Exit code 0 = tudo verde; != 0 = falha com mensagem clara (portal fora do ar, etc.).
"""

from __future__ import annotations

import argparse
import sys

_SMOKE_SNAPSHOT = {
    "schema_version": 1,
    "profile_id": "smoke",
    "run_id": "smoke-run-0001",
    "generated_at": "2026-01-01T00:00:00+00:00",
    "leads": [
        {
            "entity_id": "smoke.example.com",
            "rank_position": 1,
            "company": "Smoke Test Co",
        }
    ],
}


def run_smoke(base_url: str, token: str) -> int:
    import httpx

    base = base_url.rstrip("/")
    auth = {"Authorization": f"Bearer {token}"}
    try:
        with httpx.Client(timeout=30.0) as client:
            health = client.get(f"{base}/healthz")
            _check(health.status_code, 200, "GET /healthz")

            first = client.post(f"{base}/api/publish", json=_SMOKE_SNAPSHOT, headers=auth)
            _check(first.status_code, 201, "POST /api/publish (1ª vez)")

            again = client.post(f"{base}/api/publish", json=_SMOKE_SNAPSHOT, headers=auth)
            _check(again.status_code, 409, "POST /api/publish (idempotente)")

            feed = client.get(f"{base}/api/feedback?since=0", headers=auth)
            _check(feed.status_code, 200, "GET /api/feedback?since=0")
    except _SmokeError as exc:
        print(f"SMOKE FALHOU: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — rede/portal fora do ar
        print(f"SMOKE FALHOU: portal inacessível ({exc})", file=sys.stderr)
        return 1

    print("SMOKE OK: healthz 200, publish 201/409 idempotente, feedback 200.")
    return 0


class _SmokeError(RuntimeError):
    pass


def _check(got: int, expected: int, step: str) -> None:
    if got != expected:
        raise _SmokeError(f"{step}: esperado HTTP {expected}, obtido {got}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="smoke_portal", description="Smoke pós-deploy.")
    parser.add_argument("--base-url", required=True, help="ex.: https://selling.issei.com.br")
    parser.add_argument("--token", required=True, help="PUBLISH_TOKEN configurado no Render")
    args = parser.parse_args(argv)
    return run_smoke(args.base_url, args.token)


if __name__ == "__main__":
    raise SystemExit(main())
