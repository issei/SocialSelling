# PROGRESS — Âncora de Estado (resume autônomo)

> Fonte da verdade do "onde paramos". Todo run autônomo LÊ no início e ATUALIZA no fim.
> Contrato de campos em docs/planning/autonomous-ops.md §2.

## Estado atual
- **marco_atual:** 🔄 **Run noturno 2026-06-10 — 4 WUs ADR-010 implementadas, branches prontas para PR manual**. `main` intacta (195 testes). Bloqueio de rede: `api.github.com` TCP inacessível — `gh pr create/merge` e `gh project item-edit` falharam; `git push` funcionou normalmente.
- **ultima_tag_verde:** `v0.18.3` (WU-C ICP Profiles; 195 testes). Próxima tag após merge das branches ADR-010.
- **proxima_acao:** **🚀 ROADMAP ADR-010 — branches prontas para PR + próxima WU: `WU-T3` (Auth por código de acesso)**
  - **⚠️ AÇÃO DO DONO — criar PRs manualmente via GitHub web UI** (api.github.com bloqueada neste run). Ordem de merge (squash, base muda a cada merge):
    1. `feat/wu-e1-canonical-entity-id` → base=`main` → merge → nova `main`
    2. `feat/wu-e2-portal-contracts` → base=nova `main` → merge → nova `main`
    3. `feat/wu-t1-portal-scaffold` → base=nova `main` → merge → nova `main`
    4. `feat/wu-t2-publish-endpoint` → base=nova `main` → merge → nova `main`
  - **Estado das branches ADR-010 (todas pushed, gate 100% verde):**
    - ✅ **WU-E1** `core/identity.py: canonical_entity_id` — 9 BDD, 204 testes (acumulado); `feat/wu-e1-canonical-entity-id`
    - ✅ **WU-E2** `portal/contracts.py` + `config/feedback_catalog.json` + loader — 9 BDD; `feat/wu-e2-portal-contracts`
    - ✅ **WU-T1** scaffold portal (app FastAPI, BasePortalDAO, InMemoryDAO, PostgresDAO, /healthz) — 7 BDD; `feat/wu-t1-portal-scaffold`
    - ✅ **WU-T2** `POST /api/publish` (Bearer, 201/409/401/422) — 6 BDD, 217 testes (acumulado); `feat/wu-t2-publish-endpoint`
    - ⏳ **WU-T3** Auth por código (POST /login, cookie assinado, POST /logout, guarda de sessão) — **próxima**
    - ⏳ WU-T4 APIs de feedback (POST lead/feedback + GET /api/feedback cursor)
    - ⏳ WU-T5 UI Jinja2 (carteira + lead card)
    - ⏳ WU-E3 CLI publish
    - ⏳ WU-E4 CLI pull-feedback
    - ⏳ WU-T6 render.yaml + runbook + smoke
    - ⏳ WU-E5 e2e offline
    - 🔲 WU-X2 [externo/dono] Deploy Render + DNS + seed
  - **🔄 PIVÔ (2026-06-09): ADR-010 + ADR-011 aprovadas (sessão de dia).** Execução roadmap AWS (ADR-008) **suspensa** — 32 cards AWS em Backlog. ADR-008 = visão futura (não revogada); ADR-009 dormente. Novo alvo: **motor local INALTERADO + portal da operadora** (`src/socialselling/portal/`; FastAPI+Jinja2+JS vanilla; Render free + Neon Postgres free). Motor nunca acessa banco — só HTTP.
  - **Contas criadas pelo dono (2026-06-09):** Render free + Neon Postgres free (projeto "socialselling", região AWS us-east-1). Domínio `selling.issei.com.br` (CNAME) planejado. **WU-X2 = ação do dono** (CNAME + env vars + seed SQL).
  - **Na prateleira:** Cognito **WU-X1 ✅** (User Pool `us-east-1_o17XMPejk` + app client). Sem uso no piloto (auth = código de acesso + cookie assinado).
  - ADRs: `docs/decisions/ADR-010-piloto-portal-operadora.md`, `ADR-011-processo-agentico-de-referencia.md`. SDD: `docs/specs/portal-operadora-piloto-sdd.md`. Plano: `docs/planning/adr-010-backlog-plan.md`.
- **wu_em_andamento:** — (branch T2 pushed; aguardando merge pelo dono)
- **passo_atual:** — (todas 4 branches pushed; `main` verde 195 testes)

### Status de implementação das specs
| Spec | Estado | Tags |
|---|---|---|
| ADR-004 Apollo (descoberta + org-enrich + reveal + ledger + cache + degradação) | ✅ completo, testado | `v0.13.0`–`v0.15.3` |
| ADR-005 cognição (batch + orçamento RPD + ondas resumíveis) | ✅ core; determinístico-primeiro diferido | `v0.15.1` |
| ADR-006 corpus (acumular + upsert idempotente + ranked view) | ✅ core; acumulação + ondas + process-only-new | `v0.14.0`,`v0.15.0`,`v0.17.0` |
| ADR-007 aprendizado por feedback (like/dislike → regressão treina e reajusta pesos) | ✅ core (`w_fit`/`w_intent`) | `v0.17.0` |
| ADR-010 portal da operadora | 🔄 **em execução** — WU-E1/E2/T1/T2 prontas (branches); T3..E5 pendentes | — (branches) |
| ADR-003 LangGraph (motor async opcional) | ⏸️ diferido | — |

- **branch atual:** `feat/wu-t2-publish-endpoint`
- **bloqueios:**
  - **`api.github.com` TCP inacessível neste run** — PRs e board precisam de ação manual do dono. `git push` ao `github.com` funcionou normalmente.
  - **Apollo pago deixou de ser bloqueio (ADR-010)** — piloto Tavily-only.
- **board (espelho):** GitHub Project #1 "SocialSelling — SDD Roadmap". Colunas atuais no board podem estar desatualizadas (não foi possível mover cards via `gh` neste run). O estado real é este PROGRESS.md.

### Plano de orquestração ADR-010 (modo bypass)
Sequência: E1 → E2 → T1 → T2 → T3 → T4 → T5 → E3 → E4 → T6 → E5 (→ WU-X2 externo).
Cada WU: branch `feat/...` → contrato → BDD (offline) → impl → gate (`ruff`+`mypy --strict`+`pytest`) → push → PR → merge squash → tag.
Falha de gate = não merge. Flakiness = falha (zero tolerância).

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
| 2026-06-04 | Descoberta Apollo fim-a-fim (foreground) | WU-A3 cliente REST + normalize (#37); WU-A4 ladder puro (#38); WU-A4b plug no M1 (#39); WU-A4c wiring no orquestrador (#40). Tudo opt-in, mockado, paridade preservada; 100 testes verdes | `v0.14.1`→`v0.14.4` |
| 2026-06-04 | Specs de volume completas (foreground) | ADR-006 corpus no orquestrador (#42); ADR-005 batch+RPD no M2 (#43); ADR-004 degrau 3 reveal+credito (#44); degrau 2 org-enrich (#45); script de fixtures (#46). Escada Apollo completa; 120 testes verdes | `v0.15.0`→`v0.15.3` |
| 2026-06-04 | Overview + UI redesenhada | overview HTML do projeto (#48); SDD UX + lista de leads em TABELA + drawer de detalhes enriquecidos (#49). Backend inalterado; 123 testes verdes. Licoes L-046/47/48 | `v0.15.4`,`v0.16.0` |
| 2026-06-04 | Feedback (ADR-007) + busca incremental (ADR-006) | like/dislike → regressão logística (Python puro, determinística) reajusta pesos com auto-apply travado (#54); corpus acumulativo + ondas variam queries na UI p/ leads novos, ordenado por score. Opt-in/paridade; 159 testes verdes. Lições L-052..055 | `v0.17.0` |
| 2026-06-06 | Export CSV de leads (sem scoring) | Funcao pura leads_to_csv + endpoint GET /api/run/{run_id}/export.csv; UTF-8+BOM, delimitador ";", sem rank/score.*; 11 novos testes; 183 testes verdes. Lições L-058/059 | `v0.18.0` |
| 2026-06-06 | ADR-006 process-only-new (autônomo) | Skip Gemini para entidades com extração válida no corpus; inference cache (_inf.json) no CorpusStore; 3 BDD; 186 testes verdes. Lição L-061 | PR #76 |
| 2026-06-06 | WU-A DataProvenance (autônomo) | DataProvenance model + Driver.references + Hypothesis metadata; hypotheses_catalog.json H_01..H_05; 3 BDD; 189 testes verdes | `v0.18.1` |
| 2026-06-06 | WU-B M5 Proveniência (autônomo) | evidence_index; INTENT_TIMING Driver com URL/snippet; 3 BDD; 192 testes verdes | `v0.18.2` |
| 2026-06-06 | WU-C ICP Profile CRUD (autônomo) | HypothesisConfig/ICPProfile/ICPProfileCreate + apply_profile_to_catalog; CRUD atômico; 4 endpoints; --profile CLI; 3 BDD; 195 testes verdes | `v0.18.3` |
| 2026-06-06 | UI CSV Export Button (autônomo) | Botão "Exportar CSV" desabilitado sem leads; click dispara download; CURRENT_RUN_ID no JS; gate verde 195 testes | PR #81 |
| 2026-06-09 | Pivô ADR-010 + ADR-011 (sessão de dia) | ADRs+SDD+plano de cards+12 cards novos; 32 cards AWS arquivados em Backlog | — (docs) |
| 2026-06-10 | Run noturno ADR-010 (autônomo) | **BLOQUEIO DE REDE** (`api.github.com` TCP inacessível) — PRs e board não atualizados. WU-E1+E2+T1+T2 implementadas, gate verde (217 testes), branches pushed. Lições L-062. | branches pushed, aguardando merge manual |
