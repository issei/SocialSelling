"""Step defs — ADR-006 process-only-new (pytest-bdd). Sem rede; corpus em tmp_path."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from socialselling.contracts import CompanyEntity, HypothesisCatalog, Inference, ObservedEvidence
from socialselling.core.cache import JsonCache
from socialselling.corpus.store import CorpusStore
from socialselling.modules.m2_extracao import run_m2
from socialselling.signals import DISQUALIFIER_VOCAB, intent_vocab

_ROOT = Path(__file__).resolve().parents[2]
_NOW = datetime(2026, 1, 1, tzinfo=UTC)

scenarios("../features/adr006_process_only_new.feature")


def _vocab() -> list[str]:
    raw = json.loads((_ROOT / "config" / "hypotheses_catalog.json").read_text("utf-8"))
    return intent_vocab(HypothesisCatalog.model_validate(raw))


def _make_inference(website: str, name: str = "Empresa Teste") -> Inference:
    return Inference(
        company=CompanyEntity(
            company_id="abc123def456abc1",
            normalized_name=name,
            website=website,
            confidence=0.85,
        ),
        people=[],
        derived_from=["ev_old_001"],
        confidence=0.85,
        intent_signals=[],
        disqualifiers=[],
        persona="empresa",
    )


class _SpyGemini:
    """Cliente Gemini fake com spy de contagem de chamadas."""

    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.calls = 0
        self._response: dict[str, Any] = response or {
            "inferences": [
                {
                    "company": {
                        "normalized_name": "Gamma Servicos",
                        "website": "https://gamma.com.br",
                        "confidence": 0.82,
                    },
                    "people": [],
                    "derived_from": ["ev_gamma_001"],
                    "intent_signals": [],
                    "disqualifiers": [],
                    "confidence": 0.82,
                    "persona": "empresa",
                }
            ]
        }

    def generate_json(self, prompt: str) -> dict[str, Any]:
        self.calls += 1
        return self._response


def _make_evidence(evidence_id: str, source_url: str) -> ObservedEvidence:
    return ObservedEvidence(
        evidence_id=evidence_id,
        query="test",
        source_url=source_url,
        title="Test Evidence",
        snippet="Empresa de servicos com crescimento acelerado.",
        captured_at="2026-01-01T00:00:00+00:00",
        source_trust=0.8,
        missing_evidence=False,
    )


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


# -------------------------------------------------------------------------
# Given steps
# -------------------------------------------------------------------------


@given('um corpus com extração válida para o domínio "acme.com.br"')
def _given_valid_corpus(ctx: dict[str, Any], tmp_path: Path) -> None:
    store = CorpusStore(tmp_path / "corpus.json")
    inf = _make_inference("https://acme.com.br", "Acme Servicos")
    store.put_cached_inference("acme.com.br", inf.model_dump())
    ctx["corpus_store"] = store
    ctx["expected_inference_name"] = "Acme Servicos"


@given('uma evidência com source_url "https://acme.com.br/sobre"')
def _given_evidence_acme(ctx: dict[str, Any]) -> None:
    ctx["evidences"] = [_make_evidence("ev_acme_001", "https://acme.com.br/sobre")]


@given('um corpus com extração pendente para o domínio "beta.com.br"')
def _given_pending_corpus(ctx: dict[str, Any], tmp_path: Path) -> None:
    store = CorpusStore(tmp_path / "corpus.json")
    store.mark_pending("beta.com.br")
    ctx["corpus_store"] = store


@given('uma evidência com source_url "https://beta.com.br/home"')
def _given_evidence_beta(ctx: dict[str, Any]) -> None:
    ctx["evidences"] = [_make_evidence("ev_beta_001", "https://beta.com.br/home")]


@given("um corpus vazio")
def _given_empty_corpus(ctx: dict[str, Any], tmp_path: Path) -> None:
    store = CorpusStore(tmp_path / "corpus.json")
    ctx["corpus_store"] = store


@given('uma evidência com source_url "https://gamma.com.br/"')
def _given_evidence_gamma(ctx: dict[str, Any]) -> None:
    ctx["evidences"] = [_make_evidence("ev_gamma_001", "https://gamma.com.br/")]


# -------------------------------------------------------------------------
# When steps
# -------------------------------------------------------------------------


@when("eu executo o M2 com corpus_store")
def _when_run_m2(ctx: dict[str, Any], tmp_path: Path) -> None:
    spy = _SpyGemini()
    ctx["spy"] = spy
    ctx["result"] = run_m2(
        ctx["evidences"],
        client=spy,
        cache=JsonCache(tmp_path / "cache"),
        now=_NOW,
        cache_ttl_hours=24,
        intent_vocab=_vocab(),
        disqualifier_vocab=DISQUALIFIER_VOCAB,
        corpus_store=ctx["corpus_store"],
    )


# -------------------------------------------------------------------------
# Then steps
# -------------------------------------------------------------------------


@then("o Gemini não é chamado nenhuma vez")
def _then_zero_calls(ctx: dict[str, Any]) -> None:
    assert ctx["spy"].calls == 0, f"Esperava 0 chamadas ao Gemini, mas foram {ctx['spy'].calls}"


@then("a inferência retornada corresponde à do corpus")
def _then_matches_corpus(ctx: dict[str, Any]) -> None:
    result: list[Inference] = ctx["result"]
    assert len(result) == 1
    assert result[0].company.normalized_name == ctx["expected_inference_name"]


@then("o Gemini é chamado exatamente 1 vez")
def _then_one_call(ctx: dict[str, Any]) -> None:
    assert ctx["spy"].calls == 1, f"Esperava 1 chamada ao Gemini, mas foram {ctx['spy'].calls}"


@then('a inferência de "gamma.com.br" é armazenada no corpus como válida')
def _then_stored_in_corpus(ctx: dict[str, Any]) -> None:
    store: CorpusStore = ctx["corpus_store"]
    cached = store.get_cached_inference("gamma.com.br")
    assert cached is not None, "Inferência de gamma.com.br não foi armazenada no corpus"
    assert cached.get("company", {}).get("website") == "https://gamma.com.br"
