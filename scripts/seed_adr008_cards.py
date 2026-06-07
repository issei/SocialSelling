#!/usr/bin/env python
"""Seed dos 27 cards do roadmap ADR-008 (MVP Serverless AWS) no GitHub Project #1.

Cria todos os cards em **Backlog**, com corpo no template DoR e Priority por fase.
Fonte: ADR-008 + SDD-1 (borda) + SDD-2 (IaC) + SDD-3 (Ports & Adapters) +
camada DevOps CI/CD (docs/planning/adr-008-backlog-plan.md).

Uso:
    py scripts/seed_adr008_cards.py --dry-run   # so lista, nao cria
    py scripts/seed_adr008_cards.py             # cria os cards via `gh`

AVISO: NAO deduplica. Rodar duas vezes duplica os cards. Rodar UMA vez.
Todos entram em Backlog (autoria de dia). O dono move Backlog->Todo com DoR 100%.
Requer `gh` autenticado com escopo project (gh auth refresh -s project,read:project).
"""
# ruff: noqa: E501  -- corpos de card sao prosa longa (Gherkin/DoR); nao reflow.
from __future__ import annotations

import argparse
import json
import subprocess
import sys

OWNER = "issei"
NUMBER = "1"
PROJECT_ID = "PVT_kwHOAAi2gM4BZ3J3"
STATUS_FID = "PVTSSF_lAHOAAi2gM4BZ3J3zhUy5Jg"  # Status
BACKLOG = "6cf82daa"
TODO = "f75ad846"
DONE = "98236657"
PRIO_FID = "PVTSSF_lAHOAAi2gM4BZ3J3zhUzDd8"  # Priority
PRIO_OPT = {"Alta": "da3cda2e", "Media": "dd378f56", "Baixa": "8ffead41"}

TAMANHO = "\n\n## Tamanho\n1 WU (1-2 passos / uma janela; termina em checkpoint seguro)."

_DOR_ITEMS = [
    "Objetivo observavel em 1 frase",
    "Cabe em 1 WU (1-2 passos / uma janela)",
    "Contrato entrada->saida definido (ADR-008/SDD vinculada)",
    "Gherkin: feliz + degradado + Open-World",
    "Fixtures identificadas (ou modulo puro); sem bloqueio de rede-paga",
    "Sem decisao de fronteira em aberto",
    "Dentro do escopo (CLAUDE.md 3/5, ADR-000/008) e deterministico (1e-9, APIs/AWS mockadas)",
    "DoD especifico declarado acima",
]

# WUs que estao Ready (DoR 100%) e devem ir para Todo. WU-X1 (acao externa do dono)
# e WU-D3 (deploy auto depende do Cognito vivo) permanecem em Backlog (bloqueio).
READY = {
    "WU-P1", "WU-P2", "WU-P3", "WU-P4", "WU-P5", "WU-P6", "WU-P7", "WU-P8",
    "WU-B1", "WU-B2", "WU-B3", "WU-B4", "WU-B5", "WU-B6", "WU-B7",
    "WU-I1", "WU-I2", "WU-I3", "WU-I4", "WU-I5", "WU-I6", "WU-I7", "WU-I8",
    "WU-D1", "WU-D2",
}
# WUs concluidas fora do ciclo de desenvolvimento (acao operacional do dono).
DONE_CARDS = {"WU-X1"}

BLOCK_REASON = {
    "WU-D3": "Cognito ✅ resolvido (WU-X1: User Pool us-east-1_o17XMPejk + vars publicadas). "
             "Bloqueio restante = ORDEM: so desenvolver/mergear apos WU-I2 (template stateless) "
             "e a execucao manual de WU-D2 (deploy da Stateful 1x) — senao o deploy auto na main "
             "quebraria por falta dos exports ss-*. Promover para Todo nesse ponto.",
}
DONE_NOTE = {
    "WU-X1": "Cognito User Pool `us-east-1_o17XMPejk` + app client `54ofg7c96p74niqbdibfkrtavv` "
             "provisionados (2026-06-07); GitHub vars COGNITO_ISSUER/COGNITO_AUDIENCE publicadas.",
}

# Plano de execucao por card (passos concretos + arquivos-alvo, ancorados na arvore real).
PLANS = {
    "WU-P1": """## Plano de execucao
1. Criar `src/socialselling/core/repositories/__init__.py` e `base.py`.
2. Definir as 4 ABCs (`abc.ABC` + `@abstractmethod`) com as assinaturas exatas do SDD-3 secao 2; tipar com `from socialselling.contracts import LeadCard`.
3. Teste `tests/test_repositories_base.py`: instanciar cada ABC levanta `TypeError`.
4. Gate: `ruff` + `mypy --strict`.""",
    "WU-P2": """## Plano de execucao
1. Criar `core/repositories/local_json.py` com `LocalJSONRepository` (4 Ports).
2. **Delegar** (sem reimplementar) para os stores existentes: corpus->`corpus/store.py`; cache->`core/cache.py`; ledgers->`core/credit_ledger.py`/`core/request_ledger.py`; feedback->`learning/feedback_store.py`; waves->`corpus/waves.py`. Escrita via `core/atomic.py`.
3. `user_id` aceito e fixo (tenant logico unico) — paridade byte-identica.
4. Smoke E2E byte-identico + cenarios de atomicidade.""",
    "WU-P3": """## Plano de execucao
1. Criar `tests/support/fake_repository.py` (`FakeRepository` em memoria, dicts) implementando as 4 ABCs.
2. Upsert idempotente por `entity_id`; leitura ausente -> None.
3. Expor via fixture em `tests/conftest.py` para o nucleo.""",
    "WU-P4": """## Plano de execucao
1. Criar `tests/features/persistence_contract.feature` + steps em `tests/steps/`.
2. Parametrizar a bateria contra `LocalJSONRepository` (P2) e `FakeRepository` (P3).
3. Cenarios: upsert idempotente (1e-9), atomicidade, cache T-24h, ledger cap (sem escrita parcial), ordenacao estavel.""",
    "WU-P5": """## Plano de execucao
1. Criar `core/repositories/dynamodb.py` (UNICO modulo com `import boto3`).
2. Mapear Ports -> `PutItem`/`GetItem`/`UpdateItem`/`Query` + `ConditionExpression` (concorrencia otimista; cap de saldo). Chaves PK/SK do SDD-2 secao 2.
3. Testes com `botocore.stub.Stubber` (sem rede); rodar a MESMA `persistence_contract.feature` contra ele.""",
    "WU-P6": """## Plano de execucao
1. Adicionar `persistence_mode` em `config.py` (`[runtime]`) + `config/runtime.toml` (default "local").
2. Criar `core/repositories/factory.py: build_repositories(cfg)` retornando o conjunto de Ports concretas.
3. Modo invalido -> `ValueError` (fail-fast). Teste cobre local/aws/invalido.""",
    "WU-P7": """## Plano de execucao
1. Refatorar `orchestrator.py` (composition root) para construir os repositorios via factory e injeta-los em M1-M5/corpus/learning por parametro.
2. Remover acesso direto a arquivo/`boto3` dos modulos puros.
3. Guard no gate: `grep` falha se houver `import boto3` ou caminho de arquivo fora dos adapters. Paridade local byte-identica.""",
    "WU-P8": """## Plano de execucao
1. Em `tests/conftest.py`, fixture `autouse` que bloqueia rede (monkeypatch em `socket.socket`) e falha o teste se houver tentativa de conexao.
2. Mensagem clara apontando o teste infrator.
3. Cenario "gate offline" verde; documentar no `dor-dod`/`gate`.""",
    "WU-B1": """## Plano de execucao
1. Criar `src/socialselling/edge/__init__.py` + `edge/contracts.py` com os 7 schemas (`extra="forbid"`).
2. Reusar `ICPCriteria`/`LeadCard`/`ProspectScore`/`XAIPayload`/`OperatingMode` de `contracts.py`.
3. Teste: `RunRequest` rejeita `user_id` no corpo; `mypy --strict`.""",
    "WU-B2": """## Plano de execucao
1. Criar `edge/run_handler.py: handle(event) -> PipelineTrigger`.
2. Extrair `sub` de `$context.authorizer.claims.sub`; `now` de `requestTimeEpoch` (ISO); `run_id = sha256(user_id+icp_id+now-truncado)`.
3. Fixture de evento APIGW em `tests/fixtures/edge/`; StartSyncExecution mockado.""",
    "WU-B3": """## Plano de execucao
1. Criar `edge/serialize.py`: `RankedProspect[] + LeadCard[] -> RunResponse` (sem recomputar).
2. Ordenar `leads` por rank; preencher `finops` e `operating_mode`.
3. Fixture do output do SFN; asserir byte-identico (1e-9).""",
    "WU-B4": """## Plano de execucao
1. Criar `edge/errors.py: classify(cause) -> (ApiError, status)` conforme tabela SDD-1 secao 3.
2. Preservar a mensagem CRUA do provedor (L-057); billing -> `actionable_hint` com link.
3. Fixtures de `error.Cause` (RPD, billing, 5xx).""",
    "WU-B5": """## Plano de execucao
1. Declarar o estado `Catch` global -> `FormatError` na ASL (placeholder em `infra/stateless/statemachine/`).
2. Testar por fixture do output do SFN (erro -> ApiError correto).
3. Billing nao-retentavel vai direto ao Catch (sem retry).""",
    "WU-B6": """## Plano de execucao
1. Criar `openapi/socialselling.yaml` (POST /runs + esquemas de erro) congruente com os contratos.
2. Adicionar lint OpenAPI no CI (`openapi-spec-validator` via pip, offline).
3. Asserir que campos do yaml batem com `RunRequest`/`RunResponse`/`ApiError`.""",
    "WU-B7": """## Plano de execucao
1. Teste e2e da borda com fixtures: corpus previo + cognicao indisponivel -> 200 `DEGRADED_GEMINI`.
2. Cota sem corpus -> 429 (nunca "0 leads").
3. Lead sem intent -> visivel + `explanation.missing_signals` preenchido.""",
    "WU-I1": """## Plano de execucao
1. Criar `infra/stateful/template.yaml` (SAM): DynamoDB PAY_PER_REQUEST, PK/SK, TTL `expires_at`, 3 SecretsManager, `DeletionPolicy/UpdateReplacePolicy: Retain`, Exports `ss-*`.
2. Teste: parse YAML afirma `Retain` e schema PK/SK.
3. `sam validate` offline no gate.""",
    "WU-I2": """## Plano de execucao
1. Criar `infra/stateless/template.yaml` (SAM): fn-m1..m5, fn-run-handler, fn-wave, StateMachine, API Gateway, EventBridge; importar `ss-*` via `Fn::ImportValue`.
2. Autorizador JWT do Cognito com **Parameters** `CognitoIssuer`/`CognitoAudience` (sem default) — valores so no deploy; `sam validate` passa offline.
3. Teste afirma imports e o autorizador na rota.""",
    "WU-I3": """## Plano de execucao
1. Criar `infra/stateless/statemachine/pipeline.asl.json` (M1->M2->M3->M4->M5 + Catch->FormatError).
2. Runner local de teste executa a ASL com fixtures de cada modulo.
3. Ordem e saida byte-identicas (1e-9).""",
    "WU-I4": """## Plano de execucao
1. Adicionar `Retry`/`TimeoutSeconds` por estado na ASL (M1=30s/2x; M2=120s/3x base2s; M3-5=15s/1x).
2. Distinguir 429 transitorio (retry) de billing duro (Catch direto).
3. Testes de retry/backoff com mocks.""",
    "WU-I5": """## Plano de execucao
1. Criar `src/socialselling/aws/handlers/m1.py`..`m5.py` (wrappers finos).
2. Cada wrapper: le segredo (Secrets Manager), injeta `DynamoDBRepository` (P5/P6) + `now`, chama a funcao pura, serializa. SEM regra de negocio; modulos puros INALTERADOS.
3. Testes com repo fake + segredo mock (sem AWS).""",
    "WU-I6": """## Plano de execucao
1. Criar `src/socialselling/aws/handlers/wave.py` envolvendo `corpus/waves.py` -> `accumulate_and_rank`.
2. Regra EventBridge `cron(0 6 * * ? *)` no template -> `StartExecution` assincrono.
3. Avanco de `WAVE#STATE` SOMENTE com leads novos (L-056); cenario verde.""",
    "WU-I7": """## Plano de execucao
1. Centralizar a derivacao de chaves (PK=`USER#<user_id>`, SK por tipo) em `core/repositories/dynamodb.py` (ou `keys.py`).
2. Teste de chaves: cada tipo (LEAD/CACHE/LEDGER/FEEDBACK/WAVE) gera o PK/SK esperado.
3. `entity_id`/`company_id` por hash estavel (sem UUID/relogio).""",
    "WU-I8": """## Plano de execucao
1. Declarar policies IAM por funcao no `infra/stateless/template.yaml`: so a `SocialSellingTable` importada + o segredo do modulo.
2. Sem privilegio cruzado entre modulos.
3. Revisao + `sam validate`.""",
    "WU-D1": """## Plano de execucao
1. Editar `.github/workflows/ci.yml`: adicionar setup do SAM CLI + passo `sam validate` para `infra/stateful` e `infra/stateless`.
2. Sem credenciais AWS no job (validacao local). Fail-closed se template invalido.""",
    "WU-D2": """## Plano de execucao
1. Criar `.github/workflows/cd-stateful.yml`: `on: workflow_dispatch`; `environment:` com required reviewers; `permissions: id-token: write`.
2. `aws-actions/configure-aws-credentials@v4` assumindo `${{ secrets.AWS_ROLE_ARN }}` em `${{ secrets.AWS_REGION }}`; `sam build`/`sam deploy` da stateful.
3. Nunca em push.""",
    "WU-D3": """## Plano de execucao
1. Criar `.github/workflows/cd-stateless.yml`: `on: push` (main, apos gate); OIDC com `${{ secrets.AWS_ROLE_ARN }}`/`${{ secrets.AWS_REGION }}`; `sam deploy` da stateless (`Fn::ImportValue`).
2. **NAO mergear ate o Cognito existir** (deploy automatico falharia). Liberar apos WU-X1 + WU-I2.""",
    "WU-X1": """## Plano de execucao (acao do dono — externa ao repo)
1. Provisionar o Cognito User Pool + app client (fora deste repo).
2. Publicar `COGNITO_ISSUER` e `COGNITO_AUDIENCE` como GitHub vars.
3. Avisar para destravar WU-I2 (deploy) e WU-D3.""",
}


def _dor_block(ready: bool) -> str:
    mark = "x" if ready else " "
    lines = "\n".join(f"- [{mark}] {it}" for it in _DOR_ITEMS)
    return f"\n\n## DoR (checklist -- TODOS [x] para ir a Todo)\n{lines}"


def build_full(code: str, body: str) -> str:
    """Monta o corpo final: body + plano de execucao + Tamanho + DoR + nota de status."""
    plano = PLANS.get(code, "")
    done = code in DONE_CARDS
    ready = code in READY
    full = body + "\n\n" + plano + TAMANHO + _dor_block(done or ready)
    if done:
        full += f"\n\n> ✅ CONCLUÍDA (2026-06-07): {DONE_NOTE.get(code, '')}"
    elif ready:
        full += "\n\n> ✅ DoR completo (2026-06-07) — refinada e pronta para Todo."
    else:
        full += f"\n\n> ⛔ BLOQUEADO (manter em Backlog): {BLOCK_REASON.get(code, 'ver dependencias')}"
    return full

# (titulo, Priority, corpo) — corpo sem o bloco DoR (apendado automaticamente).
CARDS: list[tuple[str, str, str]] = [
    # ============ FASE 1 — Persistencia bimodal (SDD-3) ============
    ("WU-P1 - Ports de persistencia (ABCs)", "Alta", """\
## Objetivo
Definir as 4 interfaces abstratas (Ports) que isolam o core do meio de armazenamento, habilitando a bimodalidade local<->AWS sem tocar regra de negocio.

## Contrato (entrada -> saida)
`src/socialselling/core/repositories/base.py`: `BaseCorpusRepository`, `BaseCacheRepository`, `BaseLedgerRepository`, `BaseFeedbackRepository` com assinaturas imutaveis (SDD-3 secao 2). Reusa tipos de `contracts.py`. ADR-008 secao 5.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado as 4 ABCs definidas, Entao mypy --strict fica limpo e nenhuma e instanciavel diretamente.
- Degradado:  Dado um metodo de leitura sem dado, Entao a assinatura permite retorno None/vazio (incerteza), nunca excecao.
- Open-World: Dado BaseFeedbackRepository, Entao por tipo so aceita componentes de score (fit/intent/confidence/persona_fit), nunca ObservedEvidence/Inference.

## Fixtures necessarias
Nenhuma (apenas interfaces; modulo puro).

## Fora de escopo
Implementacoes concretas (P2/P3/P5); factory (P6).

## Dependencias / bloqueios
Nenhum (card fundacional).

## DoD especifico
ABCs nao instanciaveis; assinaturas batem com SDD-3 secao 2; mypy --strict limpo; sem boto3 nem caminho de arquivo."""),

    ("WU-P2 - LocalJSONRepository (paridade com baseline)", "Alta", """\
## Objetivo
Implementar o adapter local que mantem paridade byte-identica com o baseline pre-ADR-008, reusando core/atomic.py e os stores existentes.

## Contrato (entrada -> saida)
`LocalJSONRepository` implementa as 4 Ports (P1) sobre `core/atomic.py` (write-temp + os.replace) e os layouts JSON/NDJSON existentes. SDD-3 secao 3.1. user_id = tenant unico logico (aceito e fixo).

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado persistence_mode=local, Quando o pipeline roda o smoke E2E, Entao a saida e byte-identica ao baseline anterior (1e-9).
- Degradado:  Dado escrita interrompida apos o temp e antes do replace, Entao o arquivo final permanece a versao anterior integra.
- Open-World: Dado entity_id inexistente, Quando corpus.get e chamado, Entao retorna None (incerteza), sem ocultar nem quebrar.

## Fixtures necessarias
Reusa fixtures existentes do baseline; nenhuma nova de rede.

## Fora de escopo
DynamoDBRepository (P5); factory (P6).

## Dependencias / bloqueios
WU-P1.

## DoD especifico
Cenarios "paridade com baseline" e "atomicidade" verdes; reusa corpus/store.py, cache.py e ledgers sem reimplementar logica."""),

    ("WU-P3 - FakeRepository em memoria (duble de teste)", "Alta", """\
## Objetivo
Prover um duble em memoria das 4 Ports para testar o nucleo rapido, offline e deterministico.

## Contrato (entrada -> saida)
`FakeRepository` implementa as ABCs de P1 com armazenamento em dict. SDD-3 secao 5.1 (principio 1).

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado o FakeRepository, Quando o nucleo roda contra ele, Entao nao ha I/O e o resultado e deterministico.
- Degradado:  Dado leitura ausente, Entao retorna None/vazio.
- Open-World: Dado upsert repetido do mesmo entity_id, Entao ha uma unica entrada (idempotente).

## Fixtures necessarias
Nenhuma (em memoria; modulo puro).

## Fora de escopo
Persistencia real; contract tests (P4).

## Dependencias / bloqueios
WU-P1.

## DoD especifico
Nucleo testavel sem I/O; honra idempotencia e ordenacao; mypy --strict limpo."""),

    ("WU-P4 - Bateria de contract tests compartilhada", "Alta", """\
## Objetivo
Garantir, com uma unica bateria de comportamento, que todos os adapters honram idempotencia, atomicidade e ordenacao deterministica.

## Contrato (entrada -> saida)
`tests/features/persistence_contract.feature` roda contra LocalJSONRepository (P2) e FakeRepository (P3). SDD-3 secao 5.1 (principio 2) e secao 6.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado upsert duas vezes do mesmo card em Local e Fake, Entao o corpus resultante e identico (uma entrada, 1e-9) e a ordenacao por score e estavel.
- Degradado:  Dado LEDGER#FINOPS saldo Apollo=1, Quando consume(amount=2), Entao retorna False e o saldo permanece 1 (sem escrita parcial).
- Open-World: Dado cache gravado em now-25h, Quando cache.get com now atual, Entao retorna None (T-24h) e nao fabrica lead de cache vencido.

## Fixtures necessarias
Nenhuma de rede (dubles/arquivos locais).

## Fora de escopo
DynamoDBRepository (coberto na mesma bateria em P5).

## Dependencias / bloqueios
WU-P2, WU-P3.

## DoD especifico
A mesma bateria passa contra Local e Fake; cenarios de idempotencia/atomicidade/ordenacao verdes e deterministicos."""),

    ("WU-P5 - DynamoDBRepository (boto3, Conditional Expressions)", "Media", """\
## Objetivo
Implementar o adapter AWS sobre a Single Table, com atomicidade/idempotencia por Conditional Expressions, isolado em um unico modulo.

## Contrato (entrada -> saida)
`core/repositories/dynamodb.py` mapeia as Ports para PutItem/GetItem/UpdateItem/Query (SDD-3 secao 3.2; chaves SDD-2 secao 2). boto3 vive SO aqui.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado um LeadCard entity_id "sha256:abc" do tenant "user-abc", Quando upsert via boto3 stubado, Entao gera PK "USER#user-abc"/SK "LEAD#sha256:abc" e reescrever e idempotente (version incrementa).
- Degradado:  Dado ledger com saldo 1, Quando consume(amount=2) com ConditionExpression balance>=:amount, Entao falha sem escrita parcial.
- Open-World: Dado GetItem sem item, Entao retorna None (incerteza), nunca excecao.

## Fixtures necessarias
Stub de boto3 (PutItem/GetItem/UpdateItem/Query) -- SEM rede, SEM AWS real, SEM LocalStack.

## Fora de escopo
Templates SAM (I1/I2); deploy (D2/D3).

## Dependencias / bloqueios
WU-P1, WU-P4 (roda a mesma bateria com boto3 stubado).

## DoD especifico
Mesma bateria de contract tests passa com boto3 stubado; grep confirma que boto3 NAO e importado fora deste modulo."""),

    ("WU-P6 - Factory + chaveamento [runtime].persistence_mode", "Media", """\
## Objetivo
Selecionar o adapter por configuracao em um unico ponto (composition root), sem o nucleo instanciar repositorios.

## Contrato (entrada -> saida)
`core/repositories/factory.py: build_repositories(cfg)` le `[runtime].persistence_mode` ("local"|"aws") e devolve as instancias. ADR-008 secao 5; SDD-3 secao 4.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado persistence_mode="local", Entao a factory devolve LocalJSON*; "aws" devolve DynamoDB*.
- Degradado:  Dado persistence_mode invalido, Entao falha cedo com ValueError claro (fail-fast).
- Open-World: Dado modo "local", Entao o comportamento e identico ao baseline (paridade).

## Fixtures necessarias
Nenhuma (config; modulo puro).

## Fora de escopo
Refactor dos modulos para receber as Ports (P7).

## Dependencias / bloqueios
WU-P2, WU-P5.

## DoD especifico
Selecao correta por flag; modo invalido falha cedo; teste cobre os 3 ramos."""),

    ("WU-P7 - Refactor do nucleo p/ injecao de Ports", "Media", """\
## Objetivo
Fazer M1-M5, corpus e learning dependerem SO das Ports (injecao de dependencia), eliminando acoplamento a arquivo/boto3.

## Contrato (entrada -> saida)
Modulos puros recebem repositorios por parametro; nenhum import de boto3 nem caminho de arquivo. ADR-008 secao 5; SDD-3 secao 7 (WU-P7).

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado o nucleo refatorado, Quando roda com FakeRepository, Entao o pipeline funciona sem I/O real.
- Degradado:  Dado repositorio que retorna None, Entao o nucleo trata como incerteza, nao quebra.
- Open-World: Dado modo local, Entao a saida E2E permanece byte-identica ao baseline (paridade preservada).

## Fixtures necessarias
Reusa fixtures existentes; nenhuma nova de rede.

## Fora de escopo
Wrappers Lambda (I5).

## Dependencias / bloqueios
WU-P6.

## DoD especifico
Grep/lint no gate confirma zero import de boto3/caminho de arquivo nos modulos puros; paridade local byte-identica."""),

    ("WU-P8 - Guard de CI: proibe rede/credenciais/LocalStack", "Media", """\
## Objetivo
Travar no CI que nenhum teste nativo abra rede, use credencial real ou LocalStack -- mantendo o gate 100% offline.

## Contrato (entrada -> saida)
Guard de teste (ex.: fixture autouse que bloqueia socket) + checagem no gate. SDD-3 secao 5.1 (principio 3) e secao 7 (WU-P8).

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado ambiente de CI sem credenciais AWS e sem LocalStack, Quando gate roda, Entao ruff+mypy+pytest passam 100% verdes.
- Degradado:  Dado um teste que tenta abrir conexao, Entao o guard FALHA o teste (fail-closed).
- Open-World: Dado ausencia de chave de API, Entao a suite roda igual (tudo mockado).

## Fixtures necessarias
Nenhuma (infra de teste).

## Fora de escopo
sam validate no gate (D1).

## Dependencias / bloqueios
WU-P4.

## DoD especifico
Cenario "gate offline" verde; CI falha se algum teste tentar rede."""),

    # ============ FASE 2 — Borda BaaS (SDD-1) ============
    ("WU-B1 - edge/contracts.py (schemas da borda)", "Media", """\
## Objetivo
Definir os contratos da camada de borda, garantindo anti-spoofing de tenant por contrato (RunRequest sem user_id).

## Contrato (entrada -> saida)
`src/socialselling/edge/contracts.py`: UserContext, RunRequest, PipelineTrigger, RunResponse, LeadEnvelope, FinOpsSummary, ApiError (extra=forbid). Reusa ICPCriteria/LeadCard/ProspectScore/XAIPayload. SDD-1 secao 2.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado os schemas definidos, Entao mypy --strict fica limpo.
- Degradado:  Dado ApiError, Entao carrega error_code/message cru/provider/actionable_hint/operating_mode (causa nao mascarada).
- Open-World: Dado um corpo com campo user_id, Entao RunRequest rejeita (extra=forbid) -- tenant so vem do token.

## Fixtures necessarias
Nenhuma (contratos puros).

## Fora de escopo
Handler (B2); serializador (B3).

## Dependencias / bloqueios
WU-P1 (reuso de contracts).

## DoD especifico
RunRequest rejeita user_id no corpo (teste); mypy --strict limpo; schemas batem com SDD-1 secao 2."""),

    ("WU-B2 - run_handler: monta PipelineTrigger do evento APIGW", "Media", """\
## Objetivo
Extrair user_id da claim sub (token validado), injetar now do gatilho e derivar run_id por hash estavel, acionando o pipeline.

## Contrato (entrada -> saida)
`edge/run_handler.py`: evento APIGW -> PipelineTrigger (user_context.user_id = $context.authorizer.claims.sub; now = requestTimeEpoch ISO; run_id = SHA-256(user_id+icp_id+now-truncado)). persistence_mode="aws". SDD-1 secao 1/2.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado JWT valido sub "user-abc" e ICP "icp-talita", Quando POST /runs, Entao user_context.user_id="user-abc" e run_id = hash estavel de (user-abc, icp-talita, 2026-06-07).
- Degradado:  Dado billing esgotado a jusante, Entao a borda nao inventa mensagem -- propaga o ApiError (B4).
- Open-World: Dado corpo com user_id "user-victim", Entao e ignorado; nenhum dado de "user-victim" e acessado.

## Fixtures necessarias
Evento APIGW mockado + StartSyncExecution mockado por fixture (sem AWS).

## Fora de escopo
Serializacao da saida (B3); mapeamento de erro (B4).

## Dependencias / bloqueios
WU-B1.

## DoD especifico
Cenarios "feliz", "determinismo" (run_id identico) e "anti-spoofing" verdes; run_id nunca uuid4."""),

    ("WU-B3 - Serializador da saida unificada (m5 -> RunResponse)", "Media", """\
## Objetivo
Serializar a saida da maquina de estados em RunResponse sem recomputar nada do pipeline.

## Contrato (entrada -> saida)
RankedProspect[] + LeadCard[] -> RunResponse (leads: LeadEnvelope[] ordenado por rank; finops; operating_mode; generated_at=now). SDD-1 secao 2.3.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado a saida do SFN mockada, Quando serializa, Entao cada lead traz card, card.score e explanation, ordenado por rank.
- Degradado:  Dado operating_mode DEGRADED_GEMINI, Entao a resposta reflete o modo sem ocultar leads.
- Open-World: Dado mesma entrada de execucao anterior, Entao a serializacao de leads e byte-identica (1e-9).

## Fixtures necessarias
Fixture do output do Step Functions (mock).

## Fora de escopo
Recomputo de score/ranking (proibido); mapeamento de erro (B4).

## Dependencias / bloqueios
WU-B1, WU-B2.

## DoD especifico
Resposta byte-identica para a mesma entrada (1e-9); a borda nao recomputa pipeline."""),

    ("WU-B4 - errors.py: classificador/mapeador FinOps -> ApiError", "Media", """\
## Objetivo
Traduzir error.Cause da maquina de estados em ApiError + status HTTP correto, preservando a mensagem CRUA do provedor (L-057).

## Contrato (entrada -> saida)
`edge/errors.py`: error.Cause -> (ApiError, status). Tabela SDD-1 secao 3: RPD esgotado=429 GEMINI_RPD_EXHAUSTED; billing=429 GEMINI_BILLING_DEPLETED+link; upstream=502 UPSTREAM_5XX; JWT=401.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado erro de modulo capturado, Entao vira ApiError correto com status mapeado.
- Degradado:  Dado 429 "prepayment credits depleted" com link de billing, Entao 429 GEMINI_BILLING_DEPLETED, message = mensagem do provedor (nao generico) e actionable_hint com o link.
- Open-World: Dado RPD esgotado mas com corpus previo, Entao 200 degradado com leads conhecidos; sem corpus, 429 (nunca "0 leads" silencioso).

## Fixtures necessarias
Fixtures de error.Cause (RPD, billing L-057, 5xx) -- mockadas.

## Fora de escopo
Estado Catch/FormatError da ASL (B5).

## Dependencias / bloqueios
WU-B1.

## DoD especifico
Cenarios 429 (RPD), 429 (billing L-057) e 502 verdes; mensagem crua preservada (nunca reescrita em generico)."""),

    ("WU-B5 - Estado Catch/FormatError da maquina de estados", "Baixa", """\
## Objetivo
Garantir que qualquer excecao de modulo seja capturada e formatada em ApiError, sem quebrar a borda.

## Contrato (entrada -> saida)
Definicao do estado Catch global -> FormatError que devolve {error_code, message, provider, actionable_hint}. Testado por fixture do output do SFN. SDD-1 secao 3; SDD-2 secao 3.1.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado um modulo que lanca excecao, Quando a ASL roda, Entao roteia para FormatError e termina sem quebrar.
- Degradado:  Dado billing nao-retentavel, Entao vai direto ao Catch (sem retry) com GEMINI_BILLING_DEPLETED.
- Open-World: Dado erro de sensor com corpus previo, Entao degrada e mantem leads, nao quebra a maquina.

## Fixtures necessarias
Fixture do output do SFN com erro (mock; sem AWS).

## Fora de escopo
Politicas de retry/timeout (I4).

## Dependencias / bloqueios
WU-B4.

## DoD especifico
Erro de modulo nunca quebra a borda; vira o ApiError correto; testado por fixture do output do SFN."""),

    ("WU-B6 - Contrato OpenAPI estrito + lint", "Baixa", """\
## Objetivo
Publicar o contrato OpenAPI de POST /runs como fronteira estrita com o cockpit externo.

## Contrato (entrada -> saida)
`openapi/socialselling.yaml`: POST /runs + esquemas de erro, congruente com RunRequest/RunResponse/ApiError. SDD-1 secao 5 (WU-B6). Lint OpenAPI no CI.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado o yaml, Quando o lint OpenAPI roda, Entao passa sem erros.
- Degradado:  Dado os esquemas de erro, Entao 401/429/502 estao documentados com ApiError.
- Open-World: Dado RunResponse, Entao operating_mode e missing_signals estao no schema (degradacao visivel).

## Fixtures necessarias
Nenhuma (artefato declarativo).

## Fora de escopo
Geracao de SDK do cliente; repositorio do frontend.

## Dependencias / bloqueios
WU-B1, WU-B3, WU-B4.

## DoD especifico
Lint OpenAPI verde no CI; yaml congruente com os contratos Pydantic (campos batem)."""),

    ("WU-B7 - Cenario Open-World ponta-a-ponta da borda", "Baixa", """\
## Objetivo
Provar que degradacao com corpus previo nunca produz "vazio silencioso" e que ausencia de sinal nao rebaixa lead a falso.

## Contrato (entrada -> saida)
Teste E2E da borda com fixtures: cognicao indisponivel + corpus previo -> 200 DEGRADED_GEMINI com leads conhecidos. SDD-1 secao 4 (cenarios Open-World).

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado tenant com corpus e cognicao indisponivel, Quando POST /runs, Entao 200 DEGRADED_GEMINI com leads previos.
- Degradado:  Dado cota esgotada sem corpus, Entao 429 (nao "0 leads").
- Open-World: Dado lead sem intent recente, Entao permanece visivel com confianca reduzida e explanation.missing_signals lista o sinal ausente.

## Fixtures necessarias
Fixtures de corpus previo + SFN degradado (mock).

## Fora de escopo
Implementacao dos handlers (B2/B3/B4 ja entregues).

## Dependencias / bloqueios
WU-B3, WU-B4.

## DoD especifico
Cenarios Open-World verdes; nenhum "vazio silencioso"; nenhum lead marcado falso por ausencia de sinal."""),

    # ============ FASE 3 — IaC multi-stack (SDD-2) ============
    ("WU-I1 - Stateful Stack: DynamoDB Single Table + segredos (Retain)", "Baixa", """\
## Objetivo
Declarar a stack de dados que sobrevive a deploys: Single Table + 3 segredos, com Retain e TTL.

## Contrato (entrada -> saida)
`infra/stateful/template.yaml` (SAM): DynamoDB PAY_PER_REQUEST, PK/SK, TTL expires_at, 3 SecretsManager, DeletionPolicy/UpdateReplacePolicy Retain, Exports (ss-TableName, ss-TableArn...). SDD-2 secao 2.4.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado o template, Quando sam validate, Entao passa e o teste afirma DeletionPolicy Retain e schema PK/SK.
- Degradado:  Dado re-deploy da Stateless, Entao tabela e segredos nao sao marcados para substituicao/delecao.
- Open-World: Dado item sem prefixo de tenant, Entao e invalido por design (PK sempre USER#).

## Fixtures necessarias
Nenhuma (template declarativo; sam validate offline).

## Fora de escopo
Stateless Stack (I2); deploy (D2).

## Dependencias / bloqueios
WU-P5 (modelagem de chaves alinhada).

## DoD especifico
sam validate ok; teste afirma Retain e schema PK/SK; Exports presentes."""),

    ("WU-I2 - Stateless Stack: Lambdas + SFN + APIGW + EventBridge", "Baixa", """\
## Objetivo
Declarar a stack descartavel de codigo importando os exports da Stateful, com o autorizador JWT na borda.

## Contrato (entrada -> saida)
`infra/stateless/template.yaml` (SAM): fn-m1..m5, fn-run-handler, fn-wave, StateMachine, API Gateway (autorizador JWT Cognito), EventBridge; importa ss-* via Fn::ImportValue. SDD-2 secao 3.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado o template, Quando sam validate, Entao passa e ARNs vem de Fn::ImportValue.
- Degradado:  Dado o autorizador, Entao JWT ausente/invalido => 401 antes de qualquer Lambda.
- Open-World: Dado erro de modulo, Entao o fluxo cai no Catch (B5), nao quebra.

## Fixtures necessarias
Nenhuma (template; sam validate offline).

## Fora de escopo
ASL detalhada (I3); deploy (D3).

## Dependencias / bloqueios
WU-I1, WU-B2. BLOQUEIO EXTERNO: Cognito issuer/audience (WU-X1) -- via GitHub vars; ate la, BLOCKED.

## DoD especifico
sam validate ok; imports via Fn::ImportValue; autorizador JWT referenciando issuer/audience por parametro/var."""),

    ("WU-I3 - Definicao ASL da maquina de estados (M1->M5 + Catch)", "Baixa", """\
## Objetivo
Especificar a ASL sequencial M1->M2->M3->M4->M5 com Catch->FormatError, verificavel por runner local de teste.

## Contrato (entrada -> saida)
ASL (JSON) da PipelineStateMachine; cada Task invoca o wrapper do modulo. SDD-2 secao 3.1.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado um PipelineTrigger valido e fixtures de cada modulo, Quando a ASL roda no runner local, Entao os estados ocorrem na ordem M1->M2->M3->M4->M5 e a saida e byte-identica (1e-9).
- Degradado:  Dado excecao em um estado, Entao roteia para Catch->FormatError.
- Open-World: Dado sensor indisponivel com corpus previo, Entao degrada o operating_mode, mantem leads.

## Fixtures necessarias
Fixtures de cada modulo (mock) + runner local da ASL (sem AWS).

## Fora de escopo
Retry/backoff/timeout (I4).

## Dependencias / bloqueios
WU-I2, WU-B5.

## DoD especifico
Runner local executa a ASL com fixtures; ordem e saida deterministicas."""),

    ("WU-I4 - Politicas de retry/backoff e timeouts", "Baixa", """\
## Objetivo
Configurar retries/timeouts por estado, distinguindo erro transitorio (retry) de billing duro (Catch direto).

## Contrato (entrada -> saida)
Retry/timeout na ASL: M1=30s/2x base2s; M2=120s/3x base2s (alinha [gemini]); M3/M4/M5=15s/1x. SDD-2 secao 3.2.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado M2 com 429 transitorio 2x e depois 200, Quando a ASL roda, Entao M2 conclui apos retries com backoff exponencial.
- Degradado:  Dado 429 "prepayment credits depleted", Entao nenhum retry e feito e vai ao FormatError com GEMINI_BILLING_DEPLETED.
- Open-World: Dado retry esgotado com corpus previo, Entao degrada o operating_mode em vez de quebrar.

## Fixtures necessarias
Fixtures de respostas 429 transitorio vs billing duro (mock).

## Fora de escopo
Wrappers (I5).

## Dependencias / bloqueios
WU-I3.

## DoD especifico
Cenarios "429 transitorio dispara retry" e "billing nao-retentavel vai ao Catch" verdes."""),

    ("WU-I5 - Wrappers Lambda fn-m1..fn-m5 (injetam repo + now)", "Baixa", """\
## Objetivo
Envelopar cada modulo puro em um Lambda fino que le segredo, injeta DynamoDBRepository + now e serializa o contrato -- sem regra de negocio.

## Contrato (entrada -> saida)
fn-m1..fn-m5: leem Secrets Manager, injetam repo (P5/P6) e now, chamam a funcao pura, serializam. SDD-2 secao 3.3. Modulos puros INALTERADOS.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado um wrapper com repo fake, Quando invocado, Entao chama a funcao pura e serializa o contrato corretamente.
- Degradado:  Dado segredo ausente, Entao falha clara (sem mascarar) e o fluxo degrada via Catch.
- Open-World: Dado now injetado do payload, Entao a saida e deterministica (sem datetime.now()/uuid4 internos).

## Fixtures necessarias
Repo fake + segredo mockado (sem AWS, sem rede).

## Fora de escopo
EventBridge/onda (I6).

## Dependencias / bloqueios
WU-P5, WU-P6.

## DoD especifico
Modulos puros inalterados; wrappers testados com repo fake; sem datetime.now()/uuid4 internos."""),

    ("WU-I6 - fn-wave + regra EventBridge (cron noturno condicional)", "Baixa", """\
## Objetivo
Disparar as ondas noturnas por cron gerenciado, avancando a onda SOMENTE quando o ciclo produz leads (L-056).

## Contrato (entrada -> saida)
fn-wave envelopa corpus/waves.py -> accumulate_and_rank; Rule EventBridge cron(0 6 * * ? *) -> StartExecution assincrono. SDD-2 secao 3.5.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado gatilho EventBridge, Quando fn-wave roda e ha leads novos, Entao WAVE#STATE avanca e o corpus e persistido.
- Degradado:  Dado cognicao degradada (sem leads novos), Entao WAVE#STATE NAO avanca (L-056) e o corpus previo permanece intacto.
- Open-World: Dado sensor indisponivel, Entao a onda nao "queima" -- nada e perdido.

## Fixtures necessarias
Repo fake + gatilho EventBridge simulado (sem AWS).

## Fora de escopo
Borda sincrona (B*).

## Dependencias / bloqueios
WU-I5.

## DoD especifico
Cenario "onda nao avanca sem leads" verde; corpus previo intacto."""),

    ("WU-I7 - Mapeamento Single Table dos discriminadores SK", "Baixa", """\
## Objetivo
Garantir que cada tipo de item gere o PK/SK esperado a partir de entity_id/company_id, com isolamento por tenant.

## Contrato (entrada -> saida)
Mapeamento SK: LEAD#<entity_id>, CACHE#<hash>, LEDGER#FINOPS, FEEDBACK#<company_id>, WAVE#STATE; PK=USER#<user_id>. SDD-2 secao 2.2.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado um lead entity_id "sha256:abc" do tenant "user-abc", Entao o item tem PK "USER#user-abc"/SK "LEAD#sha256:abc".
- Degradado:  Dado dois consumos concorrentes de credito, Entao a Conditional Expression impede saldo negativo/escrita parcial.
- Open-World: Dado item sem tenant, Entao e impossivel por design (PK sempre USER#).

## Fixtures necessarias
boto3 stub; nenhuma rede.

## Fora de escopo
Templates (I1); IAM (I8).

## Dependencias / bloqueios
WU-I1, WU-P5.

## DoD especifico
Teste de chaves: cada item gera PK/SK esperado; entity_id/company_id por hash estavel (sem UUID/relogio)."""),

    ("WU-I8 - Politicas IAM minimas por Lambda", "Baixa", """\
## Objetivo
Conceder a cada Lambda acesso somente a tabela importada e ao segredo necessario, sem privilegio cruzado.

## Contrato (entrada -> saida)
IAM por funcao na Stateless Stack: so SocialSellingTable (importada) + segredo do modulo. SDD-2 secao 3.3/3.6 (WU-I8).

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado as policies, Quando revisadas, Entao cada Lambda acessa so a tabela + seu segredo.
- Degradado:  Dado um modulo, Entao ele NAO tem acesso ao segredo de outro provedor (sem privilegio cruzado).
- Open-World: Dado uma policy ampla demais, Entao e rejeitada na revisao (principio do menor privilegio).

## Fixtures necessarias
Nenhuma (revisao declarativa; sam validate).

## Fora de escopo
Deploy (D2/D3).

## Dependencias / bloqueios
WU-I2, WU-I5.

## DoD especifico
Revisao confirma menor privilegio; sem privilegio cruzado entre modulos."""),

    # ============ FASE 4 — DevOps CI/CD (novo) ============
    ("WU-D1 - sam validate no gate de CI (lint de IaC offline)", "Baixa", """\
## Objetivo
Validar os dois templates SAM no CI, offline, sem credenciais AWS -- pegar erro de IaC antes do deploy.

## Contrato (entrada -> saida)
Estende `.github/workflows/ci.yml`: passo `sam validate` para infra/stateful e infra/stateless (sem deploy, sem AWS). Plano: docs/planning/adr-008-backlog-plan.md.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado templates validos, Quando o CI roda, Entao sam validate passa para ambas as stacks.
- Degradado:  Dado um template invalido, Entao o CI falha (fail-closed) sem tocar a AWS.
- Open-World: Dado ausencia de credenciais AWS, Entao o passo roda igual (validacao e local).

## Fixtures necessarias
Nenhuma (templates; sem rede).

## Fora de escopo
Deploy real (D2/D3).

## Dependencias / bloqueios
WU-I1, WU-I2.

## DoD especifico
Gate inclui sam validate das duas stacks; verde offline; sem credenciais AWS no job."""),

    ("WU-D2 - CD da Stateful Stack (workflow_dispatch + environment aprovado)", "Baixa", """\
## Objetivo
Deploy MANUAL e aprovado da stack de dados (Retain), via OIDC, para que codigo nunca toque recursos com estado.

## Contrato (entrada -> saida)
`.github/workflows/cd-stateful.yml`: on workflow_dispatch; environment com required reviewers; permissions id-token:write; configure-aws-credentials assume `${{ secrets.AWS_ROLE_ARN }}` na regiao `${{ secrets.AWS_REGION }}` (provedor OIDC + role ja criados na AWS); sam build/deploy infra/stateful. ADR-008 secao 3.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado dispatch aprovado, Quando o workflow roda, Entao assume o role por OIDC e faz sam deploy da Stateful.
- Degradado:  Dado falha de deploy, Entao o CloudFormation faz rollback e o workflow falha (sem estado meio-aplicado).
- Open-World: Dado nenhum dispatch, Entao NADA e deployado (nunca automatico em push).

## Fixtures necessarias
Nenhuma no repo (deploy real e operacional, fora do pytest). Secrets do repo (ja configurados): AWS_ROLE_ARN, AWS_REGION.

## Fora de escopo
Stateless (D3); testes nativos (continuam offline).

## Dependencias / bloqueios
WU-I1, WU-D1. OIDC ja resolvido: provedor de identidade + role na AWS criados; secrets AWS_ROLE_ARN/AWS_REGION presentes no repo. Sem bloqueio.

## DoD especifico
Workflow so dispara por dispatch com aprovacao; OIDC assume role; sam deploy da Stateful idempotente; nunca em push."""),

    ("WU-D3 - CD da Stateless Stack (auto no merge a main, OIDC)", "Baixa", """\
## Objetivo
Deploy AUTOMATICO da stack de codigo apos CI verde na main, importando os exports da Stateful.

## Contrato (entrada -> saida)
`.github/workflows/cd-stateless.yml`: on push main (apos gate); permissions id-token:write; assume `${{ secrets.AWS_ROLE_ARN }}` na regiao `${{ secrets.AWS_REGION }}` por OIDC; sam build/deploy infra/stateless (Fn::ImportValue da Stateful). ADR-008 secao 3.

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado merge na main com CI verde, Quando o workflow roda, Entao faz sam deploy da Stateless importando exports.
- Degradado:  Dado falha de deploy, Entao rollback do CloudFormation para a revisao anterior; workflow falha.
- Open-World: Dado exports da Stateful ausentes, Entao o deploy falha claro (nao cria recurso orfao).

## Fixtures necessarias
Nenhuma no repo. Secrets (ja configurados): AWS_ROLE_ARN, AWS_REGION. Vars: Cognito issuer/audience (WU-X1).

## Fora de escopo
Stateful (D2, manual); promocao multi-env (fora de escopo MVP).

## Dependencias / bloqueios
WU-I2, WU-D1, WU-D2. OIDC ja resolvido (provedor + role + secrets AWS_ROLE_ARN/AWS_REGION). BLOQUEIO EXTERNO restante: Cognito (WU-X1).

## DoD especifico
Deploy automatico so apos gate verde; OIDC; importa exports; rollback em falha; nunca toca a Stateful."""),

    ("WU-X1 - [Externo/Bloqueio] Provisionar Cognito User Pool", "Alta", """\
## Objetivo
Prover o Cognito User Pool externo (autenticacao multi-tenant delegada) e publicar issuer/audience como GitHub vars -- destravando o autorizador JWT.

## Contrato (entrada -> saida)
User Pool provisionado FORA deste repo (ADR-008: autenticacao delegada). Saida: issuer (URL) + audience (app client id) em GitHub Actions vars (ex.: COGNITO_ISSUER, COGNITO_AUDIENCE).

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado o User Pool criado, Entao issuer/audience estao disponiveis como GitHub vars e o autorizador JWT (I2) os referencia.
- Degradado:  Dado vars ausentes, Entao I2/D3 ficam BLOCKED (nao adivinhar) -- fail-closed.
- Open-World: n/a (acao operacional do dono).

## Fixtures necessarias
Nenhuma (acao operacional/externa; ADR-008 nao autoriza implementar cadastro/senha aqui).

## Fora de escopo
Telas de cadastro/login, gestao de senha (delegado ao Cognito; guardrail ADR-008).

## Dependencias / bloqueios
BLOQUEIO: depende de acao do dono (provisionar fora do repo). Bloqueia WU-I2 e WU-D3.

## DoD especifico
issuer/audience publicados como GitHub vars; WU-I2/WU-D3 deixam de estar BLOCKED."""),
]


def run(args: list[str]) -> str:
    res = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        sys.stderr.write(res.stdout + "\n" + res.stderr + "\n")
        raise SystemExit(f"comando falhou: {' '.join(args)}")
    return res.stdout


def _code(title: str) -> str:
    return title.split(" ")[0]


def _board_index() -> dict[str, dict]:
    """Mapeia WU code -> {item_id, content_id, status} a partir do board atual."""
    out = run(["gh", "project", "item-list", NUMBER, "--owner", OWNER,
               "--limit", "100", "--format", "json"])
    idx: dict[str, dict] = {}
    for it in json.loads(out)["items"]:
        title = it.get("content", {}).get("title", "")
        code = _code(title)
        if code in PLANS:  # so cards do roadmap ADR-008
            idx[code] = {"item_id": it["id"],
                         "content_id": it.get("content", {}).get("id", ""),
                         "status": it.get("status", "")}
    return idx


def cmd_create(dry: bool) -> None:
    print(f"=== Seed ADR-008 backlog: {len(CARDS)} cards ===")
    for i, (title, prio, body) in enumerate(CARDS, 1):
        if dry:
            print(f"[{i:2}] [{prio:<5}] {title}  (Ready={_code(title) in READY})")
            continue
        print(f"[{i:2}/{len(CARDS)}] criando: {title} (Priority={prio})")
        code = _code(title)
        full = build_full(code, body)
        out = run(["gh", "project", "item-create", NUMBER, "--owner", OWNER,
                   "--title", title, "--body", full, "--format", "json"])
        item_id = json.loads(out)["id"]
        status = DONE if code in DONE_CARDS else (TODO if code in READY else BACKLOG)
        run(["gh", "project", "item-edit", "--id", item_id, "--project-id", PROJECT_ID,
             "--field-id", STATUS_FID, "--single-select-option-id", status])
        run(["gh", "project", "item-edit", "--id", item_id, "--project-id", PROJECT_ID,
             "--field-id", PRIO_FID, "--single-select-option-id", PRIO_OPT[prio]])
    print("\n(dry-run) nada criado." if dry else
          f"\nOK: {len(CARDS)} cards criados. Board: https://github.com/users/{OWNER}/projects/{NUMBER}")


def cmd_sync(dry: bool) -> None:
    """Atualiza o corpo (plano+DoR) dos cards existentes e move os Ready para Todo."""
    idx = _board_index()
    missing = [c for c in PLANS if c not in idx]
    if missing:
        print(f"AVISO: cards nao encontrados no board: {missing}")
    print(f"=== Sync ADR-008: {len(idx)} cards no board ===")
    for title, _prio, body in CARDS:
        code = _code(title)
        if code not in idx:
            continue
        info = idx[code]
        if code in DONE_CARDS:
            target_name, target_opt = "Done", DONE
        elif code in READY:
            target_name, target_opt = "Todo", TODO
        else:
            target_name, target_opt = "Backlog", BACKLOG
        move = info["status"] != target_name
        print(f"  {code}: body+plano | status {info['status']}"
              + (f" -> {target_name}" if move else f" (mantem {info['status']})"))
        if dry:
            continue
        full = build_full(code, body)
        run(["gh", "project", "item-edit", "--id", info["content_id"],
             "--title", title, "--body", full])
        if move:
            run(["gh", "project", "item-edit", "--id", info["item_id"], "--project-id", PROJECT_ID,
                 "--field-id", STATUS_FID, "--single-select-option-id", target_opt])
    ready_n = sum(1 for c in idx if c in READY)
    done_n = sum(1 for c in idx if c in DONE_CARDS)
    back_n = len(idx) - ready_n - done_n
    print(f"\n{'(dry-run) ' if dry else ''}OK: {len(idx)} corpos atualizados; "
          f"{ready_n} em Todo; {done_n} em Done; {back_n} em Backlog (bloqueio).")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="so lista, nao escreve")
    ap.add_argument("--sync", action="store_true",
                    help="atualiza corpos dos cards existentes e move Ready->Todo (nao cria)")
    a = ap.parse_args()
    (cmd_sync if a.sync else cmd_create)(a.dry_run)


if __name__ == "__main__":
    main()
