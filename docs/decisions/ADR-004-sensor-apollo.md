# ADR-004 — Apollo.io como segundo sensor firmográfico (busca + enriquecimento incremental)

- **Status:** Proposto (aguardando ratificação do dono do produto) — 2026-06-04
- **Emenda a:** ADR-000 §3 (fontes de dados: hoje "Tavily exclusivo do M1 + Gemini").
  Complementa o ADR-003 (colheita paralela multi-provedor) e o ADR-002 (UI).
- **SDD associado:** `docs/specs/apollo-busca-enriquecimento-incremental-sdd.md`.

## Contexto
O ADR-000 fixou **Tavily** como única fonte de busca do M1 e **Gemini** como cognição.
Tavily entrega snippets de busca aberta — bons para sinais sociais/intenção, fracos em
**firmografia estruturada** (setor, nº de funcionários, domínio, cargo). Sem firmografia
confiável e barata, a **poda precoce** do ADR-003 (`firmographic_triage` pré-Gemini)
depende de heurísticas frágeis sobre texto livre, e o `LeadCard` raramente traz contato
acionável (e-mail/telefone).

O Apollo.io expõe uma base B2B entity-resolved via **API REST oficial**. Seu tier
gratuito tem uma **assimetria de custo** que torna a adoção atraente sob escassez:

- **People Search** (`mixed_people/search`) — **0 crédito**. Descoberta firmográfica
  ampla, com contato **mascarado**.
- **Org/People Enrichment** (`organizations/enrich`, `people/match`) — **consomem** o
  escasso orçamento de **~100 data-credits/mês** (premissa 2026; persistem entre runs,
  resetam no mês).

Essa assimetria é exatamente o que o ADR-003 (FinOps + poda) sabe explorar: descoberta
grátis alimenta a poda barata; o crédito pago fica reservado para **revelar contato do
topo do ranking**. Adotar Apollo é, portanto, uma **decisão consciente de escopo do
dono** — adiciona um sensor, não infraestrutura.

## Decisão
1. **Adotar Apollo.io como SEGUNDO SENSOR de busca/firmografia, OPCIONAL e opt-in**
   (`[apollo].enabled=false` por padrão; requer `APOLLO_API_KEY`). Tavily permanece o
   default; Apollo é **estritamente aditivo** — desligado, o pipeline é byte-idêntico.
2. **Apollo é EVIDÊNCIA OBSERVADA (camada 1), nunca inferência.** A resposta é
   normalizada para o formato canônico de provedor (`{title,url,content,score}`) e vira
   `ObservedEvidence` (`source_trust≈0.9`). A `Inference` continua nascendo **só** no
   M2/Gemini. A entity-resolution do Apollo **não** curto-circuita o motor cognitivo.
3. **Enriquecimento INCREMENTAL por escada de crédito.** O gasto é preguiçoso e
   progressivo: degrau 1 (People Search, 0 crédito) → poda → degrau 2 (Org Enrich, 1
   crédito, condicional a lacuna firmográfica) → score/ranking → degrau 3 (People Match
   reveal, só **top-N** do ranking). Cada degrau só roda para quem o anterior aprovou.
4. **Orçamento de crédito é estado GOVERNADO e PERSISTENTE.** Diferente do orçamento de
   tokens (por-run, em memória), os créditos persistem entre runs e resetam no mês. Logo
   há um **ledger mensal em JSON atômico** (`CreditLedger`, `try_spend`/`refund`/
   reconciliação), fiel ao database-less + escrita atômica do ADR-000. **Não é banco.**
5. **Cache como economizador de crédito.** TTL dimensionado por volatilidade (People
   Search 24h; Org Enrich 30d; contato revelado 90d) — um dado pago **nunca** é cobrado
   duas vezes. Chave = hash canônico do corpo da requisição (`sort_keys=True`).
6. **Open-World preservado** (regra inviolável §3.3): 403 (sem acesso à API), 429,
   crédito esgotado e contato não-revelado viram **incerteza explícita** (`missing`,
   `gaps`, `confidence`↓), **nunca** dado fabricado. `OperatingMode` ganha
   `DEGRADED_APOLLO`; Apollo ausente degrada para Tavily sem quebrar o run.
7. **Determinismo preservado** (§3.2): Apollo sempre mockado por fixture; relógio/RNG
   injetados; ledger lê `now` injetado (período mensal reproduzível). A matemática do
   `p_score`/Hard Filter/`persona_fit` **não muda**.
8. **Demais guardrails do ADR-000 §5 mantidos:** sem banco, ORM, Redis, Celery, Docker,
   AWS, **sem scraping** (Apollo é API REST oficial). Sem CRM/outreach — contato revelado
   alimenta o `LeadCard` para ação **manual** do operador.

## Consequências
- ✅ Firmografia estruturada barata → **poda precoce mais forte** (ADR-003 §2) e
  `LeadCard` com contato acionável (top-N).
- ✅ FinOps: a descoberta grátis (People Search) faz o grosso; o crédito escasso é gasto
  só onde gera valor (revelar o topo do ranking), governado por ledger.
- ✅ Ativa `DEGRADED_APOLLO` e reusa `OperatingMode`/`DataQualityFlag`/`JsonCache`/
  `atomic_write_text` existentes.
- ⚠️ Novo estado persistente (ledger de crédito) — superfície de erro nova. Mitigado:
  JSON atômico, reconciliação com a verdade da Apollo (402), testes determinísticos com
  relógio injetado.
- ⚠️ Nova chave (`APOLLO_API_KEY`) — opcional; sem ela, Apollo fica ausente.
- ⚠️ **Risco de acesso à API no tier gratuito** (fontes 2026 divergem; alguns relatam API
  só em planos pagos). Mitigado: `enabled=false` default + degradação para Tavily em 403;
  validar a chave real **uma vez** (WU-A3) antes de investir nas WUs seguintes.
- ⚠️ Contato revelado é **PII**. Mitigado: revelar só no degrau 3 (top-N), cachear para
  não re-revelar, manter outreach fora de escopo (ADR-000 §1).

## Alternativa considerada (reflexão honesta)
Manter **só Tavily + Gemini** e extrair firmografia/contato apenas via Gemini sobre
snippets. É mais simples (zero crédito, zero estado novo), mas entrega firmografia
ruidosa (pior poda) e raramente contato direto — gastando **mais tokens Gemini** para um
resultado pior. O Apollo se paga quando o operador precisa de **contato acionável** e de
**poda barata em lote**. **Recomendação:** adotar Apollo como sensor opcional, começando
pelo caminho mínimo (M1/M2, sem depender do LangGraph), e plugar na camada do ADR-003
quando esta estiver no `main`. Se o dono preferir mínimo absoluto, manter `enabled=false`
não custa nada — o código fica dormente como o `[finops]` ficou antes do ADR-003.
