# SDD — Operator Cockpit (Data Grid de Alta Densidade)

> **Status:** Proposta (REFERÊNCIA/FUTURO — não é alvo de build imediato sem aprovação por WU).
> **Escopo:** Evolução **somente de interface** da UI de operador local (ADR-002). **Não altera** os algoritmos de score do back-end (M1–M5). O núcleo permanece intocado.
> **Fonte da verdade arquitetural:** ADR-000 (escopo canônico), ADR-002 (UI operador local).
> **Autores (comitê):** Principal Product Designer · UX Architect (Revenue Intelligence) · Staff FE Engineer (Data Grids) · Revenue Intelligence / Sales Ops · InfoViz Specialist (Bloomberg/Clay).
> **Critério máximo de sucesso:** um SDR consegue analisar 500 leads e extrair os 20 melhores alvos qualificados em **< 10 min**, sem telas opacas nem métricas sem contexto.

---

## 0. Sumário executivo & princípio condutor

A UI atual (`src/socialselling/web/static/index.html`, ~203 linhas, vanilla JS + Tailwind CDN) renderiza **Lead Cards** empilhados. Cards são ótimos para 5–20 leads e péssimos para 500–1000: forçam scroll vertical, impedem comparação coluna-a-coluna e não suportam ordenação/filtragem massiva.

Este SDD substitui os cards por um **Operator Cockpit** de três zonas — **Parâmetros · Execução · Resultados** — cujo coração é um **Data Grid virtualizado** estilo Bloomberg Terminal / Clay / Apollo. A análise profunda (XAI, comitê de compra, blueprint de conversa) migra para um **Side Drawer** que abre **sem tirar o operador da linha** (progressive disclosure).

Três princípios governam cada decisão de design abaixo:

| # | Princípio | Consequência de design concreta |
|---|-----------|--------------------------------|
| **P1** | **Information Density First** | Linha de grid de 40px, tipografia tabular `font-variant-numeric: tabular-nums`, zero card-padding redundante. Cada coluna = um eixo de decisão. |
| **P2** | **Explainable & Evidence-Driven** | Nenhum número é clicável-mudo. P_score, Fit, Intent e Confidence abrem o **colapso de incerteza** (árvore matemática do `m3_score.py`) e os **links das fontes web** que sustentam o dado. |
| **P3** | **Progressive Disclosure / Single-Screen** | Tabela mostra o essencial; o resto vive no Drawer lateral. Navegação entre leads é `↑/↓` sem fechar o Drawer. |

---

## 1. Realidade do back-end & lacuna de contrato (LER ANTES DE CODAR)

O grid quer exibir mais do que o `LeadCard` atual carrega. O núcleo **não muda**; o que muda é a **camada de apresentação** que monta o DTO entregue à UI. Mapa do que existe hoje vs. o que o cockpit exige:

| Necessidade da UI | Existe hoje? | Origem real no código | Ação |
|---|---|---|---|
| ID/Nome, setor, localização | ✅ | `LeadCard.display_name/company/sector/location` | reusar |
| P_score, Fit, Intent, Confidence, persona_fit | ✅ | `ProspectScore` (`contracts.py:180`) | reusar |
| `hard_filter_passed` (REJEITADO) | ✅ | `ProspectScore.hard_filter_passed` | reusar |
| Links Instagram/LinkedIn/Site | ✅ | `LeadLinks` | reusar |
| Hipótese dominante ativa (H_01…H_05) | ⚠️ parcial | calculável de `Inference.intent_signals` × `hypotheses_catalog.json` (mesma lógica de `_intent_from_hypotheses`) mas **não persistida** no `LeadCard` | **enriquecer DTO** |
| Chips de `intent_signals` detectados | ⚠️ | existe em `Inference.intent_signals`, **descartado** ao montar `LeadCard` (`orchestrator.py:103`) | **enriquecer DTO** |
| Decisor mapeado (nome/cargo/senioridade) | ⚠️ parcial | só `LeadCard.role` (de `people[0]`); senioridade e demais pessoas descartadas | **enriquecer DTO** |
| Comitê de compra (BMO + Structural Champion + completude) | ❌ | `Inference.people: list[PersonEntity]` existe mas só `people[0]` chega à UI; papéis BMO/SC **não são classificados** | **enriquecer DTO** (regra de papel determinística — §3.B.II) |
| Árvore matemática do P_score (drivers +/−, missing) | ⚠️ | `XAIPayload` (`positive/negative/missing_signals`, `degraded_mode`) existe mas **não chega** ao `LeadCard` (vira `why_now`/`gaps` em string) | **enriquecer DTO** (anexar `XAIPayload` íntegro) |
| Hook + script de abordagem | ❌ | não gerado hoje | **V2** (Conversation Blueprint — §3.B.III); MVP usa template determinístico |
| Contraindicações ("o que NÃO falar") | ⚠️ | derivável de `XAIPayload.missing_signals` (Open-World) | reusar como base, refinar em V2 |

### 1.1 Decisão de contrato — `LeadRowDTO` (presentation layer, ADR-002-safe)

O `orchestrator._to_lead_card` (`orchestrator.py:103`) já é o ponto onde score + inferência + XAI se juntam. **Enriquecemos ali** (camada de apresentação), sem tocar M1–M5. Concretamente, estendemos `LeadCard` com campos opcionais e expomos um endpoint que devolve o objeto completo. **Regra inviolável preservada:** Observed Evidence ≠ Inferences ≠ Hypotheses continuam isolados; o DTO apenas *projeta* as três camadas lado a lado para leitura, sem fundir referências mutáveis.

> **Guardrail (§5 do CLAUDE.md):** nenhuma infra nova (sem DB, Redis, Celery). O grid é client-side puro sobre o JSON já retornado por `/api/run`. A única mudança de back-end é serializar campos que já existem em memória e hoje são descartados.

---

## 2. Especificação do Data Grid principal (tabela virtualizada)

### 2.0 Anatomia da linha (layout de colunas)

```
┌──┬─────────────────────────┬──────────────────────────┬─────────────────────────┬───────────────────────┬────────────┬──────────────┐
│☑ │ PERFIL & SETOR          │ NOTAS DE INTELIGÊNCIA    │ HIPÓTESES & SINAIS      │ DECISOR (BMO)         │ CANAIS     │ ABORDAGEM    │
│  │ (sticky, 260px)         │ (sortable, 200px)        │ (220px)                 │ (180px)               │ (120px)    │ (140px)      │
├──┼─────────────────────────┼──────────────────────────┼─────────────────────────┼───────────────────────┼────────────┼──────────────┤
│☑ │ ▎Acme Consultoria       │ ⬤ 0.82  ▰▰▰▰▰▰▰▱▱▱       │ H_01 Crescimento Travado│ Talita Reis           │ [in][ig][🌐]│ [💬 Abordagem]│
│  │  Consultoria · SP, BR   │ Fit 0.78 · Int 0.61      │ ✓vaga_lideranca         │ CEO · C-Level         │            │              │
│  │  #B2B #5-30p            │ Conf 71%                 │ ✓intencao_ia +1         │                       │            │              │
└──┴─────────────────────────┴──────────────────────────┴─────────────────────────┴───────────────────────┴────────────┴──────────────┘
```

- **Altura de linha:** 56px (3 micro-linhas de texto). Modo "compacto" opcional: 40px (1 linha, métricas inline) — toggle no header.
- **Coluna 0 (checkbox):** 36px, sticky-left junto com Perfil.
- **Coluna Perfil:** sticky-left (permanece visível no scroll horizontal). Ancora a identidade da linha.
- **Densidade:** `tabular-nums` em todas as métricas para alinhamento decimal vertical (padrão Bloomberg).

### 2.1 Coluna **Perfil & Setor**

| Propriedade | Especificação |
|---|---|
| Conteúdo | `display_name` (negrito) → `company` (se diferente) → linha meta: `sector · location` → tags firmográficas (`business_models`, faixa de funcionários) como chips cinza 11px |
| Barra de rank | borda esquerda 3px colorida pela faixa de P_score (espelha a mini-barra), reforça leitura em scan vertical |
| **Estado REJEITADO** | quando `hard_filter_passed === false`: **opacidade 40%** na linha inteira + badge vermelho-desaturado **`REJEITADO`** ao lado do nome + tooltip com o motivo (`negative_signals[].text` do tipo `DISQUALIFIER`/`EXCLUDED_TECH`). Linha **permanece selecionável e ordenável** (operador pode querer auditar rejeições), mas afunda no fundo por padrão. |
| Hover | realce `bg-slate-50`; nome vira link para o site institucional se houver |
| Truncamento | `text-ellipsis` com `title` completo no hover; nunca quebra a altura da linha |

### 2.2 Coluna **Notas de Inteligência** (alinhada a `m3_score.py`)

| Indicador | Render | Faixas / thresholds |
|---|---|---|
| **P_score** | número proeminente (16px, semibold, `tabular-nums`) + **mini-barra horizontal** 6px. Barra normalizada contra o teto observado do lote (P_score não é limitado a 1.0 — `Field(ge=0.0)`) | **🟢 Priority Action** ≥ `t_priority` · **🟡 Monitor** ≥ `t_monitor` · **⚪ Baixo Potencial** abaixo. Thresholds vêm de `runtime.toml` (configuráveis), não hard-coded na UI. |
| **Fit** (ICP Match) | micro-indicador `Fit 0.78` + dot de cor por faixa | gradiente verde→cinza |
| **Intent** (Momentum) | micro-indicador `Int 0.61` lado a lado com Fit | `Intent === 0` → render **cinza "—"** com tooltip "Open-World: nenhum sinal de timing detectado" (nunca pintar de vermelho; ausência ≠ negativo) |
| **Confidence** | `Conf 71%` (porcentagem). `< 50%` → ícone ⚠️ âmbar | reflete `ProspectScore.confidence` (confiabilidade da extração) |

> **P2 em ação:** clicar em **qualquer** das 4 métricas abre o Drawer já rolado até o **Bloco I** (árvore matemática) com aquele driver destacado.

**Mini-barra — regra de cor (TS, fonte única de verdade):**
```ts
function scoreBand(p: number, t: ScoreThresholds): "priority" | "monitor" | "low" {
  if (p >= t.priority) return "priority"; // verde
  if (p >= t.monitor)  return "monitor";  // amarelo
  return "low";                            // cinza
}
```

### 2.3 Coluna **Hipóteses & Sinais** (alinhada a `hypotheses_catalog.json`)

| Elemento | Especificação |
|---|---|
| **Hipótese dominante** | chip colorido com `hypothesis_id` + label curto (ex: `H_01 Crescimento Travado`). "Dominante" = hipótese com **maior `prior`** entre as que dispararam (mesma lógica de `_intent_from_hypotheses`, `m3_score.py:52`). Cor por família: H_01/H_02 (dor estrutural) índigo, H_03 (expansão) verde, H_04 (IA) roxo, H_05 (formação) cinza. |
| **Chips de intent_signals** | até **3** chips `✓ <signal>` (ex: `✓ vaga_lideranca`, `✓ intencao_ia`). Excedente colapsa em `+N`. Cada chip tem tooltip com a hipótese-mãe e contribuição de `prior`. |
| Vazio | se `intent_signals` vazio: chip cinza `sem timing` (Open-World explícito). |
| Hover no chip | mostra o `surface_signal` exato e qual evidência o sustentou (link). |

### 2.4 Coluna **Decisor Mapeado (BMO)**

| Propriedade | Especificação |
|---|---|
| Conteúdo | nome do **Buying Motion Owner** + `role_title` + badge de **senioridade** (`PersonEntity.seniority`) |
| Definição de BMO (determinística) | maior senioridade entre `Inference.people` cujo `role_title` casa `icp.persona_matrix.target_roles`; empate → primeiro por ordem estável. Se nenhum casa → primeiro `people[0]`; se lista vazia → **`Decisor não mapeado`** (chip âmbar, alimenta Missing Evidence). |
| Confiança | dot pela `PersonEntity.confidence`; `< 0.5` → ⚠️ |
| Ação | clique → Drawer **Bloco II** (organograma do comitê) |

### 2.5 Coluna **Canais Destino** (ações rápidas)

| Propriedade | Especificação |
|---|---|
| Conteúdo | bloco compacto de até 3 ícones-botão: **LinkedIn** · **Instagram** · **Site** |
| Comportamento | `<a target="_blank" rel="noopener noreferrer">` — abre destino em **nova aba com 1 clique**, sem passar pelo Drawer |
| Estado ausente | canal sem URL (`null`) → ícone **desabilitado** (opacidade 30%, `aria-disabled`, sem href), nunca some (preserva alinhamento da grade) |
| Ordem | Instagram-first quando presente (alinhado ao foco do produto), depois LinkedIn, depois Site |
| A11y | cada ícone com `aria-label="Abrir LinkedIn de {nome} em nova aba"` |

### 2.6 Coluna **Abordagem Contextual**

| Propriedade | Especificação |
|---|---|
| Conteúdo | botão primário **`[💬 Ver Abordagem]`** |
| Ação | abre o **Side Drawer** rolado ao **Bloco III** (Conversation Blueprint) |
| Estado REJEITADO | botão vira secundário `[Auditar rejeição]` → Drawer abre no **Bloco I** mostrando o driver negativo que zerou o lead |
| Keyboard | `Enter` na linha focada = mesmo efeito |

### 2.7 Estados visuais globais da linha

| Estado | Tratamento |
|---|---|
| Default | fundo branco, borda inferior `slate-100` |
| Hover | `bg-slate-50`, cursor pointer na zona de Perfil |
| Selecionada (checkbox) | `bg-indigo-50`, checkbox marcado, borda-esquerda índigo |
| Ativa (Drawer aberto nela) | `ring-2 ring-indigo-400` interno + barra lateral índigo persistente |
| REJEITADO | opacidade 40%, badge, afunda na ordenação default |
| Degradado (`degraded_mode`) | ícone 🟠 discreto no canto da linha + tooltip "lote rodou em modo degradado; score com confiança reduzida" |

---

## 3. Side Drawer (painel lateral de detalhamento)

### 3.A Comportamento do container

- Desliza da **direita**, largura **480px** (≤1280px vira overlay full-height; ≥1280px empurra a grade sem recolá-la).
- **Não fecha** ao navegar entre leads: `↑/↓` move a linha ativa e recarrega o conteúdo do Drawer in-place. `Esc` ou clique fora fecha.
- Header fixo: `#rank · display_name`, badge de banda P_score, e ações rápidas (mesmos ícones de canais).
- 3 blocos roláveis dentro do Drawer, deep-linkáveis (a coluna que abriu define o scroll inicial).

### 3.B Conteúdo — três blocos

#### Bloco I — **Onde Focar** (desmembramento matemático do P_score)

Renderiza a **fórmula real** do `m3_score.py:91`, não uma aproximação:

```
P = (w_fit·Fit + w_intent·Intent) · (Confidence ^ confidence_exponent) · persona_fit
```

```
┌─ BLOCO I · ONDE FOCAR ──────────────────────────────────┐
│ P_score final ............................... 0.82  🟢   │
│                                                          │
│ ┌ Drivers positivos (soma ponderada) ──────────────┐    │
│ │  Fit            0.78 × w_fit 0.6      = +0.468    │    │
│ │   ├ tech_match     0.50 × w_fit_tech              │    │
│ │   └ industry_match 1.00 × w_fit_industry          │    │
│ │  Intent         0.61 × w_intent 0.4   = +0.244    │    │
│ │   └ H_01(0.30)+H_04(0.17)+...  (capped 1.0)       │    │
│ └──────────────────────────────────────────────────┘    │
│ ┌ Multiplicadores (colapso de incerteza) ──────────┐    │
│ │  × Confidence^exp   0.71^1.0          × 0.71      │    │
│ │  × persona_fit (fundadora)            × 1.00      │    │
│ └──────────────────────────────────────────────────┘    │
│ ┌ Fricção / penalizações ──────────────────────────┐    │
│ │  (nenhuma — hard_filter_passed = true)            │    │
│ └──────────────────────────────────────────────────┘    │
│ ⚠ Degradação de dados: NÃO (degraded_mode=false)         │
│                                                          │
│ Fontes (evidências):                                     │
│  • https://… (source_trust 0.7)  ↗                       │
│  • https://… (source_trust 0.5)  ↗                       │
└──────────────────────────────────────────────────────────┘
```

- Cada termo é **clicável** e linka às `sources` (URLs de `ObservedEvidence`) que o sustentam — **colapso de incerteza** visível (P2).
- Drivers vêm de `XAIPayload.positive_signals` / `negative_signals` (`Driver{driver, impact, text}`); a árvore numérica vem dos campos de `ProspectScore` + pesos do `runtime.toml`.
- Se `degraded_mode=true`: banner âmbar no topo + os multiplicadores afetados ganham sufixo "(confiança reduzida)".
- Rejeitados: a caixa de Fricção lista o `DISQUALIFIER`/`EXCLUDED_TECH` que zerou (`p_score = 0.0`).

#### Bloco II — **Com Quem Falar** (comitê de compra)

```
┌─ BLOCO II · COM QUEM FALAR ─────────────────────────────┐
│ Completude do comitê:  ▰▰▰▱▱  3/5  🟡                    │
│                                                          │
│ ┌ Decisor Primário (BMO) ──────────────┐                │
│ │ Talita Reis · CEO · C-Level           │ conf 0.80     │
│ │ [in] [ig]                              ↗               │
│ └───────────────────────────────────────┘                │
│ ┌ Structural Champion (SC) ─────────────┐                │
│ │ — não mapeado —          (Missing Evidence)            │
│ └───────────────────────────────────────┘                │
│ Demais pessoas detectadas:                               │
│  • Fulano · Head de Ops · Senior (conf 0.6)              │
└──────────────────────────────────────────────────────────┘
```

- **BMO** e **Structural Champion (SC)** classificados por regra determinística sobre `Inference.people` + `persona_matrix` (ver §2.4). SC = segundo papel-alvo / influenciador estrutural; se ausente, mostra **Missing Evidence** explícito (Open-World).
- **Barra de semáforo de completude:** fração de papéis-alvo do `persona_matrix.target_roles` efetivamente preenchidos. 🟢 ≥80% · 🟡 40–79% · 🔴 <40%.
- Cada pessoa: nome, `role_title`, `seniority`, dot de confiança, e links sociais quando houver.

#### Bloco III — **Conversation Blueprint**

```
┌─ BLOCO III · CONVERSATION BLUEPRINT ────────────────────┐
│ HOOK (copiar):                                  [⧉ Copiar]│
│ ❝ Vi que vocês abriram vaga de liderança e estão         │
│   estruturando time — como está a transição da operação  │
│   pra você sair do dia a dia? ❞                          │
│                                                          │
│ Script completo (IA):                          [⧉ Copiar]│
│ ┌──────────────────────────────────────────────────┐    │
│ │ <textarea editável com o roteiro gerado>          │    │
│ └──────────────────────────────────────────────────┘    │
│                                                          │
│ ⛔ CONTRAINDICAÇÕES — o que NÃO falar (não-colapsável):  │
│  • Não afirmar adoção de IA — não confirmado (Missing)   │
│  • Não citar tamanho de time — indústria não identificada│
│  • Não pressupor dor financeira — sem sinal de retração  │
└──────────────────────────────────────────────────────────┘
```

- **Hook** copiável com 1 clique (`navigator.clipboard`, toast de confirmação).
- **Script:** textarea editável. **MVP:** template determinístico montado de `why_now` + hipótese dominante (custo zero, byte-determinístico). **V2:** geração Gemini sob demanda (1 chamada, cacheada).
- **Contraindicações:** lista **vermelha não-colapsável** derivada de `XAIPayload.missing_signals` (Open-World: o que falta vira "não afirme isto"). É o guardrail anti-alucinação do SDR.

---

## 4. Operações em lote & gestão de estados (Bulk Actions)

### 4.1 Seleção múltipla

- Checkbox por linha + checkbox-mestre no header com **3 estados**: vazio / `indeterminate` (algumas) / marcado (todas as **visíveis pós-filtro**).
- `Shift+click` seleciona intervalo. Contador "N selecionados" no header.
- Seleção **persiste através de filtros/ordenação** (guardada por `company_id`, não por índice de linha).

### 4.2 Barra flutuante de ações em lote

Aparece ancorada ao rodapé quando `selected.size > 0`:

```
┌─────────────────────────────────────────────────────────────────────┐
│  24 selecionados   [⬇ Exportar CSV/Excel] [💾 Salvar lista] [🙈 Ocultar] [✕]│
└─────────────────────────────────────────────────────────────────────┘
```

| Ação | Especificação |
|---|---|
| **Exportar CSV/Excel** | gera CSV **formatado para CRM** (HubSpot/Salesforce): colunas `Company, Domain, Contact Name, Role, Seniority, LinkedIn, Instagram, Website, Email, Phone, P_score, Fit, Intent, Confidence, Dominant_Hypothesis, Intent_Signals, Why_Now, Gaps, Source_URLs`. UTF-8 BOM (Excel-safe), `;`/`,` configurável. Client-side `Blob` — sem back-end. |
| **Salvar Lista Local** | persiste a seleção como named list em `localStorage` (PoC) — nome + timestamp + `company_id[]`. Recarregável no próximo run. |
| **Ocultar Selecionados** | remove da view atual (não deleta); botão "Mostrar ocultos (N)" para reverter. |

### 4.3 Filtros avançados & Faceted Search

Barra acima do grid, filtragem **instantânea client-side** (sem round-trip):

- **Range P_score:** slider duplo (min–max) ligado às bandas (Priority/Monitor/Low).
- **Indústrias:** multiselect facetado (contagem por faceta: `Consultoria (42)`).
- **Hipóteses de dor:** multiselect de `H_01…H_05` (contagem por faceta).
- **Intent signals:** multiselect dos `surface_signals` presentes.
- **Toggles:** `Só aprovados` (oculta REJEITADO) · `Só com decisor mapeado` · `Só com Instagram`.
- **Busca textual:** input que filtra por nome/empresa/setor (debounce 150ms).
- **Chip-bar de filtros ativos** com `✕` individual e "Limpar tudo". Contador "Mostrando 134 de 500".

---

## 5. Arquitetura Frontend & performance não-funcional

### 5.1 Stack & decisão arquitetural

| Camada | Escolha | Justificativa |
|---|---|---|
| Framework | **React 18 + Vite** (build → assets estáticos) | servido pelo FastAPI atual em `/` (`app.py:79`); **nenhuma infra nova** — continua "1 processo Python, static files" (ADR-000). |
| Estilo | **Tailwind CSS** (build-time, substitui o CDN atual) | densidade via utilitários; purge reduz bundle. |
| Tabela | **TanStack Table v8** (headless) | multi-sort, faceted filters, column sizing — lógica sem opinar no render. |
| Virtualização | **@tanstack/react-virtual** (ou `react-window`) | janela de ~30 linhas no DOM para 10k em memória; 60 FPS em sort/filter. |
| Estado | **Zustand** (store leve) ou Context | seleção, filtros, lead ativo do Drawer. Sem Redux (overengineering). |
| Export | `Blob` + `URL.createObjectURL` (CSV); SheetJS opcional p/ `.xlsx` em V3 | client-side. |

> **Tradeoff registrado (risco R-7):** o MVP introduz um passo de build (Vite). Mitigação: build commitado em `web/static/` e servido como hoje; dev usa `vite dev` com proxy para `/api`. Alternativa "vanilla puro" foi rejeitada porque 60 FPS @ 10k linhas com multi-sort exige virtualização madura.

### 5.2 Component Tree & Hierarchy

```
<CockpitApp>
├── <ParamsPanel>            // zona Parâmetros (reusa /api/config, /api/config/icp, /api/assist/icp)
│   ├── <IcpEditor>
│   ├── <ScoringWeightsForm> // edita runtime.toml [scoring] via /api/config/scoring
│   └── <HypothesesEditor>
├── <RunBar>                 // zona Execução: dispara /api/run, mostra progresso/contagem/degraded
├── <ResultsView>           // zona Resultados
│   ├── <FilterBar>          // facetas, range slider, chips, busca textual
│   ├── <DataGrid>           // TanStack Table + virtual
│   │   ├── <GridHeader>     // checkbox-mestre (indeterminate), sort handlers
│   │   ├── <VirtualBody>
│   │   │   └── <LeadRow>            // memoizada
│   │   │       ├── <ProfileCell>
│   │   │       ├── <IntelCell>      // <ScoreBar>, micro-indicadores
│   │   │       ├── <HypothesisCell> // <HypothesisChip>, <SignalChip[]>
│   │   │       ├── <DecisionMakerCell>
│   │   │       ├── <ChannelsCell>   // <ChannelLink[] target=_blank>
│   │   │       └── <ApproachCell>   // botão → abre Drawer
│   │   └── <CellRenderer>          // dispatch genérico por columnDef.meta.kind
│   └── <BulkActionBar>      // flutuante; CSV/Excel, salvar, ocultar
└── <SideDrawer>            // portal; navegável ↑/↓
    ├── <DrawerHeader>
    ├── <BlockI_ScoreBreakdown>     // árvore matemática + fontes
    ├── <BlockII_BuyingCommittee>   // BMO, SC, semáforo
    └── <BlockIII_ConversationBlueprint> // hook copiável, script, contraindicações
```

### 5.3 Virtualization Strategy (NFR de performance)

| NFR | Alvo | Como |
|---|---|---|
| Capacidade | 10.000 linhas em memória | dados já em RAM (run local); sem paginação de servidor. |
| Render | 60 FPS em sort/filter/scroll | virtual window (~30 linhas no DOM), overscan 8; `LeadRow` `React.memo` com igualdade por `company_id` + flags. |
| Sort | multi-sort estável | TanStack `sortingFns` custom; **tie-break por `company_id`** para honrar o **determinismo do ranking** (regra inviolável §3). |
| Filter | instantâneo (<16ms) | índices facetados pré-computados (Map por indústria/hipótese/signal) no `onRunSuccess`. |
| Drawer | abre <100ms | conteúdo derivado do DTO já carregado; zero fetch adicional no MVP. |
| Memória | estável em 1000 leads | sem clonar arrays em cada filtro; seleção em `Set<company_id>`. |
| A11y | navegável por teclado | roving tabindex nas linhas; `role="grid"`, `aria-rowcount`. |

### 5.4 Modelo de dados (TypeScript) — paridade com Pydantic

> Espelha 1:1 `contracts.py`. Camadas semânticas isoladas: `ScoreDTO` (Camada 3), `HypothesisHitDTO`/sinais (cruzamento Inference×Catalog), `XAIPayloadDTO` (M5). Campos novos do enriquecimento marcados `// [enriquecido]`.

```ts
// ── Camada 3: score (espelha ProspectScore, contracts.py:180) ──────────────
export interface ScoreDTO {
  company_id: string;
  fit: number;            // [0,1]
  intent: number;         // [0,1] — 0 = Open-World (sem timing)
  confidence: number;     // [0,1] — confiabilidade da extração
  persona_fit: number;    // [0,1] — multiplicador de persona (default 1.0)
  p_score: number;        // >= 0 (NÃO normalizado a 1.0)
  hard_filter_passed: boolean; // false => REJEITADO
}

// ── XAI (espelha XAIPayload + Driver, contracts.py:192/200) ────────────────
export type DriverImpact = string; // ex: "+0.47", "-", "x0", "x1.00"
export interface DriverDTO {
  driver: string;        // TECH_MATCH | INTENT_TIMING | DISQUALIFIER | EXCLUDED_TECH | LOW_CONFIDENCE | PERSONA
  impact: DriverImpact;
  text: string;
}
export interface XAIPayloadDTO {
  company_id: string;
  final_p_score: number;
  positive_signals: DriverDTO[];
  negative_signals: DriverDTO[];
  missing_signals: string[];   // alimenta Contraindicações (Bloco III)
  degraded_mode: boolean;
}

// ── Pessoas / comitê (espelha PersonEntity, contracts.py:152) ──────────────
export type CommitteeRole = "BMO" | "STRUCTURAL_CHAMPION" | "OTHER"; // [enriquecido]
export interface PersonDTO {
  person_id: string;
  normalized_name: string;
  role_title: string | null;
  seniority: string | null;
  confidence: number;          // [0,1]
  committee_role: CommitteeRole; // [enriquecido] classificação determinística
  links?: { linkedin?: string | null; instagram?: string | null };
}

// ── Hipóteses & sinais (cruzamento Inference.intent_signals × catalog) ─────
export interface HypothesisHitDTO {     // [enriquecido]
  hypothesis_id: string;   // H_01..H_05
  label: string;           // rótulo curto derivado de description
  prior: number;           // contribuição ao Intent
  is_dominant: boolean;    // maior prior entre as que dispararam
}
export interface IntentSignalDTO {       // [enriquecido]
  signal: string;          // ex: "vaga_lideranca"
  hypothesis_id: string;   // hipótese-mãe
  source_url?: string;     // evidência que o sustentou
}

// ── Links / contato (espelha LeadLinks/LeadContact) ────────────────────────
export interface LeadLinksDTO { instagram: string | null; linkedin: string | null; website: string | null; }
export interface LeadContactDTO { email: string | null; phone: string | null; }

// ── Linha do grid (superset de LeadCard, contracts.py:237) ─────────────────
export interface LeadRowDTO {
  rank: number;
  company_id: string;          // chave estável p/ seleção, dedup, tie-break
  display_name: string;
  company: string | null;
  sector: string | null;
  location: string | null;
  firmographics?: { business_models?: string[]; employee_range?: string }; // [enriquecido]
  links: LeadLinksDTO;
  contact: LeadContactDTO;
  score: ScoreDTO;
  explanation: XAIPayloadDTO;  // [enriquecido] XAI íntegro (hoje vira why_now/gaps)
  hypotheses: HypothesisHitDTO[];   // [enriquecido]
  intent_signals: IntentSignalDTO[];// [enriquecido]
  committee: PersonDTO[];      // [enriquecido] people[] completo + papéis
  bmo: PersonDTO | null;       // [enriquecido] atalho p/ coluna Decisor
  why_now: string[];           // reuso direto do LeadCard
  gaps: string[];              // reuso direto (== missing_signals)
  sources: string[];           // URLs de ObservedEvidence
}

// ── Envelope do run (espelha resposta de /api/run, app.py:131) ─────────────
export interface RunResultDTO {
  run_id: string;
  status: "done" | "running" | "error";
  count: number;
  degraded_mode: boolean;      // [enriquecido] is_degraded() do orchestrator
  thresholds: ScoreThresholds; // [enriquecido] de runtime.toml
  leads: LeadRowDTO[];
}
export interface ScoreThresholds { priority: number; monitor: number; }
```

> **Contrato de compatibilidade:** todo campo `// [enriquecido]` é **opcional/aditivo** no `LeadCard` Pydantic (`Field(default=...)`), preservando os smokes E2E existentes (`render_report`, `persist_json`). O front degrada graciosamente se um campo enriquecido vier ausente (renderiza Missing Evidence).

### 5.5 Mudanças mínimas de back-end (presentation only)

1. `contracts.py`: adicionar campos opcionais a `LeadCard` (`explanation`, `committee`, `bmo`, `hypotheses`, `intent_signals`) — **sem default mutável compartilhado** (`Field(default_factory=...)`), preservando isolamento de camadas.
2. `orchestrator._to_lead_card`: parar de descartar `XAIPayload`, `inference.people` e `inference.intent_signals`; classificar BMO/SC e hipótese dominante (lógica determinística pura, reusa `_intent_from_hypotheses`).
3. `app.py /api/run`: incluir `degraded_mode` e `thresholds` no envelope JSON.
4. **Zero** mudança em M1, M2, M3 (score), M4 (ranking). Gates (`pytest-bdd`, `ruff`, `mypy --strict`) permanecem verdes.

---

## 6. Wireframes (visão completa)

### 6.1 Operator Cockpit — tela cheia

```
┌───────────────────────────────────────────────────────────────────────────────────────┐
│ SocialSelling · Operator Cockpit          [Parâmetros] [Execução] [Resultados]   ⚙ talita │
├───────────────────────────────────────────────────────────────────────────────────────┤
│ ▸ PARÂMETROS (colapsável)   ICP: icp_criteria.talita.json ▾   Pesos: w_fit .6 w_int .4 …  │
│ ▸ EXECUÇÃO   [▶ Executar pipeline]   run-7 · 500 leads · 🟠 degradado · 3.2s              │
├───────────────────────────────────────────────────────────────────────────────────────┤
│ FILTROS  P_score [▱▱▰▰▰] 0.40–1.0  Indústria(2)▾  Hipótese(1)▾  ☑só aprovados  🔍 buscar… │
│ Mostrando 134 de 500   ✕ Consultoria  ✕ H_01                              [Limpar tudo]   │
├──┬──────────────────┬───────────────────┬────────────────────┬────────────┬──────┬───────┤
│☑▾│ PERFIL & SETOR ▲ │ P / FIT / INT ▼   │ HIPÓTESES & SINAIS │ DECISOR    │CANAIS│ABORD. │
├──┼──────────────────┼───────────────────┼────────────────────┼────────────┼──────┼───────┤
│☑ │▎Acme Consultoria │⬤0.82 ▰▰▰▰▰▰▰▱▱▱  │H_01 Cresc.Travado  │Talita Reis │in ig │[💬]   │
│  │ Consult.·SP #B2B │Fit.78 Int.61 C71% │✓vaga_lider ✓ia +1  │CEO·C-Level │🌐    │       │
│☑ │▎Beta Adv.        │⬤0.74 ▰▰▰▰▰▰▱▱▱▱  │H_04 Intenção IA    │M. Souza    │in 🌐 │[💬]   │
│  │ Advocacia·RJ     │Fit.70 Int.55 C68% │✓intencao_ia        │Sócia·Owner │      │       │
│  │░Gama Co.(40% op.)│⬤0.00 ▱▱▱▱▱▱▱▱▱▱ │— sem timing        │não mapeado │—     │[audit]│
│  │░REJEITADO        │Fit.20 — C40%      │                    │            │      │       │
│  │ … (virtual: 30 linhas no DOM de 500) …                                                │
├──┴──────────────────┴───────────────────┴────────────────────┴────────────┴──────┴───────┤
│            ┌─ 24 selecionados [⬇CSV/Excel] [💾Salvar] [🙈Ocultar] [✕] ─┐                  │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Drawer aberto (sobre a linha ativa)

```
┌──────────────────── grid (esmaecido) ──────────┬──── SIDE DRAWER (480px) ───────────────┐
│ ☑ ▎Acme Consultoria … (linha ativa: ring índigo)│ #1 · Talita Reis    🟢 0.82   in ig 🌐 ✕│
│ ☑ ▎Beta Adv. …                                  ├────────────────────────────────────────┤
│   ░Gama Co. …                                    │ ┌ I · ONDE FOCAR ───────────────────┐  │
│                                                  │ │ P 0.82 = (Fit.78·.6 + Int.61·.4)  │  │
│                                                  │ │        · Conf.71^1 · persona 1.0  │  │
│                                                  │ │ Fontes: ↗ ↗ ↗                      │  │
│                                                  │ ├ II · COM QUEM FALAR ──────────────┤  │
│                                                  │ │ Comitê ▰▰▰▱▱ 3/5  BMO: Talita/CEO │  │
│                                                  │ │ SC: — não mapeado (Missing)        │  │
│                                                  │ ├ III · BLUEPRINT ──────────────────┤  │
│                                                  │ │ Hook ❝…❞ [⧉]  Script[⧉]            │  │
│                                                  │ │ ⛔ NÃO falar: IA não confirmada…   │  │
│                                                  │ └───────────────────────────────────┘  │
└──────────────────────────────────────────────────┴────────────────────────────────────────┘
   ↑/↓ navega leads sem fechar · Esc fecha
```

---

## 7. Matriz de riscos de UX

| ID | Risco | Prob. | Impacto | Mitigação |
|----|-------|-------|---------|-----------|
| R-1 | **Sobrecarga cognitiva** — densidade alta intimida SDR novato | M | A | Modo compacto/confortável toggle; onboarding tooltip 1ª vez; defaults de coluna sãos. |
| R-2 | **Métrica opaca** — usuário não confia no P_score | A | A | P2: toda métrica abre árvore matemática + fontes; nunca número solto. |
| R-3 | **Falsa negatividade do Open-World** — `Intent=0` lido como "ruim" | M | M | Render cinza "—" + tooltip "ausência de sinal ≠ desqualificação"; nunca vermelho. |
| R-4 | **Rejeitado invisível** — operador não entende por que sumiu | M | M | REJEITADO fica na grade (opacidade 40%) com motivo no hover, não é deletado. |
| R-5 | **Export quebrado em Excel** (acentos/UTF) | M | A | CSV com BOM UTF-8 + separador configurável; teste com HubSpot/Salesforce import templates. |
| R-6 | **Perda de seleção** ao filtrar/ordenar | A | M | Seleção por `Set<company_id>`, não por índice; persiste entre views. |
| R-7 | **Passo de build (Vite)** atrita com PoC single-process | M | M | Build commitado em static/; servido pelo FastAPI atual; sem infra runtime nova. |
| R-8 | **Jank de scroll** >1000 linhas | B | A | Virtualização + `React.memo` + índices facetados pré-computados; budget 60 FPS testado. |
| R-9 | **Contraindicação alucinada** no Blueprint (V2 Gemini) | M | A | MVP determinístico; V2 ancora contraindicações em `missing_signals` (Open-World), não em geração livre. |
| R-10 | **Drift de contrato** FE↔Pydantic | M | A | DTOs gerados/validados contra `contracts.py`; campos enriquecidos opcionais; smoke E2E cobre serialização. |
| R-11 | **Determinismo do ranking violado** por sort instável da UI | B | A | Tie-break por `company_id` em todo `sortingFn`; espelha regra inviolável §3. |

---

## 8. Roadmap fatiado em etapas de engenharia

### Fase MVP — "Funcional" (substituir cards por grid utilizável)
**Meta:** SDR analisa 500 leads e exporta os 20 melhores em <10 min.
- WU-1: scaffolding React+Vite+Tailwind servido pelo FastAPI atual; paridade visual da zona Parâmetros/Execução.
- WU-2: enriquecimento de DTO no `orchestrator._to_lead_card` + campos opcionais em `LeadCard` (gates verdes).
- WU-3: `<DataGrid>` virtualizado (TanStack Table + virtual) com as 6 colunas obrigatórias e estados (REJEITADO, degradado).
- WU-4: ordenação multi-sort determinística + filtros facetados básicos (range P_score, indústria, hipótese) + busca textual.
- WU-5: seleção múltipla (checkbox-mestre indeterminate) + **Exportar CSV** (CRM-ready) + Ocultar.
- WU-6: Side Drawer Bloco I (árvore P_score + fontes) e Bloco II (comitê BMO/SC + semáforo).
- **Gate de saída:** smoke E2E com 500 leads sintéticos; 60 FPS em sort; CSV importa limpo no HubSpot; teste de tempo SDR <10 min.

### Fase V2 — "Interativa" (profundidade & velocidade)
- Bloco III completo: **Conversation Blueprint** com Hook copiável + script (geração Gemini sob demanda, cacheada) + contraindicações ancoradas em `missing_signals`.
- Salvar Lista Local (localStorage) + export `.xlsx` (SheetJS).
- Navegação `↑/↓` no Drawer; deep-link da coluna→bloco; modo compacto.
- Facetas avançadas (intent_signals multiselect; toggles "só com decisor").
- Atalhos de teclado (j/k navega, x seleciona, e exporta, / busca).

### Fase V3 — "SaaS Analytics" (escala & colaboração — fora do PoC atual)
- Persistência de listas server-side (exigiria infra → **fora da ADR-000**; só se o produto graduar de PoC).
- Comparação lado-a-lado de 2–4 leads; histórico de runs e diffs de P_score.
- Colunas customizáveis/salváveis por usuário; saved views.
- Integração de export direto a CRM via API; webhooks.
- Telemetria de uso (tempo até 20 alvos, taxa de uso do Drawer) para otimizar densidade.

---

## 9. Critérios de aceite (rastreáveis ao objetivo máximo)

| # | Critério | Verificação |
|---|----------|-------------|
| A1 | Grid renderiza 500 leads sem jank perceptível (≥55 FPS no scroll) | profiling em lote sintético |
| A2 | Ordenar por P_score desc + filtrar Priority + indústria leva o operador aos top-20 em <60s de interação | teste cronometrado |
| A3 | Toda métrica numérica abre justificativa (árvore + fontes) — zero número opaco | checklist de cobertura P2 |
| A4 | REJEITADO visível, explicado e não-deletado | inspeção visual + hover |
| A5 | Export CSV importa em HubSpot/Salesforce sem erro de encoding/coluna | import real de teste |
| A6 | Determinismo: mesmo run → mesma ordem byte-idêntica (tie-break `company_id`) | reexecução + diff |
| A7 | Gates de back-end (`ruff`, `mypy --strict`, `pytest-bdd`) permanecem 100% verdes | CI |
| A8 | Open-World respeitado: `Intent=0` nunca pintado como negativo | inspeção de estados |

---

### Apêndice A — Mapa de rastreabilidade UI → código
| Elemento UI | Origem no repositório |
|---|---|
| P_score / Fit / Intent / Confidence / persona_fit | `ProspectScore` — `contracts.py:180`; fórmula `m3_score.py:91` |
| Bandas Priority/Monitor/Low | `runtime.toml [scoring]` (thresholds a adicionar) |
| Hipótese dominante / intent chips | `hypotheses_catalog.json` × `Inference.intent_signals`; lógica `_intent_from_hypotheses` `m3_score.py:52` |
| Drivers +/− e Missing (Bloco I/III) | `XAIPayload` / `Driver` — `m5_xai.py`, `contracts.py:200` |
| Decisor / comitê | `PersonEntity` / `Inference.people` — `contracts.py:152` |
| Canais (in/ig/site) | `LeadLinks` — `contracts.py:222` |
| Fontes web | `ObservedEvidence.source_url` via `LeadCard.sources` — `orchestrator.py:115` |
| Modo degradado | `is_degraded()` — `m1_busca.py` / `XAIPayload.degraded_mode` |
| Endpoints (config/run/assist) | `app.py` (`/api/config`, `/api/run`, `/api/assist/icp`) |
```
