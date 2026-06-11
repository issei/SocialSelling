# ADR-010 — Piloto "motor local + portal da operadora": validar o produto antes da infra AWS

| Campo | Valor |
|---|---|
| Status | **Aprovado** |
| Data | 2026-06-09 |
| Decisores | Dono do produto + Staff Engineer/Arquiteto |
| Emenda a | **ADR-008** (execução do roadmap AWS **suspensa**; a visão permanece válida) e **ADR-002** (a UI local deixa de ser o canal da operadora — segue como utilitário de operador/dev) |
| Complementa | ADR-006 (corpus acumulativo), ADR-007 (aprendizado por feedback) |
| Especificações derivadas | `docs/specs/portal-operadora-piloto-sdd.md` (SDD do portal) · `docs/planning/adr-010-backlog-plan.md` (plano de cards) |

## Contexto

A ADR-008 promoveu a visão AWS serverless multi-tenant a alvo de build e gerou um roadmap de
**31 cards** refinados (IaC bimodal, borda JWT, adapters DynamoDB), mais os **7 gates** de
segurança/FinOps da ADR-009. Antes do primeiro deploy real, três constatações motivam um pivô:

1. **O produto ainda não foi validado.** A pergunta que o sistema existe para responder —
   *"quem devo abordar primeiro?"* — nunca foi testada com uma operadora real usando o ranking
   no dia a dia. O roadmap AWS constrói infraestrutura multi-tenant **antes** de saber se o
   ranking gera resposta, reunião e cliente. O risco dominante hoje é **de produto**, não de
   escala — e a ordem do plano atacava o risco errado primeiro.
2. **Complexidade e risco para o desenvolvimento autônomo.** Os 31 cards são majoritariamente
   infra (IaC, IAM, gates fail-closed) — o tipo de mudança em que um erro do run autônomo custa
   caro (segurança, custo AWS) e a revisão humana é mais onerosa. Reduzir essa superfície é
   condição para manter o processo agêntico sustentável (a política de processo é objeto da
   ADR-011).
3. **No fim dos 31 cards, nenhum usuário usa nada.** O plano não continha frontend: o
   "Operator Cockpit" foi definido como repositório externo que não existe. Completar o roadmap
   inteiro ainda deixaria a operadora sem tela.

O pivô: colocar o ranking nas mãos de operadoras reais o quanto antes, com a menor infra
possível — e só então decidir se/quando a pegada AWS volta.

## Decisão

### 1. Suspensão da execução da ADR-008 (sem revogação)

- Os cards de execução do roadmap AWS (WU-P\*, WU-B\*, WU-I\*, WU-D1) e os gates da ADR-009
  (WU-S\*, WU-F\*) saem de **Todo → Backlog**, com DoR preservado.
- A **ADR-008 permanece aprovada como visão futura** (status anotado: *"Aprovado — execução
  suspensa pela ADR-010"*). Nada nela é revogado.
- A **ADR-009 fica dormente** — reativa se a pegada AWS voltar.
- Cognito (WU-X1) e OIDC de deploy ficam **provisionados na prateleira** (ver §"O que fica na
  prateleira").

### 2. Novo alvo: motor local inalterado + portal da operadora (monorepo)

```
Motor local (CLI, 1 processo)                      Portal da operadora (Render)
M1→M5, corpus, waves, learning ── POST /api/publish ──▶ snapshots (Neon)
data/feedback_events/*.jsonl   ◀── GET /api/feedback ── feedback_events (Neon)
```

- **Motor 100% local, INALTERADO:** M1–M5, corpus acumulativo (ADR-006), ondas, aprendizado
  (ADR-007). Nenhum modo `aws`, nenhuma dependência nova no core.
- **Portal:** FastAPI + Jinja2 + JS vanilla, no **monorepo** em `src/socialselling/portal/`
  (módulo novo). A UI local existente (`socialselling/web`, ADR-002) **não muda** — passa a ser
  utilitário de operador/dev.
- **Mesmo quality gate:** `ruff` + `mypy --strict` + `pytest` **100% offline e determinístico**
  (tolerância `1e-9`).
- **Modelos Pydantic compartilhados** entre motor e portal — contrato de publicação sem deriva.

### 3. Hosting: Render free + Neon Postgres free (pegada AWS zero)

| Item | Decisão |
|---|---|
| Web Service | Render free, região Virginia (US East). **Dorme após idle** — cold start aceito para o piloto. |
| Banco | Neon Postgres free, projeto `socialselling`, região AWS us-east-1 (**já criado** pelo dono em 2026-06-09). |
| Domínio | `selling.issei.com.br` via CNAME (ação do dono). |
| Segredos no Render | `DATABASE_URL`, `PUBLISH_TOKEN`, `SECRET_KEY`. |
| Segredos no motor (`.env`) | `PORTAL_BASE_URL`, `PORTAL_PUBLISH_TOKEN`. |
| AWS | Pegada **zero** no piloto. |

`DATABASE_URL` existe **só no Render** — o motor local **nunca acessa o banco**, só HTTP.

### 4. Fluxos de integração (o motor é o único cliente de máquina da API)

- **Publicação (push):** `POST /api/publish` com `Authorization: Bearer PUBLISH_TOKEN`;
  payload = snapshot do ranking por perfil; **idempotente por `(profile_id, run_id)`** —
  republicar o mesmo run não duplica nem altera.
- **Feedback (pull):** `GET /api/feedback?since=<cursor>` (mesmo token); o motor persiste os
  eventos em **JSONL append-only** em `data/feedback_events/` — backup local do dado precioso
  (a retenção curta do Neon free deixa de ser risco de perda).

### 5. Piloto e operadoras

- Começa **só com a Talita**; o desenho suporta **N operadoras**, cada uma com **ICP próprio**
  (ICP Profiles do WU-C, já entregue — `profile_id`).
- **Top-20 leads por onda**. **Tavily-only**: Apollo fica fora do piloto — só entraria com
  camada gratuita (registrado em Gaps como "avaliar enriquecimento gratuito").
- **Runs manuais** durante a experimentação — sem agendamento.

### 6. Carteira da operadora e funil de status

A operadora vê uma **carteira**, não uma "lista do dia": leads do snapshot mais recente
∪ leads com status **não-terminal** de snapshots anteriores (marcados "em acompanhamento").
Status terminal tira o lead da carteira. Lead novo entra com status `novo`.

O funil vive em `config/feedback_catalog.json` (v1) — **ids estáveis em snake_case, labels
mutáveis**, mesmo padrão do `hypotheses_catalog.json`:

```
novo → interagindo → abordado → respondeu | nao_respondeu → reuniao_marcada → cliente
laterais TERMINAIS (a qualquer momento): contato_invalido · fora_do_perfil
```

Cada status declara `terminal` (bool) e `rotulo_aprendizado` ∈ {`neutro`, `positivo`,
`positivo_forte`, `negativo_fraco`, `negativo_fit`, `qualidade_dado`} — o rótulo é insumo da
**calibração offline**, não do treino online. Terminais: `cliente`, `contato_invalido`,
`fora_do_perfil`. O mapeamento status→rótulo é fixado no catálogo (detalhado na SDD).

### 7. Aprendizado — fase 1

- **Like/dislike continua sendo o ÚNICO input** da regressão da ADR-007 (por perfil).
- Os **status de funil são coletados para calibração offline** — o consumidor é o card de
  Backlog "Calibração de pesos [persona]/priors com conversão real".
- **Ligar desfecho→aprendizado automático é ADR futura**, decidida com dados na mão.

### 8. Lead Card sem score + identidade canônica (`entity_id`)

- O Lead Card da operadora mostra **drivers XAI em linguagem natural** e **evidências com
  proveniência** (`DataProvenance` — WU-A/WU-B, já entregues). **Sem score numérico**
  (coerente com a decisão do export CSV).
- O **snapshot publicado nem contém score** — o join score↔desfecho para calibração acontece
  **no motor**, que guarda os scores por `run_id`.
- **Pré-requisito do loop:** regra canônica de identidade do lead — **domínio do site
  normalizado**, com fallback determinístico `nome+cidade` — e **teste BDD de estabilidade
  entre runs e provedores**. O feedback faz join por `entity_id`; órfãos corrompem o
  aprendizado silenciosamente.

### 9. Autenticação e LGPD mínima

- **Código de acesso individual por operadora**: hash no banco, seed via SQL editor do Neon
  (runbook). Sessão por **cookie assinado** (`SECRET_KEY`) e logout.
- `X-Robots-Tag: noindex`; **nenhuma página sem login**. **Sem Cognito/OAuth no piloto.**
- LGPD: dados pessoais de leads sempre atrás de login; retenção definida (SDD/runbook).

### 10. Storage do portal: porta DAO + dois adapters

- Porta **DAO (ABC)** + **InMemoryDAO** (testes/contract tests) + **PostgresDAO fino**
  (psycopg3, SQL puro). `CREATE TABLE IF NOT EXISTS` idempotente no startup. **Sem Alembic,
  sem ORM.**
- O gate permanece **100% offline**: os contract tests rodam no InMemoryDAO; o risco residual
  do PostgresDAO (fino por construção) é mitigado por **smoke test pós-deploy** (runbook).

Tabelas mínimas:

| Tabela | Colunas | Regra |
|---|---|---|
| `snapshots` | `profile_id`, `run_id`, `payload JSONB`, `published_at` | PK `(profile_id, run_id)`; publicação idempotente |
| `feedback_events` | `id serial`, `operator_id`, `profile_id`, `entity_id`, `run_id`, `kind` (`status` ou `reaction`), `status_id`/`reaction`, `note`, `created_at` | **append-only — nunca UPDATE** |
| `operators` | `operator_id`, `nome`, `code_hash`, `profile_id` | seed manual via runbook |

### 11. Métricas de sucesso do piloto (ratificadas)

| Métrica | O que valida |
|---|---|
| Cobertura de tabulação (% dos leads publicados com ≥1 evento) | engajamento da operadora / utilidade da carteira |
| Taxa de resposta por faixa de ranking | a tese central — o ranking ordena bem |
| Taxa de `contato_invalido` | qualidade do enriquecimento |

## Invariantes preservadas (não negociáveis)

As quatro invariantes do CLAUDE.md §3 não são tocadas — o motor segue inalterado e o portal as
honra na borda:

| Invariante (§3 do CLAUDE.md) | Motor local | Portal / integração |
|---|---|---|
| **Isolamento de camadas** | Inalterado. | O snapshot é **projeção de apresentação** (sem score); eventos de feedback ficam em store próprio (`feedback_events` + JSONL local) e **nunca viram Observed Evidence** — o join com scores acontece só no motor, offline. |
| **Determinismo byte-idêntico** | Inalterado. | Publicação idempotente por `(profile_id, run_id)`; `entity_id` canônico com teste BDD de estabilidade; contract tests determinísticos no InMemoryDAO; ids de status estáveis no catálogo. |
| **Open-World** | Inalterado. | Lead Card exibe sinais ausentes (Missing Evidence) em linguagem natural; ausência de tabulação = `neutro`, nunca sinal negativo; `nao_respondeu` é estado **explícito** marcado pela operadora, não inferido do silêncio. |
| **Persistência atômica** | `write-temp` + `os.replace` inalterado; eventos puxados em JSONL **append-only**. | Escritas em transação Postgres; `feedback_events` append-only (nunca UPDATE); upsert de snapshot idempotente — sem estado parcial. |

## Escopo (o que esta ADR **não** autoriza)

- **CRM, outreach automático/mensageria, cadências e scraping IG/LinkedIn continuam fora**
  (ADR-000 §1 e §5).
- **Portal sem cadastro self-service:** operadora entra por seed manual (runbook do Neon).
- **O motor não acessa o banco** — toda integração é via API HTTP do portal.
- **Sem Apollo pago** no piloto (só camada gratuita, se existir — ver Gaps).
- **Sem agendamento gerenciado:** runs manuais.
- **Nenhum recurso AWS novo** — a pegada do piloto é zero.

## O que fica na prateleira (não é desperdício)

- **31 cards do roadmap AWS** (WU-P\*/B\*/I\*/D1) + **7 gates** (WU-S\*/F\*): de Todo para
  Backlog **com DoR preservado** — reativáveis sem reespecificação.
- **Cognito WU-X1** (User Pool + app client) e **OIDC de deploy** (role + policy IAM):
  permanecem provisionados — custo zero parados.
- **ADR-009:** dormente; reativa junto com a pegada AWS.
- **SDD-1/2/3 da ADR-008:** seguem como especificação válida da visão futura.

Critério para tirar da prateleira: piloto validado (métricas da Decisão §11) **e** necessidade
real de multi-tenant/escala/agendamento — aí o caminho ADR-008/009 é retomado de onde parou.

## Consequências

**Positivas:**
- O ranking chega às mãos de uma operadora real em semanas — o risco de produto é atacado
  primeiro, com loop de feedback real alimentando a calibração.
- Custo de infra **zero** (Render free + Neon free); superfície de risco do run autônomo
  reduzida (sem IaC/IAM no caminho crítico).
- O dado precioso (eventos de feedback) tem **backup local** em JSONL append-only.
- Desenho já multi-operadora (ICP por perfil): adicionar operadora = seed + perfil, sem refactor.

**Negativas / trade-offs aceitos:**
- Render free **dorme após idle** — o primeiro acesso do dia é lento (aceito para o piloto).
- **Dependência de 2 SaaS free** (Render + Neon), cujos limites/termos podem mudar — mitigada
  pelo DAO fino + backup JSONL (migração barata).
- **Dado pessoal de lead passa a viver num servidor** → obrigações LGPD mínimas (login
  obrigatório, noindex, retenção definida) viram requisito, não opção.
- Sem agendamento: publicar exige operação manual do dono durante a experimentação.

## Gaps abertos

- **Avaliar enriquecimento gratuito** alternativo ao Apollo (roadmap; Apollo pago vetado no
  piloto).
- **Ligar desfecho de funil → aprendizado automático:** ADR futura, com os dados do piloto na
  mão (hoje o funil só alimenta calibração offline).
- **Migração pós-piloto:** se as métricas validarem o produto, decidir entre retomar a
  ADR-008/009 (AWS) ou escalar o desenho atual — decisão com dados de uso reais.
