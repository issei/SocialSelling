# SocialSelling — PoC local

Busca de clientes mais eficiente e automatica com IA. Responde: **"quem devo abordar primeiro?"** com um ranking explicavel de prospects.

PoC local, **database-less**, custo de infra zero (so tokens de Tavily + Gemini). Detalhes e decisoes em [CLAUDE.md](CLAUDE.md) e [ADR-000](docs/decisions/ADR-000-escopo-canonico.md).

## Requisitos
- Python 3.11+
- Chaves de API: Tavily (busca) e Gemini (cognicao)

## Setup
```bash
python -m venv .venv
# Windows:  .venv\Scripts\Activate.ps1   |  Linux/WSL:  source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env      # e preencha TAVILY_API_KEY / GEMINI_API_KEY
```

## Quality gate (lint + tipos + testes)
```powershell
./scripts/gate.ps1        # Windows PowerShell
```
```bash
./scripts/gate.sh         # Linux / WSL
```

## Estrutura
| Caminho | Conteudo |
|---|---|
| `config/` | `runtime.toml`, `hypotheses_catalog.json`, `icp_criteria.example.json` |
| `src/socialselling/` | `contracts.py` (modelos Pydantic) + `modules/ core/ skills/` (fase de dev) |
| `tests/` | `test_contracts.py` + `features/ steps/ fixtures/` (BDD por modulo) |
| `docs/` | `decisions/` (ADRs), `planning/` (roadmap), `contratos/`, licoes aprendidas |
| `.ai/` | orquestracao de agentes e governanca |
| `specs/` | documentacao herdada (canonica = SDD v1.0; resto = referencia) |

## Roadmap
Pipeline `M1 Busca -> M2 Extracao -> M3 Score -> M4 Ranking -> M5 XAI`. Sequenciamento em [docs/planning/roadmap-poc.md](docs/planning/roadmap-poc.md).

## Status
Fase 0 (fundacao) concluida. Nenhum modulo de negocio implementado ainda.
