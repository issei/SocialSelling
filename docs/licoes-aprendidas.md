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

## Orquestração / async
- **L-026 | Async | `asyncio.gather` para fan-out resiliente exige `return_exceptions=True`** + tratar `isinstance(out, BaseException)` no laço (converter em erro estruturado). Com `False`, uma exceção crua de UM provedor derruba o lote inteiro. Pego na revisão crítica do SDD LangGraph (§1.2).
- **L-027 | Triagem | Heurística barata de poda deve preferir FALSO-PROSSEGUIR a FALSO-PODAR.** `menos_de_2_anos` só marca com ano em contexto de fundação claro; ambíguo defere ao Gemini. Falso-negativo custa 1 chamada; falso-positivo perde um cliente (assimetria de custo).

## Sensores externos / FinOps de crédito (Apollo)
- **L-028 | Sensor | Sob tier gratuito, projetar a partir da ASSIMETRIA de custo dos endpoints.**
  Apollo: People Search = 0 crédito (descoberta); Enrichment/Match = créditos escassos (~100/mês).
  A descoberta grátis faz o grosso e alimenta a poda barata; o crédito pago fica reservado para
  o passo de maior valor (revelar contato do TOP-N do ranking). Padrão "escada de enriquecimento
  incremental": degrau N só roda para quem o degrau N−1 aprovou. Ver ADR-004 / SDD Apollo.
- **L-029 | Estado | Orçamento que PERSISTE entre runs e reseta no mês ≠ orçamento de tokens (por-run).**
  Créditos de vendor exigem um ledger frio em JSON atômico (`CreditLedger`, `try_spend`/`refund`/
  reconciliação com a verdade do provedor em 402), período = `now.strftime("%Y-%m")` com relógio
  INJETADO (reset reproduzível nos testes). Não é banco — é `atomic_write_text`, fiel ao ADR-000.
- **L-030 | Cache | Em endpoint PAGO, cada cache-hit é 1 crédito economizado** → TTL por volatilidade
  do dado (descoberta 24h; firmografia 30d; contato revelado 90d+), não um TTL único. Dado pago
  nunca deve ser cobrado 2×. Chave = hash canônico do corpo (`sort_keys=True`), como L-017.
- **L-031 | Integração | Sensor novo entra normalizando p/ o formato canônico do provedor**
  (`{title,url,content,score}`) → M1/M2 não mudam; vira `ObservedEvidence` (camada 1), nunca
  inferência. `enabled=false` default ⇒ pipeline byte-idêntico (invariante de paridade). Mesmo
  contrato `AsyncSearchClient` do ADR-003 ⇒ plugue trivial no `parallel_scout`.

## Estratégia de escala (volume de leads local)
- **L-032 | Restrição | Teoria das Restrições no funil: ampliar DESCOBERTA sem elevar o TETO**
  cognitivo só faz bater no muro mais rápido. Apollo (ADR-004) joga mais lead na entrada, mas o
  M2 faz 1 chamada Gemini/lead (teto = RPD do tier grátis) e o `run_pipeline` **sobrescreve** +
  corta em `max_leads=50`. Poda (ADR-003) reduz desperdício, NÃO eleva teto. Ver `docs/planning/escala-volume-leads.md`.
- **L-033 | Cognição | Quota do tier grátis Gemini é por REQUISIÇÃO (RPD), não por token** →
  a alavanca de volume é extração em LOTE (N entidades/chamada) + determinístico-primeiro
  (Apollo já dá firmografia → Gemini só p/ resíduo interpretativo) + orçamento RPD diário +
  ondas resumíveis (volume vira função do tempo). ADR-005.
- **L-034 | Acumulação | Maior ganho de volume real = corpus que ACUMULA entre runs** (upsert
  idempotente por entity_id canônico), não run stateless que sobrescreve. O corpus É o cache
  durável das extrações → protege quota entre runs; `max_leads` vira limite de exibição. ADR-006.
- **L-035 | Sequência | NÃO soltar Apollo (ADR-004) sozinho — emparelhar com ADR-005 (teto).**
  Largura sem teto estoura a quota no 1º run real. Depois: ADR-006 (corpus) → ADR-007 (NDJSON/
  shard) + ADR-008 (entity resolution, resolve L-020 no volume).

## Oportunidades de tooling (revisão de fim de tarefa — auto-learning)
- **Skill candidata `sdd-adr` (autoria de par ADR+SDD canônico):** o fluxo "pesquisar limites de
  uma API externa → ADR (emenda ao ADR-000) + SDD no estilo da casa (seções 0–8) → lições → PR
  auto-merge" já se repetiu (ADR-002/003/004). Vale institucionalizar como skill, análoga à
  `sdd-modulo`, quando surgir o 5º sensor/decisão. **Ainda não criar** (n=3, padrão estável mas
  barato de repetir à mão).
- **Script planejado `scripts/record_apollo_fixtures.py`** (análogo a `record_tavily_fixtures.py`,
  L-013): grava respostas reais dos 3 endpoints Apollo p/ o BDD; rede só nesse script. Será a
  WU-A3 do SDD Apollo — valida a chave real UMA vez e fixa o orçamento de crédito gasto na gravação.

## Aberto / a confirmar
- Fixtures gravadas de Tavily/Gemini ainda nao existem (necessarias para o BDD de M1/M2).
- `gate.ps1`/`gate.sh` so passam apos `pip install -e ".[dev]"` num venv.
- **Apollo: acesso à API no tier gratuito é incerto** (fontes 2026 divergem). Confirmar com chave
  real na WU-A3 ANTES de investir nas WUs seguintes (desenho degrada p/ Tavily em 403).
