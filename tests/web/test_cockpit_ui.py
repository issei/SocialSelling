"""Testes do cockpit v2 (redesign de alta densidade — Discovery Intelligence).

Front-end estático renderizado client-side; aqui validamos a PRESENÇA da nova
estrutura (dashboard de KPIs, sidebar em abas, header operacional) e a preservação
dos contratos/ids antigos. FastAPI TestClient, sem rede. Ver plano cockpit v2.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from socialselling.web.app import create_app


def _body() -> str:
    text: str = TestClient(create_app()).get("/").text
    return text


def test_dashboard_kpis_presentes() -> None:
    body = _body()
    # Área 5: os 5 cartões de métrica agregada do lote.
    for kpi in ("dashTotal", "dashAvg", "dashPriority", "dashTiming", "dashEnriched"):
        assert f'id="{kpi}"' in body, kpi


def test_sidebar_em_abas() -> None:
    body = _body()
    # Área 3: configuração isolada em abas (ICP / Pesos / Hipóteses).
    for tab in ("tabIcp", "tabWeights", "tabHypotheses"):
        assert f'id="{tab}"' in body, tab
    for panel in ("panelIcp", "panelWeights", "panelHypotheses"):
        assert f'id="{panel}"' in body, panel
    assert "setupTabs" in body


def test_header_operacional() -> None:
    body = _body()
    # Áreas 1+4 unificadas: seletor de ICP ativo + disparo da prospecção no topo.
    assert "<header" in body
    assert 'id="runIcp"' in body
    assert 'id="btnRun"' in body


def test_discovery_puro_sem_outreach() -> None:
    body = _body()
    # CLAUDE.md §1: nada de mensageria de outreach. O drawer NÃO gera/copia mensagem.
    lowered = body.lower()
    assert "conversation blueprint" not in lowered
    assert "copiar mensagem" not in lowered


def test_drawer_fechado_nao_bloqueia_cliques() -> None:
    # Regressão: #drawerWrap é `fixed inset-0 z-50` (cobre a tela inteira). Fechado, precisa
    # de pointer-events:none — senão engole TODOS os cliques da página (sem erro visível).
    body = _body()
    assert "#drawerWrap.drawer-hidden" in body
    rule = re.search(r"#drawerWrap\.drawer-hidden\s*\{[^}]*pointer-events:\s*none", body)
    assert rule is not None


def test_feedback_like_dislike_presente() -> None:
    # ADR-007: botões 👍/👎 por linha e no drawer, toast e integração com /api/feedback.
    body = _body()
    assert 'id="toast"' in body
    for fn in ("fbBtn", "fb(", "sendFeedback", "fbDrawer", "FEEDBACK"):
        assert fn in body, fn
    assert "/api/feedback" in body


def test_invariantes_antigos_preservados() -> None:
    # Não-regressão: os marcadores travados por test_pages/test_results_ui sobrevivem.
    body = _body()
    for anchor in ("parametros", "assistente", "resultados"):
        assert f'id="{anchor}"' in body, anchor
    for ident in ("leadsTable", "leadsBody", "leadsEmpty", "leadDrawer"):
        assert f'id="{ident}"' in body, ident
    assert 'role="dialog"' in body
    assert 'data-sort="display_name"' in body
    assert 'data-sort="p_score"' in body
    assert "renderTable" in body
    assert "openDrawer" in body
