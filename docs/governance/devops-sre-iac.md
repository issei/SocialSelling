# Práticas DevOps / SRE / IaC (adaptadas ao PoC local)

Princípios de produção aplicados na medida certa de um PoC local database-less. A complexidade de infra real (AWS/Terraform/Postgres) é **diferida** (ADR-000); aqui aplicamos os *princípios*, não o peso.

## 1. Infraestrutura como Código (local)
- **Ambiente reproduzível:** `scripts/bootstrap.ps1`/`.sh` recriam o ambiente do zero (venv + deps + `.env` + gate). Nenhum passo manual não-documentado.
- **Dependências fixadas:** `pyproject.toml` (pisos de versão); evoluir para lock se necessário.
- **Config versionada:** `config/runtime.toml` (parâmetros) e `config/*.json` (ICP, hipóteses) no git. Segredos só no `.env` (gitignored).
- **Fim de linha determinístico:** `.gitattributes` (`.sh`=LF, `.ps1`=CRLF) — evita quebra de scripts entre Windows/WSL.

## 2. CI (GitHub Actions)
- Workflow `.github/workflows/ci.yml` roda o **mesmo gate** em todo push/PR para `main`: `ruff` + `mypy --strict` + `pytest`.
- Rede de segurança independente do ambiente local — pega regressões de runs autônomos antes que o dono acorde.
- Custo zero (tier gratuito). Sem deploy (PoC local).

## 3. Quality gates (shift-left)
- **Local, pré-merge:** `./scripts/gate.*` — obrigatório antes de qualquer merge na main.
- **Pré-push (opcional, recomendado):** hook que roda o gate; bloqueia push quebrado. Instalável via `scripts/hooks/` + `git config core.hooksPath`.
- **Determinismo é gate de 1ª classe:** flakiness = falha. APIs externas sempre mockadas em teste (fixtures gravadas).

## 4. SLOs / SLIs do PoC (eficiência cognitiva, não uptime)
| SLI | Alvo (SLO) | Como medir |
|---|---|---|
| Taxa de testes verdes | 100% na main | CI/gate |
| Determinismo do pipeline | 100% (reexecução byte-idêntica) | smoke test 2x |
| Cobertura de tipos | `mypy --strict` sem erros | gate |
| Custo por execução | ≤ orçamento de tokens definido em `runtime.toml` | trace de tokens |
| Latência do pipeline (N≤50 leads) | p95 alvo a definir após M6 | `cognitive_trace.jsonl` |
| Falsos positivos de fusão de entidade | baixo (amostragem manual) | auditoria de inferências |

**Error budget:** para *determinismo* e *testes verdes* o orçamento é **zero** (bloqueante). Para latência/custo, é um alvo a calibrar — não bloqueia o merge no PoC.

## 5. Observabilidade
- **`logs/cognitive_trace.jsonl`** (append-only): um evento por decisão relevante do pipeline — `{ts, module, action, lead_id, inputs_hash, outputs_hash, tokens, degraded}`. Permite auditar custo e reproduzir decisões.
- **Rastreabilidade Evidence→Inference→Score→Decision** garantida pelos contratos (`derived_from`).
- Trace é a base para, no futuro, medir os SLIs de custo/latência sem instrumentação extra.

## 6. Gestão de mudança
- Toda decisão de fronteira arquitetural → **ADR** em `docs/decisions/`.
- Toda mudança de contrato que cruze módulos → ADR + bump coordenado.
- Conventional Commits → changelog automatizável depois.

## 7. Drills de recuperação (SRE: pratique o rollback)
- Antes de liberar autonomia plena, **ensaiar** o playbook de rollback (versioning-strategy §5): revert de um merge fake, restauração de uma tag em worktree. Recuperação não testada não é recuperação.

## 8. O que está fora (diferido, por ADR-000)
Terraform/AWS, Postgres/Redis/Celery, deploy/CD, autoscaling, dashboards Prometheus/Grafana. Entram em V1 quando o PoC provar valor — não antes.
