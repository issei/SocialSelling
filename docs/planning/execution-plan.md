# Plano de Execução Detalhado — PoC SocialSelling

Plano operacional para construir o PoC com rigor DevOps/SRE, versionando cada passo para rollback seguro. Complementa: [roadmap-poc](roadmap-poc.md) (o quê), este doc (como/quando/validação/versão), [versioning-strategy](versioning-strategy.md) (git), [autonomous-ops](autonomous-ops.md) (execução autônoma), [devops-sre-iac](../governance/devops-sre-iac.md) (práticas).

> **Princípio:** a complexidade fica no *processo de construção*, não no *sistema*. O PoC continua enxuto (ADR-000); a disciplina de versionamento/validação é que é total.

## 0. Convenções globais (valem para toda WU)

- **WU = Work Unit:** menor unidade de trabalho que termina sempre num *checkpoint commitado*. Toda WU cabe numa janela curta (importante para autonomia — ver autonomous-ops).
- **Branch por módulo:** `feat/m<n>-<nome>`. Trunk (`main`) sempre verde.
- **Checkpoint commit** (na feature branch): pode estar incompleto/vermelho; serve para resume. Prefixo `wip:`.
- **Commit estável** (merge na main): só com **gate verde**. Conventional Commits.
- **Tag de versão:** só na main, após gate verde. Mapa semver na versioning-strategy.
- **Gate (inegociável):** `./scripts/gate.ps1` → `ruff` + `mypy --strict` + `pytest -q` 100% verde e **determinístico** (reexecução byte-idêntica).
- **Definition of Done (DoD) padrão de WU:** (1) cenários BDD da WU verdes; (2) gate verde; (3) `/code-review` sem bloqueios; (4) checklist CLAUDE.md §9; (5) PROGRESS.md atualizado; (6) checkpoint/tag criado.

## 1. Mapa de versões (pontos de restauração)

| Tag | Marco | Estado |
|---|---|---|
| `v0.1.0` | Fundação (Fase 0) | ✅ feito |
| `v0.2.0` | M1 Busca (Tavily) | planejado |
| `v0.3.0` | M2 Extração (Gemini) | planejado |
| `v0.4.0` | M3 Score | planejado |
| `v0.5.0` | M4 Ranking | planejado |
| `v0.6.0` | M5 XAI + relatório | planejado |
| `v0.7.0` | Smoke E2E — **PoC funcional** | planejado |

Correções entre marcos → bump de patch (`v0.2.1`). Cada tag é um ponto de rollback testado e verde.

## 2. Fluxo padrão de uma WU (pipeline SDD-to-Code)

```
[start] ler PROGRESS.md  ──►  garantir branch feat/m<n>  ──►
  S1 contrato (Architect)  ──►  S2 BDD .feature + fixtures gravadas (Spec/QA)  ──►
  S3 implementação mínima (Backend)  ──►  S4 GATE  ──►
  S5 /code-review (Reviewer)  ──►  S6 merge main + tag  ──►  atualizar PROGRESS.md  ──► [stop em checkpoint]
```
Cada S termina num checkpoint commit. Se a janela acabar entre S2 e S3, o próximo run retoma de S3 lendo PROGRESS.md.

## 3. Detalhamento por módulo

### WU-1 — M1 Busca (Tavily) → `v0.2.0`
- **Objetivo:** de `ICPCriteria` gerar queries, consultar Tavily, cachear (T-24h) e emitir `list[ObservedEvidence]`.
- **Pré-condições:** tag `v0.1.0` presente; `.env` com `TAVILY_API_KEY` válido.
- **Passos:**
  - S1 — confirmar/ajustar contrato `ObservedEvidence`; abrir `docs/contratos` se mudar fronteira (ADR se necessário).
  - S2 — `tests/features/m1_busca.feature` (@M1): caminho feliz (fixtures gravadas → K evidências determinísticas), degradação (429 sem cache → `missing_evidence=true`, `data_quality=DEGRADED`), Open-World (zero resultados → incerteza, não erro). Gravar fixtures em `tests/fixtures/tavily/*.json`.
  - S3 — `src/socialselling/modules/m1_busca.py` + skill Tavily em `src/socialselling/skills/`; cache atômico em `data/cache/tavily/<sha256(query)>.json`; degradação conforme SDD v1.0 §1.4. **Nos testes, rede é sempre mockada.**
  - S4 — gate.
  - S5 — `/code-review`; checklist.
  - S6 — merge `feat/m1-busca`→main; `git tag -a v0.2.0`.
- **Validação:** BDD @M1 100% verde e determinístico; reexecução do M1 byte-idêntica; nenhuma chamada real em teste.
- **Versionamento:** checkpoints `wip:` por S; estável `feat(m1): ...`; tag `v0.2.0`.
- **Rollback:** falha pós-merge → `git revert` do merge (main volta a `v0.1.0` funcional); refazer → branch a partir de `v0.1.0`.
- **DoD:** padrão §0.

### WU-2 — M2 Extração (Gemini) → `v0.3.0`
- **Objetivo:** transformar `ObservedEvidence` em `Inference` (Company/Person) com `confidence` e `derived_from`.
- **Pré-condições:** `v0.2.0`; `GEMINI_API_KEY` válido.
- **Passos:** S1 contrato `Inference` → S2 `m2_extracao.feature` (@M2: extração feliz; degradação Gemini 429 → reusar última inferência válida; nenhuma inferência sem confidence; isolamento observed≠inference) + fixtures `tests/fixtures/gemini/*.json` → S3 `m2_extracao.py` (prompt estruturado, parsing validado por Pydantic, backoff exponencial) → S4 gate → S5 review → S6 merge+`v0.3.0`.
- **Validação:** toda `Inference` tem `confidence` e `derived_from` rastreável; camadas isoladas (sem referência mutável compartilhada).
- **Rollback:** `git revert` do merge → main em `v0.2.0`.

### WU-3 — M3 Score → `v0.4.0`
- **Objetivo:** fórmula linear documentada `P = (w_fit·Fit + w_intent·Intent)·(Conf^exp)` lendo `config/runtime.toml`; filtro rígido zera lead (tech proibida/B2C).
- **Passos:** S1 contrato `ProspectScore` → S2 `m3_score.feature` (@M3: determinismo `1e-9`; missing evidence reduz confiança; hard filter→0) **sem rede (sem fixtures de API)** → S3 `m3_score.py` puro/determinístico → S4 gate → S5 review → S6 `v0.4.0`.
- **Validação:** mesma entrada → mesmos scores (tolerância `1e-9`); pesos vêm de config, não hardcoded.
- **Nota:** módulo puro (sem I/O externo) — ideal para rodar em qualquer janela; paralelizável com WU-4 nos testes.

### WU-4 — M4 Ranking → `v0.5.0`
- **Objetivo:** ordenar `list[ProspectScore]` por `p_score` com **tie-break estável** → `list[RankedProspect]` (parcial, sem XAI ainda).
- **Passos:** S1 (reusa contrato) → S2 `m4_ranking.feature` (@M4: reexecução byte-idêntica; empates resolvidos por chave estável, ex. `company_id`) → S3 `m4_ranking.py` → S4 gate → S5 review → S6 `v0.5.0`.
- **Validação:** ordenação determinística byte-idêntica em reexecução.

### WU-5 — M5 XAI + relatório → `v0.6.0`
- **Objetivo:** gerar `XAIPayload` (drivers +/−, sinais ausentes, `degraded_mode`) e relatório legível "aborde X porque…".
- **Passos:** S1 contrato `XAIPayload` → S2 `m5_xai.feature` (@M5: divisões obrigatórias presentes; carimba degraded quando aplicável) → S3 `m5_xai.py` + renderizador markdown/JSON → S4 gate → S5 review → S6 `v0.6.0`.
- **Validação:** payload completo; texto explica o ranking.

### WU-6 — Orquestrador + Smoke E2E → `v0.7.0` (PoC funcional)
- **Objetivo:** `orchestrator.py` encadeia M1→M5 em memória, persiste JSON atômico, expõe CLI; smoke cross-module verde.
- **Passos:** S1 desenhar pipeline → S2 `pipeline_smoke.feature` (@pipeline @smoke: memória vazia + fixtures → N leads; **2ª execução byte-idêntica** — SDD v1.0 §1.3) → S3 `orchestrator.py` + CLI `python -m socialselling.orchestrator --icp ...` → S4 gate → S5 review → S6 merge+`v0.7.0`.
- **Validação (gate de PoC concluído):** smoke verde; `prospects_ranked.json` + relatório gerados do `icp_criteria.example.json`; custo = só tokens; determinismo total.
- **Rollback:** qualquer regressão → `git revert` ou retorno a `v0.6.0`.

## 4. Sequenciamento & dependências (DAG)
`v0.1.0 → WU-1 → WU-2 → WU-3 → WU-4 → WU-5 → WU-6`. WU-3 e WU-4 são puros (sem rede) — bons candidatos a janelas autônomas curtas. WU-1/WU-2 dependem de fixtures gravadas (gravar uma vez, com supervisão, antes de liberar autonomia plena nesses módulos).

## 5. Critérios de prontidão para iniciar o desenvolvimento
- [ ] `pip install -e ".[dev]"` num venv → `./scripts/gate.ps1` verde (baseline).
- [ ] CI (GitHub Actions) verde no push.
- [ ] PROGRESS.md inicializado apontando WU-1/S1.
- [ ] Estratégia de agendamento decidida (autonomous-ops).
