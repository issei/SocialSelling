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

## CI / Fluxo de PR
- **L-009 | CI | Ruff `UP042`: em Python 3.11+ use `enum.StrEnum`, não `class X(str, Enum)`.**
  Aplicar: enums de string herdam de `StrEnum`. O CI pegou isso antes de virar dívida.
- **L-010 | Tags | Tag criada antes do CI pode apontar para estado vermelho (`v0.1.0` tinha lint).**
  Aplicar: só criar tag de restauração a partir de `main` CI-verde. `v0.1.1` é o 1º baseline confiável.
- **L-011 | Auto-merge | Sem branch protection, `gh pr merge --auto` funde na hora (não espera CI).**
  Aplicar: `main` agora exige o check `gate` (sem revisor humano, para não travar a automação). Validar localmente no venv antes do PR economiza ciclos de CI.

## Implementação de módulos
- **L-012 | Determinismo | Injetar relógio (`now: datetime`) e derivar IDs por hash estável**
  (`sha256(query|url)[:16]`), nunca UUID aleatório nem `datetime.now()` interno. Garante reexecução byte-idêntica.
- **L-013 | Fixtures | Gravar respostas reais com `scripts/record_tavily_fixtures.py`; testes usam `FakeTavilyClient`.**
  Aplicar: rede só no script de gravação; os testes nunca tocam rede (mock por fixture). Re-gravar quando o contrato da API mudar.
- **L-014 | Pytest | Tags de feature (`@M1`) viram marks — registrar em `[tool.pytest.ini_options].markers`** para evitar `PytestUnknownMarkWarning`.

## Integração Gemini
- **L-015 | Gemini | A lista `v1beta/models` ENGANA: `gemini-2.0-flash`/`-001` dão 404 em `generateContent`.**
  Aplicar: usar `gemini-2.5-flash-lite` (rápido) ou `gemini-2.5-flash`. Validar o modelo com uma chamada real, não pela listagem.
- **L-016 | Gemini | Prompt grande (30 evidências) estoura timeout de 30s no `2.5-flash`.**
  Aplicar: `flash-lite` + `timeout=120s` + enxugar prompt (snippet ≤ 800 chars). Saída JSON via `responseMimeType=application/json`, `temperature=0`.
- **L-017 | Cognição | Cache por hash do prompt dá determinismo e FinOps** (igual ao M1). Prompt exclui `captured_at` para o hash ser estável.

- **L-018 | Lint | Rodar `ruff format` ANTES do commit evita os E501 (linha > 100).**
  Aplicar: `py -m ruff format .` faz parte do ciclo; o gate só roda `ruff check` (lint), não formata.
- **L-019 | Intent | No PoC, Intent é um PROXY** (`|derived_from| / norm`) — placeholder honesto; Intent Worker dedicado é V1 (documentado em `m3_score.py`).

- **L-020 | Qualidade | Run real revelou que fornecedores vazam como prospect** (ex.: "AWS" ficou #1, com 30 evidências).
  Aplicar: V1 precisa de resolução de entidades com lista de exclusão de vendors (aws, google, microsoft…) antes do scoring.
- **L-021 | E2E | Orquestrador com clientes injetados (Protocol) permite smoke determinístico (fixtures) E run real (CLI)** com o mesmo código.

## Motor de intenção (público Talita)
- **L-022 | Git | SEMPRE `git checkout -b` ANTES de editar.** Commitei a fatia B na `main` local por engano; recuperei com `git branch <feat>` + `git reset --hard origin/main`. A proteção do remoto evitou estrago, mas o fluxo exige branch primeiro.
- **L-023 | Score | Intent = Σ priors das hipóteses que disparam** (surface_signals ∩ intent_signals), não contagem de evidências. Ausência de sinal ⇒ intent 0 (Open-World). Desqualificador detectado zera o lead. Ver ADR-001. (Substitui L-019.)
- **L-024 | Aderência | O motor de BUSCA (M1/Tavily) ainda é afinado p/ empresas tech em inglês.** Para founders de serviços (Talita), a query generation e a extração precisam de outra rodada — provável sondagem empírica antes de codar. Priors das hipóteses são chutes a calibrar.

## Precisão de persona
- **L-025 | Ranking | `persona_fit` (multiplicador) resolve o falso-positivo de topo.** M2 classifica a persona (fundadora/fundador/empresa/indefinido); M3 multiplica o score por pesos de `[persona]` (homem→0 cai fora; empresa↓; fundadora cheio). Antes "Silvio Meira" era #1; depois o top-5 virou todo de fundadoras. Config-driven e transparente (XAI mostra "Persona alvo: fundadora").

## Aberto / a confirmar
- Fixtures gravadas de Tavily/Gemini ainda nao existem (necessarias para o BDD de M1/M2).
- `gate.ps1`/`gate.sh` so passam apos `pip install -e ".[dev]"` num venv.
