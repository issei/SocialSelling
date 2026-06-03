# Licoes Aprendidas

Registro vivo de aprendizados do projeto. Atualize ao final de cada tarefa relevante
(o dono pediu auto-learning eficiente ao longo do desenvolvimento gradual).
Formato: `L-NNN | Categoria | Licao | Como aplicar`.

## Ambiente
- **L-001 | Windows | `python` cai no stub da Microsoft Store nesta maquina; use `py`.**
  Aplicar: scripts e comandos no Windows usam `py -m <ferramenta>`. Em WSL/Linux, `python` normal.
- **L-002 | Toolchain | `pydantic` 2.12 ja existe no Python global; pytest/ruff/mypy nao.**
  Aplicar: ferramentas de dev vivem no venv via `pip install -e ".[dev]"`; nao instalar global.

## Contratos / SDD
- **L-003 | Pydantic | `extra="forbid"` faz os JSON de config casarem EXATAMENTE com o contrato.**
  Aplicar: ao mudar `config/*.json`, ajustar o contrato no mesmo commit (ou o sanity test quebra).
- **L-004 | Rastreabilidade | `Inference.derived_from` liga inferencia -> evidencias de origem.**
  Aplicar: M2 deve sempre preencher `derived_from`; nunca criar inferencia orfa.

## Processo
- **L-005 | Escopo | Walking skeleton vence overengineering.**
  Em duvida sobre incluir algo no PoC, difira (ADR-000). Matematica pesada e V1+.
- **L-006 | Validacao | Provar "executavel-ready" rodando o toolchain de verdade**
  (parse de TOML/JSON + validacao de contratos) pega erros antes de qualquer modulo existir.

## Versionamento / Operação
- **L-007 | Rollback | Tags anotadas na main = pontos de restauração; `v0.1.0` e a fundação.**
  Aplicar: rollback público via `git revert` (nunca `reset`/`--force` em main/tags). Refazer módulo → branch a partir da última tag verde.
- **L-008 | Autonomia | Estado de progresso vive no git + `.ai/state/PROGRESS.md`, não na sessão.**
  Aplicar: WUs curtas que terminam em checkpoint seguro; 1–2 passos por run; parar limpo (cota Pro = error budget).

## Aberto / a confirmar
- Fixtures gravadas de Tavily/Gemini ainda nao existem (necessarias para o BDD de M1/M2).
- `gate.ps1`/`gate.sh` so passam apos `pip install -e ".[dev]"` num venv.
