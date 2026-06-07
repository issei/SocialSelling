# Plano de backlog — ADR-008 (MVP Serverless AWS, BaaS desacoplado + IaC bimodal)

> **O que é:** o plano ordenado de cards que operacionaliza a **ADR-008** e suas três SDDs
> derivadas. Decompõe cada Work Unit (WU) das specs em um card do **GitHub Project #1** com DoR
> rascunhado, ordenado por dependência. Inclui a camada **DevOps CI/CD** (deploy via OIDC na AWS),
> que as SDDs não cobrem.
>
> **Fonte da verdade arquitetural:** ADR-008 + SDD-1/2/3. Este doc **não** os substitui — só
> sequencia o trabalho. **Estado real:** `.ai/state/PROGRESS.md`. **Board:** espelho.
>
> **Modo operacional:** este é um artefato de **dia** (autoria). Todos os cards entram em
> **Backlog**. Quem move Backlog→Todo (com DoR 100%) é o **dono**; quem desenvolve é o **run
> noturno** (`github-sdd-sync`). Ver `docs/governance/modo-operacional.md`.

## Decisões do dono (lacunas conceituais resolvidas em 2026-06-07)

| Lacuna | Decisão | Impacto nos cards |
|---|---|---|
| **Ambientes AWS** | **Só prod** (MVP enxuto, 1 conta/ambiente). | Sem parametrização multi-env nem promoção encadeada. Exports CloudFormation com nome fixo (`ss-*`). Mantém o guardrail anti-overengineering (§5). |
| **Gatilho de CD** | **Stateless auto / Stateful manual.** Merge na `main` faz deploy automático da **Stateless Stack** (código, descartável). A **Stateful Stack** (DynamoDB + segredos, `Retain`) só por `workflow_dispatch` com **environment aprovado**. | WU-D2 (stateful, manual+approval) separado de WU-D3 (stateless, auto). Protege dados de deploy de código. |
| **Cognito User Pool** | ✅ **Provisionado em 2026-06-07.** User Pool `us-east-1_o17XMPejk` + app client `54ofg7c96p74niqbdibfkrtavv`; GitHub vars `COGNITO_ISSUER`/`COGNITO_AUDIENCE` publicadas. **WU-X1 concluída (Done).** | Cards de borda (B) e IaC (I) referenciam `issuer`/`audience` via essas vars. **WU-D3** (deploy auto) deixa de estar bloqueada por Cognito; resta apenas a **ordem**: desenvolver/mergear após WU-I2 + execução manual de WU-D2 (deploy da Stateful 1x). |
| **Região + OIDC** | **OIDC já configurado na AWS** (provedor de identidade + role criados). No repositório, **secrets**: `AWS_ROLE_ARN` (ARN do role) e `AWS_REGION` (região). Nada hardcoded. | Cards D2/D3 assumem o role por OIDC (`aws-actions/configure-aws-credentials@v4`, `permissions: id-token: write`) lendo `${{ secrets.AWS_ROLE_ARN }}` e `${{ secrets.AWS_REGION }}`. OIDC deixa de ser bloqueio. |

## Princípio de ordenação

A sequência segue a **dependência técnica**, não a ordem das specs:

```
Fase 1  Persistência bimodal (SDD-3)  ── fundação: isola o core do meio de armazenamento
   │     WU-P1 → P2/P3 → P4 → P5 → P6 → P7 → P8
   ▼
Fase 2  Borda BaaS (SDD-1)            ── contratos de entrada/saída + handlers (reusa P)
   │     WU-B1 → B2 → B3 → B4 → B5 → B6 → B7
   ▼
Fase 3  IaC multi-stack (SDD-2)       ── declara os recursos (usa DynamoDBRepository de P5 e handlers de B)
   │     WU-I1 → I2 → I3 → I4 → I5 → I6 → I7 → I8
   ▼
Fase 4  DevOps CI/CD (novo)           ── valida e entrega a IaC via OIDC
         WU-D1 (sam validate no gate) → WU-D2 (CD stateful manual) → WU-D3 (CD stateless auto)
         WU-X1 (provisionar Cognito — bloqueio externo, paralelo)
```

**Por que P primeiro:** o `DynamoDBRepository` (P5) e a fábrica (P6) são pré-requisito dos
*wrappers* Lambda (I5) e a paridade bimodal (P2/P7) é o que mantém o gate **offline** durante todo
o resto. Sem a camada de Ports, qualquer trabalho de borda/IaC vazaria `boto3` para o core (viola
ADR-008 §5).

## Grafo de dependências (resumo por card)

| Card | Depende de | Bloqueio externo |
|---|---|---|
| WU-P1 Ports (ABCs) | — | — |
| WU-P2 LocalJSONRepository | P1 | — |
| WU-P3 FakeRepository | P1 | — |
| WU-P4 Contract tests | P2, P3 | — |
| WU-P5 DynamoDBRepository (boto3 stub) | P1, P4 | — |
| WU-P6 Factory + persistence_mode | P2, P5 | — |
| WU-P7 Refactor núcleo p/ injeção | P6 | — |
| WU-P8 CI guard (sem rede/AWS/LocalStack) | P4 | — |
| WU-B1 edge/contracts.py | P1 (reusa contracts) | — |
| WU-B2 run_handler (PipelineTrigger) | B1 | — |
| WU-B3 Serializador RunResponse | B1, B2 | — |
| WU-B4 errors.py (FinOps classifier) | B1 | — |
| WU-B5 Catch/FormatError (def ASL) | B4 | — |
| WU-B6 OpenAPI estrito + lint | B1, B3, B4 | — |
| WU-B7 Open-World e2e | B3, B4 | — |
| WU-I1 Stateful template | P5 (modelagem alinhada) | — |
| WU-I2 Stateless template | I1, B2 | **Cognito** (autorizador) |
| WU-I3 ASL state machine | I2, B5 | — |
| WU-I4 Retry/backoff/timeouts | I3 | — |
| WU-I5 Wrappers fn-m1..m5 | P5, P6 | — |
| WU-I6 fn-wave + EventBridge cron | I5 | — |
| WU-I7 SK single-table mapping | I1, P5 | — |
| WU-I8 IAM mínimo por Lambda | I2, I5 | — |
| WU-D1 `sam validate` no gate | I1, I2 | — |
| WU-D2 CD Stateful (manual+approval) | I1, D1 | — (OIDC já resolvido: secrets `AWS_ROLE_ARN`/`AWS_REGION`) |
| WU-D3 CD Stateless (auto no merge) | I2, D1, D2 | **Cognito** (OIDC já resolvido) |
| WU-X1 Provisionar Cognito (externo) | — | ação do dono fora do repo |

## Camada DevOps (detalhe — não coberta pelas SDDs)

O repositório já tem **OIDC configurado na AWS**. A entrega segue a separação stateful/stateless da
ADR-008 §3:

- **WU-D1 — `sam validate` no CI (offline).** Estende `.github/workflows/ci.yml` para validar os
  dois templates SAM. **Sem** credenciais AWS, sem deploy — só lint de IaC. Honra o guardrail de
  gate 100% offline (SDD-3 §5).
- **WU-D2 — CD da Stateful Stack (`workflow_dispatch` + environment aprovado).** Deploy manual,
  raro, com aprovação humana. `permissions: id-token: write`; assume `${{ secrets.AWS_ROLE_ARN }}`
  por OIDC na região `${{ secrets.AWS_REGION }}`; `sam deploy` da stack stateful
  (`DeletionPolicy: Retain`). Nunca automático — dados não podem ser tocados por push de código.
- **WU-D3 — CD da Stateless Stack (auto no merge à `main`).** Após CI verde, deploy automático das
  Lambdas/Step Functions/API Gateway/EventBridge importando os exports da stateful. OIDC com os
  mesmos secrets (`AWS_ROLE_ARN`/`AWS_REGION`). Idempotente; rollback pela revisão anterior do
  CloudFormation.
- **WU-X1 — Cognito (externo).** Provisionar o User Pool fora deste repo e publicar `issuer`/
  `audience` como GitHub vars. **Bloqueia** o autorizador JWT (I2/D3) e a validação da borda (B).

> **Fora de escopo do CD (guardrails §5):** sem multi-conta, sem Terraform, sem LocalStack, sem
> pipeline de promoção dev→staging→prod, sem rollback automático sofisticado. MVP enxuto.

## Fase 5 — Segurança & FinOps (ADR-009): write gated

O dono autorizou **operações de escrita na AWS** sob a condição de **testes + revisores de segurança
automáticos** (FinOps bem arquitetado, sem brechas). Formalizado na **ADR-009**. Consequência: o
**deploy real é write** — `WU-D2` saiu do Todo e voltou ao **Backlog**; o write só liga via o
card-portão `WU-G1`, quando os gates abaixo estiverem **Done**.

| Card | Entrega | Status |
|---|---|---|
| WU-S1 | `cfn-lint` + `checkov` no CI (required check) sobre `infra/` | Todo |
| WU-S2 | IAM Access Analyzer `validate-policy` + teste anti-wildcard sobre `infra/iam/` | Todo |
| WU-S3 | Permissions boundary nas roles criadas pelo CFN | Todo |
| WU-S4 | Revisor de segurança automático (Claude) nos PRs de `infra/` | Todo |
| WU-F1 | Caps de recurso (Lambda mem/timeout/concurrency) + log retention finita | Todo |
| WU-F2 | AWS Budgets + alerta (parametrizar valor/email) | Todo |
| WU-F3 | Cost-allocation tags obrigatórias + check no CI | Todo |
| **WU-G1** | **Portão:** liga `--allow-write` (MCP) + promove D2/D3 | **Backlog** (Ready só com S1..S4+F1..F3 = Done) |

**Gate de escrita (fail-closed):**
```
WU-S1..S4 + WU-F1..F3 (Done)  ──►  WU-G1 (liga write)  ──►  WU-D2 (deploy Stateful, manual)  ──►  WU-D3 (deploy Stateless, auto)
```
Os scanners rodam **offline** (cfn-lint/checkov/teste anti-wildcard); o Access Analyzer é validação
(sem mutação). O gate de produto (`ruff`+`mypy`+`pytest`) segue 100% offline (WU-P8).

## Quality gate (inegociável, herdado)

Todos os cards mantêm: `ruff` + `mypy --strict` + `pytest` **100% offline e determinístico**
(`1e-9`), APIs/AWS/Step Functions/Cognito **mockados por fixture**, **sem** rede, **sem**
credenciais reais, **sem** LocalStack. PR por card → CI verde → `--squash --auto`.

## Como os cards foram criados

Reproduzível via `scripts/seed_adr008_cards.py` (cria todos os 27 cards em **Backlog** no
Project #1, com corpo no template DoR e Priority codificando a fase). Idempotência: o script
**não** deduplica — rodar duas vezes duplica os cards. Rodar uma vez.
