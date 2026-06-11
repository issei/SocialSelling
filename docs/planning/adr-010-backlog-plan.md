# Plano de backlog — ADR-010 (piloto: portal da operadora)

> **O que é:** o plano ordenado de cards que operacionaliza a **ADR-010**
> (`docs/decisions/ADR-010-piloto-portal-operadora.md`) e sua SDD derivada
> (`docs/specs/portal-operadora-piloto-sdd.md`, **alvo de build**). Decompõe as 12 Work Units
> (WUs) da SDD §9 em cards do **GitHub Project #1** com DoR completo, ordenados por dependência.
> O motor local (M1–M5, corpus ADR-006, waves, aprendizado ADR-007) **não muda**; o que se
> adiciona são duas pontas finas: o portal (FastAPI + Jinja2, Render free + Neon Postgres free)
> e as CLIs `publish`/`pull-feedback` (integração **exclusivamente HTTP**; o motor nunca acessa
> o banco).
>
> **Fonte da verdade arquitetural:** ADR-010 + SDD do portal. Este doc **não** os substitui —
> só sequencia o trabalho. **Estado real:** `.ai/state/PROGRESS.md`. **Board:** espelho.
>
> **Modo operacional:** este é um artefato de **dia** (autoria). Todos os cards entram em
> **Backlog**. Quem move Backlog→Todo (com DoR 100%) é o **dono**; quem desenvolve é o **run
> noturno** (`github-sdd-sync`). Ver `docs/governance/modo-operacional.md`.

## ⚖️ REBALANCEAMENTO do board (consequência da ADR-010)

**32 cards do roadmap AWS saem de Todo → Backlog, com DoR preservado** (ADR-010: ficam *"na
prateleira, não desperdício"* — reativáveis sem reespecificação quando o piloto validar e houver
necessidade real de multi-tenant/escala/agendamento):

- **WU-P1..P8** (persistência bimodal, SDD-3);
- **WU-B1..B7** (borda BaaS, SDD-1);
- **WU-I1..I8** (IaC multi-stack, SDD-2);
- **WU-D1** (`sam validate` no gate);
- **WU-S1..S4** e **WU-F1..F3** (gates de segurança & FinOps, ADR-009 — dormente);
- o card **"feat: UI — wizard guiado de ICP..."** (UI local; o foco de UI do piloto é o portal).

Cognito (WU-X1) e o OIDC de deploy permanecem **provisionados na prateleira** (custo zero
parados). WU-D2/D3/G1 já estavam em Backlog (fail-closed da ADR-009) e lá permanecem.

## Princípio de ordenação

A sequência segue a **dependência técnica** do loop (publicar → tabular → puxar), não a ordem
de leitura da SDD:

```
Fase 1  Fundação do loop (SDD §6.1, §2, §3)   ── identidade canônica + contratos compartilhados
   │     WU-E1 (entity_id) · WU-E2 (contratos + catálogo)        [Priority: Alta]
   ▼
Fase 2  Portal (SDD §4, §5)                    ── porta DAO, APIs, auth, carteira
   │     WU-T1 → WU-T2 / WU-T3 → WU-T4 → WU-T5                   [Priority: Media]
   ▼
Fase 3  CLIs do motor (SDD §6.2, §6.3)         ── publish e pull-feedback (HTTP mockado)
   │     WU-E3 → WU-E4                                           [Priority: Media]
   ▼
Fase 4  Integração e operação (SDD §7–§9)      ── e2e offline + artefatos de deploy
         WU-T6 (render.yaml+runbook+smoke) → WU-E5 (e2e offline)  [Priority: Baixa]
         WU-X2 (deploy Render/DNS/seed — AÇÃO EXTERNA do dono)    [Priority: Baixa]
```

**Por que E1/E2 primeiro:** o join do feedback depende da identidade canônica (`entity_id`,
WU-E1) — órfãos corrompem o aprendizado silenciosamente; e **tudo** (porta DAO, APIs, CLIs)
importa os contratos de `portal/contracts.py` (WU-E2). E1→E2 destravam todo o resto. **WU-X2
destrava o deploy real, não o desenvolvimento** — o gate é 100% offline (`InMemoryDAO` +
`TestClient` + HTTP mockado), então T1..T5/E3..E5 não esperam o Render.

## Grafo de dependências (resumo por card)

| Card | Depende de | Bloqueio externo |
|---|---|---|
| WU-E1 Regra canônica de `entity_id` | — | — |
| WU-E2 Contratos portal + `feedback_catalog.json` | — | — |
| WU-T1 Scaffold portal (app + porta DAO + adapters) | E2 | — |
| WU-T2 `POST /api/publish` (Bearer, 201/409) | E2, T1 | — |
| WU-T3 Auth por código (login/sessão/logout) | E2, T1 | — |
| WU-T4 APIs de feedback (POST lead + GET cursor) | T2, T3 | — |
| WU-T5 UI da operadora (carteira + lead card) | T2, T3, T4 | — |
| WU-E3 CLI `publish` | E1, E2 | — (portal mockado nos testes) |
| WU-E4 CLI `pull-feedback` | E2, E3 | — (portal mockado nos testes) |
| WU-T6 `render.yaml` + runbook + smoke | T1, T2, T4 | — (smoke fica fora do gate) |
| WU-E5 e2e offline do loop completo | T2, T3, T4, T5, E3, E4 | — |
| WU-X2 Deploy Render + DNS + seed Talita | T6 (e T1..T5 mergeados) | **ação do dono** (Render/DNS/Neon) |

## As 12 WUs (fase e Priority)

| WU | Fase | Priority | Entrega (resumo — detalhe na SDD §9) |
|---|---|---|---|
| WU-E1 | 1 — Fundação | **Alta** | `core/identity.py: canonical_entity_id` (§6.1) — única fonte de identidade do corpus e do publish |
| WU-E2 | 1 — Fundação | **Alta** | `portal/contracts.py` (§2, literal) + `config/feedback_catalog.json` v1 (§3) + loader |
| WU-T1 | 2 — Portal | Media | Scaffold: app FastAPI, extra `[portal]`, `BasePortalDAO` (§5.2), `InMemoryDAO`, `PostgresDAO` fino, DDL §5.1, noindex, `/healthz` |
| WU-T2 | 2 — Portal | Media | `POST /api/publish`: Bearer, idempotência `(profile_id, run_id)` 201/409, 401/422 (§4) |
| WU-T3 | 2 — Portal | Media | `POST /login` (sha256 do código), sessão por cookie assinado, `POST /logout`, guarda 303 (§4.2) |
| WU-T4 | 2 — Portal | Media | `POST /lead/{entity_id}/feedback` (sessão, append-only) + `GET /api/feedback?since&limit` (Bearer, cursor) |
| WU-T5 | 2 — Portal | Media | UI Jinja2: `GET /carteira` (regra §4.1) + `GET /lead/{entity_id}` — **sem score** |
| WU-E3 | 3 — CLIs | Media | CLI `publish` (§6.2): top-20, `run_id` por hash de conteúdo, registro local com scores, `--dry-run`, degradação limpa |
| WU-E4 | 3 — CLIs | Media | CLI `pull-feedback` (§6.3): cursor, JSONL append-only, dedupe, reactions→ADR-007, statuses→calibração, órfãos isolados |
| WU-T6 | 4 — Operação | Baixa | `render.yaml` + `docs/runbooks/portal-piloto.md` (§8) + `scripts/smoke_portal.py` |
| WU-E5 | 4 — Operação | Baixa | Cenário e2e **offline** do loop completo (publish dry-run → portal InMemory → feedback → pull → consolidação) |
| WU-X2 | 4 — Operação | Baixa (**externa**) | **[Externo/dono]** Web Service no Render (Virginia), env vars, CNAME `selling.issei.com.br`, smoke, seed da Talita via SQL no Neon |

## Quality gate (inegociável, herdado)

Todos os cards mantêm: `ruff` + `mypy --strict` + `pytest` **100% offline e determinístico**
(tolerância numérica `1e-9`), HTTP do portal e APIs externas **sempre mockados** (`respx`/
`monkeypatch`/`TestClient`), contract tests do storage na **porta DAO com `InMemoryDAO`**
(SDD §5.4), **sem** rede, **sem** `DATABASE_URL` real, **sem** banco no CI. O `PostgresDAO`
(fino, 1 SQL por método) fica fora do gate — risco residual aceito, coberto pelo smoke
pós-deploy (runbook §8). PR por card → CI verde → `--squash --auto`.

## Como os cards foram criados

Reproduzível via `scripts/seed_adr010_cards.py` (cria os 12 cards em **Backlog** no Project #1,
com corpo no template DoR de `docs/governance/dor-dod.md` e o campo Priority por fase; imprime
na última linha um JSON com os item-ids para o orquestrador promover a Todo depois).
Idempotência: o script **não** deduplica — **rodar duas vezes duplica os cards. Rodar uma vez.**
