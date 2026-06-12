"""App FastAPI do portal da operadora (ADR-010 / SDD §4).

Rotas: WU-T1 scaffold + WU-T2 publish + WU-T3 auth + WU-T4 feedback + WU-T5 UI.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import Response

from socialselling.portal.dao import BasePortalDAO
from socialselling.portal.routers import auth as auth_router
from socialselling.portal.routers import publish as publish_router
from socialselling.portal.routers.auth import require_session


class NoIndexMiddleware(BaseHTTPMiddleware):
    """Adiciona X-Robots-Tag: noindex em todas as respostas (SDD §4)."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        response.headers["X-Robots-Tag"] = "noindex"
        return cast(Response, response)


def create_portal_app(dao: BasePortalDAO, *, https_only: bool = True) -> FastAPI:
    """Factory do app — recebe o DAO injetado (InMemory ou Postgres).

    https_only: True em produção (Render TLS); False em testes locais sem TLS.
    """

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        dao.ensure_schema()
        yield

    app = FastAPI(
        title="Portal da Operadora",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Sessão assinada (itsdangerous via Starlette) — HttpOnly + SameSite=Lax + Secure
    app.add_middleware(
        SessionMiddleware,
        secret_key=os.environ.get("SECRET_KEY", "dev-secret-key-CHANGE-IN-PROD"),
        https_only=https_only,
        same_site="lax",
    )
    app.add_middleware(NoIndexMiddleware)

    # Disponibiliza o DAO via state para os routers
    app.state.dao = dao

    # Routers (ordem reflete as WUs — sem dependência circular)
    app.include_router(publish_router.router)
    app.include_router(auth_router.router)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> HTMLResponse:
        return HTMLResponse('{"status":"ok"}', media_type="application/json")

    # Stub /carteira (WU-T3: guarda de sessão; conteúdo completo em WU-T5)
    @app.get("/carteira", include_in_schema=False)
    async def carteira_stub(
        _operator_id: str = Depends(require_session),  # noqa: B008
    ) -> HTMLResponse:
        return HTMLResponse("<html><body><h1>Carteira</h1></body></html>")

    return app
