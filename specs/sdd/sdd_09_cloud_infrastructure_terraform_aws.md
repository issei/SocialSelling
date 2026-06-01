# SDD-09: Infraestrutura Nuvem como Codigo Serverless
## SocialSelling — Solution Design Document
### Versão: 1.0-MVP | Classificação: CONFIDENCIAL — ENGENHARIA

---

**Escopo do Documento:** Especificacao completa da infraestrutura AWS na regiao us-east-1, modulos Terraform executaveis, politicas IAM de minimo privilegio, Aurora Serverless v2, SQS DLQ, Lambda com Mangum adapter e pipeline de deploy via GitHub Actions OIDC.

**Documentos relacionados:**
- `sdd_01_product_vision_and_core_dag.md` — Arquitetura LangGraph, AgentState
- `sdd_06_database_schema_and_graph_ready_ddl.md` — DDL PostgreSQL 16+
- `sdd_07_event_storming_and_saga_orchestration.md` — EV-17/18 (CRM webhook, SQS consumer)
- `specs/SocialSelling_DevOps_Setup_Guide.md` — Guia de setup local e pipelines CI/CD

---

## Indice

1. [Topologia Serverless na AWS (us-east-1)](#1-topologia-serverless-na-aws-us-east-1)
2. [Banco de Dados e Resiliencia Assincrona](#2-banco-de-dados-e-resiliencia-assincrona)
3. [Especificacao de Modulos Terraform](#3-especificacao-de-modulos-terraform)

---

## 1. TOPOLOGIA SERVERLESS NA AWS (us-east-1)

### 1.1 Diagrama ASCII da Arquitetura

```
+------------------+          +------------------+          +------------------------+
|  Client / SPA    |          |  GitHub Actions   |          |  CloudWatch Alarm      |
|  (Browser/Curl)  |          |  (CI/CD Pipeline) |          |  QueueDepth > 0        |
+--------+---------+          +--------+----------+          +----------+-------------+
         |                             |                                 |
         | HTTPS                       | AssumeRoleWithWebIdentity       | SNS Topic
         v                             | (OIDC — sem chaves estaticas)   v
+------------------+          +--------+----------+          +------------------------+
| API Gateway HTTP |          |  IAM Role          |          |  SNS -> Email          |
| API (us-east-1)  |          |  GitHubActionsRole |          |  engineering@company   |
| Throttle: 100/s  |          |  (deploy only)     |          +------------------------+
| Burst: 200       |          +--------+----------+
+--------+---------+                   |
         |                    lambda:UpdateFunctionCode
         | Lambda Proxy        ecr:GetAuthorizationToken
         | Integration         ecr:BatchCheckLayerAvailability
         v                             v
+------------------+          +------------------+
|  AWS Lambda      |<---------+ ECR Repository   |
|  Python 3.12     |  pull    |  socialselling   |
|  1024 MB RAM     |  image   |  :latest / :sha  |
|  300s timeout    |          +------------------+
|  VPC privada     |
|  handler:        |
|  app.main.handler|
+---+----------+---+
    |          |
    |          | boto3 / asyncpg
    |          v
    |   +------+---------------+
    |   |  RDS Proxy           |
    |   |  (connection pool)   |
    |   +------+---------------+
    |          |
    |          | writer / reader endpoints
    |          v
    |   +------+-------------------------+
    |   |  Aurora Serverless v2          |
    |   |  PostgreSQL 16                 |
    |   |  Production: 0.5-8 ACU        |
    |   |  Multi-AZ: writer + 1 reader  |
    |   |  Backup: 7 dias               |
    |   +--------------------------------+
    |
    | Secrets Manager Lambda Extension
    | (sem hardcode de credenciais)
    v
+------------------+          +------------------+
| Secrets Manager  |          |  SQS Main Queue  |
| socialselling/   |          |  VisibilityTimeout|
| {env}/db-creds   |          |  = 360s          |
| rotacao: 30d     |          +--------+---------+
+------------------+                   |
                                        | maxReceiveCount=3
                                        v
                               +--------+---------+
                               |  SQS DLQ         |
                               |  MessageRetention |
                               |  = 14d           |
                               +--------+---------+
                                        |
                               CloudWatch Alarm -> SNS
```

**Fluxo principal (request sincrono):**
1. Client envia requisicao HTTPS para o API Gateway HTTP API
2. API Gateway roteia via `ANY /{proxy+}` para a Lambda Integration
3. Lambda executa o handler FastAPI via Mangum adapter
4. Lambda busca credenciais do banco via Secrets Manager Lambda Extension (cache local — sem chamada de rede adicional por request)
5. Lambda conecta ao Aurora via RDS Proxy (connection pooling)
6. Resposta retorna ao client via API Gateway

**Fluxo assincrono (CRM webhook / SQS consumer):**
1. POST /api/v1/webhooks/crm -> Lambda -> INSERT em SQS Main Queue -> 202 Accepted
2. Consumer Lambda recebe mensagem da SQS -> processa feedback CRM -> atualiza SRS
3. Se consumer falha 3x -> mensagem move para DLQ -> CloudWatch Alarm dispara -> SNS email

**Fluxo de deploy (GitHub Actions):**
1. Push na branch main -> GitHub Actions workflow ativado
2. OIDC token emitido pelo GitHub -> AssumeRoleWithWebIdentity -> IAM Role temporaria
3. Build Docker image -> push para ECR
4. lambda:UpdateFunctionCode -> Lambda atualizada sem downtime (blue/green automatico da Lambda)

---

### 1.2 AWS Lambda

**Runtime e Handler:**
- Runtime: `python3.12`
- Handler: `app.main.handler` — wrapper Mangum que converte eventos API Gateway para o formato ASGI do FastAPI
- Mangum configurado com `lifespan="off"` (Lambda nao tem lifecycle de servidor)

**Recursos:**
- Memory: **1024 MB** — necessario para Playwright headless (picos de 800 MB durante scraping), jellyfish (processamento de strings em C), langchain/langgraph
- Timeout: **300 segundos** — budget distribuido: Scraping(120s) + EntityResolution(30s) + Scoring(15s) + Blueprint(10s) = 175s nominal; margem de 125s para degraded paths e cold start
- Reserved Concurrent Executions por ambiente:
  - Production: `10` — limitacao deliberada para proteger Aurora (max_connections=200, 10 Lambda x 20 conexoes por RDS Proxy = 200 conexoes)
  - Staging: `5`
  - Dev: `2`

**VPC e Networking:**
- Lambda implantada em subnets privadas (sem acesso direto a internet — NAT Gateway obrigatorio para chamadas externas: Instagram, LinkedIn, CNPJ.ws, Tavily)
- Security Group da Lambda: egress liberado para porta 443 (HTTPS externo via NAT), porta 5432 (Aurora via RDS Proxy dentro da VPC), porta 6379 (ElastiCache Redis dentro da VPC)
- Security Group do RDS Proxy: ingress apenas do Security Group da Lambda na porta 5432
- VPC Endpoints para servicos AWS: `com.amazonaws.us-east-1.secretsmanager`, `com.amazonaws.us-east-1.sqs`, `com.amazonaws.us-east-1.ecr.api`, `com.amazonaws.us-east-1.ecr.dkr` — reducao de latencia e custo de NAT

**Lambda Layers:**
- Layer 1: `socialselling-playwright` — binarios Playwright Chromium (~180 MB comprimido); atualizado independente do codigo da aplicacao
- Layer 2: `socialselling-ml-deps` — jellyfish, langchain, langgraph, numpy (~95 MB comprimido)
- Layer 3: `socialselling-data-deps` — httpx, playwright (Python SDK), tavily-python, asyncpg, redis (~45 MB comprimido)
- Codigo da aplicacao no pacote Lambda: ~15 MB (apenas FastAPI app, routers, services)
- Total implantado: < 250 MB (limite de 250 MB descomprimido em Lambda)

**Environment Variables (via Secrets Manager Lambda Extension):**
```
DATABASE_URL           -> resolvido em runtime via Secrets Manager Extension
REDIS_URL              -> resolvido em runtime via Secrets Manager Extension
ANTHROPIC_API_KEY      -> resolvido em runtime via Secrets Manager Extension
TAVILY_API_KEY         -> resolvido em runtime via Secrets Manager Extension
INSTAGRAM_PROXY_LIST   -> resolvido em runtime via Secrets Manager Extension
ENVIRONMENT            -> "production" | "staging" | "dev" (variavel estatica — nao secret)
AWS_REGION             -> "us-east-1" (variavel estatica)
LOG_LEVEL              -> "INFO" em producao, "DEBUG" em dev (variavel estatica)
```

Zero hardcode de credenciais. O Secrets Manager Lambda Extension intercepta referencias a segredos e os resolve localmente com cache TTL de 5 minutos — sem overhead de rede por request.

---

### 1.3 Amazon API Gateway HTTP API

**Tipo:** HTTP API (nao REST API) — latencia media 1.2ms vs 6.1ms do REST API; custo por request 70% menor; CORS gerenciado nativamente.

**Configuracao:**
- Stage: `$default` (auto-deployed — nao requer deploy manual de stages)
- Endpoint type: Regional (nao Edge-optimized — aplicacao B2B sem necessidade de CDN global)
- API Key para endpoints admin: header `x-api-key` requerido para rotas `/admin/*` e `/api/v1/icp-contract` (PUT)

**Throttling:**
- Default route throttle: `rate=100 req/s`, `burst=200`
- Rota admin (`/api/v1/admin/*`): `rate=10 req/s`, `burst=20` (throttle mais restritivo — operacoes de escrita raramente frequentes)
- Rota webhook CRM (`/api/v1/webhooks/crm`): `rate=50 req/s`, `burst=100`

**CORS:**
```
AllowOrigins: ["https://app.socialselling.com.br", "https://staging.socialselling.com.br"]
AllowMethods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
AllowHeaders: ["content-type", "x-api-key", "x-crm-signature", "authorization"]
MaxAge: 86400  # 24h preflight cache
```

**Rotas:**
- `ANY /{proxy+}` -> Lambda Integration (catch-all — FastAPI router gerencia o roteamento interno)
- Lambda Integration type: `AWS_PROXY` com payload format version `2.0`
- Timeout por integracao: 29s (limite maximo do API Gateway HTTP API)

**Nota sobre timeout:** API Gateway HTTP API limita timeout de integracao a 29 segundos. Requests de ciclo full (coleta + scoring) excedem 29s. Solucao: endpoint `/api/v1/cycles` retorna `202 Accepted` com `cycle_id` imediatamente; a Lambda invocada via SQS (sem API Gateway) executa o pipeline completo de 300s. O cliente consulta status via polling em `GET /api/v1/cycles/{cycle_id}/status`.

---

### 1.4 Amazon Aurora Serverless v2 (PostgreSQL 16)

**Configuracao de ACU (Aurora Capacity Units):**
- Production: min=0.5 ACU, max=8 ACU — escala automaticamente em incrementos de 0.5 ACU; cada ACU aprox 2 GB RAM
- Staging: min=0.5 ACU, max=4 ACU
- Dev: min=0.5 ACU, max=2 ACU, auto-pause habilitado (pause apos 5 minutos de inatividade)

**Multi-AZ (Production apenas):**
- Writer instance: `us-east-1a`
- Reader replica: `us-east-1b` (leituras de analytics e dashboards roteadas para o reader)
- Failover automatico: < 30 segundos em caso de falha do writer

**Backup e Retencao:**
- Production: retencao de 7 dias, backup window `02:00-03:00 UTC`, maintenance window `Sun 03:00-04:00 UTC`
- Staging: retencao de 3 dias
- Dev: retencao de 1 dia

**Parametros do Cluster:**
```
max_connections      = 200    # RDS Proxy multiplexes ate 200 conexoes de Lambda
work_mem             = 64MB   # Por sessao — adequado para queries de analytics
shared_buffers       = 256MB  # 25% da RAM do cluster em 1 ACU (2 GB)
effective_cache_size = 1GB    # Estimativa para otimizador de queries
maintenance_work_mem = 128MB  # Para VACUUM, CREATE INDEX
random_page_cost     = 1.1    # Aurora usa SSD — mais proximo de 1.0 que o default 4.0
wal_level            = logical # Necessario para replicacao logica (futura V1)
```

**Extensoes:**
- `pg_trgm`: ativa — usada para busca fuzzy em campos `TEXT` (pesquisa por nome de empresa)
- `pgvector`: preparada para V1 — DDL com `CREATE EXTENSION IF NOT EXISTS vector;` comentado; ativar quando embeddings de 1536 dimensoes forem implementados
- `uuid-ossp`: ativa — gerador de UUIDs v4 para primary keys
- `pg_stat_statements`: ativa — monitoramento de queries lentas via CloudWatch

**Acesso e Seguranca:**
- Acesso exclusivo via VPC (sem exposição publica — `publicly_accessible = false`)
- Subnet group: subnets privadas em `us-east-1a` e `us-east-1b`
- Security Group: ingress apenas do Security Group do RDS Proxy na porta 5432
- Credenciais via Secrets Manager com rotacao automatica de 30 dias (Lambda de rotacao gerenciada pela AWS)
- Encryption at rest: KMS key gerenciada pela AWS (`aws/rds`)
- Encryption in transit: SSL obrigatorio (certificado RDS CA)

---

### 1.5 Amazon SQS DLQ

**Estrutura de Filas:**

**Fila Principal (`socialselling-{env}-main`):**
- Type: Standard Queue (nao FIFO — ordem nao e requisito; throughput ilimitado)
- VisibilityTimeout: **360 segundos** — 60s de margem acima do timeout maximo do consumer Lambda (300s)
- MessageRetentionPeriod: 14 dias
- ReceiveMessageWaitTimeSeconds: 20 (long polling — reduz chamadas vazias e custo)
- Redrive Policy: `maxReceiveCount=3`, `deadLetterTargetArn=<arn da DLQ>`

**DLQ (`socialselling-{env}-dlq`):**
- MessageRetentionPeriod: **14 dias** (retencao maxima — tempo para investigacao e reprocessamento manual)
- VisibilityTimeout: 360 segundos (identico a fila principal)
- Sem Redrive Policy propria (DLQ nao tem DLQ)

**Semantica da Redrive Policy:**
- Mensagem recebida 1x: processamento falhou -> volta para fila com VisibilityTimeout
- Mensagem recebida 2x: nova falha -> volta para fila
- Mensagem recebida 3x: nova falha -> movida automaticamente para DLQ
- Mensagem na DLQ: CloudWatch Alarm `SQSDeadLetterQueueDepth` dispara com `Threshold=1` (qualquer mensagem na DLQ e alertavel)

**CloudWatch Alarm para DLQ:**
```
MetricName: ApproximateNumberOfMessagesVisible
Namespace: AWS/SQS
Dimensions: QueueName = socialselling-{env}-dlq
Threshold: 1
ComparisonOperator: GreaterThanOrEqualToThreshold
Period: 60 (segundos)
EvaluationPeriods: 1
TreatMissingData: notBreaching
AlarmActions: [SNS Topic ARN]
```

**Lambda consumer da DLQ:**
- Lambda separada `socialselling-{env}-dlq-processor`
- Trigger: Event Source Mapping na DLQ com batch size 1
- Acao: deserializa mensagem original, persiste em S3 bucket `socialselling-{env}-dlq-archive` com prefix `year/month/day/`, envia notificacao Slack via webhook com payload da mensagem e context de erro
- Apos processamento: mensagem deletada da DLQ (consumer confirma delecao)

---

### 1.6 AWS Secrets Manager

**Convencao de Nomenclatura:** `socialselling/{env}/{nome-do-segredo}`

| Segredo | Path Completo | Rotacao Automatica | Conteudo |
|---|---|---|---|
| Credenciais do banco de dados | `socialselling/{env}/db-credentials` | Sim — 30 dias (Lambda rotacao RDS) | `{"username": "...", "password": "...", "host": "...", "port": 5432, "dbname": "socialselling"}` |
| Chave da API Anthropic | `socialselling/{env}/anthropic-api-key` | Nao (rotacao manual trimestral) | `{"api_key": "sk-ant-..."}` |
| Chave da API Tavily | `socialselling/{env}/tavily-api-key` | Nao (rotacao manual trimestral) | `{"api_key": "tvly-..."}` |
| Pool de proxies Instagram | `socialselling/{env}/instagram-proxy-list` | Nao (atualizado por scripts de manutencao) | `{"proxies": ["http://user:pass@host:port", ...], "rotation_count": 15}` |
| Cookie pool LinkedIn | `socialselling/{env}/linkedin-cookie-pool` | Nao (renovacao automatica via script de manutencao) | `{"cookies": [{"session_id": "...", "li_at": "...", "valid_until": "..."}]}` |

**Rotacao automatica de credenciais do banco:**
- Tipo: `aws:secretsmanager:RDSMySQLRotationSingleUser` (PostgreSQL usa o mesmo mecanismo adaptado)
- Rotacao: a cada 30 dias, a Lambda de rotacao gera nova senha, atualiza o usuario no Aurora e atualiza o segredo
- Sem downtime: rotacao ocorre com dual-password window de 2 horas (senha antiga permanece valida durante a janela)
- Lambda de rotacao implantada na mesma VPC com acesso ao Aurora

---

### 1.7 AWS IAM — Principio do Menor Privilegio

**Regra absoluta: zero wildcards "*" em Resource em qualquer politica de producao.**

#### IAM Role para Lambda — `socialselling-{env}-lambda-execution-role`

**Trust Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

**Permission Policy — `socialselling-{env}-lambda-permissions`:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SecretsManagerReadAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:socialselling/ENVIRONMENT/db-credentials-*",
        "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:socialselling/ENVIRONMENT/anthropic-api-key-*",
        "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:socialselling/ENVIRONMENT/tavily-api-key-*",
        "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:socialselling/ENVIRONMENT/instagram-proxy-list-*",
        "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:socialselling/ENVIRONMENT/linkedin-cookie-pool-*"
      ]
    },
    {
      "Sid": "CloudWatchLogsAccess",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:ACCOUNT_ID:log-group:/aws/lambda/socialselling-ENVIRONMENT-*:*"
    },
    {
      "Sid": "SQSSendAndReceive",
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl"
      ],
      "Resource": [
        "arn:aws:sqs:us-east-1:ACCOUNT_ID:socialselling-ENVIRONMENT-main",
        "arn:aws:sqs:us-east-1:ACCOUNT_ID:socialselling-ENVIRONMENT-dlq"
      ]
    },
    {
      "Sid": "VPCNetworkInterfaceManagement",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateNetworkInterface",
        "ec2:DescribeNetworkInterfaces",
        "ec2:DeleteNetworkInterface"
      ],
      "Resource": "arn:aws:ec2:us-east-1:ACCOUNT_ID:network-interface/*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    },
    {
      "Sid": "S3DLQArchiveWrite",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::socialselling-ENVIRONMENT-dlq-archive/*"
    }
  ]
}
```

#### IAM Role para GitHub Actions OIDC — `socialselling-github-actions-deploy-role`

**Trust Policy (com condition para repositorio especifico e branch main):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:org-name/socialselling:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

**Nota:** a condition `sub` com `ref:refs/heads/main` garante que apenas pushes/workflows da branch `main` do repositorio `org-name/socialselling` podem assumir esta role. Pull Requests de branches de feature nao conseguem acesso.

**Permission Policy — `socialselling-github-actions-deploy-permissions`:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "LambdaDeployAccess",
      "Effect": "Allow",
      "Action": [
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:GetFunction",
        "lambda:PublishVersion",
        "lambda:UpdateAlias",
        "lambda:GetAlias"
      ],
      "Resource": [
        "arn:aws:lambda:us-east-1:ACCOUNT_ID:function:socialselling-production-api",
        "arn:aws:lambda:us-east-1:ACCOUNT_ID:function:socialselling-production-consumer",
        "arn:aws:lambda:us-east-1:ACCOUNT_ID:function:socialselling-production-dlq-processor"
      ]
    },
    {
      "Sid": "ECRPushAccess",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "arn:aws:ecr:us-east-1:ACCOUNT_ID:repository/socialselling"
    },
    {
      "Sid": "ECRImagePush",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "arn:aws:ecr:us-east-1:ACCOUNT_ID:repository/socialselling"
    },
    {
      "Sid": "CloudFormationReadForDeploy",
      "Effect": "Allow",
      "Action": [
        "cloudformation:DescribeStacks",
        "cloudformation:ListStackResources"
      ],
      "Resource": "arn:aws:cloudformation:us-east-1:ACCOUNT_ID:stack/socialselling-*"
    }
  ]
}
```

---

## 2. BANCO DE DADOS E RESILIENCIA ASSINCRONA

### 2.1 Aurora Serverless v2 — RDS Proxy

**Por que RDS Proxy:** Lambda e fundamentalmente stateless — cada invocacao pode abrir uma nova conexao com o banco. Sem proxy, 10 Lambda concurrentes abrindo 5 conexoes cada = 50 conexoes. Com cold start de outros Lambdas ou bursts, o numero de conexoes explode facilmente acima de `max_connections=200`. O RDS Proxy faz connection multiplexing: mantém um pool fixo de conexoes com o Aurora e multiplexa N conexoes de Lambda sobre esse pool.

**Configuracao do RDS Proxy:**
```
IdleClientTimeout: 1800 segundos (30 min)
MaxConnectionsPercent: 90  (usa ate 90% de max_connections = 180 conexoes)
MaxIdleConnectionsPercent: 50  (mantem ate 50% idle = 90 conexoes abertas)
ConnectionBorrowTimeout: 120 segundos
RequireTLS: true
Authentication: SECRETS — credenciais via Secrets Manager
```

**Endpoints separados:**
- Writer endpoint: `socialselling-{env}-proxy.proxy-xxxx.us-east-1.rds.amazonaws.com` — para INSERTs, UPDATEs, DELETEs
- Reader endpoint: `socialselling-{env}-proxy-ro.proxy-xxxx.us-east-1.rds.amazonaws.com` — para SELECTs de analytics, dashboards, exports

**A aplicacao usa `DATABASE_URL` (writer) e `DATABASE_READ_URL` (reader) separados. Queries de leitura das rotas `/api/v1/analytics/*` e `/api/v1/reports/*` sao explicitamente roteadas para `DATABASE_READ_URL`.**

**CloudWatch Metrics monitoradas:**
| Metrica | Namespace | Threshold de Alarme | Acao |
|---|---|---|---|
| `DatabaseConnections` | `AWS/RDS` | > 180 (90% de max) | SNS -> email; investigar vazamento de conexoes |
| `ClientConnections` | `AWS/RDS` (Proxy) | > 150 | SNS -> email; pode indicar burst de Lambda acima do esperado |
| `QueryDuration` (p99) | `AWS/RDS` | > 5000ms | SNS -> email; investigar queries lentas via pg_stat_statements |
| `ACUUtilization` | `AWS/RDS` | > 80% por 5 min | SNS -> email; avaliar aumento de max ACU |
| `ReadLatency` (p99) | `AWS/RDS` | > 100ms | SNS -> email; pode indicar contenção no reader replica |
| `WriteLatency` (p99) | `AWS/RDS` | > 50ms | SNS -> email; critico para latencia do pipeline de scoring |
| `FreeLocalStorage` | `AWS/RDS` | < 20% | SNS -> email; WAL logs podem estar acumulando |

**Auto-pause por ambiente:**
- Production: `auto_pause = false` — nunca pausar; cold start de Aurora (30-60s) e inaceitavel em producao
- Staging: `auto_pause = false` — staging deve mimetizar producao
- Dev: `auto_pause = true`, `seconds_until_auto_pause = 300` — pausar apos 5 min de inatividade para economizar custo

---

### 2.2 SQS DLQ — CloudWatch Alarm Completo

**Especificacao completa do alarme Terraform:**
```hcl
resource "aws_cloudwatch_metric_alarm" "dlq_depth_alarm" {
  alarm_name          = "socialselling-${var.environment}-dlq-messages-present"
  alarm_description   = "Mensagens na DLQ indicam falha de processamento apos 3 tentativas. Requer investigacao imediata."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.dlq.name
  }

  alarm_actions = [aws_sns_topic.engineering_alerts.arn]
  ok_actions    = [aws_sns_topic.engineering_alerts.arn]

  tags = local.common_tags
}
```

**Lambda Processadora da DLQ:**
```python
# socialselling-{env}-dlq-processor
import json
import boto3
import os
import requests
from datetime import datetime

s3_client = boto3.client("s3")
ARCHIVE_BUCKET = os.environ["DLQ_ARCHIVE_BUCKET"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]  # resolvido via Secrets Manager Extension

def handler(event: dict, context) -> dict:
    for record in event["Records"]:
        message_body = json.loads(record["body"])
        message_id = record["messageId"]
        receive_count = int(record["attributes"]["ApproximateReceiveCount"])

        # Persistir em S3 para auditoria e reprocessamento manual
        now = datetime.utcnow()
        s3_key = f"{now.year}/{now.month:02d}/{now.day:02d}/{message_id}.json"
        s3_client.put_object(
            Bucket=ARCHIVE_BUCKET,
            Key=s3_key,
            Body=json.dumps({
                "message_id": message_id,
                "receive_count": receive_count,
                "body": message_body,
                "archived_at": now.isoformat(),
                "original_queue": record["eventSourceARN"]
            }),
            ContentType="application/json"
        )

        # Notificar Slack
        requests.post(
            SLACK_WEBHOOK_URL,
            json={
                "text": f":rotating_light: *DLQ Alert — SocialSelling {os.environ['ENVIRONMENT']}*",
                "attachments": [{
                    "color": "#ff0000",
                    "fields": [
                        {"title": "Message ID", "value": message_id, "short": True},
                        {"title": "Receive Count", "value": str(receive_count), "short": True},
                        {"title": "S3 Archive", "value": f"s3://{ARCHIVE_BUCKET}/{s3_key}", "short": False},
                        {"title": "Payload Preview", "value": str(message_body)[:500], "short": False}
                    ]
                }]
            },
            timeout=5
        )

    return {"statusCode": 200, "body": f"Processed {len(event['Records'])} DLQ messages"}
```

---

### 2.3 Politica de Retry e Circuit Breaker

**Lambda Retry Policy:**
- Event Source Mapping (SQS -> Lambda): Lambda recebe a mensagem e e responsavel pelo retry via VisibilityTimeout
- Se a Lambda falha (exception nao capturada ou timeout): mensagem fica invisivel por 360s, depois volta para a fila
- Apos 3 recebimentos sem sucesso: SQS move para DLQ (redrive policy)
- Lambda nao usa retry automatico da AWS (que seria adicional ao SQS) — o retry e gerenciado pelo SQS

**Circuit Breaker na Aplicacao para Scrapers:**
```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

class CircuitState(Enum):
    CLOSED = "CLOSED"    # Normal — requisicoes passam
    OPEN = "OPEN"        # Falha detectada — requisicoes bloqueadas
    HALF_OPEN = "HALF_OPEN"  # Testando recuperacao

@dataclass
class CircuitBreaker:
    failure_threshold: int = 5          # 5 falhas consecutivas -> OPEN
    recovery_timeout: timedelta = timedelta(minutes=5)  # 5 min antes de tentar HALF_OPEN
    success_threshold: int = 2          # 2 sucessos em HALF_OPEN -> CLOSED

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: datetime = field(default=None, init=False)
    _half_open_successes: int = field(default=0, init=False)

    def call_allowed(self) -> bool:
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.OPEN:
            if datetime.utcnow() - self._last_failure_time > self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_successes = 0
                return True
            return False
        return True  # HALF_OPEN

    def record_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._half_open_successes += 1
            if self._half_open_successes >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = datetime.utcnow()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
```

**Circuit breakers por scraper:**
- `instagram_circuit`: `failure_threshold=5`, `recovery_timeout=10 min` -> modo `DEGRADED_INSTAGRAM`
- `linkedin_circuit`: `failure_threshold=3`, `recovery_timeout=15 min` -> modo `DEGRADED_LINKEDIN` (threshold menor — LinkedIn tem rate limiting mais agressivo)
- `cnpj_circuit`: `failure_threshold=5`, `recovery_timeout=5 min` -> fallback para ReceitaWS antes de abrir o circuito
- `tavily_circuit`: `failure_threshold=3`, `recovery_timeout=30 min` -> `tavily_quota_exhausted=True`

**Timeout Budget por Fase:**
```python
TIMEOUT_BUDGET_SECONDS = {
    "scraping": 120,          # Instagram + LinkedIn + CNPJ em paralelo
    "entity_resolution": 30,  # RRF + Jaro-Winkler para N entidades
    "scoring": 15,            # O_score + C_score + P_score
    "blueprint": 10,          # Geracao do ConversationBlueprint via LLM
    "total_nominal": 175,     # Soma dos nominals
    "lambda_timeout": 300,    # Margem: 125s para degraded paths + cold start
}
```

A cada fase, um `asyncio.wait_for` com o timeout correspondente e aplicado. Estouro de timeout em `scraping` aciona modo degradado (nao cancela o pipeline). Estouro em `blueprint` retorna blueprint parcial com `partial=True`.

---

## 3. ESPECIFICACAO DE MODULOS TERRAFORM

### 3.1 Estrutura de Diretorios

```
terraform/
|-- backend.tf                    # S3 backend + DynamoDB state lock
|-- main.tf                       # Composicao de modulos
|-- variables.tf                  # Variaveis tipadas com validacoes
|-- outputs.tf                    # Outputs exportados
|-- locals.tf                     # Tags comuns, nome de recursos
|-- versions.tf                   # Pinagem de versao do provider AWS
|-- envs/
|   |-- dev.tfvars                # Valores para Dev
|   |-- staging.tfvars            # Valores para Staging
|   |-- production.tfvars         # Valores para Production
|-- modules/
|   |-- iam/
|   |   |-- main.tf               # Roles, policies, OIDC provider
|   |   |-- variables.tf
|   |   |-- outputs.tf
|   |-- secrets/
|   |   |-- main.tf               # Secrets Manager secrets + rotacao
|   |   |-- variables.tf
|   |   |-- outputs.tf
|   |-- aurora/
|   |   |-- main.tf               # Aurora Serverless v2, RDS Proxy, parameter groups
|   |   |-- variables.tf
|   |   |-- outputs.tf
|   |-- sqs/
|   |   |-- main.tf               # Main queue, DLQ, CloudWatch alarm, SNS
|   |   |-- variables.tf
|   |   |-- outputs.tf
|   |-- lambda/
|   |   |-- main.tf               # Lambda function, layers, event source mapping
|   |   |-- variables.tf
|   |   |-- outputs.tf
|   |-- api_gateway/
|       |-- main.tf               # HTTP API, routes, integrations, throttling, CORS
|       |-- variables.tf
|       |-- outputs.tf
```

---

### 3.2 backend.tf

```hcl
# terraform/backend.tf
# Backend S3 + DynamoDB State Lock
#
# Justificativa do DynamoDB State Lock:
# O Terraform state armazenado em S3 e um arquivo que pode ser lido e escrito
# por multiplos operadores ou pipelines CI/CD simultaneamente. Sem lock, dois
# applies concorrentes podem ler o mesmo state, calcular planos independentes,
# e sobrescrever um o outro — resultando em state corrompido ou recursos
# orfaos nao rastreados. O DynamoDB fornece um lock distribuido via operacao
# AtomicWriteItem: o primeiro apply escreve um item com chave "LockID=<path>"
# e os demais recebem ConditionalCheckFailedException, abortando ate o lock
# ser liberado. Custo negligenciavel (fracao de centavo por operacao) e
# sem dependencia de infraestrutura adicional alem do que ja existe na conta.

terraform {
  backend "s3" {
    bucket         = "socialselling-terraform-state-ACCOUNT_ID"
    key            = "socialselling/ENVIRONMENT/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    kms_key_id     = "alias/socialselling-terraform-state-key"

    dynamodb_table = "socialselling-terraform-locks"

    # Profile especifico para acesso ao estado (separado do profile de deploy)
    # Em CI/CD, credentials vem da IAM Role OIDC — sem profile necessario
    # profile = "socialselling-terraform"
  }
}
```

**Recursos pre-existentes (criados via bootstrap script — nao gerenciados pelo modulo principal):**
```hcl
# bootstrap/main.tf — executado uma unica vez por conta AWS

resource "aws_s3_bucket" "terraform_state" {
  bucket = "socialselling-terraform-state-${data.aws_caller_identity.current.account_id}"

  lifecycle {
    prevent_destroy = true  # Nunca destruir o bucket de estado
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"  # Versionamento obrigatorio — permite rollback de state
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.terraform_state.arn
    }
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket                  = aws_s3_bucket.terraform_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "terraform_locks" {
  name         = "socialselling-terraform-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Purpose = "Terraform State Locking"
    Project = "SocialSelling"
  }
}
```

---

### 3.3 main.tf

```hcl
# terraform/main.tf
# Composicao de modulos — SocialSelling Infrastructure

terraform {
  required_version = ">= 1.6.0"
}

provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = local.common_tags
  }
}

# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

data "aws_vpc" "selected" {
  id = var.vpc_id
}

data "aws_subnets" "private" {
  filter {
    name   = "subnet-id"
    values = var.private_subnet_ids
  }
}

# ---------------------------------------------------------------------------
# Modulo IAM — Roles, policies, OIDC provider para GitHub Actions
# ---------------------------------------------------------------------------

module "iam" {
  source = "./modules/iam"

  environment         = var.environment
  account_id          = data.aws_caller_identity.current.account_id
  github_org          = var.github_org
  github_repo         = var.github_repo
  lambda_function_names = [
    "socialselling-${var.environment}-api",
    "socialselling-${var.environment}-consumer",
    "socialselling-${var.environment}-dlq-processor"
  ]
  sqs_queue_arns = [
    module.sqs.main_queue_arn,
    module.sqs.dlq_arn
  ]
  secrets_arns       = module.secrets.all_secret_arns
  dlq_archive_bucket = module.sqs.dlq_archive_bucket_arn
}

# ---------------------------------------------------------------------------
# Modulo Secrets — Secrets Manager com rotacao para credenciais DB
# ---------------------------------------------------------------------------

module "secrets" {
  source = "./modules/secrets"

  environment     = var.environment
  aurora_endpoint = module.aurora.cluster_endpoint
  aurora_db_name  = "socialselling"
}

# ---------------------------------------------------------------------------
# Modulo Aurora — Aurora Serverless v2 PostgreSQL 16 + RDS Proxy
# ---------------------------------------------------------------------------

module "aurora" {
  source = "./modules/aurora"

  environment         = var.environment
  vpc_id              = var.vpc_id
  private_subnet_ids  = var.private_subnet_ids
  lambda_sg_id        = module.lambda.lambda_security_group_id

  min_acu             = var.aurora_min_acu
  max_acu             = var.aurora_max_acu
  enable_multi_az     = var.environment == "production"
  backup_retention    = var.environment == "production" ? 7 : (var.environment == "staging" ? 3 : 1)
  auto_pause          = var.environment == "dev"
  db_credentials_arn  = module.secrets.db_credentials_arn

  parameter_group_params = {
    max_connections      = "200"
    work_mem             = "65536"  # 64 MB em KB
    shared_buffers       = "262144" # 256 MB em KB
    random_page_cost     = "1.1"
    wal_level            = "logical"
    maintenance_work_mem = "131072" # 128 MB em KB
  }

  depends_on = [module.secrets]
}

# ---------------------------------------------------------------------------
# Modulo SQS — Fila principal + DLQ + CloudWatch alarm + SNS
# ---------------------------------------------------------------------------

module "sqs" {
  source = "./modules/sqs"

  environment                   = var.environment
  visibility_timeout_seconds    = 360
  message_retention_seconds     = 1209600  # 14 dias
  max_receive_count             = 3
  alert_email                   = var.engineering_alert_email
}

# ---------------------------------------------------------------------------
# Modulo Lambda — Funcoes, Layers, Event Source Mappings
# ---------------------------------------------------------------------------

module "lambda" {
  source = "./modules/lambda"

  environment           = var.environment
  vpc_id                = var.vpc_id
  private_subnet_ids    = var.private_subnet_ids
  execution_role_arn    = module.iam.lambda_execution_role_arn
  ecr_image_uri         = "${data.aws_caller_identity.current.account_id}.dkr.ecr.us-east-1.amazonaws.com/socialselling:${var.image_tag}"

  memory_mb             = var.lambda_memory_mb
  timeout_seconds       = var.lambda_timeout_seconds
  reserved_concurrency  = var.lambda_reserved_concurrency

  sqs_main_queue_arn    = module.sqs.main_queue_arn
  sqs_dlq_arn           = module.sqs.dlq_arn
  dlq_archive_bucket    = module.sqs.dlq_archive_bucket_name

  environment_variables = {
    ENVIRONMENT      = var.environment
    AWS_ACCOUNT_ID   = data.aws_caller_identity.current.account_id
    LOG_LEVEL        = var.environment == "production" ? "INFO" : "DEBUG"
    SQS_QUEUE_URL    = module.sqs.main_queue_url
    # Credenciais e API keys resolvidas em runtime via Secrets Manager Lambda Extension
    DB_SECRET_ARN              = module.secrets.db_credentials_arn
    ANTHROPIC_SECRET_ARN       = module.secrets.anthropic_api_key_arn
    TAVILY_SECRET_ARN          = module.secrets.tavily_api_key_arn
    INSTAGRAM_PROXY_SECRET_ARN = module.secrets.instagram_proxy_list_arn
    LINKEDIN_COOKIE_SECRET_ARN = module.secrets.linkedin_cookie_pool_arn
  }

  depends_on = [module.iam, module.aurora, module.sqs, module.secrets]
}

# ---------------------------------------------------------------------------
# Modulo API Gateway — HTTP API, rotas, integracao Lambda, CORS, throttling
# ---------------------------------------------------------------------------

module "api_gateway" {
  source = "./modules/api_gateway"

  environment           = var.environment
  lambda_invoke_arn     = module.lambda.api_lambda_invoke_arn
  lambda_function_name  = module.lambda.api_lambda_function_name
  allowed_origins       = var.allowed_cors_origins
  throttle_rate         = 100
  throttle_burst        = 200

  depends_on = [module.lambda]
}
```

---

### 3.4 variables.tf

```hcl
# terraform/variables.tf

variable "environment" {
  type        = string
  description = "Ambiente de implantacao. Determina escala de recursos, retencao de backup e restricoes de custo."

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "O valor de 'environment' deve ser 'dev', 'staging' ou 'production'."
  }
}

variable "aurora_min_acu" {
  type        = number
  description = "Minimo de Aurora Capacity Units para o cluster Aurora Serverless v2. Cada ACU corresponde a aproximadamente 2 GB de RAM."
  default     = 0.5

  validation {
    condition     = var.aurora_min_acu >= 0.5
    error_message = "aurora_min_acu deve ser no minimo 0.5 ACU (minimo suportado pela Aurora Serverless v2)."
  }
}

variable "aurora_max_acu" {
  type        = number
  description = "Maximo de Aurora Capacity Units para o cluster Aurora Serverless v2. Limita o custo maximo em picos de carga."

  validation {
    condition     = var.aurora_max_acu <= 128
    error_message = "aurora_max_acu nao pode exceder 128 ACU (limite maximo da Aurora Serverless v2 para PostgreSQL)."
  }

  validation {
    condition     = var.aurora_max_acu >= var.aurora_min_acu
    error_message = "aurora_max_acu deve ser maior ou igual a aurora_min_acu."
  }
}

variable "lambda_memory_mb" {
  type        = number
  description = "Memoria alocada para a Lambda em MB. Afeta diretamente a performance do CPU (CPU escala proporcionalmente a memoria no Lambda)."
  default     = 1024

  validation {
    condition     = var.lambda_memory_mb >= 512 && var.lambda_memory_mb <= 10240
    error_message = "lambda_memory_mb deve estar entre 512 MB e 10240 MB."
  }
}

variable "lambda_timeout_seconds" {
  type        = number
  description = "Timeout maximo da Lambda em segundos. Deve ser maior que o budget de tempo nominal do pipeline (175s) para acomodar degraded paths."
  default     = 300

  validation {
    condition     = var.lambda_timeout_seconds >= 60 && var.lambda_timeout_seconds <= 900
    error_message = "lambda_timeout_seconds deve estar entre 60 e 900 segundos (limite maximo do Lambda)."
  }
}

variable "lambda_reserved_concurrency" {
  type        = number
  description = "Limite maximo de execucoes concorrentes da Lambda. Protege o Aurora de sobrecarga de conexoes. Deve ser compativel com max_connections do Aurora / conexoes por Lambda."
  default     = 10

  validation {
    condition     = var.lambda_reserved_concurrency >= 1 && var.lambda_reserved_concurrency <= 1000
    error_message = "lambda_reserved_concurrency deve estar entre 1 e 1000."
  }
}

variable "vpc_id" {
  type        = string
  description = "ID da VPC onde os recursos serao implantados. Deve ser uma VPC existente com subnets privadas e NAT Gateway configurado."

  validation {
    condition     = can(regex("^vpc-[a-z0-9]{8,17}$", var.vpc_id))
    error_message = "vpc_id deve ser um VPC ID valido no formato 'vpc-xxxxxxxxxxxxxxxxx'."
  }
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Lista de IDs de subnets privadas para implantacao da Lambda e Aurora. Minimo 2 subnets em AZs distintas para Multi-AZ em producao."

  validation {
    condition     = length(var.private_subnet_ids) >= 2
    error_message = "private_subnet_ids deve conter ao menos 2 subnet IDs (necessario para Multi-AZ do Aurora em producao)."
  }

  validation {
    condition     = alltrue([for s in var.private_subnet_ids : can(regex("^subnet-[a-z0-9]{8,17}$", s))])
    error_message = "Todos os IDs em private_subnet_ids devem ser IDs validos de subnet no formato 'subnet-xxxxxxxxxxxxxxxxx'."
  }
}

variable "github_org" {
  type        = string
  description = "Nome da organizacao GitHub para a condicao da Trust Policy do OIDC. Exemplo: 'minha-org'."
}

variable "github_repo" {
  type        = string
  description = "Nome do repositorio GitHub (sem o nome da org) para a condicao da Trust Policy do OIDC. Exemplo: 'socialselling'."
}

variable "engineering_alert_email" {
  type        = string
  description = "Endereco de email da equipe de engenharia para receber alertas de DLQ, erros criticos e alarmes de CloudWatch."

  validation {
    condition     = can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.engineering_alert_email))
    error_message = "engineering_alert_email deve ser um endereco de email valido."
  }
}

variable "allowed_cors_origins" {
  type        = list(string)
  description = "Lista de origens permitidas para CORS no API Gateway. Deve incluir apenas dominios da aplicacao."
  default     = []
}

variable "image_tag" {
  type        = string
  description = "Tag da imagem Docker no ECR para deploy na Lambda. Tipicamente o SHA do commit Git ou 'latest' para dev."
  default     = "latest"
}
```

---

### 3.5 Arquivos .tfvars para 3 Ambientes

**dev.tfvars:**
```hcl
# terraform/envs/dev.tfvars
# Ambiente de desenvolvimento — recursos minimos, auto-pause habilitado, custo otimizado

environment    = "dev"
aurora_min_acu = 0.5
aurora_max_acu = 2

lambda_memory_mb              = 1024
lambda_timeout_seconds        = 300
lambda_reserved_concurrency   = 2

# Preencher com valores reais da conta AWS de dev
vpc_id             = "vpc-0a1b2c3d4e5f60001"
private_subnet_ids = ["subnet-0a1b2c3d4e5f60011", "subnet-0a1b2c3d4e5f60012"]

github_org  = "minha-org"
github_repo = "socialselling"

engineering_alert_email = "eng-dev@socialselling.com.br"

allowed_cors_origins = [
  "http://localhost:3000",
  "http://localhost:8080",
  "https://dev.socialselling.com.br"
]

image_tag = "latest"
```

**staging.tfvars:**
```hcl
# terraform/envs/staging.tfvars
# Ambiente de staging — replica configuracao de producao em escala reduzida
# Usado para validacao de releases antes de promocao para producao

environment    = "staging"
aurora_min_acu = 0.5
aurora_max_acu = 4

lambda_memory_mb              = 1024
lambda_timeout_seconds        = 300
lambda_reserved_concurrency   = 5

# Preencher com valores reais da conta AWS de staging
vpc_id             = "vpc-0a1b2c3d4e5f60002"
private_subnet_ids = ["subnet-0a1b2c3d4e5f60021", "subnet-0a1b2c3d4e5f60022"]

github_org  = "minha-org"
github_repo = "socialselling"

engineering_alert_email = "eng-staging@socialselling.com.br"

allowed_cors_origins = [
  "https://staging.socialselling.com.br"
]

image_tag = "latest"
```

**production.tfvars:**
```hcl
# terraform/envs/production.tfvars
# Ambiente de producao — recursos dimensionados para carga real
# Multi-AZ Aurora, concorrencia Lambda maxima, retencao de backup completa

environment    = "production"
aurora_min_acu = 0.5
aurora_max_acu = 8

lambda_memory_mb              = 1024
lambda_timeout_seconds        = 300
lambda_reserved_concurrency   = 10

# Preencher com valores reais da conta AWS de producao
vpc_id             = "vpc-0a1b2c3d4e5f60003"
private_subnet_ids = [
  "subnet-0a1b2c3d4e5f60031",  # us-east-1a — writer Aurora
  "subnet-0a1b2c3d4e5f60032"   # us-east-1b — reader Aurora replica
]

github_org  = "minha-org"
github_repo = "socialselling"

engineering_alert_email = "eng-prod@socialselling.com.br"

allowed_cors_origins = [
  "https://app.socialselling.com.br"
]

# image_tag nao definido aqui — sempre passado via CLI no pipeline de producao:
# terraform apply -var-file=envs/production.tfvars -var="image_tag=${GITHUB_SHA}"
# Isso garante que o SHA do commit e sempre explicitamente especificado em producao.
```

---

### 3.6 outputs.tf

```hcl
# terraform/outputs.tf

output "api_gateway_url" {
  description = "URL base do API Gateway HTTP API para o ambiente implantado. Use esta URL como base para todas as chamadas de API."
  value       = module.api_gateway.api_url
}

output "lambda_function_name" {
  description = "Nome da Lambda function principal (API handler). Use para deploy manual via AWS CLI ou para referencias em outros modulos."
  value       = module.lambda.api_lambda_function_name
}

output "aurora_cluster_endpoint" {
  description = "Endpoint do writer do cluster Aurora Serverless v2. SENSIVEL — nao logar em texto claro. Usado pela Lambda via RDS Proxy (nao diretamente)."
  value       = module.aurora.cluster_endpoint
  sensitive   = true
}

output "aurora_reader_endpoint" {
  description = "Endpoint do reader replica do Aurora (disponivel apenas em producao com Multi-AZ). SENSIVEL."
  value       = module.aurora.reader_endpoint
  sensitive   = true
}

output "rds_proxy_endpoint" {
  description = "Endpoint do RDS Proxy (writer). Este e o endpoint que a Lambda deve usar — nao o endpoint direto do Aurora."
  value       = module.aurora.rds_proxy_endpoint
  sensitive   = true
}

output "sqs_dlq_url" {
  description = "URL da SQS Dead Letter Queue. Use para inspecao manual de mensagens em falha via AWS CLI ou console."
  value       = module.sqs.dlq_url
}

output "sqs_main_queue_url" {
  description = "URL da SQS fila principal. Use para envio de mensagens de processamento assincrono."
  value       = module.sqs.main_queue_url
}

output "ecr_repository_url" {
  description = "URL do repositorio ECR para push de imagens Docker. Formato: ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/socialselling"
  value       = module.iam.ecr_repository_url
}

output "lambda_execution_role_arn" {
  description = "ARN da IAM Role de execucao da Lambda. Use para atribuir permissions adicionais se necessario."
  value       = module.iam.lambda_execution_role_arn
}

output "github_actions_role_arn" {
  description = "ARN da IAM Role para GitHub Actions OIDC. Configure esta ARN no secret AWS_ROLE_ARN do repositorio GitHub."
  value       = module.iam.github_actions_role_arn
}
```
