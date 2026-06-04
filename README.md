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

## Rodar
### Pela linha de comando (CLI)
```bash
py -m socialselling.orchestrator --icp config/icp_criteria.talita.json
# saida: data/prospects_ranked.json + data/prospects_ranked.md (Lead Cards)
```

### Pela UI local (amigavel) — recomendado
UI web local para ver/editar parametros, gerar o ICP com ajuda do Gemini, executar e
ver os Lead Cards (Instagram clicavel). Roda so em `localhost` (ADR-002).

**Mais simples (Windows):** dê **duplo-clique em `start.bat`** — na 1a vez ele cria o venv,
instala tudo, gera o `.env` e abre o navegador. (WSL/Linux/macOS: `./start.sh`.)

Manualmente:
```bash
pip install -e ".[web]"          # ou ".[dev]" (ja inclui web)
py -m socialselling.web          # abre http://127.0.0.1:8000
```
As chaves de API ficam no `.env` (nunca na UI).

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
Pipeline M1–M5 + orquestrador completos; busca aderente ao publico-alvo (queries PT-BR +
Instagram) e **Lead Cards** acionaveis; **UI local** (FastAPI) para operar tudo. Ver
`.ai/state/PROGRESS.md`. Tags de restauracao ate `v0.11.x`.
