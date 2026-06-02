# SDD-10: Automação de Esteiras e Governança de Código
## SocialSelling — Solution Design Document
### Versão: 1.0-MVP | Classificação: CONFIDENCIAL — ENGENHARIA

---

**Autores:** Principal DevSecOps Cloud Engineer · Staff QA Architect · Principal Enterprise Architect

**Data de emissão:** 2024-11-15 | **Ciclo de revisão:** A cada alteração de pipeline ou ambiente

---

## SEÇÃO 1: ESTEIRA DE INTEGRAÇÃO CONTÍNUA (CI)

### 1.1 Visão Geral do Workflow de CI

A esteira de Integração Contínua é acionada automaticamente em todo Pull Request aberto, sincronizado ou reaberto direcionado à branch `main`. O runner padrão é `ubuntu-latest`. A política de **fail-fast** é absoluta: qualquer step com código de saída diferente de zero interrompe imediatamente o job, sem executar steps subsequentes. Nenhum resultado parcial de qualidade é aceito — o PR somente pode ser mergeado após aprovação integral da esteira.

A esteira cobre seis camadas de qualidade em ordem sequencial e obrigatória:
1. Linting e formatação estática (Ruff)
2. Verificação de tipagem estrita (MyPy modo strict)
3. Execução da suíte de testes com cobertura mínima (PyTest)
4. Upload de cobertura para rastreabilidade histórica (Codecov)
5. Varredura de vulnerabilidades em dependências (Safety)
6. Detecção de segredos expostos no código (detect-secrets)

### 1.2 Workflow YAML Completo — `.github/workflows/ci.yml`

```yaml
name: CI — Integração Contínua

on:
  pull_request:
    branches:
      - main
    types: [opened, synchronize, reopened]

jobs:
  quality:
    name: Qualidade de Código
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      - name: Checkout do repositório
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Necessário para análise de histórico pelo detect-secrets

      - name: Configurar Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Instalar dependências de desenvolvimento
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-dev.txt
        # requirements-dev.txt inclui: ruff, mypy, pytest, pytest-cov,
        # pytest-mock, responses, pytest-asyncio, safety, detect-secrets,
        # codecov, jellyfish, langchain, langgraph, fastapi, httpx

      - name: Linting — Ruff (check de erros e style)
        run: |
          ruff check . --output-format=github
        # --output-format=github formata erros como GitHub annotations
        # visíveis inline no diff do PR

      - name: Formatação — Ruff Format
        run: |
          ruff format --check .
        # Falha se qualquer arquivo estiver fora do padrão de formatação
        # Desenvolvedor deve rodar `ruff format .` localmente antes do commit

      - name: Tipagem Estática — MyPy (modo strict)
        run: |
          mypy app/ \
            --strict \
            --ignore-missing-imports \
            --disallow-untyped-defs \
            --disallow-incomplete-defs \
            --check-untyped-defs \
            --no-implicit-optional \
            --warn-redundant-casts \
            --warn-unused-ignores \
            --disallow-any-generics \
            --disallow-subclassing-any
        # Qualquer função sem anotação de tipo → build quebra
        # Qualquer retorno implícito sem tipo → build quebra

      - name: Testes — PyTest com Cobertura Mínima
        env:
          TESTING: "true"
          # Scrapers são mockados via pytest-mock; banco via SQLite in-memory
          DATABASE_URL: "sqlite+aiosqlite:///:memory:"
          OPENAI_API_KEY: "sk-test-mock-key-not-real"
          TAVILY_API_KEY: "tvly-test-mock-key-not-real"
        run: |
          pytest tests/ \
            --cov=app \
            --cov-report=xml \
            --cov-report=term-missing \
            --cov-fail-under=80 \
            --tb=short \
            -v \
            --timeout=60 \
            -m "not integration"
        # -m "not integration": testes de integração rodam apenas no CD de Staging
        # --timeout=60: nenhum teste unitário deve exceder 60 segundos
        # --cov-fail-under=80: cobertura abaixo de 80% quebra o build

      - name: Upload de Cobertura para Codecov
        if: always()
        uses: codecov/codecov-action@v4
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
          files: coverage.xml
          fail_ci_if_error: true
          flags: unit-tests
          name: socialselling-ci-coverage

      - name: Varredura de Vulnerabilidades — Safety (CVE scan)
        run: |
          pip install safety
          safety check \
            --full-report \
            --policy-file .safety-policy.yml
        # .safety-policy.yml define quais CVEs são ignorados (ex: alertas de dev only)
        # CVEs de severidade CRITICAL ou HIGH → build quebra obrigatoriamente

      - name: Detecção de Segredos Expostos — detect-secrets
        run: |
          pip install detect-secrets
          detect-secrets scan \
            --baseline .secrets.baseline \
            --exclude-files "tests/fixtures/.*\.json"
          detect-secrets audit \
            .secrets.baseline \
            --report \
            --fail-on-unaudited
        # Qualquer segredo não auditado (senha, chave de API, token) → build quebra
        # .secrets.baseline deve ser mantido atualizado no repositório
```

### 1.3 Configuração Ruff — `pyproject.toml`

```toml
[tool.ruff]
target-version = "py312"
line-length = 100
src = ["app", "tests"]

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # Pyflakes (imports não usados, variáveis indefinidas)
    "I",    # isort (ordenação de imports)
    "B",    # flake8-bugbear (bugs comuns e más práticas)
    "C4",   # flake8-comprehensions (list/dict comprehensions desnecessárias)
    "UP",   # pyupgrade (sintaxe Python moderna)
    "SIM",  # flake8-simplify (simplificações de código)
    "S",    # flake8-bandit (verificações de segurança estática)
    "ANN",  # flake8-annotations (anotações de tipo obrigatórias)
    "RET",  # flake8-return (retornos explícitos)
    "PTH",  # flake8-use-pathlib (uso de pathlib ao invés de os.path)
]
ignore = [
    "E501",   # line-length: enforced pelo formatter, não pelo linter
    "S101",   # assert: permitido em testes (pytest)
    "S105",   # hardcoded-password: falsos positivos em nomes de variáveis de teste
    "ANN101", # missing-type-self: desnecessário para métodos de instância
    "ANN102", # missing-type-cls: desnecessário para métodos de classe
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S", "ANN"]  # Testes: sem verificações de segurança ou anotações obrigatórias

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"
```

### 1.4 Configuração MyPy — `mypy.ini`

```ini
[mypy]
python_version = 3.12
strict = True
ignore_missing_imports = True
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
disallow_incomplete_defs = True
check_untyped_defs = True
disallow_untyped_decorators = True
no_implicit_optional = True
warn_redundant_casts = True
warn_unused_ignores = True
warn_no_return = True
no_implicit_reexport = True
show_error_codes = True
show_column_numbers = True

# Exceções para bibliotecas sem stubs completos
[mypy-jellyfish.*]
ignore_missing_imports = True

[mypy-langchain.*]
ignore_missing_imports = True

[mypy-langgraph.*]
ignore_missing_imports = True

[mypy-responses.*]
ignore_missing_imports = True

[mypy-playwright.*]
ignore_missing_imports = True

[mypy-psycopg2.*]
ignore_missing_imports = True

[mypy-asyncpg.*]
ignore_missing_imports = True
```

### 1.5 Configuração PyTest — `pyproject.toml` (seção pytest)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"        # Todos os testes async rodam automaticamente
timeout = 60                  # Timeout global por teste em segundos
addopts = "--strict-markers --strict-config -ra"
# --strict-markers: falha se marcador não declarado for usado
# --strict-config: falha se configuração inválida for encontrada
# -ra: exibe resumo de todos os testes que não passaram (skipped, xfailed, etc.)

filterwarnings = [
    "error",                  # Transforma todos os warnings em erros
    "ignore::DeprecationWarning:langchain",
    "ignore::PendingDeprecationWarning",
]

markers = [
    "unit: Testes unitários puros — sem I/O externo, scrapers mockados, banco in-memory",
    "integration: Testes de integração — requerem banco PostgreSQL real em Docker",
    "bdd: Testes de comportamento BDD (pytest-bdd) — validam critérios de aceitação de negócio",
    "smoke: Testes de fumaça — validam funcionalidade básica pós-deploy em ambiente real",
    "slow: Testes que levam mais de 10 segundos — executados somente em pipelines completas",
]
```

### 1.6 Critérios de Quebra de Build — Política de Qualidade

Qualquer uma das condições abaixo interrompe o build **imediatamente**, bloqueando o merge do PR:

**Condição 1 — Violação de Linting (Ruff):** qualquer erro de estilo, import desordenado, prática proibida (bandit), ou arquivo fora do padrão de formatação. Saída: código de erro no step de Ruff → job falhado.

**Condição 2 — Erro de Tipagem (MyPy strict):** qualquer função sem anotação de tipo, retorno sem tipo declarado, uso de `Any` implícito, ou chamada de função com tipos incompatíveis. Modo `strict=True` é inegociável — nenhuma exceção sem `# type: ignore[specific-code]` documentado.

**Condição 3 — Cobertura Abaixo de 80% (`--cov-fail-under=80`):** a cobertura de linhas do módulo `app/` deve ser igual ou superior a 80% em toda execução de CI. Funções matemáticas críticas (`scoring.py`, `freshness.py`, `rcs.py`) exigem 100% de cobertura via configuração no `.coveragerc`.

**Condição 4 — Teste Falhando:** qualquer asserção de teste que retorne `FAILED` ou `ERROR` — incluindo testes de tipo `parametrize` e fixtures de setup/teardown. Não existe "flaky test" tolerado em CI — testes instáveis são removidos ou corrigidos imediatamente.

**Condição 5 — CVE Crítico ou Alto em Dependências (Safety):** qualquer CVE com CVSS score ≥ 7.0 detectado nas dependências diretas ou transitivas de `requirements.txt`. Dependências devem ser atualizadas ou o CVE explicitamente auditado e excetuado no `.safety-policy.yml` com justificativa documentada.

**Condição 6 — Segredo Exposto (detect-secrets):** qualquer string identificada como chave de API, senha, token OAuth, credencial de banco ou hash de autenticação presente no código-fonte, comentários ou arquivos de configuração versionados. Segredos nunca devem existir em código — apenas em AWS Secrets Manager ou variáveis de ambiente de CI.

---

## SEÇÃO 2: ESTEIRA DE IMPLANTAÇÃO CONTÍNUA (CD)

### 2.1 Autenticação AWS via OIDC — SEM Chaves Estáticas

A esteira de CD utiliza **OpenID Connect (OIDC)** para autenticação na AWS, eliminando completamente o uso de `AWS_ACCESS_KEY_ID` e `AWS_SECRET_ACCESS_KEY` como segredos estáticos no repositório GitHub.

**Configuração do OIDC Identity Provider na AWS:**

```json
{
  "Url": "https://token.actions.githubusercontent.com",
  "ClientIDList": ["sts.amazonaws.com"],
  "ThumbprintList": ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}
```

**IAM Role Trust Policy — `socialselling-github-actions-deploy-staging`:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:org/socialselling:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

**Por que OIDC e não chaves estáticas:**

Chaves estáticas (`AWS_ACCESS_KEY_ID` fixas) apresentam três riscos estruturais inaceitáveis para um sistema de produção: (1) podem ser expostas acidentalmente em logs de CI, histórico de commits ou issues do GitHub; (2) precisam de rotação manual periódica — processo sujeito a erro humano e interrupção de serviço; (3) uma vez comprometidas, permanecem válidas até revogação manual.

O token OIDC gerado pelo GitHub Actions expira automaticamente em **1 hora**, é específico para o repositório e branch declarados na Trust Policy, é auditável no CloudTrail com contexto do job específico que o emitiu, e nunca é armazenado — é gerado fresh a cada execução do workflow.

### 2.2 Workflow YAML Completo — `.github/workflows/cd-staging.yml`

```yaml
name: CD — Deploy para Staging

on:
  push:
    branches:
      - main
  workflow_run:
    workflows: ["CI — Integração Contínua"]
    types: [completed]
    branches: [main]

permissions:
  id-token: write    # OBRIGATÓRIO para AssumeRoleWithWebIdentity via OIDC
  contents: read     # Necessário para actions/checkout

jobs:
  deploy-staging:
    name: Deploy Staging
    runs-on: ubuntu-latest
    environment: staging    # GitHub Environment com suas próprias variáveis e segredos
    timeout-minutes: 30

    # Só executa se o CI anterior passou (quando acionado por workflow_run)
    if: ${{ github.event.workflow_run.conclusion == 'success' || github.event_name == 'push' }}

    steps:
      - name: Checkout do repositório
        uses: actions/checkout@v4

      - name: Configurar Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Autenticação AWS via OIDC (Staging)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN_STAGING }}
          aws-region: us-east-1
          role-session-name: GitHubActions-Staging-${{ github.run_id }}-${{ github.run_attempt }}

      - name: Build do pacote de deploy (zip)
        run: |
          pip install -r requirements.txt -t package/ --quiet
          cp -r app/ package/
          cd package && zip -r ../socialselling-staging-${{ github.sha }}.zip . -q
          echo "Tamanho do pacote: $(du -sh ../socialselling-staging-${{ github.sha }}.zip | cut -f1)"

      - name: Fazer upload do pacote para S3 (versionamento)
        run: |
          aws s3 cp socialselling-staging-${{ github.sha }}.zip \
            s3://socialselling-deployments/staging/socialselling-staging-${{ github.sha }}.zip \
            --region us-east-1
          echo "Pacote armazenado em S3 para rollback: staging/${{ github.sha }}"

      - name: Deploy para Lambda (Staging)
        run: |
          aws lambda update-function-code \
            --function-name socialselling-handler-staging \
            --s3-bucket socialselling-deployments \
            --s3-key staging/socialselling-staging-${{ github.sha }}.zip \
            --region us-east-1

      - name: Aguardar Lambda estar ativa (Staging)
        run: |
          aws lambda wait function-updated \
            --function-name socialselling-handler-staging \
            --region us-east-1
          echo "Lambda atualizada com sucesso — commit ${{ github.sha }}"

      - name: Executar testes de integração pós-deploy (Staging)
        env:
          API_BASE_URL: ${{ secrets.STAGING_API_URL }}
          API_KEY: ${{ secrets.STAGING_API_KEY }}
          TESTING_ENV: "staging"
        run: |
          pip install pytest pytest-asyncio httpx --quiet
          pytest tests/integration/ \
            --tb=short \
            -v \
            -m integration \
            --timeout=120 \
            --junit-xml=test-results-staging.xml

      - name: Publicar resultados dos testes de integração
        if: always()
        uses: dorny/test-reporter@v1
        with:
          name: Integration Tests — Staging
          path: test-results-staging.xml
          reporter: java-junit

      - name: Notificação Slack — Deploy Staging bem-sucedido
        if: success()
        uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {
              "text": "✅ *Deploy Staging concluído*\nCommit: `${{ github.sha }}`\nAtor: ${{ github.actor }}\nWorkflow: ${{ github.workflow }}",
              "channel": "#deployments"
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}

      - name: Notificação Slack — Falha no Deploy Staging
        if: failure()
        uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {
              "text": "🔴 *FALHA no Deploy Staging*\nCommit: `${{ github.sha }}`\nAtor: ${{ github.actor }}\nLink: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}",
              "channel": "#deployments"
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### 2.3 Workflow YAML Completo — `.github/workflows/cd-production.yml`

```yaml
name: CD — Deploy para Production

on:
  workflow_dispatch:
    inputs:
      confirm_deploy:
        description: "CONFIRMAÇÃO OBRIGATÓRIA: Digite 'production' para autorizar o deploy"
        required: true
        type: string
      release_notes:
        description: "Notas desta release (obrigatório para auditoria)"
        required: true
        type: string

permissions:
  id-token: write
  contents: read

jobs:
  validate-input:
    name: Validar Confirmação de Deploy
    runs-on: ubuntu-latest
    steps:
      - name: Verificar confirmação explícita
        run: |
          if [ "${{ github.event.inputs.confirm_deploy }}" != "production" ]; then
            echo "❌ CONFIRMAÇÃO INVÁLIDA. Deploy cancelado por segurança."
            echo "Para realizar o deploy, o campo de confirmação deve conter exatamente: production"
            exit 1
          fi
          echo "✅ Confirmação válida. Prosseguindo com deploy para Production."
          echo "📋 Notas da release: ${{ github.event.inputs.release_notes }}"

  deploy-production:
    name: Deploy Production
    needs: validate-input
    runs-on: ubuntu-latest
    environment: production    # Requer aprovação manual obrigatória dos líderes de engenharia
    timeout-minutes: 45

    steps:
      - name: Checkout do repositório
        uses: actions/checkout@v4

      - name: Configurar Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Autenticação AWS via OIDC (Production)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN_PRODUCTION }}
          aws-region: us-east-1
          role-session-name: GitHubActions-Production-${{ github.run_id }}-${{ github.actor }}
          # role-session-name inclui actor para rastreabilidade no CloudTrail

      - name: Verificar que versão de Staging foi validada
        env:
          API_BASE_URL: ${{ secrets.STAGING_API_URL }}
          API_KEY: ${{ secrets.STAGING_API_KEY }}
        run: |
          # Validar que o commit atual está deployado e saudável em Staging
          STAGING_VERSION=$(curl -sf -H "X-API-Key: $API_KEY" \
            "$API_BASE_URL/api/v1/health" | python3 -c "import sys,json; print(json.load(sys.stdin)['commit_sha'])")
          if [ "$STAGING_VERSION" != "${{ github.sha }}" ]; then
            echo "❌ BLOQUEIO DE SEGURANÇA: Commit ${{ github.sha }} não está validado em Staging."
            echo "Staging está rodando: $STAGING_VERSION"
            echo "Deploy para Production requer validação prévia em Staging."
            exit 1
          fi
          echo "✅ Commit validado em Staging. Prosseguindo para Production."

      - name: Build do pacote de deploy (Production)
        run: |
          pip install -r requirements.txt -t package/ --quiet
          cp -r app/ package/
          cd package && zip -r ../socialselling-production-${{ github.sha }}.zip . -q

      - name: Upload do pacote para S3 Production (com versioning habilitado)
        run: |
          aws s3 cp socialselling-production-${{ github.sha }}.zip \
            s3://socialselling-deployments/production/socialselling-production-${{ github.sha }}.zip \
            --region us-east-1
          # S3 versioning habilitado no bucket: mantém todas as versões para rollback

      - name: Deploy para Lambda (Production)
        run: |
          aws lambda update-function-code \
            --function-name socialselling-handler-production \
            --s3-bucket socialselling-deployments \
            --s3-key production/socialselling-production-${{ github.sha }}.zip \
            --region us-east-1

      - name: Aguardar Lambda Production estar ativa
        run: |
          aws lambda wait function-updated \
            --function-name socialselling-handler-production \
            --region us-east-1

      - name: Smoke test Production
        env:
          API_BASE_URL: ${{ secrets.PRODUCTION_API_URL }}
          API_KEY: ${{ secrets.PRODUCTION_API_KEY }}
        run: |
          pip install pytest pytest-asyncio httpx --quiet
          pytest tests/smoke/ \
            -v \
            --timeout=30 \
            --junit-xml=test-results-production-smoke.xml
        # Smoke tests: verificam apenas que os endpoints respondem e o banco está acessível
        # Não executam scraping real nem modificam dados de produção

      - name: Publicar tag de release no Git
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git tag -a "release-$(date +%Y%m%d-%H%M)-${{ github.sha:0:7 }}" \
            -m "Release para Production: ${{ github.event.inputs.release_notes }}"
          git push origin --tags

      - name: Notificação Slack — Deploy Production bem-sucedido
        if: success()
        uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {
              "text": "🚀 *Deploy PRODUCTION concluído*\nCommit: `${{ github.sha }}`\nAprovado por: ${{ github.actor }}\nRelease: ${{ github.event.inputs.release_notes }}",
              "channel": "#deployments-production"
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_PRODUCTION }}

      - name: Notificação Slack — FALHA em Production
        if: failure()
        uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {
              "text": "🔴 *FALHA CRÍTICA em Production*\nCommit: `${{ github.sha }}`\nAtor: ${{ github.actor }}\nIniciar procedimento de rollback imediatamente.\nLink: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}",
              "channel": "#incidents"
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_PRODUCTION }}
```

---

## SEÇÃO 3: GOVERNANÇA E PROMOÇÃO DE AMBIENTES

### 3.1 GitHub Environments — Environment Protection Rules

**Development (ambiente dev):**

O ambiente de desenvolvimento não possui Environment Protection Rules no GitHub. Deploys são automáticos e imediatos a cada push em branches de feature. O objetivo é maximizar a velocidade de iteração. Variáveis de ambiente do Development apontam exclusivamente para recursos AWS com sufixo `-dev`, completamente isolados de Staging e Production em contas AWS distintas (Account Isolation Strategy).

Segredos disponíveis no ambiente Development:
- `AWS_ROLE_ARN_DEV`: ARN da IAM Role OIDC para a conta AWS Development
- `DEV_API_URL`: URL base da API em Development
- `DEV_API_KEY`: Chave de API admin para testes manuais em Development

**Staging (ambiente staging):**

O ambiente Staging possui as seguintes proteções:
- **Sem aprovação manual**: deploy automático após merge em `main` e conclusão bem-sucedida do CI
- **Required check**: testes de integração (`pytest tests/integration/ -m integration`) devem passar após cada deploy antes que qualquer promoção para Production seja liberada
- **Deployment branches**: restrito à branch `main` exclusivamente
- **Wait timer**: 0 minutos (deploy imediato após CI)

O ambiente Staging espelha Production em configuração, mas com volumes de dados reduzidos. Aurora Serverless v2 com Max ACU = 4 (vs. 8 em Production). Dados de Staging são dados sintéticos gerados pelo fixture loader — nunca dados reais de leads ou prospects.

**Production (ambiente production):**

O ambiente Production possui as proteções mais rígidas do sistema:

- **Aprovação manual obrigatória**: pelo menos **1 líder de engenharia** listado como Reviewer deve aprovar explicitamente o deploy no GitHub antes que o job `deploy-production` seja executado
- **Wait timer**: 5 minutos após aprovação (janela de cancelamento de emergência)
- **Deployment branches**: restrito à branch `main` exclusivamente
- **Required check**: o job `validate-input` (confirmação explícita "production") deve passar antes da aprovação dos líderes ser solicitada
- **Verificação de Staging**: o workflow verifica automaticamente que o commit a ser deployado está rodando saudável em Staging antes de prosseguir para Production

Reviewers de Production configurados no GitHub Environment:
- `@lead-engineer-1` (responsável técnico sênior)
- `@lead-engineer-2` (backup técnico)
- Mínimo: 1 dos 2 deve aprovar (sem necessidade de aprovação dupla para agilidade operacional)

### 3.2 Estratégia de Branching — Trunk-Based Development

O repositório SocialSelling adota **Trunk-Based Development simplificado**: existe uma única branch de longa duração (`main`), que deve ser sempre deployável para qualquer ambiente.

**Regras de branching:**
- Toda feature, correção ou refatoração começa em uma branch de curta duração criada a partir de `main`
- Prefixos obrigatórios: `feat/`, `fix/`, `chore/`, `docs/`, `test/`, `perf/`
- Prazo máximo de vida de uma branch: **2 dias úteis** (evita divergência excessiva do trunk)
- Merge obrigatoriamente via Pull Request — nunca push direto em `main`

**Branch Protection Rules em `main`:**

```yaml
# Configuração via GitHub API ou terraform-github-repository
protection_rules:
  main:
    required_status_checks:
      strict: true              # Branch deve estar atualizada com main antes do merge
      contexts:
        - "CI — Integração Contínua / Qualidade de Código"
    required_pull_request_reviews:
      required_approving_review_count: 1
      dismiss_stale_reviews: true    # Review é invalidada quando novo commit é pushado
      require_code_owner_reviews: true
    enforce_admins: true             # Líderes de engenharia também seguem as regras
    allow_force_pushes: false        # Proibido absolutamente
    allow_deletions: false           # Branch main não pode ser deletada
    required_linear_history: true    # Rebase obrigatório — sem merge commits no trunk
```

**CODEOWNERS (`.github/CODEOWNERS`):**

```
# Owners globais — qualquer alteração requer review de pelo menos um
*                    @lead-engineer-1 @lead-engineer-2

# Infraestrutura e CI/CD: review obrigatório do DevSecOps
infrastructure/      @devsecops-lead
.github/workflows/   @devsecops-lead

# Módulos matemáticos críticos: review obrigatório do Arquiteto de Sistemas
app/scoring/         @systems-architect
app/scoring/         @lead-engineer-1
```

### 3.3 Testes de Integração Pós-Deploy Staging

Os testes de integração executam contra a API real do ambiente Staging após cada deploy bem-sucedido. Eles usam dados sintéticos (nenhum scraper real é invocado — as respostas são interceptadas por um VCR cassette pré-gravado) e verificam o comportamento end-to-end do sistema.

**Cobertura obrigatória dos testes de integração:**

1. **Conexão com Aurora PostgreSQL**: verificar que a Lambda consegue abrir pool de conexões via RDS Proxy e executar SELECT 1 com latência < 200ms
2. **Endpoints da API — health check**: `GET /api/v1/health` deve retornar 200 com campos `status: "healthy"`, `database: "connected"`, `commit_sha`
3. **Endpoint de ciclos**: `POST /api/v1/cycles` com payload válido deve retornar 202 Accepted e `cycle_id` no formato UUID
4. **Endpoint de leads**: `GET /api/v1/leads?cycle_id=<test_cycle>&limit=5` deve retornar array paginado com campo `p_score` em [0,1]
5. **Endpoint de XAI payload**: `GET /api/v1/leads/<test_lead_id>` deve retornar payload com todos os campos obrigatórios do contrato (lead_id, scores, xai_drivers, buying_committee, approach_blueprint, data_quality)
6. **Webhook CRM**: `POST /api/v1/webhooks/crm` com HMAC-SHA256 válido deve retornar 202 Accepted e criar registro em `crm_outcome_log`
7. **Atualização de ICP contract**: `PUT /api/v1/icp-contract` com pesos somando 1.000 deve retornar novo `contract_id` com `version_hash`

**Bloqueio de promoção para Production:** o job `deploy-production` verifica explicitamente (via step "Verificar que versão de Staging foi validada") se o mesmo commit está rodando saudável em Staging antes de prosseguir. Qualquer falha nos testes de integração de Staging bloqueia automaticamente o deploy para Production, pois o check de saúde de Staging falhará.

### 3.4 Rollback de Emergência

**Rollback de Lambda (aplicação):**

Todos os pacotes de deploy são armazenados no S3 com naming convention `{env}/socialselling-{env}-{git_sha}.zip`. O bucket S3 possui versionamento habilitado. Para rollback:

```bash
# 1. Identificar o SHA da versão anterior saudável
aws s3 ls s3://socialselling-deployments/production/ | sort -r | head -10

# 2. Fazer rollback para a versão anterior
aws lambda update-function-code \
  --function-name socialselling-handler-production \
  --s3-bucket socialselling-deployments \
  --s3-key production/socialselling-production-<SHA_ANTERIOR>.zip \
  --region us-east-1

# 3. Aguardar propagação
aws lambda wait function-updated \
  --function-name socialselling-handler-production

# 4. Executar smoke tests para confirmar rollback
pytest tests/smoke/ -v --timeout=30
```

Tempo estimado de rollback: **2–4 minutos** (sem rebuild, apenas redeployar zip do S3).

**Rollback de banco de dados (Aurora PostgreSQL — PITR):**

O Aurora Serverless v2 possui Point-in-Time Recovery (PITR) com granularidade de até 5 minutos, com retenção de 7 dias em Production. Para rollback de schema ou dados:

```bash
# Restaurar cluster para um ponto específico no tempo
aws rds restore-db-cluster-to-point-in-time \
  --db-cluster-identifier socialselling-cluster-production-restored \
  --source-db-cluster-identifier socialselling-cluster-production \
  --restore-to-time 2024-11-15T14:00:00Z \
  --engine aurora-postgresql \
  --db-cluster-instance-class db.serverless \
  --region us-east-1
```

O procedimento de rollback completo (Lambda + banco) é testado em Staging trimestralmente, com tempo de RTO (Recovery Time Objective) alvo de 15 minutos para restauração completa de produção.

### 3.5 Inventário de GitHub Secrets por Ambiente

| Secret | Ambiente | Valor / Descrição |
|---|---|---|
| `AWS_ROLE_ARN_STAGING` | Staging | ARN da IAM Role OIDC para Staging: `arn:aws:iam::123456789012:role/socialselling-github-actions-deploy-staging` |
| `AWS_ROLE_ARN_PRODUCTION` | Production | ARN da IAM Role OIDC para Production: `arn:aws:iam::987654321098:role/socialselling-github-actions-deploy-production` |
| `STAGING_API_URL` | Staging | URL base da API: `https://api.socialselling.staging.internal` |
| `STAGING_API_KEY` | Staging | Chave de API admin para testes de integração em Staging |
| `PRODUCTION_API_URL` | Production | URL base da API: `https://api.socialselling.production.internal` |
| `PRODUCTION_API_KEY` | Production | Chave de API admin para smoke tests em Production |
| `CODECOV_TOKEN` | Repositório (global) | Token para upload de cobertura ao Codecov.io |
| `SLACK_WEBHOOK_URL` | Repositório (global) | Webhook do Slack para notificações de CI/CD (canal #deployments) |
| `SLACK_WEBHOOK_PRODUCTION` | Production | Webhook do Slack para notificações críticas de Production (canal #incidents) |

**Regras de gestão de segredos:**
- Nenhum segredo de Production é visível para desenvolvedores sem acesso de Owner ao repositório GitHub
- Rotação de segredos a cada 90 dias (enforced via GitHub Actions scheduled workflow que alerta quando segredos estão próximos de expirar)
- Chaves de API do Codecov e Slack têm escopo mínimo (apenas write:coverage e incoming webhook, respectivamente)
- `AWS_ROLE_ARN_*` são ARNs (não credenciais) — não representam risco de segurança se expostos, mas são mantidos como segredos por boa prática de auditoria

---

*SDD-10 | SocialSelling MVP | Versão 1.0 | Revisão: a cada alteração de pipeline*
