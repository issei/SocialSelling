# ADR-000 — Escopo Canônico do PoC Local

| Campo | Valor |
|---|---|
| Status | **Proposto** (aguardando ratificação do dono do produto) |
| Data | 2026-06-02 |
| Decisores | Dono do produto + Claude Code |
| Substitui | Resolve o conflito entre SDD v1.0, SDD MVP v1.1 e specs/sdd/01–12 |

## Contexto

O objetivo central do projeto é **tornar a busca de clientes mais eficiente e automática usando IA**, respondendo com precisão à pergunta: *"quem devo abordar primeiro?"*.

A documentação herdada (~22 mil linhas) contém **três visões arquiteturais incompatíveis**:

1. **SDD v1.0** — local, *database-less*, JSON em arquivo, Tavily + Gemini, módulos M1–M5. Enxuta.
2. **SDD MVP v1.1** — PostgreSQL 16 + Redis + Celery/RabbitMQ + FastAPI, scraping Instagram/LinkedIn + CNPJ.ws.
3. **specs/sdd/01–12** — visão alvo enterprise: AWS serverless, Terraform, lógica subjetiva, KL/RRF/MMR.

Construir as três é impossível e construir a 2 ou a 3 num PoC local é **overengineering**. Esta ADR fixa uma única fonte da verdade.

## Decisão

### Fonte da verdade canônica
Adota-se o **SDD v1.0** (`SDD_SocialSelling_v1.0.md`) como espinha arquitetural do PoC. Da v1.1 aproveitam-se **apenas** a forma dos contratos e fórmulas simples. Os documentos v1.1 (partes pesadas) e `specs/sdd/01–12` são reclassificados como **REFERÊNCIA / ROADMAP FUTURO** — não são alvo de implementação.

### Stack do PoC (mínimo viável)
| Aspecto | Decisão PoC | Diferido para |
|---|---|---|
| Runtime | 1 processo Python 3.11+ (CLI) | — |
| Persistência | JSON em arquivo (cold) + memória (hot) | Postgres → V1 |
| Busca | **Tavily API** | scraping IG/LinkedIn → V1 |
| Cognição | **Gemini API** (extração, rationale) | — |
| Scoring | Fórmula **linear transparente** documentada | Lógica subjetiva / Bayesiano recursivo → V1 |
| Diversidade/fusão | — | RRF, MMR, capture-recapture → V1 |
| Infra gerenciada | **NENHUMA** (custo só de tokens de API) | Redis/Celery/AWS → V1/V2 |
| Interface | CLI + relatório JSON/markdown | FastAPI + cockpit UX → V1 |

### Pipeline canônico (módulos determinísticos, NÃO agentes de runtime)
`M1 Busca → M2 Extração → M3 Score → M4 Ranking → M5 Explicação (XAI)`

Os módulos são funções orquestradas de forma determinística. **Não há autonomia agêntica em runtime no PoC.**

### Camadas semânticas isoladas (regra inviolável herdada da v1.0)
`Observed Evidence` ≠ `Generated Inferences` ≠ `Evaluated Hypotheses`. Nunca compartilham referências mutáveis. Uma inferência jamais é tratada como evidência observada.

### Open-World Assumption
Ausência de sinal = incerteza (aumenta `u`), nunca falso. `Missing Evidence` é modelado explicitamente.

## Matriz MVP vs. Diferido

| Capacidade | PoC (MVP) | V1 | V2 |
|---|---|---|---|
| Pipeline M1–M5 end-to-end | ✅ | | |
| Fórmula linear Fit/Intent/Confiança | ✅ | | |
| Persistência JSON atômica (write-temp + replace) | ✅ | | |
| Cache T-24h de chamadas externas | ✅ | | |
| Modos degradados (API 429/5xx) | ✅ | | |
| Catálogo de hipóteses (priors estáticos) | ✅ (3–5 hip.) | 15 hip. | |
| Lógica subjetiva / Bayesiano recursivo | | ✅ | |
| RRF / MMR / capture-recapture | | ✅ | |
| Scraping IG/LinkedIn | | ✅ | |
| PostgreSQL / Redis / FastAPI | | ✅ | |
| Meta-learning ICP / gradient descent | | | ✅ |
| AWS serverless / Terraform | | | ✅ |

## Consequências

**Positivas:** executável local em dias, não semanas; testável de forma determinística; custo ~zero; sem dívida de infra; evolução incremental sem reescrita (JSON → Postgres é migração, não redesign).

**Negativas / trade-offs aceitos:** scoring menos sofisticado que o da v1.1 (aceitável e documentado); sem UI no PoC; sinais limitados aos que Tavily/Gemini expõem.

## Gaps resolvidos por esta ADR
- Conflito das 3 arquiteturas → resolvido (v1.0 canônica).
- Fonte de dados ambígua → resolvido (Tavily+Gemini).
- Fórmula de P_score divergente entre docs → resolvido (linear, definida na fase de contratos).

## Gaps ainda abertos (tratados no roadmap)
- Valores numéricos de priors do catálogo de hipóteses.
- `icp_criteria.json` de exemplo (primeira entrada real).
- Fixtures gravadas de Tavily/Gemini para o BDD.
- Contratos Pydantic concretos por módulo.
