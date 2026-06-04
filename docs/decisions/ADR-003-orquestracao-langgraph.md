# ADR-003 — Camada de orquestração paralela (LangGraph) + FinOps

- **Status:** Aceito (aprovado pelo dono; SDD endurecido para v1.1 em revisão crítica) — 2026-06-03
- **Emenda a:** ADR-000 §5 (guardrails). Complementa ADR-001 (intenção) e ADR-002 (UI).

## Contexto
O orquestrador atual (`orchestrator.run_pipeline`) é **síncrono, single-thread**:
M1 busca em UM provedor (Tavily), M2 extrai em lote, M3/M4/M5 reduzem. Dois limites
operacionais surgem ao escalar a colheita:
1. **Fragilidade de rede** — um único provedor de busca é um ponto único de bloqueio
   (429 de quota, Cloudflare/CAPTCHA se houver fallback para scraping de navegador).
2. **Custo/quota (FinOps)** — em lotes ruidosos, gastamos tokens Gemini (extração +
   ganchos) em leads que um **desqualificador rígido** já reprovaria. Pagar Gemini
   para depois zerar o `p_score` é desperdício de quota de tier gratuito.

O ADR-000 §5 proíbe overengineering e trata M1–M5 como **funções de pipeline, não
agentes**. LangGraph é um framework de orquestração com estado — sua adoção é uma
**decisão consciente de escopo do dono**, não uma violação acidental.

## Decisão
1. **Adotar LangGraph como MOTOR DE ORQUESTRAÇÃO OPCIONAL** (`socialselling.graph`),
   dedicado à **colheita paralela multi-provedor** e à **poda precoce / FinOps**.
   Entra como extra opcional `[graph]`; o núcleo instala sem ele.
2. **O núcleo permanece PURO e determinístico.** M3 (`run_m3`) e M4 (`run_m4`)
   continuam funções puras, importadas e chamadas pelos nós do grafo. A matemática
   do `p_score`, o Hard Filter por `DISQUALIFIER_VOCAB` e o `persona_fit` **não mudam**.
   O grafo orquestra I/O e decisões de controle; **não reimplementa scoring**.
3. **Anti-bloqueio por APIs limpas, não por scraping.** A colheita usa Tavily, Brave
   Search e Google CSE (APIs REST estruturadas) em paralelo. **Proibido** Playwright/
   Selenium/scraping de navegador cru (dispara CAPTCHA/Cloudflare e fere o ADR-000).
4. **Determinismo preservado** (regra inviolável §3.2): a não-determinação do grafo
   (ordem assíncrona, jitter de backoff) NUNCA altera a saída pontuada — a evidência é
   fundida por `evidence_id` e ordenada antes da extração; M3/M4 são puros; testes
   injetam relógio fixo + RNG semeado + provedores mockados → reexecução byte-idêntica.
5. **Demais guardrails do ADR-000 §5 mantidos:** sem banco, ORM, Redis, Celery, Docker,
   AWS, scraping. Persistência segue **JSON atômico** (`JsonCache`, `atomic_write_text`).

## Consequências
- ✅ Resiliência: falha/429 de um provedor degrada, não quebra (Modo Degradado).
- ✅ FinOps: poda precoce evita gastar Gemini em leads reprovados (economia medível, §2 do SDD).
- ✅ Ativa contratos hoje **dormentes**: `OperatingMode`, `DataQualityFlag`, `[finops]`
   (`tau_finops`, `kappa_degraded`).
- ⚠️ Nova dependência (`langgraph`) + nova superfície de código. Mitigado: extra opcional,
   núcleo intocado, fallback para o `run_pipeline` síncrono sempre disponível.
- ⚠️ Novas chaves no `.env` (Brave/Google CSE) — opcionais; sem elas, o scout degrada
   para os provedores disponíveis.

## Alternativa considerada (reflexão honesta)
O mesmo valor (async multi-provedor + poda) é alcançável com um orquestrador async
**leve** (`asyncio` + um reducer manual), sem LangGraph. LangGraph se paga quando o
grafo por-lead cresce (comitê de compra, multi-hop, replanejamento). **Recomendação:**
adotar LangGraph pela legibilidade do state-machine e pela trilha de evolução, mantendo
o núcleo puro como fonte da verdade do scoring. Se o dono preferir mínimo, a §7 do SDD
descreve a variante "async-lite" sem a dependência.
