# CLAUDE.md — Memória Operacional do Projeto SocialSelling

> Este arquivo é a memória persistente do projeto para o Claude Code. Leia-o por inteiro no início de cada sessão. A **fonte da verdade arquitetural** é a ADR-000.

## 1. Visão do produto
SocialSelling torna a **busca de clientes mais eficiente e automática usando IA**. Responde a uma pergunta: **"Quem devo abordar primeiro?"** — produzindo um ranking explicável de prospects.

**Fora de escopo (não implementar):** CRM, automação de outreach/mensageria, cadências de e-mail, previsão de funil.

## 2. Decisão canônica (LEIA ANTES DE CODAR)
- Fonte da verdade: **SDD v1.0** (`SDD_SocialSelling_v1.0.md`) + ADR-000 (`docs/decisions/ADR-000-escopo-canonico.md`).
- `specs/SocialSelling_MVP_SDD_v1_1.md` e `specs/sdd/01–12` são **REFERÊNCIA/FUTURO**, não alvo de build. Não importe Postgres, Redis, Celery, scraping ou AWS deles.

## 3. Arquitetura do PoC
- Runtime: **1 processo Python 3.11+**, CLI. Sem servidor, sem banco, sem fila, sem Docker.
- Persistência: **JSON em arquivo** (cold) + memória (hot). Escrita **atômica** (write-temp + `os.replace`).
- Sensores externos: **Tavily** (busca, exclusivo do M1) + **Gemini** (cognição: M2/M3/M5).
- Custo de infra gerenciada: **zero**. Único custo = tokens das 2 APIs.

### Pipeline (módulos determinísticos — NÃO agentes de runtime)
```
M1 Busca/Tavily → M2 Extração/Gemini → M3 Score → M4 Ranking → M5 Explicação/XAI
```

### Regras invioláveis
1. **Isolamento de camadas semânticas:** Observed Evidence ≠ Inferences ≠ Hypotheses. Nunca compartilham referência mutável.
2. **Determinismo no ranking:** mesma memória → saída byte-idêntica (tie-break estável).
3. **Open-World:** ausência de sinal = incerteza (`u`↑), nunca falso. `Missing Evidence` é explícito.
4. **Persistência atômica.**

## 4. Como trabalhamos — SDD-to-Code Loop (obrigatório por módulo)
1. **Contrato** Pydantic (entrada/saída) derivado do SDD.
2. **Cenários Gherkin** `.feature` + **fixtures gravadas** (JSON) das APIs — *spec-first, antes do código*.
3. **Implementação** mínima para passar os cenários.
4. **Gate:** `pytest-bdd` 100% verde (determinístico) + `ruff` + `mypy --strict`.
5. **Integração via PR:** branch por mudança → push → `gh pr create --base main --fill` → `gh pr merge --squash --auto --delete-branch`. **Nunca commit/push direto na `main`.** Flakiness = falha (zero tolerância a não-determinismo).

APIs externas **sempre mockadas** nos testes com fixtures gravadas. Asserções numéricas com tolerância `abs(a-b) <= 1e-9`.

## 5. Guardrails anti-overengineering (o que NÃO fazer no PoC)
- ❌ Banco de dados, ORM, migrations, Redis, Celery, RabbitMQ, FastAPI, Docker, AWS/Terraform.
- ❌ Lógica subjetiva ω, Bayesiano recursivo, KL/EIG, RRF, MMR, capture-recapture (são V1+).
- ❌ Scraping de Instagram/LinkedIn.
- ❌ Tratar M1–M5 como agentes autônomos. São funções de pipeline.
- ❌ Abstrações especulativas "para o futuro". Implemente o mínimo da fatia atual.
- ✅ Em dúvida sobre incluir algo: se não for necessário para o smoke test ponta-a-ponta, **difira**.

> **Exceção consciente (ADR-007):** o aprendizado por feedback like/dislike usa um **modelo
> treinado** (regressão logística) que reajusta `w_fit`/`w_intent` automaticamente. É uma exceção
> deliberada ao "Bayesiano/ML difere para V1+", mantida no espírito do PoC: **Python puro** (sem
> numpy/sklearn), **treino determinístico** (§3.2) e **travas** (gate de amostra, L2, shrinkage,
> clamp). Opt-in por `[learning].enabled`. Ver ADR-007.

## 6. Estrutura de pastas (alvo do PoC)
```
CLAUDE.md, pyproject.toml, .env.example, .gitignore, README.md
config/   runtime.toml, hypotheses_catalog.json, icp_criteria.example.json
docs/     decisions/ (ADRs)  planning/ (roadmap)  analysis/ (gaps)  contratos/
.ai/      agents/ (orquestração)  governance/ (princípios)
specs/    documentação herdada (canônica = v1.0; resto = referência)
src/socialselling/  skills/ modules/ core/ orchestrator.py   # fase de dev
tests/    features/ (.feature)  steps/  fixtures/ (payloads gravados)
data/     observed_evidence.json inferences.json hypotheses_eval.json cache/
logs/     cognitive_trace.jsonl
```

## 7. Glossário mínimo
- **ICP**: Ideal Customer Profile — contrato de quem é o cliente ideal.
- **Prospect / Lead**: empresa candidata a ser abordada.
- **Fit**: aderência estrutural ao ICP. **Intent**: momentum/sinais recentes. **Confiança (Cs)**: convergência das fontes.
- **XAI Payload**: justificativa estruturada (drivers +/−, sinais ausentes).
- **Missing Evidence**: sinal esperado e não encontrado → aumenta incerteza.

## 8. Comandos
> **Windows:** use `py` (o alias `python` cai no stub da Microsoft Store nesta máquina — ver `docs/licoes-aprendidas.md` L-001). Em WSL/Linux, `python` normal.

- Setup: `py -m venv .venv` → ativar → `pip install -e ".[dev]"` → `cp .env.example .env`
- **Quality gate (lint+tipos+testes):** `./scripts/gate.ps1` (Win) ou `./scripts/gate.sh` (WSL)
- Testes: `py -m pytest -q` · Lint: `py -m ruff check .` · Tipos: `py -m mypy`
- Rodar pipeline (CLI): `py -m socialselling.orchestrator --icp config/icp_criteria.talita.json`
- **UI local (ADR-002):** `py -m socialselling.web` → http://127.0.0.1:8000 (ver/editar params, assistente Gemini, executar, Lead Cards). Deps: `pip install -e ".[web]"`.

**Para avançar um módulo M1–M5:** use a skill `sdd-modulo` (institucionaliza o SDD-to-Code Loop com gates).
**Ao final de cada tarefa:** registre aprendizados em `docs/licoes-aprendidas.md` (auto-learning).

## 10. Planejamento e operação (LER antes de desenvolver)
- **Plano-mestre:** `docs/planning/execution-plan.md` (WUs, validação, versão, rollback por passo).
- **Versionamento/rollback:** `docs/planning/versioning-strategy.md` (tags = pontos de restauração).
- **Operação autônoma (plano Pro):** `docs/planning/autonomous-ops.md` + âncora de estado `.ai/state/PROGRESS.md`.
- **Práticas:** `docs/governance/devops-sre-iac.md`. CI em `.github/workflows/ci.yml`.
- **Regra de resume:** todo run autônomo LÊ `.ai/state/PROGRESS.md` no início e o ATUALIZA no fim. Setup do zero: `./scripts/bootstrap.ps1`.

## 9. Checklist de revisão (antes de cada commit)
- [ ] Cenários BDD do módulo 100% verdes e determinísticos.
- [ ] `ruff` e `mypy --strict` limpos.
- [ ] Não viola nenhuma regra inviolável (§3) nem guardrail (§5).
- [ ] Camadas semânticas isoladas; nenhuma inferência sem score de confiança.
- [ ] Não introduziu dependência de infra fora do escopo da ADR-000.
