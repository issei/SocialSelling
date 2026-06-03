# Especificação — UI de Operador Local (SocialSelling)

> Status: **proposta para revisão**. Fonte de escopo: ADR-002 (emenda ao ADR-000 §5).
> Spec-first: este documento precede o código. Aprovado o plano, segue-se o
> SDD-to-Code Loop (contrato → testes → implementação → gate → PR).

## 1. Objetivo
Dar uma forma **amigável e local** de operar o pipeline, para um usuário não-técnico
(ex.: a especialista/dona do ICP):
1. **Ver e editar parâmetros** — ICP, catálogo de hipóteses, pesos de score.
2. **Parametrizar com ajuda da IA (Gemini)** — descrever o negócio em texto e receber
   um rascunho de ICP (e hipóteses) já válido, para revisar e salvar.
3. **Executar** o processo (M1→M5) com um clique.
4. **Ver o resultado** — os Lead Cards de forma visual (Instagram em destaque, clicável).

Fora de escopo: autenticação, multiusuário, deploy, banco, fila — ver ADR-002.

## 2. Princípios de arquitetura
- **Núcleo intocado e puro.** A web importa e chama `orchestrator.run_pipeline` e os
  loaders de config; **não** altera os contratos nem os módulos M1–M5.
- **Sem estado novo.** A UI lê/grava os mesmos artefatos: `config/icp_criteria*.json`,
  `config/hypotheses_catalog.json`, `config/runtime.toml`, e lê `data/prospects_ranked.json`.
  Escrita **atômica** (reaproveita o helper de `os.replace`).
- **Segredos só no `.env`.** As chaves nunca aparecem na UI nem são editáveis por ela.
- **Determinismo preservado.** A web não introduz não-determinismo no núcleo.
- **Sem build front-end.** Jinja2 + Tailwind (CDN). Um punhado de páginas.

## 3. Estrutura de pastas (nova)
```
src/socialselling/web/
  __init__.py
  app.py            # cria o FastAPI app, monta rotas e templates
  routes.py         # endpoints (config, assist, run, results)
  services.py       # ponte fina para o nucleo (load/save config, run, assist)
  __main__.py       # `py -m socialselling.web` -> uvicorn localhost:8000
  templates/        # base.html, index.html, _lead_card.html, _params.html
  static/           # (opcional) css custom minimo; Tailwind vem por CDN
tests/web/
  test_config_api.py  test_assist_api.py  test_run_api.py  test_pages.py
```

## 4. Telas (server-rendered)
### 4.1 Dashboard (`GET /`)
Uma página única com três seções (abas/âncoras):
- **Parâmetros**: formulário amigável + editor JSON cru para ICP, hipóteses e pesos.
  Botão *Validar & Salvar* (valida contra os contratos Pydantic; erro → mensagem clara).
- **Assistente (Gemini)**: campo "descreva seu negócio" + botão *Gerar rascunho de ICP*.
  Mostra o JSON proposto para revisão; *Usar este rascunho* preenche o formulário de ICP.
- **Executar & Resultados**: seletor de ICP (ex.: `talita`/`example`), botão *Executar*,
  spinner durante o run, e a lista de **Lead Cards** renderizada (Instagram em destaque).

### 4.2 Componente Lead Card (visual)
Cada card: `#rank · display_name — role @ company`, setor · local, **P=score** (fit/intent/conf),
📸 **Instagram** (link clicável), 🔗 LinkedIn / 🌐 Site, "Por que agora", lacunas, nº de fontes.
Ordenado por rank. Cards com `hard_filter_passed=false` não aparecem (já filtrados pelo núcleo).

## 5. API (FastAPI)
| Método | Rota | Função |
|---|---|---|
| GET | `/` | Dashboard (HTML) |
| GET | `/api/config` | Retorna ICP atual + hipóteses + pesos (JSON) |
| POST | `/api/config/icp` | Valida (`ICPCriteria`) e salva `config/icp_criteria.<nome>.json` |
| POST | `/api/config/hypotheses` | Valida (`HypothesisCatalog`) e salva |
| POST | `/api/config/scoring` | Valida e atualiza os pesos em `runtime.toml` |
| POST | `/api/assist/icp` | Descrição do negócio → Gemini → rascunho `ICPCriteria` validado |
| POST | `/api/run` | Dispara o pipeline (background); retorna `run_id` |
| GET | `/api/run/{run_id}` | Status (`running`/`done`/`error`) + Lead Cards quando pronto |

Notas:
- **`/api/run` assíncrono**: o run faz chamadas externas (segundos). Roda em
  `BackgroundTasks`/threadpool; o front faz *polling* curto em `/api/run/{id}`.
  Estado do run mantido **em memória** do processo (sem banco) — coerente com o PoC.
- **`/api/assist/icp`**: reusa o prompt de `docs/prompts/gerar-icp.md`. Resposta do
  Gemini é validada com `ICPCriteria`; em falha, retorna erro amigável (sem salvar).
- Validação: toda escrita passa pelos contratos; corpo inválido → HTTP 422 + mensagem.

## 6. Parametrização assistida por Gemini (detalhe)
1. Usuário escreve: "vendo programa de gestão para fundadoras de consultoria...".
2. Backend monta o prompt do `gerar-icp` (schema + regras) + a descrição.
3. `GeminiClient.generate_json` retorna o JSON; backend valida com `ICPCriteria`.
4. Sucesso → devolve o rascunho para a tela (não salva ainda; usuário revisa e salva).
5. Reaproveita o `GeminiClient` existente (mesma chave do `.env`, modelo do `runtime.toml`).
6. (Opcional, fase 2) gerar também rascunho de `hypotheses_catalog` a partir de "gatilhos de compra".

## 7. Plano de testes
**Gate inalterado**: `ruff` + `mypy --strict` + `pytest` 100% verde e determinístico.
A web é testada com **FastAPI `TestClient`** (sem subir servidor) e **mocks** — zero rede.

| Teste | O que valida |
|---|---|
| `test_pages.py` | `GET /` responde 200 e contém âncoras das 3 seções |
| `test_config_api.py` | `GET /api/config` retorna o estado; `POST` ICP **inválido → 422**; ICP válido → salva (em dir temporário) e relê |
| `test_assist_api.py` | `POST /api/assist/icp` com **Gemini mockado** retornando rascunho → valida e devolve; Gemini retornando lixo → erro 422 (não salva) |
| `test_run_api.py` | `POST /api/run` com **pipeline mockado** (`run_pipeline` → Lead Cards fixos) → `run_id`; `GET /api/run/{id}` → `done` + cards; ordem por rank |
| `test_services.py` | save atômico não corrompe em falha; paths configuráveis (não escreve no repo real durante teste) |

Princípios de teste:
- **Injeção de dependências**: `services` recebe paths de config e os clientes
  (Gemini/pipeline) por parâmetro/override, para os testes passarem fakes.
- **Sem rede**: Gemini e o pipeline são mockados (como já fazemos no núcleo).
- **Isolamento de FS**: testes escrevem em `tmp_path`, nunca em `config/` real.
- Determinismo: respostas mockadas fixas → asserts estáveis.

## 8. Plano de implementação (WUs, cada uma = 1 PR verde)
- **WU-U1 — Fundação web**: ADR-002 + esta spec (este PR, docs). Depois: deps `[web]`
  (fastapi, uvicorn, jinja2), `app.py` mínimo (`GET /` + `GET /api/config`), `__main__`,
  1 teste de página. *Gate verde.*
- **WU-U2 — Parâmetros**: endpoints de config (GET/POST ICP, hipóteses, scoring) com
  validação e save atômico em `services`; testes de validação e persistência (tmp).
- **WU-U3 — Assistente Gemini**: `POST /api/assist/icp` reusando o prompt gerar-icp +
  `GeminiClient`; testes com Gemini mockado (sucesso e lixo→erro).
- **WU-U4 — Executar & Resultados (API)**: `POST /api/run` (background) + `GET /api/run/{id}`
  com pipeline mockado; estado em memória; testes de ciclo running→done.
- **WU-U5 — Front-end**: templates Jinja2 + Tailwind (CDN); formulário de parâmetros,
  assistente, botão executar com polling, e os Lead Cards visuais. Smoke `TestClient`.
- **WU-U6 — Acabamento**: README "como rodar a UI" (`py -m socialselling.web` →
  http://localhost:8000), mensagens de erro amigáveis, e um teste E2E (TestClient) cobrindo
  o fluxo feliz (gerar ICP mock → salvar → executar mock → ver cards).

Versionamento: tags `v0.10.0` (API web) … `v0.11.0` (UI completa). Rollback por tag.

## 9. Riscos e mitigações
- **Run longo/instável (rede)**: background + status + timeout; erros viram mensagem na UI.
- **Edição de JSON inválido**: validação Pydantic antes de salvar; nunca grava inválido.
- **Vazamento de chave**: `.env` nunca exposto pela UI; a tela não lê/edita segredos.
- **Escopo inflar**: ADR-002 fixa limites (localhost, sem auth, sem banco, sem build front).

## 10. Pendências fora desta spec (backlog já existente)
- Precisão de persona no ranking (entram homens/contas de empresa) — `docs/analysis/sondagem-talita.md`.
  Pode virar um filtro/controle exposto também na UI numa fase seguinte.
