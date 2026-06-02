# SDD-11: Estratégia de Testes e Cenários BDD
## SocialSelling — Solution Design Document
### Versão: 1.0-MVP | Classificação: CONFIDENCIAL — ENGENHARIA

---

**Autores:** Staff QA Architect · Principal Enterprise Architect · Arquiteto de Sistemas Cognitivos

**Data de emissão:** 2024-11-15 | **Ciclo de revisão:** A cada adição de módulo ou hipótese ao sistema

---

## SEÇÃO 1: ESTRATÉGIA DE TESTES UNITÁRIOS COM PYTEST

### 1.1 Política de Isolamento de Rede

Todos os testes unitários do SocialSelling devem ser **completamente herméticos**: nenhuma chamada real é feita para Instagram, LinkedIn, CNPJ.ws, OpenAI ou Tavily durante a execução da suíte unitária. O isolamento é garantido por três mecanismos:

**Mecanismo 1 — pytest-mock:** utilizado para substituir funções e métodos que fazem chamadas a scrapers ou APIs externas. A fixture `mocker` (injetada automaticamente pelo pytest-mock) intercepta chamadas antes que cheguem ao adaptador HTTP, retornando payloads controlados definidos nos arquivos de fixture.

**Mecanismo 2 — responses (biblioteca):** utilizado para interceptar chamadas HTTP realizadas pela biblioteca `requests` ou `httpx`. Qualquer chamada HTTP não registrada no mock `@responses.activate` causa falha imediata do teste — garantindo que nenhum teste "vaze" para a rede sem ser detectado.

**Mecanismo 3 — Banco de dados in-memory:** todos os testes unitários que necessitam de persistência utilizam SQLite com `aiosqlite` em modo in-memory (`sqlite+aiosqlite:///:memory:`). O schema completo é aplicado via Alembic migrations no setup da fixture de sessão. Testes de integração que necessitam de PostgreSQL real são marcados com `@pytest.mark.integration` e executados apenas na esteira de CD de Staging.

**Estrutura de diretórios de fixtures:**

```
tests/
├── conftest.py                          # Fixtures compartilhadas globalmente
├── fixtures/
│   ├── mock_instagram_profile.json      # Resposta simulada de perfil Instagram
│   ├── mock_instagram_posts.json        # Posts e captions simulados
│   ├── mock_instagram_anchor_comments.json  # Comentários em âncoras
│   ├── mock_linkedin_profile.json       # Perfil LinkedIn com cargo e tenure
│   ├── mock_linkedin_jobs.json          # Vagas ativas simuladas
│   ├── mock_cnpj_response.json          # Dados cadastrais CNPJ simulados
│   ├── mock_crm_webhook_won.json        # Payload de CLOSED_WON do CRM
│   └── mock_crm_webhook_lost.json       # Payload de CLOSED_LOST do CRM
├── unit/
│   ├── test_scoring.py                  # MatrixRankFunction, O_score, C_score, P_score
│   ├── test_freshness.py                # E_fresh, Freshness Decay, modos degradados
│   ├── test_rcs.py                      # Resolution Confidence Score, Jaro-Winkler
│   ├── test_subjective_logic.py         # Desconto, Consenso, guarda ZeroDivisionError
│   ├── test_bayesian.py                 # Atualização bayesiana, transições de estado
│   ├── test_committee.py                # S_persona, CommitteeCompleteness, SC vs BMO
│   ├── test_finops.py                   # EIG, MIC, FinOps Stopping Rule
│   ├── test_dss.py                      # Discovery Saturation Score, Delta Search
│   ├── test_graph_nodes.py              # Mutação de estado do grafo LangGraph
│   └── test_blueprint.py               # Conversation Blueprint Generator (CBG)
├── integration/
│   ├── test_api_endpoints.py            # Testes de integração dos endpoints FastAPI
│   ├── test_aurora_connection.py        # Conexão e queries ao Aurora PostgreSQL real
│   └── test_crm_webhook.py              # Webhook CRM end-to-end
├── bdd/
│   ├── features/
│   │   ├── lead_qualification.feature   # Cenário 1: Centralização Excessiva
│   │   ├── lead_pruning.feature         # Cenário 2: Poda por hierarquia
│   │   └── degraded_operation.feature   # Cenário 3: LinkedIn indisponível
│   └── step_definitions/
│       ├── common_steps.py
│       ├── scoring_steps.py
│       └── degraded_steps.py
└── smoke/
    ├── test_health_check.py             # Smoke: endpoint /health responde
    └── test_basic_flow.py               # Smoke: fluxo básico sem dados reais
```

**`conftest.py` — Fixtures compartilhadas:**

```python
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from typing import Generator

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_instagram_profile() -> dict:
    """Payload simulado de perfil Instagram — Lex & Associados."""
    return json.loads((FIXTURES_DIR / "mock_instagram_profile.json").read_text())


@pytest.fixture
def mock_linkedin_jobs() -> list[dict]:
    """Lista de vagas ativas simuladas do LinkedIn — 3 vagas operacionais."""
    return json.loads((FIXTURES_DIR / "mock_linkedin_jobs.json").read_text())


@pytest.fixture
def mock_cnpj_data() -> dict:
    """Dados cadastrais CNPJ simulados — CNAE 6911-7/00 (Advocacia)."""
    return json.loads((FIXTURES_DIR / "mock_cnpj_response.json").read_text())


@pytest.fixture
def icp_contract_advocacia() -> dict:
    """Contrato ICP padrão para o segmento Advocacia."""
    return {
        "contract_id": "test-contract-001",
        "target_segments": ["Advocacia"],
        "weight_fit": 0.45,
        "weight_intent": 0.35,
        "weight_reachability": 0.20,
        "tau_finops": 0.15,
        "delta_dss": 0.05,
        "dss_window_size": 50,
        "alpha_rank": 0.60,
        "beta_rank": 4.0,
        "icp_centralization_min": 0.60,
        "icp_maturity_threshold": 0.40,
        "delta_penalty": 0.15,
        "keyword_taxonomy": {
            "pain_keywords": [
                "delegar", "centralização", "sobrecarga", "processo",
                "autonomia", "equipe", "gargalo", "estrutura"
            ]
        },
    }


@pytest.fixture
def mock_scraper_instagram(mocker) -> MagicMock:
    """Mock do Instagram Scraper — retorna dados do Lex & Associados."""
    mock = mocker.patch("app.scrapers.instagram.InstagramScraper.fetch_profile")
    mock.return_value = json.loads((FIXTURES_DIR / "mock_instagram_profile.json").read_text())
    return mock


@pytest.fixture
def mock_scraper_linkedin_rate_limited(mocker) -> MagicMock:
    """Mock do LinkedIn Scraper simulando HTTP 429 (rate-limited)."""
    mock = mocker.patch("app.scrapers.linkedin.LinkedInScraper.fetch_profile")
    from app.scrapers.exceptions import ScraperRateLimitError
    mock.side_effect = ScraperRateLimitError("LinkedIn rate-limited — HTTP 429")
    return mock
```

### 1.2 Testes de Mutação de Estado do Grafo LangGraph

Para cada um dos 10 nós do grafo LangGraph, são definidos dois testes obrigatórios: (1) caminho feliz — verifica que o nó transforma corretamente o `LeadState` quando inputs são válidos; (2) caminho de falha — verifica que o nó trata exceções corretamente e marca o estado com `errors` sem propagar a exceção para fora do nó.

**Template de teste para nós do grafo:**

```python
# tests/unit/test_graph_nodes.py

import pytest
from copy import deepcopy
from app.graph.nodes import ScrapingNode, NormalizationNode, EntityResolutionNode
from app.graph.state import LeadState, OperatingMode

@pytest.fixture
def base_lead_state() -> LeadState:
    """Estado inicial mínimo do grafo para testes unitários."""
    return LeadState(
        lead_id="LE-TEST-001",
        cycle_id="CYC-TEST-001",
        operating_mode=OperatingMode.FULL,
        evidence_batch=[],
        entity_nodes={},
        entity_edges=[],
        inferences=[],
        hypotheses={},
        committee=None,
        scores=None,
        blueprint=None,
        stopping_triggered=False,
        stopping_reason=None,
        errors=[],
        compensation_executed=[],
    )

class TestScrapingNode:
    """Testes para o nó de coleta de evidências (M1 — Sensory Search)."""

    def test_scraping_node_full_mode_populates_evidence_batch(
        self, base_lead_state, mock_scraper_instagram, mock_linkedin_jobs, mocker
    ):
        """
        Caminho feliz: nó de scraping em modo FULL popula evidence_batch com
        evidências de ambas as fontes e define operating_mode como FULL.
        """
        mocker.patch(
            "app.scrapers.linkedin.LinkedInScraper.fetch_jobs",
            return_value=mock_linkedin_jobs,
        )
        node = ScrapingNode()
        result_state = node.execute(base_lead_state)

        assert result_state.operating_mode == OperatingMode.FULL
        assert len(result_state.evidence_batch) >= 2
        assert result_state.errors == []
        assert any(e.source == "instagram_scraper" for e in result_state.evidence_batch)
        assert any(e.source == "linkedin_scraper" for e in result_state.evidence_batch)

    def test_scraping_node_linkedin_rate_limited_activates_degraded_mode(
        self, base_lead_state, mock_scraper_instagram, mock_scraper_linkedin_rate_limited
    ):
        """
        Falha parcial: LinkedIn rate-limited ativa modo DEGRADED_LINKEDIN.
        O nó não deve lançar exceção — deve registrar a compensação e continuar.
        """
        node = ScrapingNode()
        result_state = node.execute(base_lead_state)

        assert result_state.operating_mode == OperatingMode.DEGRADED_LINKEDIN
        assert "DEGRADED_LINKEDIN_activated" in result_state.compensation_executed
        assert result_state.errors == []  # Não é erro — é modo degradado esperado
        # Evidências de Instagram ainda devem estar presentes
        assert any(e.source == "instagram_scraper" for e in result_state.evidence_batch)

    def test_scraping_node_dual_source_failure_emits_critical_alert(
        self, base_lead_state, mocker
    ):
        """
        Falha total: ambos os scrapers falham → CACHE_ONLY, DSS=0 forçado, alerta emitido.
        """
        from app.scrapers.exceptions import ScraperUnavailableError
        mocker.patch(
            "app.scrapers.instagram.InstagramScraper.fetch_profile",
            side_effect=ScraperUnavailableError("Instagram scraper down"),
        )
        mocker.patch(
            "app.scrapers.linkedin.LinkedInScraper.fetch_profile",
            side_effect=ScraperUnavailableError("LinkedIn scraper down"),
        )
        mock_alert = mocker.patch("app.observability.emit_critical_alert")

        node = ScrapingNode()
        result_state = node.execute(base_lead_state)

        assert result_state.operating_mode == OperatingMode.CACHE_ONLY
        assert result_state.stopping_triggered is True
        assert result_state.stopping_reason == "dual_source_failure"
        mock_alert.assert_called_once()
```

### 1.3 Testes Unitários Críticos — 8 Funções de Teste Detalhadas

```python
# tests/unit/test_scoring.py

import math
import pytest
from app.scoring.matrix_rank import matrix_rank_function, compute_f_c_factor
from app.scoring.opportunity import compute_o_score
from app.scoring.confidence import compute_c_score
from app.events import InvestigationOpportunityEvent


class TestMatrixRankFunction:
    """Testes unitários da MatrixRankFunction — P_score = O × (1 - α × e^{-β × C})."""

    def test_matrix_rank_function_alto_o_alto_c(self):
        """
        TESTE 1: P_score correto para Quadrante Alto-O/Alto-C.

        Dado O=0.90, C=0.80, α=0.60, β=4.0:
        f(C) = 1 - 0.60 × e^{-4.0 × 0.80}
             = 1 - 0.60 × e^{-3.20}
             = 1 - 0.60 × 0.04076
             = 1 - 0.02446
             = 0.97554
        P = 0.90 × 0.97554 = 0.87799

        Verificação: P_score deve ser ≈ 0.878.
        """
        result = matrix_rank_function(
            o_score=0.90,
            c_score=0.80,
            alpha=0.60,
            beta=4.0,
        )
        assert abs(result.p_score - 0.878) < 0.002  # Tolerância de 0.2%
        assert result.threshold_band == "QUALIFIED — PRIORITY ACTION"
        assert result.data_quality_flag == "NORMAL"

    def test_matrix_rank_function_investigation_opportunity_event(self, mocker):
        """
        TESTE 2: Quadrante Alto-O/Baixo-C emite InvestigationOpportunity event.

        Dado O=0.75, C=0.25 (O≥0.70 e C<0.35 e P≥0.30):
        f(0.25) = 1 - 0.60 × e^{-1.0} = 1 - 0.60 × 0.3679 = 1 - 0.2207 = 0.7793
        P = 0.75 × 0.7793 = 0.5845

        Verificações: data_quality_flag='LOW', InvestigationOpportunity emitido.
        """
        mock_emit = mocker.patch("app.scoring.matrix_rank.emit_event")

        result = matrix_rank_function(
            o_score=0.75,
            c_score=0.25,
            alpha=0.60,
            beta=4.0,
        )

        assert result.data_quality_flag == "LOW"
        assert abs(result.p_score - 0.5845) < 0.005
        mock_emit.assert_called_once_with(
            InvestigationOpportunityEvent(
                o_score=0.75,
                c_score=0.25,
                p_score=result.p_score,
            )
        )

    def test_matrix_rank_function_tiebreak_five_levels(self):
        """
        Verifica que leads com P_score dentro da tolerância de empate (|ΔP| < 0.005)
        são ordenados pelos 5 critérios de desempate na sequência correta:
        O_score DESC, C_score DESC, feat_e_fresh DESC, bmo_momentum_score DESC, UUID ASC.
        """
        from app.scoring.ranking import rank_leads

        leads = [
            {"entity_id": "b-uuid", "p_score": 0.7010, "o_score": 0.80, "c_score": 0.70, "feat_e_fresh": 0.90, "bmo_momentum_score": 0.60},
            {"entity_id": "a-uuid", "p_score": 0.7012, "o_score": 0.80, "c_score": 0.70, "feat_e_fresh": 0.90, "bmo_momentum_score": 0.60},
            # Diferença: 0.0002 < 0.005 → empate → desempate por UUID ASC
        ]
        ranked = rank_leads(leads, tiebreak_tolerance=0.005)
        assert ranked[0]["entity_id"] == "a-uuid"  # UUID ASC: 'a' < 'b'


# tests/unit/test_freshness.py

import math
import pytest
from app.scoring.freshness import compute_e_fresh, EvidenceType, OperatingMode


class TestFreshnessDecay:

    def test_freshness_decay_half_life_post_instagram(self):
        """
        TESTE 3: E_fresh deve ser exatamente 0.50 quando Δt = t₁/₂.

        Para post_caption_instagram: t₁/₂ = 14 dias.
        E_fresh(14) = e^{-ln(2) × 14/14} = e^{-ln(2)} = e^{-0.6931} = 0.5000

        Esta é a definição matemática de meia-vida.
        """
        result = compute_e_fresh(
            evidence_type=EvidenceType.POST_CAPTION_INSTAGRAM,
            delta_t_days=14.0,
            operating_mode=OperatingMode.FULL,
        )
        assert abs(result - 0.5000) < 0.0001

    def test_freshness_decay_degraded_instagram_accelerated(self):
        """
        TESTE 4: Modo DEGRADED_INSTAGRAM acelera decaimento para t₁/₂ = 12h = 0.5 dias.

        E_fresh(1 dia) = e^{-ln(2) × 1.0 / 0.5}
                       = e^{-ln(2) × 2.0}
                       = e^{-1.3863}
                       = 0.2500

        Um dia após a captura em modo degradado, a evidência já vale apenas 25%.
        """
        result = compute_e_fresh(
            evidence_type=EvidenceType.POST_CAPTION_INSTAGRAM,
            delta_t_days=1.0,
            operating_mode=OperatingMode.DEGRADED_INSTAGRAM,
        )
        assert abs(result - 0.2500) < 0.0001

    def test_freshness_decay_cnpj_data_long_half_life(self):
        """
        Dados cadastrais CNPJ têm t₁/₂ = 180 dias.
        Após 30 dias, E_fresh deve ser ≈ 0.89.

        E_fresh(30) = e^{-0.6931 × 30/180} = e^{-0.1155} = 0.8909
        """
        result = compute_e_fresh(
            evidence_type=EvidenceType.CNPJ_CADASTRAL_DATA,
            delta_t_days=30.0,
            operating_mode=OperatingMode.FULL,
        )
        assert abs(result - 0.8909) < 0.001


# tests/unit/test_rcs.py

import pytest
from app.entity_resolution.rcs import compute_rcs, normalize_string


class TestResolutionConfidenceScore:

    def test_rcs_auto_merge_identical_strings_same_city_same_cnae(self):
        """
        TESTE 5: Strings idênticas, mesma cidade, CNAE idêntico → RCS ≥ 0.82 (auto-merge).

        JaroWinkler('lex associados', 'lex associados') = 1.0000
        RCS = 1.0000 × λ_spatial(1.00) × λ_CNAE(1.00) = 1.0000
        """
        result = compute_rcs(
            s1="Lex Associados",
            s2="Lex Associados",
            city_s1="São Paulo",
            city_s2="São Paulo",
            cnae_s1="6911700",
            cnae_s2="6911700",
        )
        assert result.rcs_score >= 0.82
        assert result.resolution_decision == "AUTO_MERGE"

    def test_rcs_manual_review_similar_strings_different_states(self):
        """
        Strings similares mas em estados distintos → penalização de λ_spatial=0.70.
        JaroWinkler estimado ≈ 0.95 × 0.70 × λ_CNAE → deve cair na banda MANUAL_REVIEW.
        """
        result = compute_rcs(
            s1="Consultoria Omega",
            s2="Omega Consultores",
            city_s1="São Paulo",
            city_s2="Belo Horizonte",
            cnae_s1="7020400",
            cnae_s2="7020400",
        )
        assert 0.65 <= result.rcs_score < 0.82
        assert result.resolution_decision == "MANUAL_REVIEW"

    def test_rcs_distinct_entities_low_similarity(self):
        """
        Strings completamente distintas → RCS < 0.65 → entidades distintas.
        """
        result = compute_rcs(
            s1="Advocacia Castro & Lima",
            s2="TechSoft Solutions Ltda",
            city_s1="Rio de Janeiro",
            city_s2="São Paulo",
            cnae_s1="6911700",
            cnae_s2="6201500",
        )
        assert result.rcs_score < 0.65
        assert result.resolution_decision == "DISTINCT_ENTITIES"


# tests/unit/test_scoring.py (continuação)

class TestCScore:

    def test_c_score_collapse_when_srs_near_zero(self):
        """
        TESTE 6: Efeito colapso — quando SRS_k = 0 para qualquer fonte, C_score = 0.

        C_score = RCS × C_s × (1-U_committee) × Hypothesis_Confidence × ∏SRS_k
        ∏SRS_k = 0.00 × 0.80 × 0.95 = 0.0000
        C_score = qualquer_valor × 0.0000 = 0.0000

        Propriedade formal: multiplicatividade garante que fonte com SRS=0 colapsa o score.
        """
        result = compute_c_score(
            rcs=0.87,
            c_s_shannon=0.74,
            uncertainty_committee=0.28,
            hypothesis_confidence=0.79,
            srs_per_source={
                "instagram_scraper": 0.0,    # Fonte colapsada
                "linkedin_scraper": 0.80,
                "cnpj_resolver": 0.95,
            },
        )
        assert result.c_score == 0.0
        assert result.srs_product == 0.0

    def test_c_score_healthy_with_all_srs_above_threshold(self):
        """
        Todas as fontes com SRS ≥ 0.75 → C_score saudável.
        ∏SRS = 0.82 × 0.77 × 0.95 = 0.6003
        C_score ≈ 0.87 × 0.74 × (1-0.28) × 0.79 × 0.6003 ≈ 0.218
        (Valor exato depende da implementação completa)
        """
        result = compute_c_score(
            rcs=0.87,
            c_s_shannon=0.74,
            uncertainty_committee=0.28,
            hypothesis_confidence=0.79,
            srs_per_source={
                "instagram_scraper": 0.82,
                "linkedin_scraper": 0.77,
                "cnpj_resolver": 0.95,
            },
        )
        assert result.c_score > 0.0
        assert result.srs_product == pytest.approx(0.6003, abs=0.001)


# tests/unit/test_subjective_logic.py

import pytest
from app.subjective_logic.fusion import consensus_fusion, agent_discounting


class TestSubjectiveLogic:

    def test_consensus_fusion_guard_zero_division(self):
        """
        TESTE 7: Guarda ZeroDivisionError — ambas as fontes com u=0 (certeza absoluta).

        Denominador = u_A + u_B - u_A×u_B = 0 + 0 - 0 = 0 → ZeroDivisionError potencial.

        Comportamento esperado: retornar ω da fonte com maior SRS (SRS_A=0.85 > SRS_B=0.70)
        sem lançar nenhuma exceção.
        """
        omega_A = (0.80, 0.20, 0.00)  # Certeza absoluta de A
        omega_B = (0.30, 0.70, 0.00)  # Certeza absoluta de B (divergente)
        srs_A = 0.85
        srs_B = 0.70

        result = consensus_fusion(omega_A, omega_B, srs_A=srs_A, srs_B=srs_B)

        # Deve retornar omega de A (SRS_A superior) sem exceção
        assert result == (0.80, 0.20, 0.00)
        # Verificar que b+d+u=1
        assert abs(sum(result) - 1.0) < 0.001

    def test_consensus_fusion_standard_case(self):
        """
        Caso padrão: A=(0.60, 0.20, 0.20), B=(0.50, 0.10, 0.40).

        Denominador = 0.20 + 0.40 - 0.20×0.40 = 0.60 - 0.08 = 0.52
        b = (0.60×0.40 + 0.50×0.20) / 0.52 = (0.24 + 0.10) / 0.52 = 0.6538
        d = (0.20×0.40 + 0.10×0.20) / 0.52 = (0.08 + 0.02) / 0.52 = 0.1923
        u = (0.20×0.40) / 0.52 = 0.08 / 0.52 = 0.1538

        Verificação: b+d+u = 0.6538 + 0.1923 + 0.1538 = 0.9999 ≈ 1.0 ✓
        """
        result = consensus_fusion(
            omega_A=(0.60, 0.20, 0.20),
            omega_B=(0.50, 0.10, 0.40),
            srs_A=0.80,
            srs_B=0.80,
        )
        assert abs(result[0] - 0.6538) < 0.001  # b
        assert abs(result[1] - 0.1923) < 0.001  # d
        assert abs(result[2] - 0.1538) < 0.001  # u
        assert abs(sum(result) - 1.0) < 0.001


# tests/unit/test_finops.py

class TestFinOpsStopping:

    def test_finops_stopping_rule_sensor_disabled(self, mocker):
        """
        TESTE 8: Sensor desativado quando EIG/MIC < τ_FinOps.

        Dado:
          sensor = 'linkedin_deep_enrichment'
          EIG = 0.002 bits
          MIC = 0.08 R$
          EIG/MIC = 0.002/0.08 = 0.025 bits/R$0.01

        τ_FinOps = 0.15 bits/R$0.01

        EIG/MIC (0.025) < τ (0.15) → NO-GO → sensor desativado.
        """
        from app.finops.stopping import evaluate_finops_rule
        mock_log = mocker.patch("app.finops.stopping.log_pruning_event")

        result = evaluate_finops_rule(
            sensor_id="linkedin_deep_enrichment",
            eig_bits=0.002,
            mic_brl=0.08,
            tau_finops=0.15,
            lead_id="LE-TEST-001",
            cycle_id="CYC-TEST-001",
        )

        assert result.decision == "NO-GO"
        assert result.eig_mic_ratio == pytest.approx(0.025, abs=0.001)
        assert result.condition_met is True  # "condition_met" = condição de parada atingida
        mock_log.assert_called_once()  # Registro em pruned_reason_log obrigatório

    def test_finops_stopping_rule_sensor_approved(self):
        """
        Sensor aprovado quando EIG/MIC ≥ τ_FinOps.

        EIG = 0.090 bits, MIC = 0.080 R$
        EIG/MIC = 1.125 bits/R$0.01 ≥ τ = 0.15 → GO.
        """
        from app.finops.stopping import evaluate_finops_rule

        result = evaluate_finops_rule(
            sensor_id="linkedin_deep_enrichment",
            eig_bits=0.090,
            mic_brl=0.080,
            tau_finops=0.15,
            lead_id="LE-TEST-001",
            cycle_id="CYC-TEST-001",
        )

        assert result.decision == "GO"
        assert result.eig_mic_ratio == pytest.approx(1.125, abs=0.01)
        assert result.condition_met is False  # Condição de parada NÃO atingida
```

### 1.4 Estrutura Completa do `conftest.py` com Fixtures de Banco

```python
# tests/conftest.py (extensão para banco de dados in-memory)

import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.db.session import get_db_session


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Motor SQLAlchemy in-memory para testes unitários e de integração leve."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Sessão de banco de dados isolada por teste — rollback automático após cada teste."""
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()  # Rollback garante isolamento entre testes
```

### 1.5 Coverage Requirements

**Cobertura global:** mínimo 80% de linhas para o módulo `app/`, verificada pelo flag `--cov-fail-under=80` do PyTest.

**Cobertura de 100% obrigatória** para os seguintes módulos críticos (configurado no `.coveragerc`):

```ini
[coverage:run]
source = app
omit =
    app/migrations/*
    app/tests/*

[coverage:report]
fail_under = 80
exclude_lines =
    pragma: no cover
    def __repr__
    if TYPE_CHECKING:

[coverage:paths]
source =
    app/scoring/
    app/subjective_logic/
    app/entity_resolution/rcs.py
    app/finops/stopping.py
    app/scoring/freshness.py
```

Os módulos de scoring (`matrix_rank.py`, `o_score.py`, `c_score.py`), freshness decay (`freshness.py`), RCS (`rcs.py`), lógica subjetiva (`fusion.py`, `discounting.py`) e FinOps (`stopping.py`) devem ter 100% de coverage de linhas. Qualquer linha não coberta nesses módulos é um risco de regressão silenciosa em cálculos financeiros de priorização.

---

## SEÇÃO 2: ESPECIFICAÇÃO BDD (BEHAVIOR-DRIVEN DEVELOPMENT)

### 2.1 Framework e Configuração

O SocialSelling utiliza **pytest-bdd** com arquivos `.feature` escritos na sintaxe Gherkin canônica. Os arquivos de feature são a fonte de verdade dos critérios de aceitação de negócio — devem ser compreensíveis pelo Product Owner e pelo Arquiteto de Sistemas sem conhecimento técnico de Python.

**Instalação:** `pip install pytest-bdd`

**Configuração em `pyproject.toml`:**
```toml
[tool.pytest.ini_options]
markers = [
    "bdd: Cenários BDD escritos em Gherkin validando critérios de negócio",
]
```

**Execução isolada dos testes BDD:**
```bash
pytest tests/bdd/ -m bdd -v --tb=short
```

### 2.2 Estrutura dos Arquivos BDD

```
tests/bdd/
├── features/
│   ├── lead_qualification.feature      # Cenário 1: Centralização Excessiva
│   ├── lead_pruning.feature            # Cenário 2: Poda hierárquica
│   └── degraded_operation.feature      # Cenário 3: LinkedIn indisponível
└── step_definitions/
    ├── common_steps.py                 # Steps compartilhados (Dado/Quando/Então genéricos)
    ├── scoring_steps.py                # Steps de scoring (P_score, O_score, C_score)
    ├── committee_steps.py              # Steps de comitê (SC, BMO, S_persona)
    └── degraded_steps.py              # Steps de modos degradados
```

---

## SEÇÃO 3: CENÁRIOS GHERKIN OBRIGATÓRIOS

### Cenário 1 — `tests/bdd/features/lead_qualification.feature`

```gherkin
# language: pt
# encoding: utf-8

Funcionalidade: Qualificação de Lead com Hipótese H2 — Centralização Excessiva
  Como um operador comercial do sistema SocialSelling
  Quero que o sistema identifique e ranqueie leads com dor de centralização excessiva
  Para que eu possa priorizar minhas abordagens com máximo potencial de conversão
  e gerar Conversation Blueprints precisos e acionáveis

  Contexto:
    Dado que o sistema está operacional com todos os scrapers disponíveis
    E que o modo de operação inicial é "FULL"

  Cenário: Lead de Advocacia com Centralização Excessiva qualificado como PRIORITY ACTION
    Dado que o sistema possui um contrato ICP ativo para o segmento "Advocacia"
    E que o ICP define icp_centralization_min como 0.60
    E que o ICP define os pesos: weight_fit=0.45, weight_intent=0.35, weight_reachability=0.20
    E que o ICP define alpha_rank=0.60 e beta_rank=4.0
    E que existe um perfil de empresa "Lex & Associados" com Instagram handle "@lexassociados"
    E que o scraper Instagram retornou os seguintes posts da fundadora nos últimos 21 dias:
      | post_id | caption                                                            | days_ago |
      | P001    | "Mais um mês correndo atrás de tudo sozinha."                     | 3        |
      | P002    | "Preciso aprender a delegar de verdade."                           | 8        |
      | P003    | "Equipe crescendo mas ainda depende muito de mim."                 | 15       |
      | P004    | "Quero implementar IA mas sei que preciso organizar antes."        | 19       |
    E que o scraper LinkedIn retornou 2 vagas ativas para cargos operacionais sênior
    E que o scraper CNPJ retornou CNAE "6911-7/00" (Atividades Jurídicas) para a empresa
    E que o Score de Seniority da Sócia-Fundadora Dra. Fernanda Melo é 1.00
    E que o Score de Role Alignment para o papel de Economic Buyer é 0.72
    E que o histórico de SRS do instagram_scraper é 0.82
    E que o histórico de SRS do linkedin_scraper é 0.77
    E que o histórico de SRS do cnpj_resolver é 0.95
    Quando o pipeline de hydration completo é executado para este lead
    Então o sistema deve classificar a hipótese H2 como "ACTIVE"
    E o posterior de H2 deve ser maior que 0.45
    E o Fit Score deve ser maior que 0.60
    E o S_intent deve ser maior que 0.60 dado o cluster de 4 posts de dor nos últimos 21 dias
    E o O_score deve ser maior que 0.65
    E o C_score deve ser maior que 0.40
    E o P_score deve ser maior que 0.45 qualificando como "QUALIFIED — MONITOR" no mínimo
    E o sistema deve identificar a Dra. Fernanda Melo como "STRUCTURAL_CHAMPION"
    E o campo data_quality_flag deve ser "NORMAL"
    E o campo operating_mode deve ser "FULL"
    E o campo sources_active deve conter "instagram_scraper", "linkedin_scraper" e "cnpj_resolver"
    E o Conversation Blueprint deve conter um Hook com urgency_level "ALTA" ou "MEDIA"
    E o Hook deve referenciar ao menos uma evidência dos últimos 21 dias via trigger_evidence_ids
    E a Pain Narrative deve conter ao menos uma das âncoras textuais observadas nos posts
    E a CTA Suggestion deve recomendar canal "instagram_comment" ou "linkedin_comment"
    E as Contraindications devem incluir orientação sobre não abordar a fundadora diretamente
    E o payload final deve conter todos os campos obrigatórios do contrato XAI Unified Payload:
      | campo                |
      | lead_id              |
      | generated_at         |
      | cycle_id             |
      | scores               |
      | xai_drivers          |
      | target_entity        |
      | buying_committee     |
      | hypothesis_evaluation|
      | approach_blueprint   |
      | evidence_layers      |
      | data_quality         |
```

### Cenário 2 — `tests/bdd/features/lead_pruning.feature`

```gherkin
# language: pt
# encoding: utf-8

Funcionalidade: Poda Precoce de Membro com Cargo Abaixo da Linha Hierárquica Mínima
  Como um sistema de gestão de comitê de compras
  Quero que membros identificados com seniority_score insuficiente sejam podados cedo
  Para economizar custo de tokens e manter o pipeline limpo e preciso

  Contexto:
    Dado que o sistema está operacional em modo "FULL"

  Cenário: Analista de Projetos podado por score hierárquico insuficiente para papel decisor
    Dado que o sistema possui um contrato ICP ativo para o segmento "Consultoria"
    E que existe um perfil de empresa "TechParceiros Consultoria Ltda" devidamente cadastrado
    E que existe um perfil de pessoa "João Silva" vinculado à empresa
    E que o cargo declarado de João Silva no LinkedIn é "Analista de Projetos"
    E que o Score de Seniority calculado para "Analista de Projetos" é 0.20
    E que o Score de Role Alignment de João Silva para papéis decisores do ICP é 0.15
    E que o bmo_momentum_score de João Silva é 0.10 (ausência de cluster de posts de dor)
    E que não há evidências de que João Silva seja tomador de decisão na empresa
    E que o O_score calculado para a empresa TechParceiros é 0.50
    Quando o nó de análise do Triage Agent calcula o S_persona para João Silva
    Então o member_score de João Silva deve ser calculado como:
      0.40×0.20 + 0.35×0.15 + 0.25×0.10 = 0.080 + 0.0525 + 0.025 = 0.1575
    E o member_score de João Silva deve ser menor que 0.30 (threshold mínimo de relevância)
    E João Silva não deve receber a designation "BUYING_MOTION_OWNER"
    E João Silva não deve receber a designation "STRUCTURAL_CHAMPION"
    E João Silva deve receber a designation "MEMBER" com nota de baixo impacto
    E a borda condicional do grafo deve acionar a poda deste membro para análise adicional
    E um registro deve ser criado no pruned_reason_log com:
      | campo              | valor                         |
      | entity_id          | person_id de João Silva       |
      | primary_stopping_rule | "seniority_below_threshold" |
    E nenhuma chamada de LLM adicional deve ser feita para análise de João Silva
    E o committee_completeness da empresa TechParceiros deve permanecer abaixo de 0.50
    E o committee_uncertainty deve ser maior que 0.50 refletindo ausência de decisores

  Cenário: Lead descartado por P_score abaixo do threshold de viabilidade
    Dado que existe um lead com O_score=0.30 e C_score=0.30
    Quando a MatrixRankFunction é executada
    Então o P_score calculado deve ser:
      f(0.30) = 1 - 0.60 × e^{-1.20} = 1 - 0.60 × 0.3012 = 1 - 0.1807 = 0.8193
      P = 0.30 × 0.8193 = 0.2458
    E o P_score deve ser menor que 0.25 (threshold DISQUALIFIED — PRUNED)
    E o lead deve ser classificado como "DISQUALIFIED — PRUNED"
    E um registro deve ser criado no pruned_reason_log com primary_stopping_rule "low_p_score"
    E o lead NÃO deve ser adicionado ao Delta Search Mode automaticamente
    E o lead NÃO deve aparecer na lista de leads ranqueados da API
```

### Cenário 3 — `tests/bdd/features/degraded_operation.feature`

```gherkin
# language: pt
# encoding: utf-8

Funcionalidade: Operação Resiliente em Modo Degradado — LinkedIn Indisponível
  Como um sistema de coleta de inteligência
  Quero que o pipeline continue operando quando o LinkedIn scraper falha
  Para garantir que nenhum lead seja completamente descartado por falha de infraestrutura
  E que o operador seja claramente informado sobre a qualidade dos dados disponíveis

  Contexto:
    Dado que o sistema está processando um ciclo de hydration

  Cenário: LinkedIn scraper retorna HTTP 429 — sistema opera em modo DEGRADED_LINKEDIN
    Dado que o sistema iniciou um ciclo de hydration para o lead "TechAlpha Software House"
    E que o Instagram scraper está operacional e retornou as seguintes evidências:
      | evidence_id | evidence_type          | raw_value                                            | days_ago |
      | EV-T001     | post_caption_instagram | "Crescendo mas o produto ainda depende de mim."     | 2        |
      | EV-T002     | post_caption_instagram | "Preciso sair da operação e ir pro estratégico."    | 7        |
      | EV-T003     | bio_instagram          | "CEO @TechAlpha | Software sob medida para PMEs"    | 0        |
      | EV-T004     | comment_on_anchor      | Comentário em @g4educacao sobre delegação           | 5        |
      | EV-T005     | mutual_follower_anchor | Seguidor mútuo do perfil âncora @endeavorbrasil     | 0        |
    E que o CNPJ resolver retornou dados cadastrais com CNAE "6201-5/01"
    E que o LinkedIn scraper retorna HTTP 429 na primeira tentativa
    E que o LinkedIn scraper retorna HTTP 429 na segunda tentativa com intervalo de 5 segundos
    E que o LinkedIn scraper retorna HTTP 429 na terceira tentativa com intervalo de 10 segundos
    E que o sistema detectou 3 falhas consecutivas e ativou o modo de compensação
    Quando o pipeline continua a execução com os dados parciais disponíveis
    Então o campo operating_mode no LeadState deve ser "DEGRADED_LINKEDIN"
    E o campo "DEGRADED_LINKEDIN_activated" deve estar presente em compensation_executed
    E o uncertainty de todos os atributos derivados de LinkedIn deve ser incrementado em 0.20
    E especificamente o uncertainty de "cargo_linkedin" deve ser 1.00 (dado ausente)
    E especificamente o uncertainty de "job_postings" deve ser 1.00 (dado ausente)
    E a hipótese H3 deve ter uncertainty_residual definido como 0.80
    E a hipótese H4 deve ter uncertainty_residual definido como 0.80
    E as hipóteses H3 e H4 devem permanecer em estado "CANDIDATE" sem transição para "ACTIVE"
    E o sistema deve processar as 5 evidências do Instagram normalmente
    E os scores O_score, C_score e P_score devem ser calculados com os dados parciais
    E o C_score calculado deve ser menor do que seria calculado em modo FULL
    E o campo data_quality_flag do lead deve ser "DEGRADED"
    E o campo sources_active no data_quality deve conter exatamente:
      | source           |
      | instagram_scraper|
      | cnpj_resolver    |
    E o campo degraded_attributes deve listar pelo menos "linkedin_cargo" e "linkedin_vagas"
    E o lead deve ser persistido no analytical_feature_store com data_quality_flag "DEGRADED"
    E o sistema NÃO deve lançar nenhuma exceção Python durante todo o pipeline
    E o sistema NÃO deve interromper a esteira de execução
    E o Conversation Blueprint deve ser gerado com flag "partial_data_warning": true
    E o Blueprint deve incluir nota de que "cargo e vagas do LinkedIn não confirmados"
    E NÃO deve existir entrada no pruned_reason_log para o lead "TechAlpha Software House"
    E o search_logs deve conter um registro com:
      | campo            | valor                    |
      | source_key       | linkedin_scraper         |
      | http_status      | 429                      |
      | operating_mode   | DEGRADED_LINKEDIN        |

  Cenário: Ambos os scrapers falham — sistema entra em modo CACHE_ONLY
    Dado que o Instagram scraper retorna HTTP 403 por CAPTCHA em todas as tentativas
    E que o LinkedIn scraper retorna HTTP 429 em todas as tentativas
    E que não há cache Redis disponível para o lead em processamento
    Quando o sistema detecta dual-source failure
    Então o operating_mode deve ser definido como "CACHE_ONLY"
    E o campo stopping_triggered no LeadState deve ser true
    E o campo stopping_reason deve ser "dual_source_failure"
    E o DSS deve ser forçado para 0 neste ciclo
    E um alerta crítico de observabilidade deve ser emitido via CloudWatch
    E o lead NÃO deve gerar XAI Unified Payload neste ciclo
    E o lead deve ser enfileirado na SQS DLQ para reprocessamento futuro
    E nenhum dado parcial inconsistente deve ser persistido no analytical_feature_store
```

---

*SDD-11 | SocialSelling MVP | Versão 1.0 | Revisão: a cada adição de módulo ou hipótese*
