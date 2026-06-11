"""Router: POST /api/publish — publicação de snapshot pelo motor (SDD §4).

Auth: Bearer PUBLISH_TOKEN (variável de ambiente).
Idempotência por (profile_id, run_id): 201 publicado agora; 409 já existia.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from socialselling.portal.contracts import PublishedSnapshot
from socialselling.portal.dao import BasePortalDAO

router = APIRouter()


def _get_dao(request: Request) -> BasePortalDAO:
    dao: BasePortalDAO = request.app.state.dao
    return dao


def _verify_bearer(authorization: str = Header(default="")) -> None:
    token = os.environ.get("PUBLISH_TOKEN", "")
    expected = f"Bearer {token}"
    if not token or authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post(
    "/api/publish",
    status_code=201,
    dependencies=[Depends(_verify_bearer)],
)
async def publish_snapshot(
    snapshot: PublishedSnapshot,
    dao: BasePortalDAO = Depends(_get_dao),  # noqa: B008
) -> JSONResponse:
    """Recebe e persiste um PublishedSnapshot.

    201 → snapshot publicado agora.
    409 → (profile_id, run_id) já existia (idempotente — motor trata como sucesso).
    401 → token ausente/errado.
    422 → contrato violado (extra=forbid, ranks não-estritos, >20 leads).
    """
    from datetime import UTC, datetime

    now = datetime.now(UTC).isoformat()
    inserted = dao.put_snapshot(snapshot, now=now)
    if not inserted:
        raise HTTPException(status_code=409, detail="Snapshot already exists")
    return JSONResponse({"run_id": snapshot.run_id}, status_code=201)
