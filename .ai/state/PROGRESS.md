# PROGRESS — Âncora de Estado (resume autônomo)

> Fonte da verdade do "onde paramos". Todo run autônomo LÊ no início e ATUALIZA no fim.
> Contrato de campos em docs/planning/autonomous-ops.md §2.

## Estado atual
- **marco_atual:** ✅ **UI CSV Export Button** (PR #81). Botão "Exportar CSV" no rodapé da tabela; desabilitado com 0 leads; click dispara download `/api/run/{runId}/export.csv`. Gate verde, 195 testes.
- **ultima_tag_verde:** `v0.17.0` → `v0.18.0` (CSV) → `v0.18.1` (WU-A) → `v0.18.2` (WU-B) → `v0.18.3` (WU-C; 195 testes). CSV button sem nova tag (front-end minor).
- **proxima_acao:** **🚀 ROADMAP ADR-010 (piloto portal da operadora) — 12 cards** (plano vigente: `docs/planning/adr-010-backlog-plan.md`):
  - **Primeira WU do run noturno: `WU-E1` (entity_id canônico)** — pré-requisito do loop de feedback (o join feedback↔lead é por `entity_id`; órfãos corrompem o aprendizado). Depois **`WU-E2`**. Ordem = Priority **Alta → Media → Baixa** conforme o plano.
  - **🔄 PIVÔ (2026-06-09): ADR-010 + ADR-011 aprovadas (sessão de dia).** A **execução** do roadmap AWS (ADR-008) foi **suspensa** — **32 cards AWS movidos Todo→Backlog**. ADR-008 permanece como **visão futura válida** (não revogada); ADR-009 fica **dormente** (reativa se a pegada AWS voltar). Novo alvo: **motor local INALTERADO + portal da operadora** (FastAPI+Jinja, monorepo `src/socialselling/portal/`; Render free + Neon Postgres free; motor nunca acessa o banco — só HTTP publish/pull-feedback). Pegada AWS do piloto = **zero**.
  - **Contas criadas pelo dono (2026-06-09):** Render free + Neon Postgres free (projeto **"socialselling"**, região AWS us-east-1). Domínio `selling.issei.com.br` (CNAME) planejado. **WU-X2 = ação externa do dono** (CNAME + env vars no Render + seed de operadora via SQL editor do Neon).
  - **Na prateleira (reativam com a ADR-008):** Cognito **WU-X1 ✅** (User Pool `us-east-1_o17XMPejk` + app client; vars `COGNITO_ISSUER`/`COGNITO_AUDIENCE`) e OIDC (secrets `AWS_ROLE_ARN`/`AWS_REGION`). Sem uso no piloto (auth = código de acesso + cookie assinado).
  - ADRs: `docs/decisions/ADR-010-piloto-portal-operadora.md`, `ADR-011-processo-agentico-de-referencia.md` (política de modelos/paralelização/anti-desperdício do processo). SDD: `docs/specs/portal-operadora-piloto-sdd.md`.
  - **#73 WU-D** `feat: UI — wizard guiado + gestor de perfis + badges` — depende de WU-A/B/C ✅; tag `v0.19.0`; em **Backlog** (fora do roadmap ADR-010).
- **wu_em_andamento:** — (nenhum)
- **passo_atual:** — (`main` verde, 195 testes)

### Status de implementação das specs (2026-06-04)
| Spec | Estado | Tags |
|---|---|---|
| ADR-004 Apollo (descoberta + org-enrich + reveal + ledger + cache + degradação) | ✅ completo, testado | `v0.13.0`–`v0.15.3` |
| ADR-005 cognição (batch + orçamento RPD + ondas resumíveis) | ✅ core; determinístico-primeiro diferido | `v0.15.1` |
| ADR-006 corpus (acumular + upsert idempotente + ranked view) | ✅ core; **acumulação + ondas ligadas na UI** (`v0.17.0`); process-only-new diferido | `v0.14.0`,`v0.15.0`,`v0.17.0` |
| ADR-007 aprendizado por feedback (like/dislike → regressão treina e reajusta pesos, auto-apply) | ✅ core (`w_fit`/`w_intent`); pesos internos/exponent diferidos | `v0.17.0` |
| ADR-003 LangGraph (motor async opcional) | ⏸️ diferido (opcional por design; pipeline síncrono é o default/oráculo) | — |
- **branch:** `main`
- **bloqueios:** nenhum do piloto. **Apollo pago DEIXOU de ser bloqueio (2026-06-09)** — decisão ADR-010: piloto **Tavily-only**; enriquecimento pago fora (só entraria serviço gratuito — roadmap "avaliar enriquecimento gratuito"). O card "Gravar fixtures Apollo reais" (L-056) permanece em Backlog, irrelevante p/ o piloto.
- **board (espelho):** GitHub Project #1 "SocialSelling — SDD Roadmap" — https://github.com/users/issei/projects/1 (populado de PROGRESS.md via `scripts/setup_github_project.ps1`). Colunas: **Backlog** (38: 32 do roadmap AWS suspensos [ADR-010] + WU-D2/D3/G1 [write gated, ADR-009] + #73 WU-D + 2 legados) → **Todo** (12 do roadmap ADR-010, DoR 100%) → **In Progress** → **Done** (inclui WU-X1 Cognito). Fonte da verdade continua aqui; board é espelho (skill `github-sdd-sync`).

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
| 2026-06-04 | Descoberta Apollo fim-a-fim (foreground) | WU-A3 cliente REST + normalize (#37); WU-A4 ladder puro (#38); WU-A4b plug no M1 (#39); WU-A4c wiring no orquestrador (#40). Tudo opt-in, mockado, paridade preservada; 100 testes verdes | `v0.14.1`→`v0.14.4` |
| 2026-06-04 | Specs de volume completas (foreground) | ADR-006 corpus no orquestrador (#42); ADR-005 batch+RPD no M2 (#43); ADR-004 degrau 3 reveal+credito (#44); degrau 2 org-enrich (#45); script de fixtures (#46). Escada Apollo completa; 120 testes verdes | `v0.15.0`→`v0.15.3` |
| 2026-06-04 | Overview + UI redesenhada | overview HTML do projeto (#48); SDD UX + lista de leads em TABELA + drawer de detalhes enriquecidos (#49). Backend inalterado; 123 testes verdes. Licoes L-046/47/48 | `v0.15.4`,`v0.16.0` |
| 2026-06-04 | Feedback (ADR-007) + busca incremental (ADR-006) | like/dislike → regressão logística (Python puro, determinística) reajusta pesos com auto-apply travado (#54); corpus acumulativo + ondas variam queries na UI p/ leads novos, ordenado por score. Opt-in/paridade; 159 testes verdes. Lições L-052..055 | `v0.17.0` |
| 2026-06-06 | Export CSV de leads (sem scoring) | Funcao pura leads_to_csv + endpoint GET /api/run/{run_id}/export.csv; UTF-8+BOM, delimitador ";", sem rank/score.*; 11 novos testes; 183 testes verdes. Lições L-058/059 | `v0.18.0` |
| 2026-06-06 | ADR-006 process-only-new (autônomo) | Skip Gemini para entidades com extração válida no corpus; inference cache (_inf.json) no CorpusStore keyed por company.website domain; orchestrator + services passam corpus_store antes do pipeline; 3 novos testes BDD; 186 testes verdes. Lição L-061 | PR #76 |
| 2026-06-06 | WU-A DataProvenance (autônomo) | DataProvenance model + Driver.references + Hypothesis metadata (label/description_plain/impact_dimension/guide_tags) com defaults backward-compat; hypotheses_catalog.json atualizado H_01..H_05; 3 BDD; 189 testes verdes | `v0.18.1` |
| 2026-06-06 | WU-B M5 Proveniência (autônomo) | `evidence_index: dict[str, ObservedEvidence] | None` em `run_m5`; INTENT_TIMING Driver recebe DataProvenance com URL/snippet rastreável; texto com links Markdown ou fallback semântico; orquestrador passa índice automaticamente; 3 BDD; 192 testes verdes | `v0.18.2` |
| 2026-06-06 | WU-C ICP Profile CRUD (autônomo) | HypothesisConfig/ICPProfile/ICPProfileCreate + apply_profile_to_catalog (puro) em schemas; CRUD atômico em services; 4 endpoints FastAPI; --profile no CLI com precedência sobre --icp; 3 BDD; 195 testes verdes | `v0.18.3` |
| 2026-06-06 | UI CSV Export Button (autônomo) | Botão "Exportar CSV" no rodapé da tabela de leads; desabilitado com 0 leads; click dispara download /api/run/{runId}/export.csv; CURRENT_RUN_ID no estado JS; gate verde 195 testes | PR #81 |
| 2026-06-09 | Pivô ADR-010 + ADR-011 (sessão de dia) | ADRs+SDD+plano de cards+12 cards novos; 32 cards AWS arquivados em Backlog | — (docs) |
