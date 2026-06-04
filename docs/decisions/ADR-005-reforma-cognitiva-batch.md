# ADR-005 — Reforma cognitiva: extração em lote, determinístico-primeiro e orçamento de requisições

- **Status:** Proposto (aguardando ratificação do dono do produto) — 2026-06-04
- **Emenda a:** ADR-000 §3 (cognição Gemini) e fluxo do M2. Complementa ADR-003 (poda) e
  ADR-004 (Apollo). Anexo ao roadmap `docs/planning/escala-volume-leads.md` (Pilar A).

## Contexto
O M2 atual faz **1 chamada Gemini por lead**. No tier gratuito, o teto não é o número de
tokens, é o **RPD (requisições/dia)**. A poda do ADR-003 reduz **desperdício** (não chama
Gemini para leads reprovados), mas **não eleva o teto**: se N leads sobrevivem à triagem,
são N chamadas. Com o ADR-004 (Apollo) ampliando a descoberta, o primeiro run de volume
real **estoura a quota Gemini** — largura sem teto cognitivo é um muro mais próximo.

Dois fatos sub-explorados:
1. **O Apollo já entrega firmografia estruturada** (setor, nº de funcionários, domínio,
   cargo). Hoje o Gemini é gasto re-extraindo o que o Apollo já deu de graça.
2. **O custo é por chamada, não por entidade.** Uma chamada que estrutura 10 entidades
   custa ~1 requisição de quota, não 10.

## Decisão
1. **Extração em LOTE (batch).** O M2 passa a estruturar **N entidades por chamada Gemini**
   (janela configurável `[gemini].batch_size`). Reduz o consumo de RPD por ~`batch_size`.
   A composição do batch é **determinística** (entidades ordenadas por `entity_id`, janela
   fixa) e o **cache é por hash do batch** — preserva a regra §3.2 (reexecução
   byte-idêntica). Falha/parse inválido de um item degrada **só aquele item**
   (`missing_evidence`/baixa confiança), não o batch.
2. **DETERMINÍSTICO-PRIMEIRO.** Antes do Gemini, um passo **puro** preenche a `Inference`
   com os campos **já estruturados** pela evidência (Apollo: setor, funcionários, domínio,
   cargo). O Gemini só é chamado para o **resíduo interpretativo** (intent/persona a partir
   de snippet social, desambiguação) — e **apenas** para entidades cujo resíduo justifica o
   custo. Entidade 100% coberta pelo Apollo pode **dispensar Gemini**. A `Inference` continua
   carregando `confidence` e `derived_from` (camadas isoladas preservadas).
3. **Orçamento de REQUISIÇÕES Gemini, diário e persistente.** Irmão do ledger de crédito do
   ADR-004: um `RequestLedger` (JSON atômico, período = dia do relógio **injetado**) conta
   requisições Gemini/dia contra um `gemini_rpd_cap` configurável. Estourou ⇒ não chama;
   marca o restante como **pendente** (não erro).
4. **Ondas resumíveis.** Um run grande é fatiado em **ondas**; cada onda processa um lote de
   entidades novas, persiste o progresso (`.ai/state/PROGRESS.md` + corpus do ADR-006) e
   **para limpo** ao atingir o orçamento do dia. O próximo run/dia **retoma** de onde parou.
   O volume vira função do **tempo** (dias), não de um único run sob quota.
5. **Determinismo preservado** (§3.2): batch ordenado, cache por hash, relógio/RNG injetados,
   Gemini mockado por fixture nos testes. A matemática do `p_score`/Hard Filter/`persona_fit`
   **não muda**; M3/M4 permanecem puros.
6. **Guardrails do ADR-000 §5 mantidos:** sem banco, sem fila — ondas são laços `asyncio`/
   sequenciais com estado em JSON atômico. Sem modelo local obrigatório (ver alternativa).

## Consequências
- ✅ Eleva o **teto** de leads/dia por ~`batch_size` (a alavanca, não só o desperdício).
- ✅ Determinístico-primeiro economiza Gemini onde o Apollo já cobre — sinergia direta com
  ADR-004.
- ✅ Ondas resumíveis + ledger de RPD = run de volume **dentro** da quota, sem travar em 429.
- ⚠️ Batch acopla o cache: mudar 1 entidade invalida o batch dela. Mitigado: o **corpus**
  (ADR-006) é o cache durável real — entidade extraída uma vez não re-entra em batch.
- ⚠️ Prompt de batch maior → risco de timeout (L-016). Mitigado: `batch_size` modesto +
  `snippet ≤ 800 chars` + `timeout=120s` (lições já registradas) + `flash-lite`.
- ⚠️ Nova superfície (ledger de RPD, montagem de batch). Mitigado: contratos `extra=forbid`,
  testes determinísticos com relógio injetado.

## Alternativa considerada (reflexão honesta)
**Modelo local** (ex.: um LLM pequeno via `llama.cpp`/Ollama) para a classificação barata
(persona/desqualificador), reservando Gemini só para o topo. Eleva o teto sem consumir RPD,
mas adiciona **peso de runtime** (download de pesos, RAM, latência) que tensiona o guardrail
"1 processo enxuto". **Recomendação:** ficar com batch + determinístico-primeiro + orçamento
RPD primeiro (zero dependência nova pesada); avaliar modelo local como **ADR futuro** só se a
quota Gemini provar ser o limite mesmo após o batch. Determinístico-primeiro já captura boa
parte do ganho de um modelo local, sem o custo de operá-lo.
