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

## Build de volume — execução e fechamento
- **L-042 | Paridade | Toda feature de volume entrou OPT-IN com default desligado** (`[apollo]`/`[corpus]`/`[gemini].rpd` enabled=false) → o smoke E2E permanece byte-idêntico (invariante de paridade). Padrão de ouro p/ evoluir sem regressão: cada integração nova só altera o caminho quando explicitamente ligada; sem ela, `run_pipeline` é o mesmo.
- **L-043 | Batch | M2 já fazia 1 chamada Gemini por RUN (não por lead)** — o teto real é o tamanho do prompt (~30 evidências, L-016). Chunking determinístico (ordena por evidence_id, lotes de `batch_size`) eleva o teto p/ volume; `batch_size >= total` => 1 lote = prompt IDÊNTICO (paridade). RPD ledger só debita em cache MISS; esgotado => pula lote (onda futura).
- **L-044 | Side-effect | Construir um ledger (escrita atômica) dentro do `run_pipeline` poluía `data/` real nos testes.** Guardar a construção com `if apollo is not None and cards:`/`and inferences:` evita escrever quando não há nada a fazer — e some o efeito colateral. Ledgers ficam gitignored, mas evitar a escrita à toa é mais limpo.
- **L-045 | Escopo | "Terminar todas as specs" ≠ implementar cada sub-feature.** Determinístico-primeiro (ADR-005) e process-only-new (ADR-006) foram DIFERIDOS conscientemente (alto risco de redesenho do M2 / entidade só emerge pós-M2; cache+corpus já dão o FinOps). Documentar o diferido com razão é entrega honesta; rushar refino arriscado por completude não é.

## UI / UX
- **L-046 | Tailwind CDN | Classes de cor montadas em JS (`bg-${tone}-500`) podem não ser geradas** pelo Play CDN se ele não as vir como literais. **Safelist:** um `<div class="hidden ...">` com todas as classes dinâmicas garante a geração — sem flash de estilo. Também: sempre `esc()` (escape HTML) em dados de Gemini/Apollo antes de injetar via innerHTML (anti-injeção).
- **L-047 | UX | Lista de leads = padrão "scan-then-focus":** tabela densa e ordenável para VARRER/comparar (score com barra, ícones de canal com `stopPropagation`), + drawer slide-over para FOCAR num lead e ver o enriquecido (contato, firmografia, por-que-agora, lacunas, fontes). Mudança estritamente de apresentação: contrato `/api/run` e IDs do JS preservados → testes de não-regressão garantem isso.
- **L-048 | Verificação | Sem navegador Chrome conectado (extensão não pareada) + computer-use offline = não dá screenshot automático.** Verificação de runtime possível: subir o servidor e `Invoke-WebRequest` confere HTTP 200 + presença da estrutura nova. Cuidado: escapar aspas no PowerShell (`\"` em regex vira falso-negativo). Tests via FastAPI TestClient cobrem o contrato.
- **L-049 | UX/Escopo | Redesign do cockpit v2 = "Discovery puro": só dado REAL do `LeadCard`.** Spec do comitê pedia colunas/seções que não existem nos dados (Timing "3 dias", Hipótese nomeada) e um "Conversation Blueprint" que gera mensagem de outreach — fora de escopo (CLAUDE.md §1) e com fato inventado (viola Open-World §3). Decisão: cortar o fabricado (Timing vira badge `intent>0` real; evidência principal = `why_now[0]`) e o gerador de mensagem; manter contato+canais p/ abordagem manual. Densidade (dark, `tabular-nums`, abas) sem inventar sinal. Mudança 100% de apresentação: zero alteração de backend (ADR-002), IDs e funções JS preservados → testes de não-regressão verdes.
- **L-051 | CSS/Footgun | Container `fixed inset-0 z-50` (overlay tela-cheia) FECHADO precisa de `pointer-events:none`.** No cockpit v2 o `#drawerWrap` virou tela-cheia z-50, mas o `.drawer-hidden` só zerava o `pointer-events` do filho (`#leadOverlay`), não do wrap → uma camada **invisível** por cima de tudo engolia TODOS os cliques, **sem erro** (sintoma: "não clico em nada e não dá erro"). Fix: `#drawerWrap.drawer-hidden{pointer-events:none}` (e `auto` ao abrir, p/ o overlay capturar o clique-para-fechar). Verificação que pega isso e os testes de string não: `document.elementFromPoint(x,y)` no centro da tela (respeita `pointer-events` como clique real) + `getComputedStyle(wrap).pointerEvents` via chrome-devtools MCP. Guard de regressão = regex da regra CSS no HTML servido.
- **L-050 | Verificação | chrome-devtools MCP renderiza screenshot do cockpit (atualiza L-048).** O 1º `take_screenshot` pode dar timeout (CDN do Tailwind carregando) — basta retentar. Para exercitar tabela+drawer SEM chaves de API: sobrepor `window.fetch` interceptando `/api/run` (devolve `Response` com leads-mock) e chamar a função global `run()` — porque `LEADS` é `let` (binding léxico, NÃO `window.LEADS`), reassinalar de fora não funciona; só o caminho real de render popula o closure. Function declarations de topo (`run`, `renderTable`, `openDrawer`) SÃO globais e chamáveis; `let`/`const` não.

## Aprendizado por feedback + busca incremental (ADR-006/007)
- **L-052 | ML/Determinismo | Dá p/ ter MODELO TREINADO sem furar o determinismo (§3.2).** Regressão logística em Python puro com gradiente FULL-BATCH, init em zeros, épocas fixas, amostras ordenadas por `company_id` e **sem `random`** ⇒ mesmo `feedback.json` → mesmos pesos, bit a bit → ranking byte-idêntico. Auto-apply seguro com 4 travas: **gate** (`min_likes` E `min_dislikes` — sem os dois lados não treina), **L2**, **shrinkage** rumo aos pesos atuais (mais votos ⇒ mais confiança) e **clamp/normalização** (preserva a escala da fórmula). Exceção consciente ao §5, documentada em ADR-007.
- **L-053 | Feedback | Capturar as features NO CLIQUE torna o store de votos autossuficiente.** O voto guarda os componentes do score (`fit`/`intent`/…) do card naquele instante → o treino não recomputa o pipeline nem exige alterar `ProspectScore`. Store de feedback espelha o `CorpusStore` (chave = `company_id`, escrita atômica, last-write-wins; re-clicar no mesmo selo = `label:"none"` remove).
- **L-054 | Busca incremental | "Achar leads NOVOS" sem paginação do Tavily = variar o TEXTO da query por onda.** `generate_queries(wave)`: `wave=0` = queries-base (paridade); `wave>0` = janela deslizante determinística de `industries × regiões × modificadores`. Como a chave do cache É a query, variar o texto **é** o cache-bypass — não precisa de flag extra. Estado da onda por ICP (`WaveStore`) só avança no modo acumulativo (corpus on); CLI/smoke ficam em `wave=0`. O `accumulate_and_rank` (1 helper p/ CLI+UI) faz o corpus crescer e re-ranquear por score, deduplicado por `entity_id`.
- **L-055 | Git | PRs encadeados sem esperar o merge: `git rebase --onto origin/main <commit-da-feature-A>`.** Com PR-A ainda aberto, baseei PR-B no HEAD de A; após o squash-merge de A, `rebase --onto origin/main <A>` descarta o commit de A (conteúdo já na main) e replica só B → diff do PR-B limpo, sem esperar a fila de merge.
- **L-056 | Onda/Resiliência | Avançar a onda em TODO run (mesmo vazio) "queima" as ondas boas (cacheadas) quando a cognição degrada.** Sintoma reportado: "a prospecção não recupera/exibe resultados". Diagnóstico em camadas que ISOLOU o meu código do externo: (1) `waves.json` avançou mas `leads_corpus.json` não existia ⇒ `run_pipeline` voltou 0 cards (o `accumulate` só persiste se há cards); (2) round-trip do corpus com card realista = OK ⇒ wiring meu não é o bug; (3) M1 offline (só-cache) = 28/30 evidências reais nas waves 0/1 ⇒ colapso é PÓS-M1; (4) prompt do M2 (chave de cache = prompt inteiro) AUSENTE no cache do Gemini ⇒ exige chamada real; (5) **chamada mínima ao Gemini real (`generate_json`) → 429**. Causa-raiz = **cota free-tier do Gemini**; o M2 captura o 429 (degrada) e devolve `[]` → 0 cards → tela vazia. Meu código não tocou o M2, mas **piorava** ao avançar a onda à toa. Fix: avançar a onda **só quando o ciclo produz leads**; UI mostra "0 leads / possível cota do Gemini". Lição de processo: para "sumiu o resultado", a chamada real mínima à API externa é o teste que separa "meu código" de "camada externa" — fazer cedo.

- **L-057 | Cognição/Billing | O 429 do Gemini NÃO era cota free-tier que reseta — era `prepayment credits depleted` (billing pré-pago esgotado).** O corpo cru do 429 (`error.message`) dizia exatamente isso + link de billing; o `GeminiClient` antigo descartava o corpo e levantava um genérico "429". Não reseta no relógio — só resolve adicionando crédito no AI Studio. **Correção de produto (não dá p/ "consertar" billing no código):** (1) `GeminiClient` passou a surfaciar `error.message` do Google em 429/4xx; (2) o limite web embrulha o cliente (`_CapturingCognition`) e guarda o último erro mesmo que o M2 o engula; (3) `run_for_icp` levanta `CognitionUnavailable` quando o ciclo fica SEM NADA a exibir POR falha de cognição — mas com corpus prévio mostra o que há; (4) o endpoint vira **502 com a mensagem real** e a UI exibe um painel acionável (link de billing). Lição-chave: **degradação silenciosa esconde a causa acionável** — propagar a mensagem CRUA do provedor até o usuário no limite web (verificado: `POST /api/run` → 502 com "prepayment credits depleted"). Corrige a atribuição "cota free-tier" da L-056.

## Oportunidades de tooling (revisão de fim de tarefa — auto-learning)
- **Skill candidata `sdd-adr` (autoria de par ADR+SDD canônico):** o fluxo "pesquisar limites de
  uma API externa → ADR (emenda ao ADR-000) + SDD no estilo da casa (seções 0–8) → lições → PR
  auto-merge" já se repetiu (ADR-002/003/004). Vale institucionalizar como skill, análoga à
  `sdd-modulo`, quando surgir o 5º sensor/decisão. **Ainda não criar** (n=3, padrão estável mas
  barato de repetir à mão).
- **Script planejado `scripts/record_apollo_fixtures.py`** (análogo a `record_tavily_fixtures.py`,
  L-013): grava respostas reais dos 3 endpoints Apollo p/ o BDD; rede só nesse script. Será a
  WU-A3 do SDD Apollo — valida a chave real UMA vez e fixa o orçamento de crédito gasto na gravação.

## Build de volume (execução bypass)
- **L-036 | Gate | `scripts/gate.ps1` usa `py`, mas `py` cai no Python global 3.14 SEM as ferramentas de dev** (pytest/ruff/mypy vivem no `.venv`). Localmente, rodar o gate por `.\.venv\Scripts\python.exe -m {ruff|mypy|pytest}` (não `py -m`). O CI usa setup próprio e não sofre disso. **RESOLVIDO:** `gate.ps1` agora prefere `$PSScriptRoot\..\.venv\Scripts\python.exe` quando existe (fallback `py`), imprimindo qual Python usou. Roda `& $py -m …` direto.
- **L-037 | mypy+test | `mypy --strict` reprova `StrEnumMembro == "literal"`** (comparison-overlap) — usar `.value` no teste. E **kwargs inválidos em construtor Pydantic** (teste de `extra=forbid`) — usar `Model.model_validate({...})` com dict, senão o mypy acusa `call-arg`. Padrão para todos os testes de contrato.
- **L-038 | Commit | Here-string do PowerShell `@'…'@` vaza o `@` para o SUBJECT do commit** (vira "@ feat: …"). Usar `git commit -F <arquivo>` (Write do arquivo de mensagem) em vez de `-m @'…'@`. Confirmar com `git log -1 --format=%s` antes do PR.

## Orquestração de agentes (paralelismo)
- **L-039 | Agentes | Agentes async em BACKGROUND TRAVAM em prompt de permissão** (não conseguem aprovar interativamente). Os 3 agentes do fan-out (credit/RPD/corpus ledgers) ESCREVERAM os arquivos, mas penduraram ao rodar o gate/`gh`/`git push` (sinal: `.claude/settings.local.json` modificado). **Padrão "harvest" que funcionou:** colher os arquivos das worktrees (`.claude/worktrees/agent-*/…`), rodar o gate no main loop e fazer commit/PR/merge eu mesmo. Mitigações futuras: (a) pré-conceder permissões; (b) agentes só ESCREVEM, o main loop faz gate+merge; (c) rodar em foreground.
- **L-040 | Worktree | Worktree de agente NÃO tem `.venv`** (gitignored, não copiado). O gate dentro dela exige o venv do repo original + `PYTHONPATH=<worktree>\src`. Atrito real no Windows → reforça o padrão "agentes escrevem, main loop valida". Worktrees ficam `locked` enquanto o harness as rastreia; `git worktree remove -f -f` força, mas pode confundir o estado — deixar para o fim da sessão.
- **L-041 | Diagnóstico | Para diagnosticar agente travado, inspecione o FILESYSTEM da worktree** (`git status`, `ls` dos arquivos-alvo) em vez de ler o `.output` (transcript JSONL estoura o contexto). Revela exatamente até onde o agente chegou.

## Pré-condições externas (billing / entitlement)
- **L-056 | Apollo | A master API (`mixed_people/search` etc.) é INACESSÍVEL no plano Free** —
  retorna `HTTP 403 {"error_code":"API_INACCESSIBLE", "error":"... not accessible with this
  api_key on a free plan. Please upgrade your plan ..."}`. Confirmado com chave real (06/2026).
  **Pegadinha:** People Search aparece como **"0 crédito"** na interface web, o que induz a crer
  que é usável via API no Free — NÃO é; o "0 crédito" vale só no app web, a API mestre é bloqueada
  por *entitlement de plano*, independente de crédito. Diagnóstico: o 403 do cliente esconde o
  body; bater no endpoint cru (`httpx.post` com `x-api-key`) revela o `error_code`. **Não é
  problema de código nem de formato de chave** — o cliente já manda a chave no header
  (`x-api-key`), e o aviso de "key na URL" do portal é ruído. **Como aplicar:** gravar fixtures
  reais (`scripts/record_apollo_fixtures.py`) exige **upgrade do plano Apollo**; até lá o card fica
  em Backlog. O runtime já degrada p/ Tavily em 403, então só o *recording* de fixtures bloqueia.
  Resolve o item aberto antigo ("acesso à API no Free é incerto").

## Aberto / a confirmar
- Fixtures gravadas de Tavily/Gemini ainda nao existem (necessarias para o BDD de M1/M2).
- `gate.ps1`/`gate.sh` so passam apos `pip install -e ".[dev]"` num venv.
