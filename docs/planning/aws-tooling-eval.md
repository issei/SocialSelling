# Avaliação de tooling AWS (awslabs/agent-plugins + awslabs/mcp)

> **Para quê:** escolher um conjunto **mínimo** de ferramentas oficiais da AWS Labs que ajudem a
> autorar/operar a fatia AWS do roadmap ADR-008 (SAM, Lambda, Step Functions, DynamoDB single-table,
> API Gateway, EventBridge, IAM/OIDC) **sem** ferir o gate offline nem o guardrail anti-overengineering.
>
> **Data:** 2026-06-07. **Fontes:** https://github.com/awslabs/agent-plugins · https://github.com/awslabs/mcp

## Restrições que governam a escolha

1. **Gate 100% offline/determinístico** (SDD-3 §5, WU-P8): sem AWS real, sem rede, sem LocalStack no
   `pytest`/CI. Estas ferramentas são **auxiliares de autoria (dia/dev)** — **nunca** entram em
   `pytest`, CI ou runtime. Os testes seguem com `boto3` stubado. O `.mcp.json` só afeta a sessão
   interativa do Claude Code; o workflow de CI (`gate`) não carrega MCP.
2. **Anti-overengineering** (CLAUDE.md §5): dos ~34 MCP servers do awslabs/mcp, a maioria (RDS,
   Bedrock, EKS, Neptune…) é irrelevante ao PoC. Adotado só o que casa com cards reais.
3. **Deploys auditáveis**: mutações na AWS vão pelo **pipeline SAM + OIDC** (WU-D2/D3), não por
   chamadas ad-hoc. Por isso os servers ficam em **modo read-only**.

## Decisão

### MCP servers adicionados (`.mcp.json`, read-only)

| Server (uvx) | Serve a | Modo |
|---|---|---|
| `awslabs.dynamodb-mcp-server` | WU-I1/I7/P5 — single-table design e data modeling | `DDB-MCP-READONLY=true` (design sem mutação) |
| `awslabs.aws-iac-mcp-server` | revisar templates SAM/CFN + **validação de segurança** da policy IAM (`infra/iam/`) | validação local; troubleshooting usa creds read-only |
| `awslabs.aws-documentation-mcp-server` | docs AWS atualizadas sob demanda | sem credenciais |
| `awslabs.aws-serverless-mcp-server` | WU-B*/I*/D* — Lambda/APIGW/SFN/EventBridge/SAM | **sem `--allow-write`** (read-only; deploy fica no pipeline OIDC) |

Credenciais: usam a **cadeia padrão** (a mesma que rodou `aws sts`/Cognito), região `us-east-1`.
Sem `AWS_PROFILE` fixo. Pré-requisito: `uvx` (já instalado, uv 0.9.x).

### Plugin do marketplace — **não adotado**

O plugin `aws-serverless` (de `awslabs/agent-plugins`) cobre terreno equivalente ao
`aws-serverless-mcp-server`. Para evitar redundância, ficou-se com o **MCP server**. Caso se queira
o plugin no futuro: `/plugin marketplace add awslabs/agent-plugins` → `/plugin install aws-serverless@agent-plugins-for-aws`.

## Avaliados e descartados (por escopo)

- `deploy-on-aws` (plugin) — geração de IaC/custo genérica; o roadmap já tem SDDs/IaC definidas.
- MCP servers de RDS/Aurora/DocumentDB/Neptune/Keyspaces/Redshift, Bedrock/SageMaker/Kendra/Q,
  EKS/ECS/Finch, AppSync, IoT, Transform — fora do escopo do PoC (guardrail §5).
- Servers de **write** (Cloud Control, API MCP de mutação) — deploys vão pelo pipeline OIDC.

## Como usar (dev)

- Abrir o repo no Claude Code: os 4 servers aparecem para aprovação. Use-os para **desenhar**
  (single-table, ASL, templates), **validar** (IaC/policy) e **consultar docs** — não para deployar.
- Deploy real continua: WU-D2 (`workflow_dispatch`, stateful) e WU-D3 (auto na main, stateless),
  via OIDC com a policy `infra/iam/github-actions-deploy-policy.json`.

> **Trava:** se algum dia um teste depender de um MCP server, é bug de DoR (WU-P8). O gate é offline.
