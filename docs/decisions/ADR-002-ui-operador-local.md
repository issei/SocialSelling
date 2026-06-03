# ADR-002 — UI de operador local (FastAPI) como superfície opcional

- **Status:** Aceito (aprovado pelo dono) — 2026-06-03
- **Emenda a:** ADR-000 §5 (guardrails anti-overengineering), que proíbe FastAPI.

## Contexto
O PoC entrega um pipeline determinístico (M1→M5) via CLI e arquivos JSON. Operá-lo
hoje exige editar JSON na mão e rodar comandos. O dono pediu uma **forma amigável**
de (a) ver/editar parâmetros (ICP, hipóteses, pesos), (b) executar o processo e
(c) ver os Lead Cards — além de **parametrização inicial assistida por Gemini**.
Explicitamente sugeriu FastAPI + HTML + Tailwind rodando local.

O ADR-000 §5 lista FastAPI como proibido. Esta é uma decisão consciente do dono de
**expandir o escopo**, não uma violação acidental.

## Decisão
1. **Permitir FastAPI EXCLUSIVAMENTE como UI de operador local** — uma superfície
   fina sobre o núcleo existente, rodando em `localhost`, uso single-user/dev.
2. **O núcleo do pipeline permanece infra-free e puro.** `orchestrator.run_pipeline`
   e os módulos M1–M5 **não importam** FastAPI. A web é um pacote separado
   (`socialselling.web`) que apenas *chama* o núcleo. Determinismo e testes do
   núcleo ficam intactos.
3. **Os demais guardrails do ADR-000 §5 CONTINUAM valendo:** sem banco, ORM,
   migrations, Redis, Celery, Docker, AWS/Terraform, scraping. Sem autenticação,
   sem multiusuário, sem deploy — é uma ferramenta local.
4. **Sem build front-end:** Tailwind via CDN, HTML via templates server-rendered
   (Jinja2). Zero Node/webpack.
5. **Dependências** entram como extra opcional `[web]` (fastapi, uvicorn, jinja2);
   o núcleo instala sem elas. CI/dev instalam `[dev]` que inclui `[web]`.

## Consequências
- ✅ Operação amigável (ver/editar/executar/ver resultado) sem tocar JSON na mão.
- ✅ Parametrização inicial assistida por Gemini (reaproveita `gerar-icp`).
- ✅ Núcleo continua testável e determinístico; a web é mockável (TestClient).
- ⚠️ Aumenta a superfície de código e dependências — mitigado por: web isolada,
  sem estado próprio (lê/grava os mesmos `config/*.json` e `data/*`), sem persistência nova.
- ⚠️ `localhost` only; não expor à rede. Chaves de API seguem no `.env` (nunca na UI).

## Alternativas consideradas
- **Manter só CLI:** mais enxuto, mas não atende ao pedido de usabilidade.
- **TUI (textual/rich):** sem dependência web, mas menos amigável p/ editar JSON e
  ver cards com links clicáveis (Instagram). FastAPI+HTML ganha em UX para este caso.
- **Streamlit:** rápido, mas menos controlável e adiciona um framework opinativo;
  FastAPI+HTML+Tailwind dá controle total com dependências mínimas.
