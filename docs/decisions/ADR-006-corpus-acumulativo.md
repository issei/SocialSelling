# ADR-006 — Corpus de leads acumulativo (upsert idempotente, persistente e crescente)

- **Status:** Proposto (aguardando ratificação do dono do produto) — 2026-06-04
- **Emenda a:** persistência do `orchestrator` (ADR-000 §3 — JSON em arquivo). Complementa
  ADR-005 (cognição). Anexo ao roadmap `docs/planning/escala-volume-leads.md` (Pilar B).

## Contexto
Hoje o `run_pipeline` **sobrescreve** `data/prospects_ranked.json` e retorna
`cards[:max_leads_per_cycle]` (corte em **50**). Consequências para volume:
- Cada run **descarta** o resultado do anterior — o esforço **não acumula**.
- O `max_leads_per_cycle=50` é um **limite de volume**, não só de exibição.
- Re-rodar o mesmo ICP **re-processa** entidades já vistas — desperdício de Gemini/crédito.

Para "muito mais leads rodando local", o volume precisa **acumular no tempo**, não morrer a
cada execução. Este é o **maior ganho de volume real** do roadmap — mais do que ampliar a
descoberta (ADR-004), porque transforma N runs de 50 em um corpus de N×50 que só cresce.

## Decisão
1. **Corpus persistente e crescente.** Introduz-se um **store de leads** durável
   (`data/corpus/…`, JSON/NDJSON atômico) que **acumula entre runs**. O `prospects_ranked.json`
   passa a ser uma **projeção/visão** ordenada do corpus, não a fonte da verdade.
2. **Upsert IDEMPOTENTE por `entity_id` canônico.** Cada entidade tem chave estável (domínio
   canônico — alinhado ao Pilar D/ADR-008). Reprocessar a mesma entidade **atualiza** o
   registro (merge de evidências/inferência mais recente), nunca duplica. Idempotência =
   reexecução byte-idêntica do corpus dado o mesmo input (regra §3.2).
3. **Processar só o NOVO.** Cada run/onda (ADR-005) consulta o corpus e extrai (Gemini) **só
   entidades ausentes ou expiradas**. O corpus é, portanto, o **cache durável das extrações**
   — torna o cache-por-prompt (L-017) secundário e **protege a quota Gemini entre runs**.
4. **Ranking sobre o corpus inteiro.** M4 ordena o corpus acumulado (tie-break estável por
   `entity_id`). `max_leads_per_cycle` é **rebaixado a limite de exibição/relatório**, não de
   volume — some como teto de quantos leads o sistema "conhece".
5. **Persistência atômica preservada** (ADR-000): escrita write-temp + `os.replace`; ao
   crescer, evolui para append/shards (Pilar C/ADR-007) **sem** virar banco.
6. **Determinismo** (§3.2): merge de upsert determinístico (última-evidência-vence por
   `captured_at` + tie-break por `evidence_id`), relógio injetado, sem `datetime.now()`
   interno. Testes: dois runs sobre as mesmas fixtures ⇒ corpus byte-idêntico; um run que
   re-vê entidade do run anterior **não** gera chamada Gemini nova.

## Consequências
- ✅ **Volume acumula no tempo** — 10 runs de 50 = corpus de ~500, deduplicado, não 50.
- ✅ Re-rodar é **barato**: só o novo é extraído ⇒ economia direta de RPD Gemini e crédito
  Apollo (sinergia com ADR-004/005).
- ✅ Remove o `max_leads=50` como teto de volume; vira controle de apresentação.
- ✅ Base natural para o Cockpit (ADR-002) mostrar "corpus conhecido" crescendo.
- ⚠️ Estado durável maior = mais superfície de corrupção. Mitigado: escrita atômica, schema
  Pydantic `extra=forbid`, e migração para shards (ADR-007) antes de ficar grande.
- ⚠️ `entity_id` ingênuo (`hash(nome)`) duplicaria o corpus. **Dependência:** exige o Pilar D
  (ADR-008, domínio canônico) para upsert correto — por isso C/D vêm logo após.
- ⚠️ Política de expiração (re-extrair entidade após T) precisa ser definida (default: nunca
  expira firmografia; intent expira em dias). Parametrizável em `runtime.toml`.

## Alternativa considerada (reflexão honesta)
Manter o run **stateless** (sobrescreve) e simplesmente **elevar `max_leads_per_cycle`** para,
digamos, 1.000. É trivial, mas **não acumula** (cada run recomeça do zero, re-paga Gemini/
crédito por tudo) e **estoura a quota** num único run gigante. O corpus acumulativo é o que
torna o volume **sustentável** sob tier gratuito: o esforço de cada dia **persiste** e o
sistema fica mais rico a cada execução. **Recomendação:** adotar o corpus; manter o run
stateless apenas como modo de *smoke test* determinístico (fixtures), onde acumular não
importa.
