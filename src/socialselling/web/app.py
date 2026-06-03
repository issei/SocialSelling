"""App FastAPI da UI de operador local (ADR-002).

Superfície fina sobre o núcleo: não importa M1–M5 diretamente além do que os
serviços expõem. Roda em localhost (ver `__main__`). Sem auth, sem banco.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from socialselling.contracts import HypothesisCatalog
from socialselling.web.schemas import SaveIcpRequest, ScoringUpdate
from socialselling.web.services import (
    DEFAULT_CONFIG_DIR,
    DEFAULT_RUNTIME,
    InvalidName,
    load_config,
    read_icp,
    save_hypotheses,
    save_icp,
    save_scoring,
)

_PLACEHOLDER_HTML = """<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SocialSelling — UI local</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-800">
  <main class="max-w-3xl mx-auto p-8 space-y-6">
    <h1 class="text-2xl font-bold">SocialSelling — Operador local</h1>
    <section id="parametros"><h2 class="font-semibold">Parâmetros</h2></section>
    <section id="assistente"><h2 class="font-semibold">Assistente (Gemini)</h2></section>
    <section id="resultados"><h2 class="font-semibold">Resultados</h2></section>
    <p class="text-sm text-slate-500">Fundação web (WU-U1). Telas completas nas próximas fatias.</p>
  </main>
</body>
</html>
"""


def create_app(
    *,
    config_dir: Path = DEFAULT_CONFIG_DIR,
    runtime_path: Path = DEFAULT_RUNTIME,
) -> FastAPI:
    """Cria o app FastAPI. Paths injetáveis para testes (FS isolado)."""
    app = FastAPI(title="SocialSelling — UI local", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _PLACEHOLDER_HTML

    @app.get("/api/config")
    def api_config() -> dict[str, Any]:
        return load_config(config_dir, runtime_path)

    @app.get("/api/config/icp")
    def api_get_icp(name: str) -> dict[str, Any]:
        try:
            return read_icp(config_dir, name)
        except InvalidName as exc:
            raise HTTPException(status_code=400, detail=f"nome invalido: {name}") from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"ICP nao encontrado: {name}") from exc

    @app.post("/api/config/icp")
    def api_save_icp(req: SaveIcpRequest) -> dict[str, Any]:
        try:
            save_icp(config_dir, req.name, req.icp)
        except InvalidName as exc:
            raise HTTPException(status_code=400, detail=f"nome invalido: {req.name}") from exc
        return {"ok": True, "saved": req.name}

    @app.post("/api/config/hypotheses")
    def api_save_hypotheses(catalog: HypothesisCatalog) -> dict[str, Any]:
        save_hypotheses(config_dir, catalog)
        return {"ok": True, "count": len(catalog.hypotheses)}

    @app.post("/api/config/scoring")
    def api_save_scoring(update: ScoringUpdate) -> dict[str, Any]:
        save_scoring(runtime_path, update.model_dump())
        return {"ok": True}

    return app


app = create_app()
