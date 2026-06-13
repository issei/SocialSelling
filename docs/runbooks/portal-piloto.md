# Runbook — Portal da Operadora (piloto ADR-010)

> Operação manual do piloto. Cobre deploy (WU-X2, ação do dono), seed da operadora,
> DNS, ciclo manual de publicação/feedback e métricas de sucesso. Fonte: SDD do portal §8.
> **Segredos nunca entram no repositório** — vivem só no painel do Render.

## 0. Pré-requisitos (já criados em 2026-06-09)
- **Neon Postgres free:** projeto `socialselling`, região AWS `us-east-1`. Copie a
  connection string **pooled** (vira `DATABASE_URL` só no Render).
- **Render free:** conta conectada ao repositório GitHub.
- **Domínio:** `selling.issei.com.br` (CNAME a configurar).

## 1. Deploy no Render (WU-X2)
1. No Render: **New → Blueprint** apontando para o repo. O `render.yaml` (raiz) define o
   Web Service free, região **Virginia (US East)** (mesma do Neon), build/start/health.
2. Preencha as 3 env vars (todas `sync: false` no `render.yaml` — sem valor no repo):
   - `DATABASE_URL` — connection string pooled do Neon.
   - `PUBLISH_TOKEN` — gere: `py -c "import secrets; print(secrets.token_urlsafe(32))"`.
     (Mesmo valor vai no `.env` local do motor como `PORTAL_PUBLISH_TOKEN`.)
   - `SECRET_KEY` — gere: `py -c "import secrets; print(secrets.token_urlsafe(32))"`.
3. Deploy. O start roda `uvicorn socialselling.portal.main:app`. O `portal/main.py`
   reconecta ao Neon por uso (o free suspende conexões ociosas — sem isso, a conexão
   morreria silenciosamente após idle).
4. **Free dorme após inatividade:** o primeiro acesso pode levar ~1 min (aceito no piloto).

## 2. Seed da operadora (após o 1º start criar as tabelas)
O `ensure_schema()` cria `snapshots`/`feedback_events`/`operators` no startup. Depois, no
**SQL editor do Neon**, insira a operadora:

```sql
INSERT INTO operators (operator_id, nome, code_hash, profile_id)
VALUES ('talita', 'Talita', '<sha256 hex do código>', 'talita')
ON CONFLICT (operator_id) DO UPDATE SET code_hash = EXCLUDED.code_hash;
```

Gere o código e o hash localmente:
```
py -c "import secrets; print(secrets.token_urlsafe(16))"          # o código de acesso
py -c "import hashlib; print(hashlib.sha256(b'<codigo>').hexdigest())"  # o code_hash
```
Entregue o **código** à operadora por canal privado (nunca commitar).

> Atalho de dev/local: `py scripts/seed_neon.py` faz o mesmo contra o `DATABASE_URL` do `.env`.

## 3. DNS / domínio
CNAME `selling.issei.com.br` → host `.onrender.com` do serviço. Adicione o custom domain
no Render (TLS automático).

## 4. Smoke pós-deploy
Única peça que toca o portal real (cobre o risco residual do `PostgresDAO`; fora do gate):
```
py scripts/smoke_portal.py --base-url https://selling.issei.com.br --token <PUBLISH_TOKEN>
```
Sequência: `GET /healthz` 200 → `POST /api/publish` 201 → repetir → 409 → `GET /api/feedback?since=0` 200.
Exit code 0 = verde.

## 5. Ciclo manual do piloto (sem agendamento)
1. `py -m socialselling.sync.pull_feedback` (WU-E4 — puxa tabulações pendentes).
2. Rodar o pipeline: `py -m socialselling.orchestrator --profile talita`.
3. `py -m socialselling.sync.publish --profile talita` (publica o novo top-20).
4. Avisar a operadora que há carteira nova.

> `--dry-run` no `publish` grava só o registro local (`data/published/`), sem POST.

## 6. Expurgo pós-pull
A cópia canônica dos eventos vive no motor (`data/feedback_events/events.jsonl`). A retenção
curta do Neon free deixa de ser risco após o pull. Não há expurgo manual obrigatório no piloto;
se o Neon encher, os eventos já consolidados podem ser truncados no banco (o motor tem o backup).

## 7. Métricas de sucesso (computadas no motor, offline)
A partir de `data/feedback_events/` + `data/calibration/` + `data/published/`:
- **Cobertura de tabulação:** % dos leads publicados com ≥ 1 evento.
- **Taxa de resposta por faixa de ranking** (1–5, 6–10, 11–20) — valida "quem abordar primeiro".
- **Taxa de `contato_invalido`** — qualidade do enriquecimento.

## 8. Troubleshooting
- **500 no primeiro acesso após idle:** conexão Neon suspensa; o `ReconnectingPostgresDAO`
  reabre na requisição seguinte. Se persistir, verifique `DATABASE_URL` no Render.
- **401 no publish:** `PORTAL_PUBLISH_TOKEN` (motor) ≠ `PUBLISH_TOKEN` (Render).
- **Login falha:** `code_hash` no Neon ≠ sha256 do código entregue; refaça o seed (§2).
