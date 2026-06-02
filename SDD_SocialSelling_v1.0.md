# SDD — Solution Design Document: Sistema de Inteligência de Dados "SocialSelling"
## PoC / MVP Ultraleve — Local Runtime & Zero-Cost Infra Edition

| Campo | Valor |
|---|---|
| Documento | SDD-SOCIALSELLING-MVP |
| Versão | 1.0.0 |
| Status | APPROVED-FOR-VIBE-CODING |
| Classificação | Engineering / Confidential |
| Runtime alvo | Single-host local (Python 3.11+) |
| Persistência | File-Based JSON (cold) + In-Memory (hot) |
| Sensores externos | Tavily API (search), Gemini API (cognition) |
| Bancos de dados gerenciados | NENHUM (database-less por diretriz) |
| Fonte da verdade | ESTE documento (SDD-to-Code Loop) |

---

## DIRETRIZ ARQUITETURAL SUPREMA — LOCAL RUNTIME & ZERO-COST INFRA

O sistema opera integralmente em um único processo local (ou pool de processos `multiprocessing`), com **processamento em memória (In-Memory Processing)** e **persistência fria em arquivos JSON locais (File-Based Storage)**. Não há servidor de banco de dados, fila gerenciada, cache distribuído ou orquestrador em nuvem. O custo de infraestrutura gerenciada é **zero**; o único custo variável é o consumo de créditos/tokens das duas APIs externas.

Mapeamento canônico de sensores cognitivos (imutável):

| API | Módulos Consumidores | Papel arquitetural |
|---|---|---|
| **Tavily API** | M1 (exclusivo) | Único sensor exaustivo de busca e colheita semântica web/redes. Nenhum outro módulo chama Tavily. |
| **Gemini API** | M3, M4, M5 | Motor cognitivo local: extração semântica, inferência bayesiana de dores, parsing de comitê parcialmente observável, tradução XAI. |

Regras invioláveis (enforced no SDD-to-Code Loop):

1. **Isolamento estrito de camadas semânticas.** Os três níveis de dados — `Observed Evidence`, `Generated Inferences`, `Evaluated Hypotheses` — vivem em estruturas de memória separadas e nunca compartilham referências mutáveis. Proíbe-se vazamento/contaminação semântica (uma inferência jamais é tratada como evidência observada).
2. **Determinismo na ordenação final.** A `MatrixRankFunction` produz saída determinística para o mesmo snapshot de memória (tie-break estável).
3. **Mundo Aberto (Open-World Assumption).** Ausência de sinal não é falso; é incerteza. Missing Evidence aumenta `u` (uncertainty) e achata a posterior.
4. **Atomicidade da persistência fria.** Toda escrita em JSON é atômica (write-temp + `os.replace`).

---

## SEÇÃO 1 — VIBE CODING & BDD ORCHESTRATION FRAMEWORK

### 1.1 Padrão SDD-to-Code Loop

O SDD é a **única fonte da verdade arquitetural**. Ferramentas de Vibe Coding (Aider, Cursor, Claude Engineer) geram código guiadas exclusivamente por este documento. Nenhuma função de agente, estrutura de dados ou lógica em memória pode ser commitada se divergir do SDD.

Ciclo iterativo determinístico:

```
┌─────────────────────────────────────────────────────────────────┐
│ SDD (fonte da verdade)                                            │
│   │                                                               │
│   ▼                                                               │
│ [1] Extrair contrato do módulo (Inputs/Outputs JSON + assinaturas)│
│   │                                                               │
│   ▼                                                               │
│ [2] Gerar Feature Files Gherkin (.feature) a partir dos cenários  │
│   │                                                               │
│   ▼                                                               │
│ [3] Vibe Coding: agente gera implementação Python                 │
│   │                                                               │
│   ▼                                                               │
│ [4] pytest-bdd executa cenários LOCAIS                            │
│   │                                                               │
│   ├── FALHA ──► feedback estruturado ──► volta a [3] (auto-itera) │
│   │                                                               │
│   ▼ 100% PASS (determinístico)                                    │
│ [5] Lint + type-check (ruff + mypy --strict) + commit             │
└─────────────────────────────────────────────────────────────────┘
```

Regra de gating: o agente gerador **itera na escrita das funções até que 100% dos cenários BDD locais passem de forma determinística**. Flakiness é tratado como falha (zero tolerância a não-determinismo nos testes; chamadas a Tavily/Gemini são mockadas com fixtures gravadas em JSON durante o BDD).

### 1.2 Estrutura de repositório local (zero-infra)

```
socialselling/
├── SDD_SocialSelling_v1.0.md          # fonte da verdade
├── pyproject.toml                     # deps: httpx, pydantic, pytest-bdd, ruff, mypy
├── .env                               # TAVILY_API_KEY, GEMINI_API_KEY (gitignored)
├── config/
│   ├── runtime.toml                   # thresholds: tau_finops, cache_ttl, model ids
│   └── hypotheses_catalog.json        # 15 hipóteses do MVP (priors)
├── data/
│   ├── observed_evidence.json         # camada 1 (cold)
│   ├── inferences.json                # camada 2 (cold)
│   ├── hypotheses_eval.json           # camada 3 (cold)
│   ├── feature_store.json             # snapshot consolidado
│   └── cache/
│       └── tavily/<sha256(query)>.json # cache T-24h
├── logs/
│   └── cognitive_trace.jsonl          # observabilidade cognitiva (append-only)
├── src/
│   ├── skills/                        # MCP / skills locais (I/O, Tavily, Gemini)
│   ├── modules/                       # M1..M5
│   ├── core/                          # subjective_logic, bayesian, finops, graph
│   └── orchestrator.py                # pipeline M1→M5 em memória
└── tests/
    ├── features/                      # *.feature (Gherkin)
    ├── steps/                         # step defs pytest-bdd
    └── fixtures/                      # payloads gravados (Tavily/Gemini mocks)
```

### 1.3 Integração BDD Nativa

Cada módulo funcional possui cenários formais em **Gherkin Syntax** (`Given/When/Then`), executados via `pytest-bdd`. Convenções obrigatórias:

- Cada `.feature` referencia o `@module_id` (`@M1`..`@M5`) e o `@contract` correspondente neste SDD.
- Steps que tocam APIs externas usam o decorator de fixture `@with_recorded_fixture("<nome>")`, que injeta payloads JSON gravados (determinismo).
- Asserções numéricas (scores, opiniões ω) usam tolerância explícita `abs(actual - expected) <= 1e-9` para reprodutibilidade de ponto flutuante.

Exemplo de cenário de smoke do pipeline (cross-module):

```gherkin
@pipeline @smoke
Feature: Pipeline end-to-end determinístico em memória

  Scenario: Lead com evidências fortes converge para ranking estável
    Given um snapshot de memória vazio
    And fixtures Tavily gravadas para a query "CEO TechCorp pricing pain"
    And fixtures Gemini gravadas para extração e inferência
    When eu executo o orquestrador M1 até M5
    Then o feature_store.json contém exatamente 1 lead avaliado
    And o O_score e o C_score são computados de forma independente
    And o XAI Unified Payload contém as 3 divisões obrigatórias
    And uma segunda execução produz ranking byte-idêntico
```

### 1.4 Tratamento de Falhas e Degradação Automatizada

O ecossistema local reage de forma autônoma a falhas de API. Tabela de reação:

| Evento | Detecção | Ação imediata | Flag Feature Store |
|---|---|---|---|
| Tavily HTTP 429 (rate-limit) | status code | Servir cache local `data/cache/tavily/` se idade ≤ 24h (T-24h); senão pular query e marcar `missing_evidence=true` | `data_quality = DEGRADED` |
| Gemini HTTP 429 | status code | Backoff exponencial local (`base=2s, jitter, max_retries=3`); se esgotar, congelar inferência do lote e reusar última inferência válida em cache | `cognition_quality = DEGRADED` |
| Timeout de rede (>T_to) | `httpx.TimeoutException` | Retry idempotente 1x; se falhar, degradar e continuar | `DEGRADED` |
| 5xx server-side | status code | Retry com backoff; circuito abre após 3 falhas seguidas | `DEGRADED` |
| Cache miss + API down | exceção encadeada | Marcar feature como `u=1.0` (incerteza total, Open-World) | `DEGRADED` |

Lógica de chaveamento (pseudocódigo normativo):

```python
def fetch_with_degradation(query: str, kind: Literal["tavily","gemini"]) -> Payload:
    cached = cache_get(query, kind)           # lê data/cache/<kind>/<hash>.json
    try:
        resp = api_call(query, kind)
        cache_put(query, kind, resp, ttl_h=24)
        feature_store.set_flag(kind, "OK")
        return resp
    except RateLimitError:                      # HTTP 429
        feature_store.set_flag(kind, "DEGRADED")
        if cached and cached.age_h <= 24:        # T-24h
            return cached.payload
        return Payload.missing(reason="rate_limited_no_cache")  # u -> aumenta
    except (TimeoutError, ServerError):
        feature_store.set_flag(kind, "DEGRADED")
        return cached.payload if cached else Payload.missing(reason="api_down")
```

Quando qualquer flag está `DEGRADED`, o Módulo 5 carimba o XAI Payload com `degraded_mode=true` e rebaixa a confiança final (`C_score`) aplicando um fator de penalidade `kappa_degraded ∈ (0,1)` configurável em `runtime.toml`.

---
