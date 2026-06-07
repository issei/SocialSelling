# ADR-009 — Operações de escrita na AWS sob gates automáticos de segurança e FinOps

| Campo | Valor |
|---|---|
| Status | **Aprovado** |
| Data | 2026-06-07 |
| Decisores | Dono do produto + Staff Engineer/Arquiteto |
| Complementa | **ADR-008** (MVP serverless + IaC bimodal) |
| Especificações derivadas | cards WU-S1..S4 (segurança), WU-F1..F3 (FinOps), WU-G1 (habilitação) no Project #1 |

## Contexto

A ADR-008 estabeleceu o MVP serverless na AWS com deploy via OIDC. Até aqui, as ferramentas de
apoio (MCP servers awslabs, `aws-tooling-eval.md`) foram mantidas **read-only** e as mutações
ficaram restritas ao pipeline SAM+OIDC. O dono autorizou **habilitar operações de escrita na AWS**
(deploy real + `--allow-write` no MCP serverless), **sob uma condição inegociável**:

> Habilitar write **somente** com **testes e revisores de segurança automáticos** que garantam
> **FinOps bem arquitetado** e **nenhuma brecha de segurança**.

Esta ADR transforma essa condição em **gates obrigatórios** e define que **toda capacidade de
escrita é fail-closed**: na ausência dos gates verdes, o write permanece desligado.

## Decisão

### 1. Write é gated (fail-closed)
Nenhuma operação de escrita na AWS é habilitada antes de os gates de segurança e FinOps estarem
**verdes na `main`**. Isso cobre:
- O **deploy real** (WU-D2 stateful, WU-D3 stateless) — são write.
- O **`--allow-write`** do `aws-serverless-mcp-server` no `.mcp.json`.

A habilitação é um **card-portão explícito (WU-G1)** que só vira Ready quando WU-S1..S4 e
WU-F1..F3 estiverem **Done**.

### 2. Gates de segurança automáticos (CI, preventivo + defesa em profundidade)
- **Scan de IaC:** `cfn-lint` + **checkov** sobre os templates SAM (`infra/`), como **required
  checks** que **falham o build** em finding de severidade relevante (WU-S1).
- **Validação de IAM:** **IAM Access Analyzer** (`access-analyzer validate-policy`) sobre as policies
  em `infra/iam/`, mais um teste que **proíbe wildcards perigosos** (`Action:"*"`/`Resource:"*"` em
  ações sensíveis; `iam:PassRole` sem `Condition`) (WU-S2).
- **Menor privilégio reforçado:** **permissions boundary** nas roles que o CloudFormation cria para
  os recursos da stack (limita o raio de explosão) (WU-S3).
- **Revisor automático no PR:** além dos hard-gates, um **agente revisor de segurança** (Claude via
  GitHub Action / skill `security-review`) comenta PRs que tocam `infra/` (WU-S4). O agente é
  **advisory**; o bloqueio de merge é dos required checks.

### 3. Gates de FinOps automáticos (custo bem arquitetado)
- **Caps de recurso nos templates:** Lambda `MemorySize`/`Timeout` limitados, **log retention**
  finita (sem custo infinito de logs), DynamoDB `PAY_PER_REQUEST`, **reserved concurrency** nas
  Lambdas para conter rajada (WU-F1).
- **AWS Budgets + alertas:** orçamento mensal com alerta (SNS/email) — teto de gasto observável,
  alinhado ao `LEDGER#FINOPS` da ADR-003/008 (WU-F2).
- **Cost-allocation tags obrigatórias:** todo recurso com tags (`Project`, `Environment`,
  `CostCenter`/owner), checadas no CI (WU-F3).

### 4. Tudo continua fora do gate offline
Os scanners (`cfn-lint`/`checkov`/teste anti-wildcard) rodam **offline** no CI — não falam com a
AWS. O Access Analyzer `validate-policy` é uma chamada de **validação** (sem mutação). O quality
gate de produto (`ruff`+`mypy`+`pytest`) **permanece 100% offline e determinístico** (SDD-3 §5,
WU-P8). Os gates de IaC são **jobs adicionais**, não dependem de AWS real para o scan.

## Invariantes preservadas
- **Determinismo/offline do gate de produto:** inalterado.
- **Deploys auditáveis:** mutações só pelo pipeline OIDC (WU-D2/D3) com a policy mínima
  (`infra/iam/`), nunca por chamada ad-hoc não revisada.
- **Anti-overengineering (CLAUDE.md §5):** ferramentas nativas/OSS (cfn-lint, checkov, Access
  Analyzer, Budgets) — sem plataforma pesada de governança.

## Escopo (o que esta ADR não autoriza)
- Não habilita write **antes** dos gates (fail-closed).
- Não troca o pipeline OIDC por mutação ad-hoc via MCP em produção (o `--allow-write` do MCP é
  auxiliar de **dev**, sob os mesmos gates).
- Não introduz multi-conta, SCPs de Organização nem ferramenta paga de FinOps (fora do MVP).

## Consequências
**Positivas:** write na AWS com rede de segurança preventiva (scan + IAM mínimo + boundary) e custo
sob controle (caps + budgets + tags); revisão dupla (CI + agente).
**Trade-offs:** mais jobs de CI e disciplina de tags/caps; o write fica **bloqueado** até os 7 cards
de gate fecharem (custo consciente da condição do dono).

## Gaps abertos
- Limite/valor exato do AWS Budget e destinatário do alerta (parametrizar em WU-F2).
- Política de severidade do checkov (quais checks são bloqueantes vs warning) — definir em WU-S1.
