"""App FastAPI da UI de operador local (ADR-002).

Superfície fina sobre o núcleo: não importa M1–M5 diretamente além do que os
serviços expõem. Roda em localhost (ver `__main__`). Sem auth, sem banco.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from socialselling.config import load_env, load_runtime
from socialselling.contracts import HypothesisCatalog, LeadCard
from socialselling.skills.gemini_client import (
    CognitionClient,
    GeminiClient,
    GeminiError,
    RateLimitError,
)
from socialselling.web.schemas import (
    AssistRequest,
    RunRequest,
    SaveIcpRequest,
    ScoringUpdate,
)
from socialselling.web.services import (
    DEFAULT_CONFIG_DIR,
    DEFAULT_RUNTIME,
    InvalidName,
    MissingKeys,
    assist_icp,
    load_config,
    read_hypotheses,
    read_icp,
    run_for_icp,
    save_hypotheses,
    save_icp,
    save_scoring,
)

_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
_STATIC_DIR = Path(__file__).resolve().parent / "static"

PipelineRunner = Callable[[str], list[LeadCard]]


def create_app(
    *,
    config_dir: Path = DEFAULT_CONFIG_DIR,
    runtime_path: Path = DEFAULT_RUNTIME,
    cognition_client: CognitionClient | None = None,
    pipeline_runner: PipelineRunner | None = None,
) -> FastAPI:
    """Cria o app FastAPI. Paths, Gemini e runner injetáveis para testes (FS/rede isolados)."""
    app = FastAPI(title="SocialSelling — UI local", docs_url=None, redoc_url=None)
    runs: dict[str, dict[str, Any]] = {}
    counter = {"n": 0}

    def _runner(icp_name: str) -> list[LeadCard]:
        if pipeline_runner is not None:
            return pipeline_runner(icp_name)
        return run_for_icp(config_dir, runtime_path, _ENV_PATH, icp_name)

    def _gemini() -> CognitionClient:
        if cognition_client is not None:
            return cognition_client
        env = load_env(_ENV_PATH)
        key = env.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
        if not key:
            raise HTTPException(status_code=400, detail="GEMINI_API_KEY ausente no .env")
        return GeminiClient(key, model=load_runtime(runtime_path).gemini.model)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (_STATIC_DIR / "index.html").read_text(encoding="utf-8")

    @app.get("/api/config")
    def api_config() -> dict[str, Any]:
        return load_config(config_dir, runtime_path)

    @app.get("/api/config/hypotheses")
    def api_get_hypotheses() -> dict[str, Any]:
        return read_hypotheses(config_dir)

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

    @app.post("/api/assist/icp")
    def api_assist_icp(req: AssistRequest) -> dict[str, Any]:
        client = _gemini()
        try:
            icp = assist_icp(req.description, client)
        except (RateLimitError, GeminiError) as exc:
            raise HTTPException(status_code=502, detail=f"falha no Gemini: {exc}") from exc
        except ValidationError as exc:
            raise HTTPException(
                status_code=422, detail="o Gemini retornou um ICP invalido"
            ) from exc
        return icp.model_dump()

    @app.post("/api/run")
    def api_run(req: RunRequest) -> dict[str, Any]:
        try:
            cards = _runner(req.icp_name)
        except InvalidName as exc:
            raise HTTPException(status_code=400, detail=f"nome invalido: {req.icp_name}") from exc
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail=f"ICP nao encontrado: {req.icp_name}"
            ) from exc
        except MissingKeys as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (RateLimitError, GeminiError) as exc:
            raise HTTPException(status_code=502, detail=f"falha externa: {exc}") from exc
        counter["n"] += 1
        run_id = f"run-{counter['n']}"
        leads = [c.model_dump() for c in cards]
        runs[run_id] = {"status": "done", "leads": leads}
        return {"run_id": run_id, "status": "done", "count": len(leads), "leads": leads}

    @app.get("/api/run/{run_id}")
    def api_run_status(run_id: str) -> dict[str, Any]:
        if run_id not in runs:
            raise HTTPException(status_code=404, detail=f"run nao encontrado: {run_id}")
        return runs[run_id]

    return app


app = create_app()
