# ADR-008 — MVP Serverless multi-tenant na AWS: backend desacoplado (BaaS) + IaC bimodal

| Campo | Valor |
|---|---|
| Status | **Aprovado** |
| Data | 2026-06-07 |
| Decisores | Dono do produto + Staff Engineer/Arquiteto |
| Emenda a | **ADR-000** (runtime de 1 processo local) e **ADR-002** (UI de operador local/FastAPI acoplada) |
| Complementa | ADR-003 (orquestração/FinOps), ADR-004 (sensor Apollo), ADR-006 (corpus acumulativo), ADR-007 (aprendizado por feedback) |
| Especificações derivadas | `docs/specs/borda-api-gateway-jwt-sdd.md` (SDD-1), `docs/specs/iac-multi-stack-aws-sdd.md` (SDD-2), `docs/specs/persistencia-adapters-sdd.md` (SDD-3) |

## Contexto

A PoC do ADR-000 atingiu seu objetivo: validou ponta-a-ponta o pipeline `M1 Busca → M2 Extração → M3 Score → M4 Ranking → M5 XAI`, com persistência JSON atômica, cache T-24h, corpus acumulativo (ADR-006) e aprendizado por feedback (ADR-007), tudo em **1 processo Python rodando localmente**. A interface de operador (ADR-002) é um servidor FastAPI **acoplado ao mesmo processo**, servindo assets locais.

Esse desenho tem três limites que agora bloqueiam a evolução para produto:

1. **Single-tenant por construção.** O estado mora em arquivos (`data/corpus/leads_corpus.json`, `data/feedback.json`, ledgers) de uma única máquina. Não há isolamento lógico de dados por usuário — uma premissa inviável para um MVP com múltiplas operadoras.
2. **Sem escala nem agendamento gerenciado.** As "ondas" de busca (`corpus/waves.py`) hoje dependem de alguém rodar a CLI. Não há gatilho automático, nem isolamento de falha por módulo, nem retry gerenciado.
3. **Apresentação acoplada ao backend.** A UI (FastAPI + assets) vive no mesmo repositório e processo do motor cognitivo, o que impede versionar o contrato de API de forma estrita e evoluir o frontend independentemente.

A documentação herdada (`specs/sdd/09–10`) já antecipava uma visão AWS serverless + IaC, classificada como **ROADMAP FUTURO** pela ADR-000. Esta ADR **promove essa visão a alvo de build** para o MVP — mas sob uma restrição inegociável que a torna diferente de uma reescrita: o repositório deve permanecer **bimodal**.

### A restrição que governa toda a decisão: bimodalidade

A capacidade de rodar o motor **100% local, offline e determinístico** não é um legado a ser descartado — é uma **ferramenta de desenvolvimento de primeira classe**. É como o time grava novas fixtures de API, simula cenários, refina hipóteses e valida o quality gate sem depender da nuvem nem de emuladores pesados (LocalStack). Perder isso tornaria cada iteração lenta e cara. Portanto:

> **O repositório passa a ser estritamente bimodal.** A mesma base de código provisiona um MVP serverless multi-tenant na AWS **e** mantém a execução local via CLI (`orchestrator.py`) e scripts, com paridade comportamental garantida. O chaveamento é uma flag de configuração, não um fork de código.

## Decisão

### 1. Reclassificação do repositório: de monólito local para Backend-as-a-Service (BaaS) + IaC

Este repositório passa a ser **exclusivamente backend e infraestrutura como código**. A camada de apresentação local (servidor FastAPI da ADR-002 + assets do cockpit) é **extraída integralmente para um repositório externo independente** ("Operator Cockpit"). A fronteira entre os dois repositórios é um **contrato OpenAPI estrito**, versionado, que este repositório passa a expor e a ser a fonte da verdade.

A ADR-002 é **emendada**: o servidor web local deixa de ser o canal de produção; permanece, no máximo, como utilitário de desenvolvimento opcional sobre o modo local. A experiência de operador em produção é servida pelo cockpit externo consumindo a API.

### 2. Migração para AWS Serverless (modo `aws`)

| Recurso AWS | Papel no SocialSelling | Mapeamento ao desenho atual |
|---|---|---|
| **AWS Step Functions** | Orquestração síncrona/visual do fluxo `M1→M2→M3→M4→M5` (máquina de estados sequencial). | Substitui o `orchestrator.py` como **coordenador em runtime** no modo `aws`. O orquestrador local permanece para o modo `local`. |
| **AWS Lambda** | Computação isolada por módulo: cada um de M1–M5 é envelopado em uma função Lambda (*wrapper* fino). | O *wrapper* importa a função pura do módulo; o **core M1–M5 não muda** (ver invariante 5). |
| **Amazon DynamoDB** | Persistência unificada de estado (corpus, cache, ledgers, feedback) em **Single Table Design**. | Substitui os arquivos JSON no modo `aws`. Detalhe em SDD-2. |
| **Amazon API Gateway** | Exposição de rotas HTTPS do BaaS, validação de JWT e injeção de contexto multi-tenant. | É a nova "borda". Detalhe em SDD-1. |
| **AWS Secrets Manager** | Custódia dos tokens sensíveis (Tavily, Apollo, Gemini). | Substitui `.env` no modo `aws`. No modo `local`, `.env` permanece. |
| **Amazon EventBridge** | Agendamento das **ondas de busca noturnas** (`corpus/waves.py` → `accumulate_and_rank`). | Substitui o disparo manual da CLI por gatilho `cron` gerenciado. |
| **Amazon Cognito** (User Pool externo) | Autenticação multi-tenant (provedor externo). | Delegada — **não** implementamos cadastro/senha (ver §Escopo). |

### 3. Infraestrutura como Código segregada em duas stacks (AWS SAM/CloudFormation)

A IaC é declarativa (AWS SAM sobre CloudFormation) e dividida em **duas stacks lógicas** com ciclos de vida distintos, para que recursos com estado nunca sejam destruídos por um deploy de código:

- **Stateful Stack** — recursos com dados que **sobrevivem a deploys**: a tabela DynamoDB (Single Table) e os segredos do Secrets Manager. Política de `DeletionPolicy: Retain`.
- **Stateless Stack** — recursos **substituíveis a cada deploy**: as Lambdas (M1–M5 + handlers de borda), a máquina de estados Step Functions, o API Gateway e as regras do EventBridge. Importa por *export/import* os ARNs/nomes da Stateful Stack.

Detalhe completo da modelagem em **SDD-2**.

### 4. Modelo de isolamento multi-tenant (autorização na borda)

A autenticação é **delegada a um Amazon Cognito User Pool externo**. O fluxo de isolamento é:

1. O cockpit externo autentica o usuário no Cognito e obtém um **JWT**.
2. Toda requisição ao API Gateway carrega esse JWT no header `Authorization`.
3. O API Gateway, configurado com um **autorizador JWT (Cognito)**, **valida a assinatura** do token antes de qualquer Lambda rodar.
4. O API Gateway injeta a claim `sub` do token no contexto da requisição — `$context.authorizer.claims.sub` — **mapeada como `user_id`**.
5. O backend usa esse `user_id` de forma **obrigatória** como prefixo de partição (`USER#<user_id>`) em toda leitura/escrita no DynamoDB, garantindo isolamento lógico por tenant.

Consequência de design: **nenhum Lambda confia em `user_id` vindo do corpo da requisição** — apenas no que o API Gateway injetou a partir do token validado. Isso fecha a superfície de *tenant spoofing*.

### 5. Padrão Ports & Adapters (Repository Pattern) na camada `core/`

Para viabilizar a bimodalidade sem ramificar o código de negócio, introduz-se **Ports & Adapters** na camada `src/socialselling/core/`:

- **Ports (interfaces abstratas):** `BaseCorpusRepository`, `BaseCacheRepository`, `BaseLedgerRepository`, `BaseFeedbackRepository`. Definem assinaturas imutáveis de leitura, escrita atômica e *upsert* idempotente por `entity_id`. O motor (M1–M5, corpus, learning) só conhece as Ports.
- **Adapters (implementações concretas):**
  - `LocalJSONRepository` — consome a infraestrutura local existente (`core/atomic.py`: `write-temp` + `os.replace`). Ativo quando `persistence_mode = "local"`.
  - `DynamoDBRepository` — usa `boto3` com `PutItem`/`GetItem`/`UpdateItem` e *Conditional Expressions* (concorrência otimista e idempotência). Ativo quando `persistence_mode = "aws"`.

A seleção do adapter é feita por uma fábrica que lê o **único ponto de chaveamento**:

```toml
[runtime]
persistence_mode = "local"   # "local" | "aws"
```

Quando `persistence_mode = "local"`, o comportamento do sistema é **idêntico ao baseline anterior** (invariante de paridade).

Detalhe completo das Ports/Adapters e do plano de testes em **SDD-3**.

## Invariantes preservadas (não negociáveis)

Esta evolução é projetada para **não tocar** nas quatro invariantes semânticas do projeto. Como cada uma é honrada nos dois modos:

| Invariante (§3 do CLAUDE.md) | Modo `local` | Modo `aws` |
|---|---|---|
| **Isolamento de camadas** (Observed Evidence ≠ Inferences ≠ Evaluated Hypotheses; feedback só na apresentação) | Inalterado: contratos Pydantic `extra="forbid"`, sem referência mutável compartilhada. | Preservado: cada Lambda recebe/devolve o **contrato serializado** (não compartilha objeto em memória). O feedback (ADR-007) opera sobre `LeadCard.score`, persistido como item `LEDGER`/`FEEDBACK`, **nunca** sobre itens `LEAD#`/Evidence. |
| **Determinismo byte-idêntico** (`now`/RNG injetados; `entity_id` = SHA-256 estável; tolerância `1e-9`; feedback full-batch, pesos em zero, ordenação por `company_id`) | Inalterado. | Preservado: os Lambdas **injetam `now`** (do payload do Step Functions, não `datetime.now()` interno) e **derivam `entity_id` por SHA-256** (nunca UUID aleatório). A função pura é a mesma binária do modo local. |
| **Open-World** (ausência de sinal = incerteza, nunca falso; degradação por `κ_degraded = 0.80` e expoente de confiança; dislike mantém o lead visível com selo) | Inalterado (`[finops].kappa_degraded = 0.80`). | Preservado: erros de sensor/cota **degradam a confiança** e marcam `OperatingMode` degradado — nunca quebram a máquina de estados nem ocultam o lead. SDD-1 especifica a surfaciação crua do erro. |
| **Persistência atômica** | `write-temp` + `os.replace` via `core/atomic.py`. | *Conditional writes* atômicas do DynamoDB (escrita condicional; sem escrita parcial). |

## Escopo (o que esta ADR **não** autoriza)

Mantêm-se os guardrails do ADR-000 §5 e §1:

- **Não** inventar telas, componentes de UI, fluxos de cadastro ou gerenciamento de senhas — autenticação é **delegada ao Cognito** (provedor externo).
- **Não** implementar CRM, outreach automático/mensageria, cadências, nem scraping de Instagram/LinkedIn.
- **Não** acoplar SDKs da AWS (`boto3`) nem caminhos de arquivo rígidos dentro dos módulos `m1_busca.py`…`m5_xai.py` — eles permanecem **funções puras agnósticas de infraestrutura** (invariante 5; SDD-3).

## Consequências

**Positivas:**
- MVP multi-tenant, escalável e com agendamento gerenciado, sem operar servidores.
- Isolamento de falha por módulo (cada M é um Lambda) e retry/backoff gerenciados (SDD-2).
- Contrato OpenAPI estrito como fronteira limpa com o cockpit externo, permitindo evoluir frontend e backend de forma independente.
- **A produtividade de desenvolvimento é protegida:** o modo `local` continua rápido, offline, gratuito (só tokens) e determinístico — gravar fixtures e rodar o gate não exige nuvem nem LocalStack.
- Custo de infra elástico (serverless paga-por-uso); o único custo fixo de dados é a tabela DynamoDB.

**Negativas / trade-offs aceitos:**
- Complexidade de IaC e de duas stacks (mitigada pela segregação stateful/stateless e por SAM declarativo).
- O modo `aws` introduz `boto3` e limites de cold-start de Lambda (aceitável para um pipeline de busca, não interativo em tempo real).
- Manter **paridade bimodal** exige disciplina de teste: a Port é o contrato; os dois Adapters devem passar a **mesma** suíte de comportamento (SDD-3). Custo recorrente assumido conscientemente.
- Dependência operacional de um Cognito User Pool externo (fora deste repositório).

## Gaps resolvidos por esta ADR
- Single-tenant → resolvido (isolamento lógico por `USER#user_id` no DynamoDB, injetado do JWT).
- Apresentação acoplada → resolvida (extração para repositório externo + OpenAPI).
- Agendamento manual de ondas → resolvido (EventBridge).
- Acoplamento do core à infra de armazenamento → resolvido (Ports & Adapters).

## Gaps ainda abertos (tratados nas SDDs e no roadmap)
- Estratégia de migração de dados do JSON local existente para o DynamoDB (item de roadmap; o modo `local` continua a fonte de iteração).
- Estabilidade de `entity_id`/`company_id` entre runs e provedores (herdado de ADR-006/ADR-007) — resolve junto com a entity resolution canônica.
- Custo e quotas reais por tenant em produção (observabilidade FinOps no DynamoDB `LEDGER#FINOPS`, SDD-2).
