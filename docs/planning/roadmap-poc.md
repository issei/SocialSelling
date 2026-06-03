# Roadmap do PoC — SocialSelling

Sequenciamento incremental guiado pelo SDD-to-Code Loop. Cada item entrega uma fatia testável. **Regra:** só avança ao próximo quando o gate do anterior está verde. Referência: ADR-000, CLAUDE.md.

## Fase 0 — Fundação (sem código de negócio)
Objetivo: tornar o repositório executável e o loop SDD operável.

| # | Entrega | Critério de prontidão |
|---|---|---|
| 0.1 | `pyproject.toml` (httpx, pydantic v2, pytest, pytest-bdd, ruff, mypy) + `.gitignore` + `.env.example` | `pip install -e .` funciona; `ruff`/`mypy` rodam |
| 0.2 | `config/runtime.toml` (thresholds: cache_ttl, τ_finops, κ_degraded, model ids) | valores default documentados |
| 0.3 | `config/hypotheses_catalog.json` (3–5 hipóteses com priors numéricos) | schema validável |
| 0.4 | `config/icp_criteria.example.json` (1 ICP de exemplo — primeira entrada real) | validado contra contrato |
| 0.5 | Contratos Pydantic por módulo em `docs/contratos/` + `src/socialselling/contracts.py` | tipos de I/O de M1–M5 definidos |
| 0.6 | Esqueleto de pastas `src/`, `tests/features|steps|fixtures`, `data/`, `logs/` | estrutura criada com `.gitkeep` |

**Gate Fase 0:** projeto instala, lint/types passam em vazio, contratos type-check.

## Fases de módulo (M1→M5) — cada uma é um ciclo SDD-to-Code completo
Para cada módulo: (a) contrato → (b) `.feature` + fixtures gravadas → (c) implementação → (d) gate `pytest-bdd`+`ruff`+`mypy --strict` → (e) commit em branch.

### M1 — Busca (Tavily)
- **Entrada:** `icp_criteria.json`. **Saída:** `observed_evidence.json` (camada observada).
- **Faz:** gera N queries a partir do ICP → consulta Tavily → cacheia (T-24h) → normaliza resultados brutos.
- **Aceite (BDD):** dado fixtures Tavily gravadas para uma query, M1 produz K evidências observadas determinísticas; em 429 sem cache, marca `missing_evidence=true` e `data_quality=DEGRADED`.

### M2 — Extração (Gemini)
- **Entrada:** evidências observadas. **Saída:** `inferences.json` (camada separada).
- **Faz:** Gemini estrutura snippets em entidades Company/Person; cada inferência carrega score de confiança.
- **Aceite:** nenhuma inferência sem `confidence`; observed e inferences nunca compartilham referência; degrade em 429 reusa última inferência válida.

### M3 — Score
- **Entrada:** inferências. **Saída:** scores Fit/Intent/Confiança por prospect.
- **Faz:** fórmula **linear documentada**: `P = (w_fit·Fit + w_intent·Intent) × f(Confiança)`; missing evidence reduz confiança.
- **Aceite:** mesma entrada → mesmos scores (tolerância `1e-9`); filtro rígido (ex.: B2C/tecnologia proibida) zera o lead.

### M4 — Ranking
- **Entrada:** scores. **Saída:** lista ordenada.
- **Faz:** ordena por P_score com **tie-break estável**.
- **Aceite:** reexecução produz ordenação byte-idêntica.

### M5 — Explicação (XAI)
- **Entrada:** prospect rankeado. **Saída:** XAI payload + relatório legível.
- **Faz:** drivers positivos, negativos e sinais ausentes; carimba `degraded_mode` quando aplicável.
- **Aceite:** payload contém as divisões obrigatórias; texto explica "aborde X porque…".

## Fase final — Smoke test end-to-end
- Cenário cross-module (já esboçado em SDD v1.0 §1.3): memória vazia + fixtures gravadas → `orchestrator` M1..M5 → exatamente N leads avaliados; **segunda execução byte-idêntica**.
- **Gate de PoC concluído:** smoke verde + relatório de exemplo gerado a partir do `icp_criteria.example.json`.

## Dependências (DAG)
`0.* → M1 → M2 → M3 → M4 → M5 → Smoke`. M3 e M5 dependem do catálogo de hipóteses (0.3). M4 não tem lógica externa (paralelizável com testes de M3).

## Critérios de conclusão do PoC
1. `python -m socialselling.orchestrator --icp ...` produz `prospects_ranked.json` + relatório.
2. Suíte BDD 100% verde e determinística.
3. Custo de execução = só tokens Tavily/Gemini; nenhuma infra gerenciada.
4. Nenhuma regra inviolável ou guardrail violado.
