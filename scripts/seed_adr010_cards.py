#!/usr/bin/env python
"""Seed dos 12 cards do piloto ADR-010 (portal da operadora) no GitHub Project #1.

Cria todos os cards em **Backlog**, com corpo no template DoR (docs/governance/dor-dod.md)
e o campo Priority por fase do plano (docs/planning/adr-010-backlog-plan.md).
Fonte: ADR-010 + SDD docs/specs/portal-operadora-piloto-sdd.md (secoes citadas nos corpos).

Uso:
    py scripts/seed_adr010_cards.py --dry-run   # so lista, nao cria
    py scripts/seed_adr010_cards.py             # cria os cards via `gh`

AVISO: NAO deduplica. Rodar duas vezes duplica os cards. Rodar UMA vez.
Todos entram em Backlog (autoria de dia). O dono/orquestrador move Backlog->Todo.
A ULTIMA linha do stdout e um JSON [{"wu", "id", "title"}, ...] com os item-ids
criados, para o orquestrador promover a Todo depois.
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
PRIO_FID = "PVTSSF_lAHOAAi2gM4BZ3J3zhUzDd8"  # Priority
PRIO_OPT = {"Alta": "da3cda2e", "Media": "dd378f56", "Baixa": "8ffead41"}

TAMANHO = "\n\n## Tamanho\n1 WU (1-2 passos / uma janela; termina em checkpoint seguro)."

_DOR_ITEMS = [
    "Objetivo observável em 1 frase",
    "Cabe em 1 WU (1-2 passos / uma janela)",
    "Contrato entrada→saída definido (ADR-010 + SDD do portal vinculadas)",
    "Gherkin: feliz + degradado + Open-World",
    "Fixtures identificadas (ou módulo puro); sem bloqueio de rede-paga",
    "Sem decisão de fronteira em aberto",
    "Dentro do escopo canônico (CLAUDE.md §3/§5, ADR-010) e determinístico (1e-9, HTTP/APIs mockados)",
    "DoD específico declarado acima",
]

DOR_BLOCK = (
    "\n\n## DoR (checklist — marque [x]; só vai para Todo com TODOS [x])\n"
    + "\n".join(f"- [x] {item}" for item in _DOR_ITEMS)
    + "\n\n> ✅ DoR completo na autoria (SDD do portal §2/§5/§7 já entrega contratos, Gherkin e estratégia de fixtures)."
)

X2_NOTE = (
    "\n\n> ⚠️ Nota DoR (card EXTERNO): a execução é **manual do dono** (Render/DNS/Neon), "
    "fora do run noturno — `github-sdd-sync` NÃO deve pegar este card. O checklist está [x] "
    "porque o runbook (SDD §8) elimina ambiguidade; o \"gate\" desta WU é o smoke pós-deploy "
    "verde no domínio final, não o pytest."
)

# (wu, titulo, Priority, corpo no template dor-dod.md — sem o bloco DoR, apendado depois)
CARDS: list[tuple[str, str, str, str]] = [
    # ===================== FASE 1 — Fundacao do loop (Alta) =====================
    ("WU-E1", "WU-E1 - Regra canonica de entity_id (core/identity.py)", "Alta", """\
## Objetivo
Estabelecer `canonical_entity_id` como a única fonte de identidade do lead (estável entre runs e provedores), para que o join do feedback nunca produza órfãos silenciosos que corrompam o aprendizado.

## Contrato (entrada → saída)
SDD portal-operadora-piloto §6.1: `src/socialselling/core/identity.py: canonical_entity_id(website: str | None, name: str, city: str | None) -> str`. (1) host válido no website → domínio normalizado (urlsplit com/sem scheme, casefold, remove "www." inicial, remove porta, descarta path/query/fragment, remove "." final); (2) fallback determinístico → `"sha256:<hex64>"` de `nome_normalizado|cidade_normalizada` (NFKD→ASCII, casefold, espaços colapsados, strip; cidade ausente = ""). Consumida pelo corpus (ADR-006) e pelo publish (WU-E3) como ÚNICA fonte de identidade. ADR-010 §8.

## Critérios de aceitação (Gherkin)
- Feliz:      Dado o site "https://www.Cliniq.com.br/sobre?x=1" num run e "cliniq.com.br" em outro (ou vindo de outro provedor) Quando derivo o entity_id Então ambos retornam "cliniq.com.br" (mesmo id entre runs e provedores).
- Degradado:  Dado um website sem host válido (vazio ou lixo) Quando derivo o entity_id Então cai no fallback sha256 de nome+cidade normalizados, sem exceção; e mesmo nome+cidade com variação de acentos/caixa produz o MESMO hash.
- Open-World: Dado um lead sem site e sem cidade Quando derivo o entity_id Então cidade ausente vale "" (explícito) e o hash permanece estável — ausência de sinal não fabrica identidade nem quebra; leads distintos produzem ids distintos.

## Fixtures necessárias
Nenhuma (módulo puro, sem rede e sem API externa).

## Fora de escopo
CLI publish (WU-E3); contratos do portal (WU-E2); qualquer mudança nas fórmulas de score/ranking (não-objetivo da SDD §0).

## Dependências / bloqueios
Nenhum (card fundacional do loop — pré-requisito de WU-E3/E4).

## DoD específico
Teste BDD de estabilidade verde (variações de scheme/www/caixa/acentos ⇒ mesmo id; leads distintos ⇒ ids distintos); corpus adota a função como única fonte de identidade; `mypy --strict` limpo."""),

    ("WU-E2", "WU-E2 - Contratos do portal + feedback_catalog.json v1", "Alta", """\
## Objetivo
Disponibilizar os contratos Pydantic compartilhados motor↔portal e o catálogo de status do funil, eliminando deriva de contrato entre as duas pontas do loop.

## Contrato (entrada → saída)
SDD §2 (transcrito LITERALMENTE) em `src/socialselling/portal/contracts.py`: `PublishedDriver`, `PublishedLead`, `PublishedSnapshot` (validador de ranks 1..N estritos, max 20), `FeedbackKind`, `Reaction`, `FeedbackEvent` (validador kind consistente), `FeedbackEventIn`, `FeedbackPage`, `RotuloAprendizado`, `CatalogStatus`, `FeedbackCatalog` (ids/ordens únicos), `Operator` — todos `ConfigDict(extra="forbid")`; `DataProvenance` REUSADO de `socialselling.contracts` (não duplicar). SDD §3: `config/feedback_catalog.json` v1 (JSON literal, 9 statuses, ids snake_case estáveis) + loader/validação. Apenas modelos de dados — sem lógica de negócio, sem import de FastAPI/psycopg.

## Critérios de aceitação (Gherkin)
- Feliz:      Dado um PublishedSnapshot com 20 leads rank_position 1..20 Quando serializo e desserializo (round-trip) Então o resultado é byte-idêntico e válido.
- Degradado:  Dado um lead com campo extra "score" (ou ranks não-estritos, ou kind=status sem status_id) Quando valido Então ValidationError/ValueError — o contrato rejeita (extra=forbid), nada passa silenciosamente.
- Open-World: Dado um lead sem segmento/cidade/uf e com missing_evidence preenchida Quando valido Então os campos opcionais valem None (explícito) e missing_evidence é preservada — ausência de sinal não invalida o lead.

## Fixtures necessárias
Nenhuma (contratos puros + JSON de config local; sem rede).

## Fora de escopo
App FastAPI e porta DAO (WU-T1); endpoints (WU-T2/T4); qualquer consumo do `rotulo_aprendizado` (calibração offline é card futuro do Backlog).

## Dependências / bloqueios
Nenhum (os modelos são autocontidos; `DataProvenance` já existe em `contracts.py`).

## DoD específico
Round-trip de (de)serialização verde; validadores testados (ranks estritos, kind consistente, ids/ordens únicos no catálogo); `extra="forbid"` rejeita campo `score` em teste; loader valida o `feedback_catalog.json` literal da SDD §3; `mypy --strict` limpo."""),

    # ===================== FASE 2 — Portal (Media) =====================
    ("WU-T1", "WU-T1 - Scaffold do portal: app + porta DAO + adapters", "Media", """\
## Objetivo
Criar o esqueleto do portal (FastAPI em `src/socialselling/portal/`) com a porta de storage e seus dois adapters, de modo que todo o resto do portal dependa SÓ da interface e o gate fique 100% offline.

## Contrato (entrada → saída)
SDD §5.2 `BasePortalDAO` (ABC, assinaturas imutáveis: `ensure_schema`, `put_snapshot`, `list_snapshots`, `append_event`, `events_since`, `latest_status_by_entity`, `find_operator_by_code_hash`) em `portal/dao.py`; SDD §5.3 adapters: `InMemoryDAO` (`portal/dao_memory.py`) e `PostgresDAO` fino (`portal/dao_postgres.py`, 1 SQL por método, `psycopg` importado SOMENTE aqui); SDD §5.1 DDL literal via `ensure_schema()` no startup (CREATE TABLE IF NOT EXISTS; sem Alembic/ORM/índices extras). App FastAPI com middleware global `X-Robots-Tag: noindex` + `GET /healthz`; extra `[portal]` no `pyproject.toml`. Consome contratos da WU-E2.

## Critérios de aceitação (Gherkin)
- Feliz:      Dado o InMemoryDAO Quando rodo os contract tests da porta Então put_snapshot é idempotente (segunda inserção do mesmo (profile_id, run_id) retorna False), list_snapshots vem mais recente primeiro (published_at DESC, tie-break run_id DESC) e events_since retorna ordem ASC com serial crescente.
- Degradado:  Dado o app de pé Quando faço GET /healthz Então responde 200 sem tocar dados de lead (liveness para Render/smoke); e toda resposta do app carrega X-Robots-Tag: noindex.
- Open-World: Dado latest_status_by_entity para um perfil em que uma entidade não tem NENHUM evento de status Então a entidade está AUSENTE do dict (o chamador interpreta como "novo" — default explícito; o DAO nunca fabrica evento).

## Fixtures necessárias
Nenhuma fixture de API externa; contract tests rodam na porta com `InMemoryDAO`; rotas com FastAPI `TestClient` (sem rede). `PostgresDAO` fica FORA do gate (risco residual aceito — SDD §5.4; coberto pelo smoke pós-deploy do WU-T6).

## Fora de escopo
Endpoints de publicação/feedback (WU-T2/T4); auth (WU-T3); UI (WU-T5); conexão de banco real no CI (proibida).

## Dependências / bloqueios
WU-E2 (contratos `portal/contracts.py`).

## DoD específico
Contract tests da porta verdes no `InMemoryDAO` (`tests/features/portal_dao_contract.feature`, steps parametrizados); grep no gate confirma `psycopg` importado só em `dao_postgres.py`; gate 100% offline; `mypy --strict` limpo."""),

    ("WU-T2", "WU-T2 - POST /api/publish (Bearer, idempotente 201/409)", "Media", """\
## Objetivo
Receber snapshots do motor com autenticação por token e idempotência por (profile_id, run_id), para que republicar o mesmo ranking nunca duplique a carteira.

## Contrato (entrada → saída)
SDD §4 (tabela de endpoints): `POST /api/publish` com Bearer `PUBLISH_TOKEN`; corpo = `PublishedSnapshot` (SDD §2); persiste via `BasePortalDAO.put_snapshot` (SDD §5.2) com `now` injetado na borda. Respostas: `201` publicado agora; `409` já existia (o motor trata como sucesso idempotente); `401` token ausente/errado; `422` contrato violado (extra=forbid, ranks não-estritos, >20 leads).

## Critérios de aceitação (Gherkin)
- Feliz:      Dado um PublishedSnapshot válido e o Bearer correto Quando POST /api/publish Então 201 e o snapshot é persistido por (profile_id, run_id); repetir o MESMO snapshot Então 409 e a carteira não duplica.
- Degradado:  Dado um POST sem header Authorization válido Então 401 e NADA é persistido; Dado um corpo com campo extra "score" em um lead Então 422 (extra=forbid) e nada é persistido.
- Open-World: Dado um snapshot cujos leads trazem missing_evidence preenchida Quando publicado Então é aceito e persistido como veio — sinal ausente é dado legítimo do contrato, nunca motivo de rejeição.

## Fixtures necessárias
Nenhuma fixture de API externa; rotas testadas com FastAPI `TestClient` + `InMemoryDAO` injetado (sem rede; SDD §5.4).

## Fora de escopo
CLI `publish` do motor (WU-E3); GET /api/feedback (WU-T4); UI (WU-T5).

## Dependências / bloqueios
WU-E2 (contratos), WU-T1 (app + porta DAO).

## DoD específico
Cenários da SDD §7 "API de publicação do portal" verdes (401 não persiste; 422 para campo `score`); 409 verificado sem duplicação (list_snapshots inalterado); relógio injetado (sem `datetime.now()` no caminho de persistência)."""),

    ("WU-T3", "WU-T3 - Auth da operadora por codigo de acesso (login/sessao/logout)", "Media", """\
## Objetivo
Autenticar a operadora com um único código de alta entropia e escopar TUDO que ela vê ao seu profile_id via cookie de sessão assinado, protegendo dados pessoais de leads (LGPD).

## Contrato (entrada → saída)
SDD §4 + §4.2: `POST /login` (form com um campo; `sha256(código)` → `BasePortalDAO.find_operator_by_code_hash`, SDD §5.2; achou → cookie de sessão assinado com `SECRET_KEY` carregando `operator_id`+`profile_id`; não achou → 401 genérico); `POST /logout` invalida a sessão; guarda de sessão nas páginas (`303 → /login`). Modelo `Operator` (SDD §2). Cookies `HttpOnly`/`Secure`/`SameSite=Lax`; `SessionMiddleware` do Starlette (dep `itsdangerous` no extra `[portal]`). Sem bcrypt/KDF no piloto (código aleatório de alta entropia — risco aceito e registrado na SDD §4.2).

## Critérios de aceitação (Gherkin)
- Feliz:      Dado uma operadora seedada com o code_hash de "codigo-correto" Quando ela envia POST /login com "codigo-correto" Então recebe cookie de sessão assinado com operator_id e profile_id e é redirecionada para /carteira.
- Degradado:  Quando alguém envia POST /login com "codigo-errado" Então 401 com mensagem genérica ("código inválido", sem distinguir causa) e nenhuma sessão é criada.
- Open-World: Quando um cliente SEM cookie acessa GET /carteira Então é redirecionado (303) para /login e nenhum dado de lead é exposto — ausência de sessão = acesso nenhum, nunca acesso parcial.

## Fixtures necessárias
Nenhuma fixture de API externa; `TestClient` + `InMemoryDAO` com operadora seedada em memória (sem rede).

## Fora de escopo
Self-service (cadastro, reset de código, convites — seed manual via SQL, SDD §10); Cognito/OAuth (prateleira ADR-008); o seed real da Talita (WU-X2).

## Dependências / bloqueios
WU-E2 (modelo `Operator`), WU-T1 (app + porta DAO).

## DoD específico
Cenários da SDD §7 "Autenticação por código de acesso" verdes (feliz, 401 genérico, página protegida); teste verifica atributos `HttpOnly`/`Secure`/`SameSite=Lax` do cookie; logout invalida a sessão."""),

    ("WU-T4", "WU-T4 - APIs de feedback: POST do lead (sessao) + GET por cursor (Bearer)", "Media", """\
## Objetivo
Registrar a tabulação da operadora como eventos append-only (anti-spoofing por sessão) e expô-los ao motor por cursor idempotente — o coração do loop de feedback.

## Contrato (entrada → saída)
SDD §4: `POST /lead/{entity_id}/feedback` via sessão — corpo `FeedbackEventIn` (SDD §2); `operator_id`/`profile_id` da SESSÃO e `run_id` do snapshot mais recente que contém o lead, NUNCA do corpo (anti-spoofing); `status_id` validado contra `config/feedback_catalog.json`; grava via `BasePortalDAO.append_event` (SDD §5.2, append-only — correção = novo evento). `GET /api/feedback?since=<event_id>&limit=<n>` via Bearer `PUBLISH_TOKEN` — eventos com `event_id > since`, ordem ASC, resposta `FeedbackPage`; `since` além do fim → `events=[]`, `next_since=since`. Erros: 303→/login sem sessão; 404 lead fora da carteira; 401 Bearer; 422.

## Critérios de aceitação (Gherkin)
- Feliz:      Dado uma sessão válida da operadora "talita" Quando ela envia POST /lead/cliniq.com.br/feedback com kind=status e status_id=abordado Então um FeedbackEvent é anexado com operator_id/profile_id da sessão e run_id do snapshot mais recente que contém o lead, e nenhum evento anterior é alterado (correção = novo evento).
- Degradado:  Dado uma sessão válida Quando ela envia kind=status com status_id "quase_cliente" (fora do catálogo) Então 422 e nada é gravado; Dado um lead que não pertence à carteira do perfil Então 404.
- Open-World: Dado o cursor `since` além do último event_id Quando GET /api/feedback Então `events=[]` e `next_since=since` (idempotente) — fim do stream é ausência explícita, nunca erro nem evento fabricado.

## Fixtures necessárias
Nenhuma fixture de API externa; `TestClient` + `InMemoryDAO` com snapshot e operadora seedados em memória (sem rede); catálogo lido de `config/feedback_catalog.json`.

## Fora de escopo
UI de tabulação (WU-T5); consolidação no motor (WU-E4); qualquer UPDATE/DELETE de evento (proibido por invariante).

## Dependências / bloqueios
WU-T2 (snapshots persistidos — resolução do run_id) e WU-T3 (sessão). Transitivas: E2, T1.

## DoD específico
Cenários da SDD §7 "Tabulação de feedback" e o cenário de cursor verdes; revisão/grep confirma que NENHUM caminho de código faz UPDATE/DELETE em `feedback_events`; `run_id`/`operator_id`/`profile_id` jamais aceitos do corpo do request."""),

    ("WU-T5", "WU-T5 - UI da operadora: carteira + lead card (sem score)", "Media", """\
## Objetivo
Dar à operadora a visão acionável da sua carteira (com leads em acompanhamento) e o lead card explicável, sem jamais expor score numérico.

## Contrato (entrada → saída)
SDD §4.1: `GET /carteira` — visível = leads do snapshot mais recente ∪ leads não-terminais de snapshots anteriores ("em acompanhamento"); regras 1–5 (default "novo"; último evento kind=status vence; terminal sai; dedupe na posição mais recente; ordenação determinística: rank_position, depois company casefold, tie-break entity_id); modelo de visão `CarteiraItem`. `GET /lead/{entity_id}` — contato/links, drivers em linguagem natural com proveniência (`PublishedDriver.references`), `missing_evidence`, status atual + histórico, controles de status e like/dislike; 404 se fora da carteira do perfil. Jinja2 + JS vanilla; consome `BasePortalDAO.list_snapshots`/`latest_status_by_entity` (SDD §5.2). **Sem score numérico** (ADR-010).

## Critérios de aceitação (Gherkin)
- Feliz:      Dado o snapshot run_2 (mais recente) com A, B, C e o run_1 com C, D, E, com D="abordado" e E="fora_do_perfil" Quando a operadora abre GET /carteira Então vê A, B, C na ordem de rank_position de run_2, D marcado "em acompanhamento", E ausente (terminal) e C uma única vez; se D virar "cliente", some no próximo acesso.
- Degradado:  Dado um entity_id que não pertence à carteira do perfil da sessão Quando GET /lead/{entity_id} Então 404 (nenhum dado de outro perfil vaza); sem sessão, 303 → /login.
- Open-World: Dado um lead publicado SEM nenhum evento de status Quando a carteira é montada Então o status exibido é "novo" sem fabricar evento, e o lead card lista missing_evidence explicitamente (sinal ausente visível, nunca ocultado).

## Fixtures necessárias
Nenhuma fixture de API externa; `TestClient` + `InMemoryDAO` com snapshots/eventos seedados (sem rede); serviço da carteira testado como função pura determinística.

## Fora de escopo
Qualquer exibição de score/número de ranking além da ordem; mudanças na UI local `socialselling/web` (não muda — ADR-010); mobile/notificações (SDD §10).

## Dependências / bloqueios
WU-T2 (snapshots), WU-T3 (sessão), WU-T4 (eventos/status).

## DoD específico
Cenários da SDD §7 "Carteira da operadora" verdes (incluindo dedupe e determinismo: duas montagens ⇒ ordem idêntica); assert estrutural de que o template do lead card não renderiza nenhum número de score; cobertura do serviço da carteira com testes determinísticos."""),

    # ===================== FASE 3 — CLIs do motor (Media) =====================
    ("WU-E3", "WU-E3 - CLI publish: top-20 sem score, run_id por hash, degradacao limpa", "Media", """\
## Objetivo
Publicar o top-20 do corpus ranqueado do perfil no portal via HTTP (idempotente por conteúdo), guardando os scores SÓ no registro local — o portal nunca vê score.

## Contrato (entrada → saída)
SDD §6.2: `src/socialselling/sync/publish.py` (`py -m socialselling.sync.publish --profile <id> [--dry-run]`). Corpus ranqueado do perfil (ADR-006) → corte top-20 → `PublishedSnapshot` (SDD §2; drivers de `XAIPayload.positive_signals`/`negative_signals` com references; `missing_evidence` = `missing_signals`; split best-effort de location em cidade/UF; NENHUM campo de score). `run_id` = `sha256(profile_id + "|" + ",".join(f"{rank}:{entity_id}"))[:16]` — sem relógio. Registro local atômico (`core/atomic.py`) em `data/published/<profile_id>/<run_id>.json` com snapshot + scores por entity_id (fit, intent, confidence, persona_fit, p_score). `--dry-run` para no registro local; senão `POST /api/publish` com Bearer `PORTAL_PUBLISH_TOKEN` (`.env`: `PORTAL_BASE_URL`). 201 e 409 = sucesso. Usa `canonical_entity_id` (WU-E1).

## Critérios de aceitação (Gherkin)
- Feliz:      Dado o corpus ranqueado do perfil "talita" com 32 leads Quando executo publish --profile talita Então o snapshot enviado tem 20 leads com rank_position 1..20, nenhum campo numérico de score aparece no payload, o registro local guarda os scores por entity_id e o portal (mockado) responde 201; com o corpus inalterado, o run_id é idêntico e o 409 é tratado como sucesso idempotente.
- Degradado:  Dado que o POST /api/publish falha com erro de conexão (portal fora do ar) Quando executo publish Então o snapshot fica gravado em data/published/, a CLI termina com exit code != 0 e mensagem crua acionável, e pipeline/corpus permanecem intactos (snapshot local pronto para reenvio).
- Open-World: Dado um lead do ranking com sinais ausentes em XAIPayload.missing_signals Quando o snapshot é montado Então PublishedLead.missing_evidence lista os mesmos sinais e o lead permanece publicado (ausência de sinal não o rebaixa a falso nem o exclui).

## Fixtures necessárias
Nenhuma fixture de API externa nova; HTTP do portal **mockado** nos testes (respx/monkeypatch sobre o cliente HTTP); corpus de teste local determinístico. Sem rede no gate.

## Fora de escopo
Pull de feedback (WU-E4); agendamento (runs manuais — SDD §10); qualquer mudança em M1–M5/fórmulas de score (não-objetivo).

## Dependências / bloqueios
WU-E1 (entity_id canônico), WU-E2 (contratos). O portal real NÃO é dependência (HTTP mockado).

## DoD específico
Cenários da SDD §7 "Publicação de snapshot" verdes com HTTP mockado; assert estrutural de payload sem score; escrita do registro local atômica (write-temp + os.replace); run_id reproduzível byte-idêntico para o mesmo corpus."""),

    ("WU-E4", "WU-E4 - CLI pull-feedback: cursor, JSONL append-only, consolidacao ADR-007", "Media", """\
## Objetivo
Trazer os eventos de feedback do portal para o motor (cópia canônica local em JSONL) e consolidá-los — reactions no aprendizado ADR-007 por perfil, statuses na calibração offline — sem jamais corromper o treino com órfãos.

## Contrato (entrada → saída)
SDD §6.3: `src/socialselling/sync/pull_feedback.py` (`py -m socialselling.sync.pull_feedback`). Cursor em `data/feedback_events/cursor.json` (ausente = 0) → `GET /api/feedback?since=N` (Bearer) em loop até página vazia (`FeedbackPage`, SDD §2) → append em `data/feedback_events/events.jsonl` (append-only; dedupe por event_id <= cursor). Consolidação em ordem de event_id: reaction → `FeedbackStore` ADR-007 do perfil (`data/feedback/<profile_id>.json`) com `FeedbackFeatures` lidas do registro local `data/published/<profile_id>/<run_id>.json` (scores capturados na publicação, nunca recomputados); status → `data/calibration/eventos.jsonl`. Órfão (run_id/entity_id sem registro local) → `data/feedback_events/orfaos.jsonl` + warning. Cursor atualizado ATOMICAMENTE POR ÚLTIMO (`core/atomic.py`).

## Critérios de aceitação (Gherkin)
- Feliz:      Dado o cursor local em 0 e o portal (mockado) com 3 eventos (1 reaction, 2 status) Quando executo pull-feedback Então os 3 são anexados em events.jsonl, a reaction vira FeedbackRecord no FeedbackStore do perfil com features do registro local, os 2 status vão para data/calibration/eventos.jsonl e o cursor avança para o maior event_id, gravado atomicamente por último.
- Degradado:  Dado o cursor em 42 e nenhum evento novo Quando executo pull-feedback duas vezes Então ambas recebem events=[] e next_since=42 e NENHUM arquivo local muda entre as execuções (reexecução idempotente por dedupe de event_id).
- Open-World: Dado um evento reaction com run_id SEM registro local em data/published/ Quando executo pull-feedback Então o evento vai para orfaos.jsonl com warning, NENHUMA feature é inventada nem entra no FeedbackStore, e os demais eventos do lote são consolidados normalmente.

## Fixtures necessárias
Nenhuma fixture de API externa nova; HTTP do portal **mockado** nos testes (respx/monkeypatch); registros locais de `data/published/` criados pelo próprio teste (ou via publish --dry-run). Sem rede no gate.

## Fora de escopo
Ligar status de funil ao aprendizado automático (ADR futura — fase 1 só coleta; like/dislike segue único input da ADR-007); expurgo no Neon (procedimento manual do runbook).

## Dependências / bloqueios
WU-E2 (contratos), WU-E3 (registro local com scores em data/published/). Portal real NÃO é dependência.

## DoD específico
Cenários da SDD §7 "Pull de feedback e consolidação" verdes com HTTP mockado; reexecução não duplica nem altera arquivos (comparação byte-idêntica); ordem de consolidação por event_id testada; cursor sempre gravado por último."""),

    # ===================== FASE 4 — Integracao e operacao (Baixa) =====================
    ("WU-T6", "WU-T6 - render.yaml + runbook do piloto + smoke_portal.py", "Baixa", """\
## Objetivo
Entregar os artefatos de operação do piloto (IaC declarativa do Render, runbook completo e smoke pós-deploy) para que o WU-X2 do dono seja executável sem ambiguidade.

## Contrato (entrada → saída)
SDD §8: (a) `render.yaml` — Web Service free, região Virginia (US East, mesma do Neon), build `pip install -e ".[portal]"`, start `uvicorn socialselling.portal.app:app --host 0.0.0.0 --port $PORT`, health check `/healthz`, env vars `DATABASE_URL`/`PUBLISH_TOKEN`/`SECRET_KEY` REFERENCIADAS SEM VALOR; (b) `docs/runbooks/portal-piloto.md` — §8 completo (Neon, seed SQL da operadora, geração de código/hash, CNAME selling.issei.com.br, ciclo manual do piloto, expurgo pós-pull, métricas de sucesso); (c) `scripts/smoke_portal.py` — única peça que toca o portal real (cobre o risco residual do PostgresDAO): GET /healthz 200 → POST /api/publish snapshot sintético profile_id="smoke" → 201 → repetir → 409 → GET /api/feedback?since=0 → 200.

## Critérios de aceitação (Gherkin)
- Feliz:      Dado o render.yaml Quando o lint YAML roda no gate Então passa e build/start/health/env-vars batem com a SDD §8.
- Degradado:  Dado o smoke executado contra uma URL com o portal fora do ar Quando roda Então falha com mensagem clara e exit code != 0 (e o smoke NUNCA roda dentro do pytest/gate — é ferramenta operacional).
- Open-World: Dado o render.yaml sem nenhum valor de segredo (env vars só referenciadas) Quando o repositório é inspecionado Então nenhum segredo está commitado e a ausência dos valores localmente não quebra o gate (segredos vivem só no Render).

## Fixtures necessárias
Nenhuma fixture de API externa; lint YAML offline; o smoke é parametrizado por URL arbitrária e fica fora do gate (SDD §5.4/§8).

## Fora de escopo
Executar o deploy/DNS/seed (WU-X2 — ação do dono); agendamento; qualquer recurso AWS.

## Dependências / bloqueios
WU-T1 (app/healthz), WU-T2 e WU-T4 (rotas que o smoke exercita).

## DoD específico
`render.yaml` validado (lint YAML no gate); runbook revisado pelo dono; smoke executável localmente contra URL arbitrária (`py scripts/smoke_portal.py --base-url ...`), sem rodar no gate."""),

    ("WU-E5", "WU-E5 - Cenario e2e offline do loop completo (publish->feedback->pull)", "Baixa", """\
## Objetivo
Provar o contrato ponta-a-ponta do loop (publicar → logar → tabular → puxar → consolidar) dentro do gate, 100% offline e determinístico — o smoke test ponta-a-ponta do piloto no CI.

## Contrato (entrada → saída)
SDD §9 (WU-E5): cenário BDD que encadeia `publish --dry-run` (snapshot + registro local) → snapshot injetado no portal com `InMemoryDAO` (sem rede) → login da operadora → eventos de status e reaction via rotas → `pull-feedback` executado contra o app de teste (transport do TestClient no lugar de HTTP real) → verificação da consolidação: `FeedbackStore` ADR-007 do perfil, `data/calibration/eventos.jsonl` e cursor. Integra os contratos de TODAS as WUs anteriores sem código de produto novo (só cola de teste).

## Critérios de aceitação (Gherkin)
- Feliz:      Dado o loop completo executado offline Quando o cenário roda Então o snapshot publicado aparece na carteira, os eventos da operadora são puxados e consolidados (FeedbackStore + calibração) e o cursor termina no maior event_id.
- Degradado:  Dado o loop já consolidado Quando o pull-feedback é reexecutado Então nada é duplicado nem alterado (idempotência por dedupe de event_id; arquivos byte-idênticos).
- Open-World: Dado um lead publicado sem nenhum evento durante o e2e Então ele permanece "novo" na carteira ao final, e a missing_evidence do snapshot atravessa o loop intacta (do XAIPayload ao lead card).

## Fixtures necessárias
Nenhuma fixture de API externa; `InMemoryDAO` + `TestClient` como transporte (zero rede); corpus de teste determinístico reusado de WU-E3.

## Fora de escopo
Smoke contra o portal real (WU-T6/X2); novas features — esta WU só integra e prova o que já existe.

## Dependências / bloqueios
WU-T2, WU-T3, WU-T4, WU-T5, WU-E3, WU-E4 (todas mergeadas).

## DoD específico
Cenário e2e verde, determinístico e 100% offline no CI; reexecução byte-idêntica; registrado em PROGRESS como o "smoke ponta-a-ponta" do piloto."""),

    ("WU-X2", "WU-X2 - [Externo/dono] Deploy no Render + DNS + seed da Talita no Neon", "Baixa", """\
## Objetivo
Colocar o portal no ar (Render free, Virginia) com domínio selling.issei.com.br e a operadora Talita seedada, para que o piloto real comece — smoke pós-deploy verde é a prova.

## Contrato (entrada → saída)
SDD §8 (runbook — executar `docs/runbooks/portal-piloto.md` do WU-T6): (1) criar o Web Service free no Render, região **Virginia (US East)**, a partir do `render.yaml`; (2) configurar env vars `DATABASE_URL` (connection string pooled do Neon, projeto `socialselling` já criado), `PUBLISH_TOKEN` e `SECRET_KEY` (gerar com `secrets.token_urlsafe(32)`); (3) CNAME `selling.issei.com.br` → host `.onrender.com` + custom domain no Render (TLS automático); (4) rodar `scripts/smoke_portal.py` contra o domínio final; (5) seed da operadora Talita via SQL editor do Neon (INSERT em `operators` com sha256 do código gerado por `secrets.token_urlsafe(16)`; entregar o código por canal privado).

## Critérios de aceitação (Gherkin)
- Feliz:      Dado o serviço deployado e o seed feito Quando o smoke roda contra https://selling.issei.com.br Então healthz 200 → publish 201 → republicação 409 → feedback 200, e a Talita loga com o código e vê a carteira publicada.
- Degradado:  Dado o free tier dormindo após idle Quando o primeiro acesso ocorre Então pode levar ~1 min (comportamento aceito na SDD §8 — não é incidente).
- Open-World: Dado uma env var obrigatória ausente no Render Quando o serviço sobe Então falha no start (fail-closed) — nada é servido sem configuração completa, nenhum dado exposto sem auth.

## Fixtures necessárias
Nenhuma (ação operacional fora do repositório e fora do pytest; o smoke do WU-T6 é a verificação).

## Fora de escopo
Qualquer código no repo (já entregue em T1..T6); agendamento; AWS; self-service de operadoras.

## Dependências / bloqueios
WU-T6 (render.yaml + runbook + smoke) e portal mergeado na main (WU-T1..T5). BLOQUEIO: **ação manual do dono** (contas Render/Neon, DNS do domínio issei.com.br).

## DoD específico
Smoke pós-deploy verde no domínio final; Talita loga com o código e vê a carteira; runbook anotado com o que foi feito (sem segredos) e PROGRESS atualizado."""),
]


def run(args: list[str]) -> str:
    res = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        sys.stderr.write((res.stdout or "") + "\n" + (res.stderr or "") + "\n")
        raise SystemExit(f"comando gh falhou (exit {res.returncode}): {' '.join(args[:4])} ...")
    return res.stdout


def build_full(wu: str, body: str) -> str:
    """Corpo final: template dor-dod + Tamanho + bloco DoR (todos [x])."""
    full = body + TAMANHO + DOR_BLOCK
    if wu == "WU-X2":
        full += X2_NOTE
    return full


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed dos 12 cards ADR-010 no Project #1")
    ap.add_argument("--dry-run", action="store_true", help="so lista, nao cria")
    a = ap.parse_args()

    results: list[dict[str, str | None]] = []
    print(f"=== Seed ADR-010: {len(CARDS)} cards (todos em Backlog) ===")
    for i, (wu, title, prio, body) in enumerate(CARDS, 1):
        if a.dry_run:
            print(f"[{i:2}] [{prio:<5}] {title}")
            results.append({"wu": wu, "id": None, "title": title})
            continue
        print(f"[{i:2}/{len(CARDS)}] criando: {title} (Priority={prio})")
        out = run(["gh", "project", "item-create", NUMBER, "--owner", OWNER,
                   "--title", title, "--body", build_full(wu, body),
                   "--format", "json"])
        item_id = json.loads(out)["id"]
        run(["gh", "project", "item-edit", "--id", item_id, "--project-id", PROJECT_ID,
             "--field-id", STATUS_FID, "--single-select-option-id", BACKLOG])
        run(["gh", "project", "item-edit", "--id", item_id, "--project-id", PROJECT_ID,
             "--field-id", PRIO_FID, "--single-select-option-id", PRIO_OPT[prio]])
        results.append({"wu": wu, "id": item_id, "title": title})

    if a.dry_run:
        print("(dry-run) nada criado.")
    else:
        print(f"OK: {len(results)} cards criados em Backlog. "
              f"Board: https://github.com/users/{OWNER}/projects/{NUMBER}")
    # ULTIMA linha: JSON para o orquestrador promover a Todo depois.
    print(json.dumps(results, ensure_ascii=True))


if __name__ == "__main__":
    main()
