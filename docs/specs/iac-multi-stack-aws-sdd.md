# SDD — Infraestrutura como Código multi-stack na AWS (SAM/CloudFormation)

> **Status:** **PROPOSTA (v1.0 — aguardando aprovação do dono)**.
> Deriva do **ADR-008** (§3 IaC two-stack; §2 AWS Serverless). Spec-first: este documento precede
> o código. A IaC é declarativa (**AWS SAM** sobre CloudFormation). Os testes do core continuam
> **offline e determinísticos** (SDD-3); esta SDD especifica recursos, **não** introduz dependência
> de nuvem nos testes nativos.
>
> **Foco:** especificar a arquitetura declarativa dos recursos AWS, dividida em **Stateful Stack**
> (DynamoDB Single Table + Secrets Manager) e **Stateless Stack** (Lambdas M1–M5, Step Functions,
> API Gateway, EventBridge). Detalha a modelagem Single Table Design com isolamento multi-tenant.

---

## 0. Premissas, invariantes e reaproveitamento

| Invariante (não negociável) | Origem | Como a IaC respeita |
|---|---|---|
| Persistência atômica, sem escrita parcial | CLAUDE.md §3.4 | DynamoDB com *Conditional Expressions* (escrita condicional atômica) — análogo serverless do `write-temp`+`os.replace`. |
| Isolamento multi-tenant obrigatório | ADR-008 §4 | PK = `USER#<user_id>` em **toda** linha; nenhum item sem prefixo de tenant. |
| Determinismo byte-idêntico | CLAUDE.md §3.2 | Lambdas injetam `now`/RNG do payload; `entity_id` = SHA-256; sem `datetime.now()`/`uuid4()` internos. |
| Open-World: falha ≠ falso | CLAUDE.md §3.3 | Retry/backoff + degradação controlada (`κ_degraded`); a máquina de estados nunca derruba o lead. |
| Custódia de segredos fora do código | ADR-008 §2 | Tavily/Apollo/Gemini no Secrets Manager (Stateful Stack); `.env` permanece só no modo `local`. |
| Core M1–M5 agnóstico de infra | ADR-008 §5 | Cada Lambda é *wrapper* fino que injeta o `DynamoDBRepository` (SDD-3) e chama a função pura. |
| Dados sobrevivem a deploys | ADR-008 §3 | Stateful Stack com `DeletionPolicy: Retain`; Stateless Stack é descartável. |

**Não-objetivo:** esta SDD **não** modela Terraform (usamos SAM/CloudFormation), **não** provisiona
o Cognito User Pool (externo, ADR-008), **não** cobre o repositório de frontend.

---

## 1. Visão geral das duas stacks

```
┌─────────────────────── Stateful Stack (ciclo de vida longo, Retain) ───────────────────────┐
│  DynamoDB  SocialSellingTable  (Single Table Design, PAY_PER_REQUEST)                       │
│  SecretsManager  /socialselling/tavily  /socialselling/apollo  /socialselling/gemini        │
│  Exports: TableName, TableArn, TableStreamArn, SecretArns                                    │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                   ▲ import (Fn::ImportValue)
┌─────────────────────── Stateless Stack (descartável a cada deploy) ────────────────────────┐
│  API Gateway (REST) + autorizador JWT Cognito  ──►  StateMachine (Step Functions)           │
│  StateMachine:  M1Search → M2Extract → M3Score → M4Rank → M5Xai  (Catch → FormatError)      │
│  Lambdas:  fn-m1 … fn-m5, fn-run-handler (borda), fn-wave (ondas)                            │
│  EventBridge Rule (cron noturno) ──►  StartExecution (assíncrono) → accumulate_and_rank      │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

Separar por ciclo de vida garante que um deploy de código (frequente) **nunca** possa destruir
ou recriar a tabela de dados ou os segredos.

---

## 2. Stateful Stack — DynamoDB Single Table Design

Uma única tabela, `SocialSellingTable`, `BillingMode: PAY_PER_REQUEST`. O isolamento multi-tenant
é **estrutural**: toda partição pertence a um `user_id`.

### 2.1 Chaves primárias

| Atributo | Composição | Papel |
|---|---|---|
| **PK** (Partition Key) | `USER#<user_id>` | Isola logicamente cada tenant. `user_id` vem do JWT (SDD-1), nunca do corpo. |
| **SK** (Sort Key) | discrimina o tipo de registro (ver §2.2) | Permite colocar corpus, cache, ledgers e feedback do mesmo tenant na mesma partição. |

### 2.2 Padrões de SK (discriminadores estáveis do motor)

| SK | Item | Mapeia do modo local | Operação dominante |
|---|---|---|---|
| `LEAD#<entity_id>` | Entrada do **Corpus Acumulativo** (ADR-006). `entity_id` = **SHA-256 estável** do lead. | `data/corpus/leads_corpus.json` | `UpdateItem` (upsert idempotente). |
| `CACHE#<hash_chave>` | Cache atômico **T-24h** de respostas de sensores. `hash_chave` = hash do prompt/query. | `data/cache/*` (`core/cache.py`) | `GetItem` / `PutItem` com `TTL`. |
| `LEDGER#FINOPS` | Item único por tenant que consolida saldos: créditos mensais do Apollo (`credit_ledger.py`) e RPD diário do Gemini (`request_ledger.py`). | `data/apollo_credit_ledger.json`, `data/gemini_request_ledger.json` | `UpdateItem` com `ADD`/condição. |
| `FEEDBACK#<company_id>` | Voto like/dislike (ADR-007) + componentes do score capturados no clique. | `data/feedback.json` | `PutItem` (chave = `company_id`). |
| `WAVE#STATE` | Estado da onda incremental (`corpus/waves.py`). | `data/corpus/waves.json` | `UpdateItem`. |

> **Por que isso preserva as invariantes:** `entity_id`/`company_id` continuam **derivados por
> hash estável** (nunca UUID/relógio) ⇒ mesma entrada ⇒ mesma SK ⇒ upsert idempotente e ranking
> determinístico. O isolamento de camadas é mantido: itens `LEAD#` (apresentação/corpus) e
> `FEEDBACK#` (ADR-007, camada de apresentação) **nunca** contêm Observed Evidence nem Inferences
> cruas — o feedback toca só componentes de `LeadCard.score`.

### 2.3 TTL e atomicidade

- **TTL nativo** (atributo `expires_at`) só nos itens `CACHE#` → expira a T-24h sem job de limpeza.
- **Atomicidade:** toda escrita usa *Conditional Expression* (ex.: `attribute_not_exists(PK) OR
  version < :v`) para concorrência otimista e idempotência (detalhe no `DynamoDBRepository`, SDD-3).
  Nenhuma escrita é parcial — equivalente serverless do `os.replace`.

### 2.4 Esboço SAM (Stateful)

```yaml
# infra/stateful/template.yaml  (resumo)
Resources:
  SocialSellingTable:
    Type: AWS::DynamoDB::Table
    DeletionPolicy: Retain
    UpdateReplacePolicy: Retain
    Properties:
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - { AttributeName: PK, AttributeType: S }
        - { AttributeName: SK, AttributeType: S }
      KeySchema:
        - { AttributeName: PK, KeyType: HASH }
        - { AttributeName: SK, KeyType: RANGE }
      TimeToLiveSpecification: { AttributeName: expires_at, Enabled: true }
  TavilySecret:  { Type: AWS::SecretsManager::Secret, Properties: { Name: /socialselling/tavily } }
  ApolloSecret:  { Type: AWS::SecretsManager::Secret, Properties: { Name: /socialselling/apollo } }
  GeminiSecret:  { Type: AWS::SecretsManager::Secret, Properties: { Name: /socialselling/gemini } }
Outputs:
  TableName: { Value: !Ref SocialSellingTable, Export: { Name: ss-TableName } }
  TableArn:  { Value: !GetAtt SocialSellingTable.Arn, Export: { Name: ss-TableArn } }
```

---

## 3. Stateless Stack — Step Functions, Lambdas, API Gateway, EventBridge

### 3.1 Máquina de estados (Step Functions)

Transição **sequencial e síncrona** que espelha o pipeline canônico. Cada estado é uma `Task` que
invoca o Lambda que envelopa o módulo puro correspondente.

```
[StartAt: M1Search]
   M1Search   (fn-m1)  → M2Extract
   M2Extract  (fn-m2)  → M3Score        ◄── timeout estrito + retry/backoff (extração é o gargalo)
   M3Score    (fn-m3)  → M4Rank
   M4Rank     (fn-m4)  → M5Xai
   M5Xai      (fn-m5)  → [End]   (saída: RankedProspect[] + LeadCard[])
   * qualquer estado → Catch → FormatError → [End]  (ApiError; nunca quebra a borda — SDD-1 §3)
```

Diagrama de estados (ASL conceitual):

```
┌──────────┐  ┌──────────┐  ┌─────────┐  ┌────────┐  ┌────────┐
│ M1Search │─▶│ M2Extract│─▶│ M3Score │─▶│ M4Rank │─▶│ M5Xai  │─▶ End
└────┬─────┘  └────┬─────┘  └────┬────┘  └───┬────┘  └───┬────┘
     └─────────────┴─────────────┴───────────┴──────────┴──▶ Catch ▶ FormatError ▶ End
```

### 3.2 Políticas de retry e timeout

| Estado | Timeout | Retry | Backoff |
|---|---|---|---|
| `M1Search` | 30 s | 2x em `States.TaskFailed`/5xx | exponencial, base 2 s |
| `M2Extract` | **120 s** (alinha `[gemini].timeout_seconds`) | 3x (= `[gemini].max_retries`) em 429/5xx **transitórios** | **exponencial, base 2 s** (= `backoff_base_seconds`) |
| `M3Score`/`M4Rank`/`M5Xai` | 15 s | 1x (puro/determinístico; falha = bug) | — |

> **Open-World na orquestração:** 429 de **billing/cota dura** (L-057, `prepayment credits
> depleted`) **não** é retentável — vai direto ao `Catch`/`FormatError` (a borda devolve 429
> acionável). Só 429/5xx **transitórios** disparam retry. Esgotado o retry, **degrada** o
> `OperatingMode` em vez de quebrar, quando há corpus prévio.

### 3.3 Lambdas

| Função | Envelopa | Responsabilidade do *wrapper* |
|---|---|---|
| `fn-m1`…`fn-m5` | `m1_busca`…`m5_xai` (puros) | Ler segredo do Secrets Manager; injetar `DynamoDBRepository` (SDD-3) + `now`; chamar a função pura; serializar contrato. **Sem regra de negócio.** |
| `fn-run-handler` | Borda (SDD-1) | Monta `PipelineTrigger`, faz `StartSyncExecution`, serializa `RunResponse`. |
| `fn-wave` | `corpus/waves.py` → `accumulate_and_rank` | Avança a onda incremental e persiste o corpus (gatilho noturno). |

Política IAM mínima por Lambda: acesso só à `SocialSellingTable` (importada) e ao segredo
necessário. Sem privilégios cruzados entre módulos.

### 3.4 API Gateway

REST API com autorizador JWT do Cognito (SDD-1). Rota síncrona `POST /runs` → `fn-run-handler`
ou integração direta `StartSyncExecution`. Validação de assinatura na borda; injeção de
`$context.authorizer.claims.sub` → `user_id`.

### 3.5 EventBridge — ondas noturnas

```yaml
WaveSchedule:
  Type: AWS::Events::Rule
  Properties:
    ScheduleExpression: "cron(0 6 * * ? *)"   # 06:00 UTC ~ 03:00 BRT (onda noturna)
    Targets:
      - Arn: !GetAtt PipelineStateMachine.Arn
        RoleArn: !GetAtt WaveInvokeRole.Arn
        Input: '{ "trigger": "wave", "persistence_mode": "aws" }'
```

A regra dispara `StartExecution` **assíncrono** (máquina *standard*) que roda `accumulate_and_rank`
por tenant ativo, avançando a onda **somente quando o ciclo produz leads** (Lição L-056: avançar
a onda à toa "queima" ondas boas).

---

## 4. Cenários BDD (Gherkin)

Testar IaC sem nuvem: validamos a **definição** (templates SAM e a ASL da máquina de estados) e o
**comportamento** dos *wrappers* contra um `DynamoDBRepository` **fake/mock** (SDD-3). Nenhum teste
fala com a AWS real nem com LocalStack.

```gherkin
# language: pt
Funcionalidade: IaC multi-stack — modelagem, isolamento e orquestração

  # ---------- Caminho feliz ----------
  Cenário: Item de corpus isolado por tenant com chave estável
    Dado um lead com entity_id "sha256:abc" do tenant "user-abc"
    Quando o wrapper persiste via DynamoDBRepository (fake)
    Então o item tem PK "USER#user-abc" e SK "LEAD#sha256:abc"
    E reescrever o mesmo lead é idempotente (mesmo PK/SK, version incrementa)

  Cenário: Máquina de estados encadeia M1..M5 em ordem determinística
    Dado um PipelineTrigger válido e fixtures de cada módulo
    Quando a ASL é executada pelo runner local de teste
    Então os estados ocorrem na ordem M1Search→M2Extract→M3Score→M4Rank→M5Xai
    E a saída final é byte-idêntica para a mesma entrada (1e-9)

  Cenário: Stateful Stack retém dados em re-deploy da Stateless Stack
    Dado um template Stateful com DeletionPolicy Retain
    Quando o template é validado
    Então a tabela e os segredos não são marcados para substituição/deleção

  # ---------- Degradado por limites/billing ----------
  Cenário: 429 transitório do Gemini dispara retry com backoff exponencial
    Dado o estado M2Extract com retry 3x base 2s
    E o Gemini responde 429 transitório duas vezes e depois 200
    Quando a máquina de estados executa
    Então M2Extract conclui com sucesso após os retries
    E o atraso entre tentativas cresce exponencialmente

  Cenário: Billing esgotado não é retentável e vai ao Catch (L-057)
    Dado o Gemini responde 429 "prepayment credits depleted"
    Quando M2Extract executa
    Então nenhum retry é feito para esse erro
    E o fluxo roteia para FormatError com error_code "GEMINI_BILLING_DEPLETED"

  Cenário: Ledger FinOps consolida saldos do tenant atomicamente
    Dado um LEDGER#FINOPS do tenant "user-abc"
    Quando dois consumos concorrentes de crédito Apollo ocorrem
    Então a Conditional Expression impede saldo negativo ou escrita parcial

  # ---------- Open-World ----------
  Cenário: Onda noturna não avança quando o ciclo não produz leads (L-056)
    Dado um gatilho EventBridge de onda e cognição degradada (sem leads novos)
    Quando fn-wave executa
    Então WAVE#STATE não é avançado
    E o corpus prévio permanece intacto e visível

  Cenário: Falha de sensor degrada o modo sem ocultar o lead
    Dado M1Search com Tavily indisponível após retries, e corpus prévio existente
    Quando a máquina de estados executa
    Então operating_mode é degradado
    E os leads conhecidos do tenant permanecem na saída
```

---

## 5. Work Units (rastreáveis — Run Noturno)

| WU | Entrega | Critério de aceitação |
|---|---|---|
| **WU-I1** | `infra/stateful/template.yaml` (DynamoDB Single Table + 3 segredos, Retain, TTL, Exports) | `sam validate` ok; teste afirma `DeletionPolicy: Retain` e schema PK/SK. |
| **WU-I2** | `infra/stateless/template.yaml` (Lambdas, StateMachine, API Gateway, EventBridge) importando exports da Stateful | `sam validate` ok; ARNs importados via `Fn::ImportValue`. |
| **WU-I3** | Definição ASL da máquina de estados (M1→M5 + Catch/FormatError) | Runner de teste executa a ASL com fixtures; ordem e saída determinísticas. |
| **WU-I4** | Políticas de retry/backoff e timeouts (esp. M2=120s/3x/base2s) | Cenários "429 transitório" e "billing não-retentável" verdes. |
| **WU-I5** | *Wrappers* Lambda `fn-m1`…`fn-m5` (injetam `DynamoDBRepository` + `now`; lêem segredo) | Módulos puros inalterados; wrappers testados com repo fake. |
| **WU-I6** | `fn-wave` + regra EventBridge (cron) com avanço de onda condicional (L-056) | Cenário "onda não avança sem leads" verde. |
| **WU-I7** | Mapeamento Single Table dos discriminadores SK (`LEAD#`,`CACHE#`,`LEDGER#FINOPS`,`FEEDBACK#`,`WAVE#`) | Teste de chaves: cada item gera o PK/SK esperado a partir do `entity_id`/`company_id`. |
| **WU-I8** | Políticas IAM mínimas por Lambda (só a tabela + segredo necessário) | Revisão; sem privilégio cruzado. |

**Quality gate (inegociável):** a validação de IaC (`sam validate`) e os testes de comportamento
dos *wrappers*/ASL rodam **offline**; o `DynamoDBRepository` é substituído por **fake** nos testes
(SDD-3). Proibido depender de AWS real, credenciais reais ou LocalStack no `pytest` nativo.
`ruff` + `mypy --strict` + `pytest` 100% verdes e determinísticos.
