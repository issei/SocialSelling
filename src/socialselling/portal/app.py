"""App FastAPI do portal da operadora (ADR-010 / SDD §4).

Scaffold WU-T1: middleware X-Robots-Tag, /healthz, injeção do DAO.
Rotas de publicação/feedback/auth/UI são adicionadas em WU-T2..T5.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from socialselling.portal.dao import BasePortalDAO


class NoIndexMiddleware(BaseHTTPMiddleware):
    """Adiciona X-Robots-Tag: noindex em todas as respostas (SDD §4)."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        response.headers["X-Robots-Tag"] = "noindex"
        return cast(Response, response)


def create_portal_app(dao: BasePortalDAO) -> FastAPI:
    """Factory do app — recebe o DAO injetado (InMemory ou Postgres)."""

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
    app.add_middleware(NoIndexMiddleware)

    # Disponibiliza o DAO via state para os routers
    app.state.dao = dao

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    return app
