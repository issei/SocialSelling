"""Router: POST /lead/{entity_id}/feedback (sessão) + GET /api/feedback (Bearer).

POST — tabulação da operadora (anti-spoofing: operator_id/profile_id da sessão;
run_id = snapshot mais recente que contém o lead; status_id validado no catálogo).
GET  — cursor idempotente para o motor (CLI pull-feedback).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from socialselling.portal.catalog import load_feedback_catalog
from socialselling.portal.contracts import FeedbackEventIn, FeedbackKind, FeedbackPage
from socialselling.portal.dao import BasePortalDAO
from socialselling.portal.routers.auth import require_session

router = APIRouter()


def _get_dao(request: Request) -> BasePortalDAO:
    dao: BasePortalDAO = request.app.state.dao
    return dao


def _verify_bearer(authorization: str = Header(default="")) -> None:
    token = os.environ.get("PUBLISH_TOKEN", "")
    expected = f"Bearer {token}"
    if not token or authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _find_run_id(dao: BasePortalDAO, profile_id: str, entity_id: str) -> str | None:
    """Retorna o run_id do snapshot mais recente que contém entity_id, ou None."""
    for snap in dao.list_snapshots(profile_id):
        for lead in snap.leads:
            if lead.entity_id == entity_id:
                return snap.run_id
    return None


@router.post("/lead/{entity_id}/feedback", include_in_schema=False)
async def post_lead_feedback(
    entity_id: str,
    body: FeedbackEventIn,
    request: Request,
    operator_id: str = Depends(require_session),  # noqa: B008
    dao: BasePortalDAO = Depends(_get_dao),  # noqa: B008
) -> JSONResponse:
    """Grava evento append-only de feedback (sessão da operadora).

    operator_id/profile_id vêm da sessão (anti-spoofing).
    run_id = snapshot mais recente que contém o lead.
    status_id validado no catálogo; correção = novo evento (nunca UPDATE).
    """
    profile_id = str(request.session.get("profile_id", ""))

    # Localiza o run_id (e verifica se o lead pertence à carteira do perfil)
    run_id = _find_run_id(dao, profile_id, entity_id)
    if run_id is None:
        raise HTTPException(status_code=404, detail="Lead não pertence à carteira do perfil")

    # Valida status_id contra o catálogo
    if body.kind is FeedbackKind.STATUS:
        if body.status_id is None:
            raise HTTPException(
                status_code=422,
                detail="status_id é obrigatório quando kind=status",
            )
        catalog = load_feedback_catalog()
        valid_ids = {s.status_id for s in catalog.statuses}
        if body.status_id not in valid_ids:
            raise HTTPException(
                status_code=422,
                detail=f"status_id '{body.status_id}' não existe no catálogo",
            )
    elif body.kind is FeedbackKind.REACTION:
        if body.reaction is None:
            raise HTTPException(
                status_code=422,
                detail="reaction é obrigatória quando kind=reaction",
            )

    now = datetime.now(UTC).isoformat()
    event_id = dao.append_event(
        operator_id=operator_id,
        profile_id=profile_id,
        entity_id=entity_id,
        run_id=run_id,
        kind=body.kind,
        status_id=body.status_id,
        reaction=body.reaction,
        note=body.note,
        now=now,
    )
    return JSONResponse({"event_id": event_id}, status_code=200)


@router.get(
    "/api/feedback",
    dependencies=[Depends(_verify_bearer)],
    include_in_schema=False,
)
async def get_feedback(
    dao: BasePortalDAO = Depends(_get_dao),  # noqa: B008
    since: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=1000),
) -> FeedbackPage:
    """Eventos com event_id > since, ordem ASC. Além do fim → events=[], next_since=since."""
    events = dao.events_since(since, limit=limit)
    next_since = events[-1].event_id if events else since
    return FeedbackPage(events=events, next_since=next_since)
