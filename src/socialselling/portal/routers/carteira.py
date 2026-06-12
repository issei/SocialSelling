"""Router: GET /carteira + GET /lead/{entity_id} — UI da operadora (SDD §4, §4.1).

Jinja2 + JS vanilla. Sem score numérico exposto (ADR-010). Sessão obrigatória.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from socialselling.portal.catalog import load_feedback_catalog
from socialselling.portal.contracts import FeedbackEvent
from socialselling.portal.dao import BasePortalDAO
from socialselling.portal.routers.auth import require_session
from socialselling.portal.services import build_carteira

router = APIRouter()

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _get_dao(request: Request) -> BasePortalDAO:
    dao: BasePortalDAO = request.app.state.dao
    return dao


@router.get("/carteira", include_in_schema=False, response_class=HTMLResponse)
async def carteira(
    request: Request,
    _operator_id: str = Depends(require_session),  # noqa: B008
    dao: BasePortalDAO = Depends(_get_dao),  # noqa: B008
) -> HTMLResponse:
    """Carteira da operadora — leads visíveis escopados ao profile_id da sessão."""
    profile_id = str(request.session.get("profile_id", ""))
    catalog = load_feedback_catalog()
    items = build_carteira(dao, profile_id, catalog)
    return templates.TemplateResponse(
        request,
        "carteira.html",
        {
            "items": items,
            "catalog_statuses": catalog.statuses,
        },
    )


@router.get("/lead/{entity_id}", include_in_schema=False, response_class=HTMLResponse)
async def lead_detail(
    entity_id: str,
    request: Request,
    operator_id: str = Depends(require_session),  # noqa: B008
    dao: BasePortalDAO = Depends(_get_dao),  # noqa: B008
) -> HTMLResponse:
    """Lead card detalhado — sem score numérico (ADR-010)."""
    profile_id = str(request.session.get("profile_id", ""))
    catalog = load_feedback_catalog()
    items = build_carteira(dao, profile_id, catalog)

    # Localiza o item na carteira (404 se fora do escopo do perfil)
    item = next((i for i in items if i.lead.entity_id == entity_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Lead não encontrado na carteira")

    # Histórico de eventos do lead (filtrado no servidor)
    all_events: list[FeedbackEvent] = dao.events_since(0, limit=1000)
    history = [
        e
        for e in all_events
        if e.profile_id == profile_id and e.entity_id == entity_id
    ]

    return templates.TemplateResponse(
        request,
        "lead.html",
        {
            "item": item,
            "history": history,
            "catalog_statuses": catalog.statuses,
        },
    )
