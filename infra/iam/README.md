# IAM — role de deploy do GitHub Actions (OIDC)

Política de permissões do **role assumido por OIDC** nos workflows de CD (WU-D2 stateful manual,
WU-D3 stateless auto). O provedor OIDC e o role já existem na AWS; os secrets `AWS_ROLE_ARN` e
`AWS_REGION` estão no repositório. Este diretório cobre só a **policy de permissões** (o que o
role pode fazer) — não a *trust policy* (quem pode assumir).

## Arquivo
- [`github-actions-deploy-policy.json`](github-actions-deploy-policy.json) — permissões para
  `sam deploy` das duas stacks.

## Premissas (importantes)
A policy é escopada por **conta `497568177086`**, **região `us-east-1`** e pelos nomes:

| Item | Convenção assumida |
|---|---|
| Stack stateful | `socialselling-stateful` (`sam deploy --stack-name socialselling-stateful`) |
| Stack stateless | `socialselling-stateless` |
| Tabela DynamoDB | `SocialSellingTable` (logical/physical name no template — SDD-2) |
| Segredos | `/socialselling/*` (SDD-2: tavily/apollo/gemini) |
| Funções/roles/regras criadas pelo CFN | prefixo `socialselling-*` (derivam do nome da stack) |
| Bucket de artefatos SAM | `aws-sam-cli-managed-default-*` (de `sam deploy --resolve-s3`) |

> Se você deployar com **outro nome de stack**, ajuste os ARNs (`socialselling-*`) na policy —
> senão o IAM scope não casa e o deploy falha por AccessDenied.

## Como aplicar
```bash
# cria a policy gerenciada
aws iam create-policy \
  --policy-name SocialSellingDeploy \
  --policy-document file://infra/iam/github-actions-deploy-policy.json

# anexa ao role do OIDC (substitua <ROLE_NAME> pelo role do AWS_ROLE_ARN)
aws iam attach-role-policy \
  --role-name <ROLE_NAME> \
  --policy-arn arn:aws:iam::497568177086:policy/SocialSellingDeploy
```

## O que cada bloco cobre
- **CloudFormation** — criar/atualizar/deletar as 2 stacks + a stack gerenciada do SAM;
  `ListExports` (para o `Fn::ImportValue ss-*` da stateless ler a stateful).
- **S3** — bucket de artefatos do SAM (`--resolve-s3`). *Alternativa mais restrita:* pré-crie um
  bucket e use `sam deploy --s3-bucket <nome>`; aí troque este bloco pelo ARN fixo do bucket.
- **Lambda / API Gateway / Step Functions / EventBridge** — recursos da stateless.
- **CloudWatch Logs** — log groups das Lambdas (`/aws/lambda/socialselling-*`) e da state machine
  (`/aws/vendedlogs/states/socialselling-*`).
- **DynamoDB / Secrets Manager** — recursos da stateful (a tabela e os 3 segredos).
- **IAM** — criar/gerenciar as roles que o CFN gera para os recursos (escopo `role/socialselling-*`)
  e **`iam:PassRole`** (passar essas roles para lambda/states/events/apigateway, com `Condition`
  `iam:PassedToService`).

## Notas de segurança
- O bloco IAM é o de maior privilégio. Está limitado a `role/socialselling-*`; para endurecer,
  use uma **permissions boundary** nas roles criadas pelo CFN (`iam:PermissionsBoundary`).
- Nada aqui dá acesso a `s3:*` global, `iam:*` global, nem a recursos fora do prefixo do projeto.
- Os tokens reais (Tavily/Apollo/Gemini) **não** entram aqui — são preenchidos manualmente no
  Secrets Manager após o primeiro deploy da stateful (WU-D2).
