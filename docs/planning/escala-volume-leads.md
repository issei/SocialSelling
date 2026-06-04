# Estratégia de Evolução — Escalar volume de leads rodando local

> **Tipo:** documento-âncora de planejamento (o *porquê* e a *sequência*). Os *como* vivem
> nos ADRs/SDDs referenciados. **Objetivo do dono:** após as próximas melhorias, o sistema
> — mesmo rodando local, database-less — deve buscar **muito mais leads**.
> **Data:** 2026-06-04. **Não revoga** ADR-000; opera dentro dos guardrails (local, sem
> banco/Redis/Celery/Docker/AWS, sem scraping, JSON atômico).

## 1. Diagnóstico — Teoria das Restrições aplicada ao funil

`leads_úteis = descobertos × sobrevivência × acumulado_entre_runs`, limitado por **quota**
(Gemini RPD, créditos Apollo) e por **estado local** (JSON monolítico, resolução de entidade).

| Etapa | Restrição **hoje** (medida no código) | Coberto por | Veredito |
|---|---|---|---|
| **Descoberta (M1)** | Tavily `max_queries=3 × max_results=10` ≈ 30 evidências/run | **ADR-004** (Apollo People Search, 0 crédito) | ✅ resolvido |
| **Cognição (M2/Gemini)** | **1 chamada/lead**; quota **RPD** do tier grátis é o teto real | ADR-003 só **poda desperdício** | ❌ **gargalo nº 1** |
| **Acumulação entre runs** | `run_pipeline` **sobrescreve** `prospects_ranked.json`; corta em `max_leads_per_cycle=50` | — | ❌ **gargalo nº 2** |
| **Estado local** | 1 JSON monolítico reescrito inteiro (O(n)/escrita) | — | ⚠️ trava em milhares |
| **Qualidade no volume** | `company_id = hash(nome.lower())`; vendors vazam (L-020) | — | ⚠️ volume vira ruído |

**Insight central:** os SDDs aprovados resolvem **largura de descoberta** (Apollo) e
**desperdício** (poda), mas **não elevam o teto cognitivo** nem **acumulam volume**. Apollo
joga mais lead na entrada; o sistema atual **descarta o excedente** (corta em 50, sobrescreve)
e **estoura a quota Gemini**. *Largura sem teto = bater no muro mais rápido.*

## 2. Os 4 pilares (a estratégia)

| Pilar | Move qual restrição | Decisão | Documento |
|---|---|---|---|
| **A — Teto cognitivo** | Cognição (nº 1) | extração **em lote** + **determinístico-primeiro** (Apollo dispensa Gemini p/ firmografia) + **orçamento de requisições Gemini/dia** + ondas resumíveis | **ADR-005** |
| **B — Corpus acumulativo** | Acumulação (nº 2) | store de leads **persistente e crescente** com **upsert idempotente**; cada run processa só o **novo**; ranking sobre o corpus inteiro; `max_leads` vira limite de **exibição** | **ADR-006** |
| **C — Estado que escala** | Estado local | JSON monolítico → **NDJSON append-only / shards por entidade** (ainda atômico, ainda database-less) | nota §4 → ADR-007 (futuro) |
| **D — Resolução de entidade** | Qualidade no volume | `company_id` por **domínio canônico** + **exclusão de vendors** (L-020) + dedup cross-provider | nota §4 → ADR-008 (futuro) |

Todos respeitam o ADR-000. Nenhum introduz infra gerenciada.

## 3. Sequência recomendada (e por quê)

```
ADR-004 Apollo (descoberta) ──┐
                              ├── JUNTOS: largura sem teto estoura a quota no 1º run real
ADR-005 Pilar A (teto)      ──┘
        │
        ▼
ADR-006 Pilar B (corpus acumulativo)   ← maior ganho de VOLUME REAL (acumula no tempo)
        │
        ▼
ADR-007 Pilar C (NDJSON/shard)  +  ADR-008 Pilar D (entity resolution)  ← endurecimento
```

**Regra de ouro:** **não soltar o Apollo sozinho.** ADR-004 e ADR-005 entram emparelhados —
descoberta ampla só vira valor se a cognição aguentar o fluxo dentro da quota.

**Sinergia A↔B:** o corpus do Pilar B **é** o cache durável das extrações — uma entidade
extraída uma vez nunca é re-extraída (upsert dedup), o que torna o cache-por-prompt (L-017)
secundário e protege a quota Gemini entre runs. O Pilar A enche o corpus rápido; o Pilar B
garante que o esforço **persiste**.

## 4. Notas dos pilares C e D (ainda não ADR — pré-decisão)

- **C (estado):** o ADR-000 já antevê "JSON → Postgres é migração, não redesign". O passo
  intermediário **sem banco** é NDJSON append-only (corpus cresce por *append* O(1)) +
  índice leve em memória + shards por faixa de `entity_id`. Escrita atômica preservada
  (`atomic_write_text` por shard). Gatilho para virar ADR-007: corpus > ~5k leads ou
  latência de escrita perceptível.
- **D (qualidade):** sem isto, 10× volume = 10× ruído no topo. Mínimo viável: `entity_id`
  derivado do **domínio normalizado** (não do nome), `DISQUALIFIER_VOCAB`-style
  `VENDOR_EXCLUSION` (aws, google, microsoft, …) aplicado **antes** do scoring, e fusão
  cross-provider por domínio. Apollo (ADR-004) **facilita D**: já entrega domínio
  canônico, reduzindo a ambiguidade de nome. Gatilho para ADR-008: primeiro run de volume
  real com Apollo (validar empiricamente o ruído — L-020/L-024).

## 5. Métrica de sucesso (definição de "muito mais")

Alvo verificável do roadmap: a partir do `icp_criteria.talita.json`, um run local deve ser
capaz de **avaliar ≥ 500 entidades distintas** acumuladas em ≤ 5 ondas resumíveis, **dentro
da quota gratuita Gemini/dia**, com ranking determinístico sobre o corpus inteiro e **sem**
vendor no top-20. (Hoje: 50 por run, sobrescrito, com vazamento de vendor.)

## 5b. Status de implementação (2026-06-04)

| Pilar | Estado | Onde |
|---|---|---|
| **A — teto cognitivo** | ✅ batch + orçamento RPD + ondas resumíveis (`run_m2` chunking, `RequestBudget`). Determinístico-primeiro **diferido V1+** (exigiria redesenho do M2; cache-por-prompt + corpus já capturam a maior parte do ganho). | `m2_extracao.py`, `core/request_ledger.py`, `v0.15.1` |
| **B — corpus acumulativo** | ✅ acumular entre runs + upsert idempotente + projeção ranqueada (`CorpusStore`, `corpus/integration.py`). Process-only-new **diferido V1+** (entidade só emerge pós-M2; cache Gemini + corpus já dão o FinOps). | `corpus/`, `v0.14.0`/`v0.15.0` |
| **A↔ Apollo (ADR-004)** | ✅ escada completa: descoberta (degrau 1), org-enrich (degrau 2), reveal (degrau 3), ledger de crédito mensal, cache por volatilidade, degradação Open-World. | `apollo/`, `skills/apollo_client.py`, `v0.13.0`–`v0.15.3` |
| **C — estado escalável** | ⏸️ diferido (gatilho: corpus > ~5k leads). JSON monolítico ainda serve. | nota §4 |
| **D — entity resolution** | ⏸️ diferido (gatilho: 1º run de volume real; calibrar com Apollo). | nota §4 |

Tudo **opt-in** (`[apollo].enabled` / `[corpus].enabled` / `[gemini].rpd_enabled`): desligado, o pipeline é byte-idêntico ao baseline (invariante de paridade, smoke E2E verde). **Para ativar o volume:** ligar as três flags no `runtime.toml` + `record_apollo_fixtures.py` (supervisionado) + calibrar o mapeamento ICP→filtros (heurístico, L-024).

## 6. Riscos transversais

- **Quota Gemini RPD é o teto duro** — mesmo com batch, há limite/dia. Mitiga: ondas
  resumíveis (ADR-005) + corpus que não re-extrai (ADR-006). O volume vira função do *tempo*
  (dias), não de um único run.
- **Determinismo sob batch** — batch deve ter composição determinística (entidades ordenadas,
  janela fixa) e cache por hash do batch; senão fere a regra §3.2. Detalhado no ADR-005.
- **PII em volume** — mais leads = mais contato revelado (Apollo). Mantém-se reveal só no
  top-N e fora de escopo qualquer outreach (ADR-000 §1).
