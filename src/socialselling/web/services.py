"""Ponte fina entre a UI web e o núcleo (lê/grava os mesmos artefatos de config).

NÃO contém lógica de pipeline — apenas orquestra leitura/escrita de configuração
e delega ao núcleo. Mantém o núcleo (M1–M5) intocado (ADR-002).
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from socialselling.config import load_env, load_runtime
from socialselling.contracts import HypothesisCatalog, ICPCriteria, LeadCard
from socialselling.core.atomic import atomic_write_text
from socialselling.corpus.integration import accumulate_and_rank
from socialselling.corpus.store import CorpusStore
from socialselling.corpus.waves import WaveStore
from socialselling.learning.feedback_store import FeedbackStore
from socialselling.learning.schemas import FeedbackFeatures, FeedbackLabel, LearnedWeights
from socialselling.learning.tuner import retrain
from socialselling.orchestrator import run_pipeline
from socialselling.skills.gemini_client import (
    CognitionClient,
    GeminiClient,
    GeminiError,
    RateLimitError,
)
from socialselling.skills.tavily_client import TavilyClient

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_DIR = _ROOT / "config"
DEFAULT_RUNTIME = _ROOT / "config" / "runtime.toml"

_ICP_NAME_RE = re.compile(r"^icp_criteria[\w.\-]*\.json$")
_SCORING_KEYS = (
    "w_fit",
    "w_intent",
    "confidence_exponent",
    "w_fit_tech",
    "w_fit_industry",
)


class InvalidName(ValueError):
    """Nome de arquivo de ICP fora do padrão permitido."""


class MissingKeys(RuntimeError):
    """Chaves de API ausentes no .env para executar o pipeline."""


class CognitionUnavailable(RuntimeError):
    """O ciclo não produziu NADA porque a cognição (Gemini) falhou (ex.: 429/billing).

    Carrega a mensagem real do provedor para a UI exibir algo acionável, em vez de
    uma tabela vazia silenciosa. Distingue 'busca não achou leads' de 'sensor caiu'.
    """


class _CapturingCognition:
    """Embrulha o cliente Gemini e GUARDA o último erro de cognição.

    O M2 captura RateLimitError/GeminiError (degradação por design) e devolve []; este
    wrapper preserva a causa para o limite web decidir se deve surfaciá-la ao usuário.
    """

    def __init__(self, inner: CognitionClient) -> None:
        self._inner = inner
        self.last_error: Exception | None = None

    def generate_json(self, prompt: str) -> dict[str, Any]:
        try:
            return self._inner.generate_json(prompt)
        except (RateLimitError, GeminiError) as exc:
            self.last_error = exc
            raise


def _safe_icp_path(config_dir: Path, name: str) -> Path:
    if not _ICP_NAME_RE.match(name):
        raise InvalidName(name)
    return config_dir / name


def load_config(
    config_dir: Path = DEFAULT_CONFIG_DIR,
    runtime_path: Path = DEFAULT_RUNTIME,
) -> dict[str, Any]:
    """Snapshot legível da configuração atual para a UI."""
    cfg = load_runtime(runtime_path)
    icp_files = sorted(p.name for p in config_dir.glob("icp_criteria*.json"))
    catalog_path = config_dir / "hypotheses_catalog.json"
    hypotheses: list[dict[str, Any]] = []
    if catalog_path.exists():
        catalog = HypothesisCatalog.model_validate(
            json.loads(catalog_path.read_text(encoding="utf-8"))
        )
        hypotheses = [
            {"id": h.hypothesis_id, "prior": h.prior, "description": h.description}
            for h in catalog.hypotheses
        ]
    return {
        "icp_files": icp_files,
        "scoring": cfg.scoring.model_dump(),
        "tavily": {
            "persona_term": cfg.tavily.persona_term,
            "include_domains": cfg.tavily.include_domains,
            "max_queries": cfg.tavily.max_queries,
        },
        "hypotheses": hypotheses,
    }


def read_icp(config_dir: Path, name: str) -> dict[str, Any]:
    """Lê o JSON cru de um ICP (para edição na UI). Valida o nome do arquivo."""
    path = _safe_icp_path(config_dir, name)
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def read_hypotheses(config_dir: Path) -> dict[str, Any]:
    """Lê o catálogo de hipóteses cru (para edição na UI)."""
    data: dict[str, Any] = json.loads(
        (config_dir / "hypotheses_catalog.json").read_text(encoding="utf-8")
    )
    return data


def save_icp(config_dir: Path, name: str, icp: ICPCriteria) -> None:
    """Grava o ICP (já validado) atomicamente."""
    path = _safe_icp_path(config_dir, name)
    atomic_write_text(path, json.dumps(icp.model_dump(), ensure_ascii=False, indent=2) + "\n")


def save_hypotheses(config_dir: Path, catalog: HypothesisCatalog) -> None:
    """Grava o catálogo de hipóteses (já validado) atomicamente."""
    path = config_dir / "hypotheses_catalog.json"
    atomic_write_text(path, json.dumps(catalog.model_dump(), ensure_ascii=False, indent=2) + "\n")


_ICP_ASSIST_PROMPT = (
    "Voce e especialista em ICP B2B. A partir da DESCRICAO do negocio, gere um "
    "icp_criteria valido. Responda SOMENTE com JSON (sem markdown) neste formato exato "
    "(nao adicione nem renomeie campos):\n"
    '{"icp_id":str_snake_case,"firmographics":{"industries":[str_minusculo],'
    '"employee_range":{"min":int>=0,"max":int>=min},"geographies":{"country":str_ISO2,'
    '"regions":[str]},"business_models":[str]},"technographics":{"mandatory":[str],'
    '"preferred":[str],"excluded":[str]},"persona_matrix":{"target_roles":[STR_MAIUSC],'
    '"min_seniority":str},"intent_triggers":[STR_MAIUSC]}\n'
    "Regras: industries/technographics em minusculas (busca em PT-BR); country ISO-2; "
    "min<=max; sem campos extras. Para servicos cujo decisor e a fundadora, "
    "technographics.mandatory pode ser [] (ferramenta de gestao nao e detectavel).\n\n"
    "DESCRICAO DO NEGOCIO:\n"
)


def assist_icp(description: str, client: CognitionClient) -> ICPCriteria:
    """Gera um rascunho de ICP a partir da descrição do negócio (Gemini) e valida."""
    payload = client.generate_json(_ICP_ASSIST_PROMPT + description.strip())
    return ICPCriteria.model_validate(payload)


def run_for_icp(
    config_dir: Path,
    runtime_path: Path,
    env_path: Path,
    icp_name: str,
) -> list[LeadCard]:
    """Executa o pipeline real (Tavily+Gemini) para o ICP selecionado → Lead Cards."""
    env = load_env(env_path)
    tkey = env.get("TAVILY_API_KEY") or os.environ.get("TAVILY_API_KEY", "")
    gkey = env.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
    if not tkey or not gkey:
        raise MissingKeys("TAVILY_API_KEY/GEMINI_API_KEY ausentes no .env")
    cfg = load_runtime(runtime_path)
    icp = ICPCriteria.model_validate(read_icp(config_dir, icp_name))
    catalog = HypothesisCatalog.model_validate(
        json.loads((config_dir / "hypotheses_catalog.json").read_text(encoding="utf-8"))
    )
    now = datetime.now(UTC)
    # Busca incremental (ADR-006): a onda do ICP varia as queries p/ trazer leads NOVOS.
    # Onda só avança no modo acumulativo; stateless usa wave=0 (paridade).
    waves = WaveStore(_ROOT / cfg.corpus.waves_path) if cfg.corpus.enabled else None
    wave = waves.current(icp_name) if waves is not None else 0
    gemini = _CapturingCognition(GeminiClient(gkey, model=cfg.gemini.model))
    # Corpus inicializado antes do pipeline para ativar process-only-new (ADR-006).
    corpus_store = CorpusStore(_ROOT / cfg.corpus.path) if cfg.corpus.enabled else None
    fresh = run_pipeline(
        icp,
        tavily=TavilyClient(tkey),
        gemini=gemini,
        hypotheses=catalog,
        cache_root=_ROOT / "data" / "cache",
        now=now,
        cfg=cfg,
        wave=wave,
        corpus_store=corpus_store,
    )
    if corpus_store is None:
        cards = fresh
    else:
        # Corpus acumulativo (ADR-006): na UI, cada execução ACUMULA e re-ranqueia o
        # corpus inteiro por score.
        cards = accumulate_and_rank(
            corpus_store, fresh, now, max_display=cfg.runtime.max_leads_per_cycle
        )
        # A onda só avança quando o ciclo PRODUZIU leads. Avançar em run vazio "queimaria"
        # ondas boas (cacheadas) quando a busca/cognição degrada — ex.: Gemini 429.
        if waves is not None and fresh:
            waves.advance(icp_name)
    # Nada a exibir + cognição falhou ⇒ surface o motivo REAL (ex.: billing/429 do Gemini),
    # não uma lista vazia silenciosa. Com corpus prévio (cards != []), mostramos o que há.
    if not cards and gemini.last_error is not None:
        raise CognitionUnavailable(str(gemini.last_error))
    return cards


def save_scoring(runtime_path: Path, scoring: dict[str, float]) -> None:
    """Atualiza os pesos de [scoring] no runtime.toml, preservando comentários."""
    text = runtime_path.read_text(encoding="utf-8")
    for key in _SCORING_KEYS:
        if key in scoring:
            text = re.sub(
                rf"(?m)^{key}\s*=\s*.*$",
                f"{key} = {scoring[key]}",
                text,
            )
    atomic_write_text(runtime_path, text)


def record_feedback(
    store: FeedbackStore,
    runtime_path: Path,
    *,
    company_id: str,
    label: str,
    features: FeedbackFeatures,
    now: datetime,
) -> LearnedWeights:
    """Registra o voto e, se o aprendizado estiver ligado e com amostra suficiente,
    reajusta e GRAVA os pesos do score (auto-apply, ADR-007).

    O feedback é sempre persistido; o reajuste só ocorre com `[learning].enabled`.
    """
    cfg = load_runtime(runtime_path)
    if label == "none":
        store.remove(company_id)
    else:
        store.upsert(company_id, FeedbackLabel(label), features, now)

    likes, dislikes = store.counts()
    if not cfg.learning.enabled:
        return LearnedWeights(
            w_fit=cfg.scoring.w_fit,
            w_intent=cfg.scoring.w_intent,
            n_likes=likes,
            n_dislikes=dislikes,
            applied=False,
            reason="aprendizado desligado",
        )

    learned = retrain(
        store,
        {"w_fit": cfg.scoring.w_fit, "w_intent": cfg.scoring.w_intent},
        cfg.learning,
    )
    if learned.applied:
        save_scoring(runtime_path, {"w_fit": learned.w_fit, "w_intent": learned.w_intent})
    return learned


def feedback_labels(store: FeedbackStore) -> dict[str, str]:
    """Mapa company_id -> 'like'|'dislike' para a UI pintar os selos ao carregar."""
    return store.labels()


_CSV_HEADERS = [
    "Nome", "Empresa", "Cargo", "Setor", "Localizacao",
    "Instagram", "LinkedIn", "Website", "E-mail", "Telefone", "Fontes",
]


def leads_to_csv(cards: list[LeadCard]) -> str:
    """Serializa Lead Cards em CSV UTF-8 com BOM — delimitador ';'; sem scoring."""
    buf = io.StringIO()
    buf.write("﻿")  # BOM UTF-8
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(_CSV_HEADERS)
    for card in cards:
        writer.writerow([
            card.display_name,
            card.company or "",
            card.role or "",
            card.sector or "",
            card.location or "",
            card.links.instagram or "",
            card.links.linkedin or "",
            card.links.website or "",
            card.contact.email or "",
            card.contact.phone or "",
            " | ".join(card.sources),
        ])
    return buf.getvalue()
