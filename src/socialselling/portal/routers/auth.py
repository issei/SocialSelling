"""Router: POST /login, POST /logout, GET /login — auth da operadora (SDD §4.2).

Código de acesso individual: sha256(código) → lookup em operators.code_hash.
Sessão por cookie assinado (SessionMiddleware do Starlette / itsdangerous).
HttpOnly + Secure + SameSite=Lax; sem bcrypt (código de alta entropia — SDD §4.2).
"""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from starlette.responses import RedirectResponse, Response

from socialselling.portal.dao import BasePortalDAO

router = APIRouter()

_LOGIN_HTML = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Portal — Login</title></head>
<body>
<form method="post" action="/login">
  <label>Código de acesso<br>
    <input type="password" name="code" autocomplete="current-password" autofocus>
  </label>
  <button type="submit">Entrar</button>
</form>
</body>
</html>"""


def _get_dao(request: Request) -> BasePortalDAO:
    dao: BasePortalDAO = request.app.state.dao
    return dao


def require_session(request: Request) -> str:
    """Dependency: retorna operator_id da sessão ou lança 303 para /login."""
    operator_id = request.session.get("operator_id")
    if not operator_id:
        raise HTTPException(
            status_code=303,
            headers={"Location": "/login"},
            detail="Sessão ausente",
        )
    return str(operator_id)


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def get_login_page() -> HTMLResponse:
    return HTMLResponse(content=_LOGIN_HTML)


@router.post("/login", include_in_schema=False)
async def post_login(
    request: Request,
    code: str = Form(...),
    dao: BasePortalDAO = Depends(_get_dao),  # noqa: B008
) -> Response:
    """sha256(código) → find_operator_by_code_hash; achou → sessão; não achou → 401."""
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    operator = dao.find_operator_by_code_hash(code_hash)
    if operator is None:
        return HTMLResponse(content="código inválido", status_code=401)
    request.session["operator_id"] = operator.operator_id
    request.session["profile_id"] = operator.profile_id
    return RedirectResponse(url="/carteira", status_code=303)


@router.post("/logout", include_in_schema=False)
async def post_logout(request: Request) -> Response:
    """Limpa a sessão e redireciona para /login."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
