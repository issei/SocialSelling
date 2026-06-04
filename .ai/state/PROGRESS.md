# PROGRESS — Âncora de Estado (resume autônomo)

> Fonte da verdade do "onde paramos". Todo run autônomo LÊ no início e ATUALIZA no fim.
> Contrato de campos em docs/planning/autonomous-ops.md §2.

## Estado atual
- **marco_atual:** 🏗️ **Build de VOLUME iniciado** (modo bypass autorizado pelo dono). Prioridade = ADR-004 (Apollo) + ADR-005 (cognição batch) + ADR-006 (corpus acumulativo); LangGraph (ADR-003) é opcional/diferido. Roadmap: `docs/planning/escala-volume-leads.md`. **WU-A1 concluída** → `v0.13.0`.
- **ultima_tag_verde:** `v0.14.0` (fundação de volume: ledgers crédito/RPD + corpus acumulativo; 73 testes verdes)
- **proxima_acao:** **WU-A3** — `skills/apollo_client.py` (cliente REST httpx; RateLimit/ApolloError) + `scripts/record_apollo_fixtures.py` (grava respostas reais dos 3 endpoints; chave já presente no `.env`) + testes de normalização/degradação (403/429). Depois: WU-A4 (ladder + plug no M1 + reveal pós-M4), WU-A5 (org-enrich condicional). Em paralelo (ADR-005/006): fiar `credit_ledger`/`request_ledger`/`corpus` no `config.py` + orquestrador (WUs de integração).
- **wu_em_andamento:** — (fundação ledgers+corpus mergeada via PR #35)
- **passo_atual:** — (`main` verde, 73 testes; `.env` com APOLLO_API_KEY preenchido; gate via `.venv\Scripts\python.exe -m …`)
- **branch:** `main`
- **bloqueios:** NENHUM (chave Apollo presente; fixtures reais só na WU-A3)

### Plano de orquestração (modo bypass — green→auto-merge→tag)
Sequência (do roadmap §3, "não soltar Apollo sozinho"): **A1✅ → A2/RPD/corpus (paralelos) → A3 (fixtures, precisa chave✓) → A4 ladder+M1 → A5 org-enrich → ADR-005 batch+determinístico-primeiro → ADR-006 wiring corpus no orquestrador → C/D**. Cada WU: branch `feat/…` → contrato → BDD/testes (sem rede; APIs mockadas) → impl → gate (`ruff`+`mypy --strict`+`pytest`) → PR `--squash --auto` → tag `v0.13.x`/`v0.14.0`. Falha de gate = não merge (rollback via última tag).
- **Modelos:** Opus (main) p/ orquestração e WUs de risco (ledgers, integração); sonnet p/ módulos puros isolados em paralelo; haiku p/ tarefas mecânicas. Autolearning: `docs/licoes-aprendidas.md` ao fim de cada WU.
- **backlog de calibração (não bloqueia, ver `docs/analysis/sondagem-talita.md`):** calibrar pesos `[persona]`/priors com conversão real; pessoa-vs-empresa quando a conta da firma não traz a fundadora; (opcional, fora do guardrail) enriquecimento de contato.

## Pré-condições antes de liberar autonomia plena
- [x] `bootstrap` executado (venv + deps) e gate completo verde (ruff+mypy+pytest).
- [x] CI verde no GitHub; `main` protegida (merge exige check `gate`).
- [ ] Fixtures Tavily/Gemini gravadas com supervisão (WU-1/WU-2 tocam rede).
- [ ] Estratégia de agendamento ativada (autonomous-ops §7).

## Histórico
| Data | Run | Resultado | Tag/Checkpoint |
|---|---|---|---|
| 2026-06-02 | Fase 0 (fundação) | toolchain + contratos + planejamento | `v0.1.0` (pré-CI) |
| 2026-06-03 | Planejamento + fluxo PR | PR #1 (docs), PR #2 (fix StrEnum), CI verde, branch protection | `v0.1.1` |
| 2026-06-03 | WU-1 M1 Busca (autônomo) | cliente Tavily + cache atômico + degradação; BDD determinístico; fixtures reais gravadas | `v0.2.0` |
| 2026-06-03 | WU-2 M2 Extração (autônomo) | cliente Gemini + cache + degradação; 17 inferências reais; isolamento de camadas; BDD determinístico | `v0.3.0` |
| 2026-06-03 | WU-3 M3 Score (autônomo) | módulo puro; fórmula linear Fit/Intent/Confiança; hard filter; determinismo 1e-9 | `v0.4.0` |
| 2026-06-03 | WU-4 M4 Ranking (autônomo) | módulo puro; ordenação p_score desc + tie-break estável; byte-idêntico | `v0.5.0` |
| 2026-06-03 | WU-5 M5 XAI (autônomo) | módulo puro por regras; drivers +/− + sinais ausentes + degraded_mode | `v0.6.0` |
| 2026-06-03 | WU-6 Orquestrador + Smoke (autônomo) | pipeline M1→M5 + CLI + persistência atômica; smoke E2E byte-idêntico; run real = 17 prospects | `v0.7.0` |
| 2026-06-03 | Motor de intenção (público Talita) | ICP+hipóteses (#12); M2 extrai sinais (#13); M3 intent das hipóteses + hard filter (#14); M5 XAI + BDD de objetivo (#15) | `v0.7.1`→`v0.8.0` |
| 2026-06-03 | Aderência da busca + Lead Card | sondagem empírica; busca PT-BR+Instagram (#17); contato no M2; LeadCard acionável. Run real = 29 leads c/ Instagram | `v0.8.1`→`v0.9.0` |
| 2026-06-03 | UI de operador local (FastAPI) | ADR-002; fundação web (#20); API params (#21); assistente Gemini (#22); executar/resultados (#23); front-end (#24); E2E+README | `v0.10.0`→`v0.11.x` |
| 2026-06-03 | Precisão de persona | M2 classifica persona; M3 persona_fit (config [persona]); XAI explica. Run real: top-5 = fundadoras | `v0.12.0` |
| 2026-06-03 | Launcher + SDD LangGraph | start.bat/start.sh (#27); SDD Orquestração Paralela+FinOps aprovado e endurecido v1.1 + ADR-003 (#28) | `v0.12.1` |
| 2026-06-04 | Specs de volume + ADRs | SDD+ADR-004 Apollo (#31); roadmap escala-volume + ADR-005 (cognição) + ADR-006 (corpus) (#32) | — (docs) |
| 2026-06-04 | WU-A1 Apollo schemas+config (bypass) | apollo/schemas.py + ApolloCfg + [apollo] runtime + testes de contrato; gate verde 49 testes (#33) | `v0.13.0` |
| 2026-06-04 | Fundação ledgers+corpus (fan-out de agentes) | 3 agentes sonnet em paralelo escreveram credit_ledger/request_ledger/corpus; travaram em prompt de permissão; colhidos+gateados+mergeados pelo main loop (#35); gate verde 73 testes. Licoes L-039/40/41 | `v0.14.0` |
