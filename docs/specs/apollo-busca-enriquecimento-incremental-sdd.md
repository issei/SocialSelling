# SDD — Apollo.io como sensor firmográfico (busca + enriquecimento incremental, tier gratuito)

> **Status:** **PROPOSTA (v1.0 — aguardando aprovação do dono)**.
> Requer **ADR-004** (emenda ao ADR-000 §3: hoje "Tavily exclusivo do M1 + Gemini").
> Apollo entra como **segundo sensor de busca/firmografia**, análogo a como o ADR-003
> autorizou Brave/Google CSE. Spec-first: este documento precede o código. Segue o
> SDD-to-Code Loop do repositório (contrato → BDD+fixtures → implementação → gate
> `ruff`+`mypy --strict`+`pytest` → PR).
>
> **Princípio reitor — "incremental da melhor forma possível":** o tier gratuito do
> Apollo é escasso (**100 data-credits/mês**, que **persistem entre runs** e **resetam
> mensalmente**). Logo o gasto de crédito é tratado como uma **escada de enriquecimento
> preguiçosa e progressiva**: cada degrau mais caro só roda para o **subconjunto de
> leads que o degrau anterior justificou**, e **nunca** se paga duas vezes pelo mesmo
> dado (cache + ledger persistente). O degrau **zero-crédito** (People Search) faz quase
> todo o trabalho; os créditos pagos são reservados para **revelar contato do topo do
> ranking**.
>
> **Não-objetivo:** Apollo **não** substitui o motor cognitivo. A inferência continua
> sendo do M2/Gemini; Apollo é **evidência observada estruturada** (camada 1), nunca uma
> inferência. Sem scraping, sem CRM, sem outreach (ADR-000 §1/§5).

---

## 0. Premissas, invariantes e reaproveitamento do repositório

| Invariante (não negociável) | Origem no repo | Como o Apollo respeita |
|---|---|---|
| Isolamento de camadas: Evidence ≠ Inference | `contracts.py`, CLAUDE.md §3.1 | Resposta Apollo → `ObservedEvidence` (camada 1); a entidade-resolução do Apollo **não** vira `Inference` sem passar pelo M2 |
| Open-World: ausência = incerteza, nunca falso | CLAUDE.md §3.3, `m1_busca._missing` | 403 sem-API / 429 / **crédito esgotado** ⇒ `missing_evidence=True` + `DEGRADED`, jamais dado fabricado |
| Determinismo byte-idêntico | regra §3.2 | Apollo sempre mockado por fixture; relógio e RNG injetados; ledger lê `now` injetado |
| Persistência atômica JSON, database-less | `core.atomic`, `core.cache.JsonCache` | Cache de respostas **e** ledger de créditos via `atomic_write_text` (write-temp + `os.replace`) |
| Sem scraping de navegador | ADR-000 §5 | Apollo é **API REST oficial**; redundância por provedor, não por headless |
| Custo de infra = zero (só tokens das APIs) | ADR-000 §3 | Tier gratuito Apollo = **US$ 0** de infra; o único orçamento novo são **créditos**, não dinheiro |
| Contratos `extra="forbid"` | `contracts.py` | Novos schemas (§4) são **aditivos**, em `skills/apollo_client.py` e `graph/schemas.py` |
| Normalização canônica de provedor | SDD-LangGraph §1.2 (`AsyncSearchClient`) | Apollo implementa o **mesmo Protocol** e normaliza para `{"results":[{title,url,content,score}]}` ⇒ `m1_busca._map_result` e o prompt do M2 funcionam **sem alteração** |

**Contratos dormentes que esta camada usa:** `OperatingMode` (acrescenta
`DEGRADED_APOLLO`), `DataQualityFlag`, e o `[finops]`/ledger do SDD-LangGraph (ADR-003).

**Decisão-chave do tier gratuito (resolve a assimetria de custo):**

| Endpoint Apollo | URL | Custo de crédito | Papel no pipeline |
|---|---|---|---|
| **People Search** | `POST /api/v1/mixed_people/search` | **0 crédito** (otimizado p/ API) | **Degrau 1 — descoberta**. Faz o grosso do trabalho de graça. Retorna pessoas entity-resolved + firmografia, com **contato mascarado** (`email_not_unlocked@domain.com`) |
| Organization Search | `POST /api/v1/mixed_companies/search` | **consome** crédito | **Evitado** no tier gratuito (People Search já traz a empresa aninhada) |
| **Organization Enrichment** | `POST /api/v1/organizations/enrich` | **1 crédito/org** | **Degrau 2 — firmografia precisa** (só p/ leads que passaram da triagem e têm lacuna) |
| **People Enrichment / Match** | `POST /api/v1/people/match` | **1 data-credit + email/mobile credit** (reveal) | **Degrau 3 — revelar contato** (só p/ **top-N** do ranking) |

> **Fatos do tier gratuito (2026), rotulados como premissa de orçamento — ver §8 Riscos:**
> ~**100 data-credits/mês**, **10.000 email-credits/mês** (domínio corporativo) ou
> **100/mês** (domínio pessoal/Gmail), **5 mobile-credits/mês**, reset mensal. O acesso
> à API e os limites de RPM **não são publicados por tier** e podem variar; o desenho é
> **defensivo** — se a chave não tiver acesso à API (403), o provedor fica **ausente** e
> o pipeline degrada para Tavily sem quebrar. Fonte: docs.apollo.io/docs/api-pricing.

---

## 1. A Escada de Enriquecimento Incremental (coração do SDD)

A regra é **"o degrau N só roda para quem o degrau N−1 aprovou"**. Cada degrau acima
do 1 debita o ledger de créditos (§3); todos consultam o cache antes de gastar (§2).

```
Degrau 0  Tavily (M1 atual)            token-only      descoberta ampla, snippets sociais
   │
Degrau 1  Apollo People Search         0 CRÉDITO       firmografia estruturada + persona,
   │       (mixed_people/search)                        contato MASCARADO → vira ObservedEvidence
   │                                                     ↳ alimenta a TRIAGEM BARATA (poda sem Gemini)
   ▼
  [prune_gate]  poda fora_de_setor / persona-empresa / teto<tau_finops   (ADR-003 §2)
   │  (sobreviventes apenas)
   ▼
Degrau 2  Apollo Org Enrichment        1 crédito/org   SÓ se faltar firmografia confiável
   │       (organizations/enrich)                       (employee_count/industry/tech) p/ o score
   ▼
  M2 Gemini (inferência) → M3 score → M4 ranking        (núcleo puro, inalterado)
   │  (TOP-N do ranking apenas; N = orçamento de crédito restante)
   ▼
Degrau 3  Apollo People Match (reveal) 1 cr + email/mob REVELAR e-mail/telefone do lead final
           (people/match)                               → preenche LeadCard.contact
```

**Por que esta ordem é ótima sob escassez de crédito:**

1. **O trabalho caro é empurrado para o fim do funil.** Revelar contato (degrau 3) é o
   único passo que gasta os escassos email/mobile-credits; ele só toca **leads que já
   passaram em triagem, extração, score e ranking**. Com 100 créditos/mês, isso é a
   diferença entre revelar os **20 melhores** leads do mês ou queimar a cota nos 100
   primeiros ruidosos.
2. **A descoberta é grátis.** People Search não debita crédito → podemos varrer o ICP em
   largura sem orçamento, e usar o resultado estruturado para **podar antes do Gemini**
   (sinergia direta com a poda precoce do ADR-003 §2 — Apollo é a fonte firmográfica
   ideal para o `firmographic_triage` barato).
3. **Org Enrichment é condicional.** Só roda quando o People Search **não** trouxe a
   firmografia necessária para o score — evita 1 crédito/lead desnecessário.

### 1.1 Gating por orçamento e por valor (quem sobe cada degrau)

```python
# src/socialselling/apollo/ladder.py  (orquestra os degraus; puro exceto chamadas de I/O)
def select_for_org_enrich(leads, inferences, budget) -> list[Lead]:
    """Degrau 2: só quem passou na triagem E tem lacuna firmográfica relevante p/ o score."""
    candidates = [l for l, inf in zip(leads, inferences)
                  if not inf.pruned and _missing_firmographics(inf)]   # employee_count/industry None
    return candidates[: budget.remaining_data_credits()]               # respeita o ledger

def select_for_reveal(ranked, budget) -> list[RankedProspect]:
    """Degrau 3: TOP-N do ranking, limitado pelo MENOR entre data e email credits restantes."""
    n = min(budget.remaining_data_credits(), budget.remaining_email_credits())
    return ranked[:n]            # ranking já é determinístico (M4): -p_score, company_id
```

> **Invariante de incrementalidade:** a escolha de quem sobe cada degrau é **função do
> ranking determinístico (M4)** e do **ledger** — dado o mesmo cache, o mesmo conjunto
> de leads é revelado, byte-idêntico. `max_concurrency` afeta latência, não seleção.

---

## 2. Cache como economizador de crédito (reusa `JsonCache`)

O cache deixa de ser só latência: **cada hit de cache em endpoint pago é 1 crédito não
gasto**. Por isso o TTL é **dimensionado por volatilidade do dado**, não por um valor
único:

| Dado | Endpoint | TTL de cache | Justificativa |
|---|---|---|---|
| People Search (descoberta) | `mixed_people/search` | **24 h** (igual Tavily) | resultados mudam com o ICP/dia; é grátis, TTL curto é ok |
| Org firmografia | `organizations/enrich` | **30 dias** | firmografia é estável; re-pagar crédito por ela é desperdício |
| Contato revelado (e-mail/tel) | `people/match` (reveal) | **90 dias** (ou ∞ até invalidação) | contato revelado **nunca** deve custar 2 créditos; é o dado mais caro |

```python
# A chave de cache é o hash canônico do corpo da requisição (sort_keys=True), reusando
# core.cache.query_hash — assim payloads equivalentes (ordem de filtros diferente)
# colidem no MESMO slot e não geram cobrança dupla.
key = query_hash(json.dumps(apollo_request_body, sort_keys=True, ensure_ascii=False))
cached = cache.get(key, now, ttl_hours=ttl_for(endpoint))
if cached is not None:                      # HIT → 0 crédito
    return cached
# MISS → debita ledger ANTES da chamada paga (reserva otimista), confirma no retorno
```

> **Regra do crédito:** nenhum endpoint pago é chamado sem **(a)** consultar o cache e
> **(b)** ter o ledger reservado o crédito. Cache frio + crédito esgotado ⇒ `missing`,
> nunca chamada.

---

## 3. Ledger de créditos persistente e mensal (novo, atômico, database-less)

Diferente do orçamento de **tokens** (por-run, em memória — SDD-LangGraph §4), o
orçamento de **créditos Apollo persiste entre runs e reseta no mês**. Logo precisa de um
estado **frio em disco**, escrito atomicamente. **Não** é banco — é um JSON atômico,
fiel ao guardrail §5 do CLAUDE.md.

```python
# src/socialselling/core/credit_ledger.py
from pydantic import BaseModel, ConfigDict, Field
from socialselling.core.atomic import atomic_write_text

class CreditLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: str                              # "YYYY-MM" do relógio INJETADO (reset mensal)
    data_credits_used: int = Field(ge=0, default=0)
    email_credits_used: int = Field(ge=0, default=0)
    mobile_credits_used: int = Field(ge=0, default=0)
    # Limites do tier (de runtime.toml [apollo]); premissa, ver §8.
    data_credits_cap: int = 100
    email_credits_cap: int = 100             # default conservador (domínio pessoal)
    mobile_credits_cap: int = 5

class CreditBudget:
    """Carrega o ledger do mês corrente; rola o período no vIRAR do mês (now injetado)."""
    def __init__(self, path: str, now: datetime, caps: "ApolloCaps") -> None:
        ledger = _load(path)
        period = now.strftime("%Y-%m")
        if ledger is None or ledger.period != period:        # mês novo → zera contadores
            ledger = CreditLedger(period=period, **caps.as_dict())
            atomic_write_text(path, ledger.model_dump_json())
        self._ledger, self._path = ledger, path

    def remaining_data_credits(self) -> int:
        return max(0, self._ledger.data_credits_cap - self._ledger.data_credits_used)

    def try_spend(self, *, data: int = 0, email: int = 0, mobile: int = 0) -> bool:
        """Reserva atômica: True se cabe no orçamento (debita e PERSISTE); False ⇒ degrada."""
        if (self._ledger.data_credits_used + data > self._ledger.data_credits_cap or
                self._ledger.email_credits_used + email > self._ledger.email_credits_cap or
                self._ledger.mobile_credits_used + mobile > self._ledger.mobile_credits_cap):
            return False
        self._ledger.data_credits_used += data
        self._ledger.email_credits_used += email
        self._ledger.mobile_credits_used += mobile
        atomic_write_text(self._path, self._ledger.model_dump_json())   # write-temp + os.replace
        return True
```

> **Consistência sob falha:** `try_spend` reserva **antes** da chamada (pessimista). Se a
> chamada Apollo falhar com **429/5xx** depois de reservar, um `refund(...)` simétrico
> devolve o crédito (idempotente por `request_hash`, registrado no cache de idempotência).
> Se a falha for **402/limite atingido reportado pela própria Apollo**, o ledger é
> **reconciliado** para `used = cap` (a verdade do provedor vence). Persistência sempre
> atômica.

> **Por que persistente:** sem isso, dois runs no mesmo dia gastariam a cota duas vezes
> "sem saber". O ledger transforma os 100 créditos/mês num **recurso governado**, exposto
> no Cockpit (ADR-002) como medidor de saldo.

---

## 4. Contratos (Pydantic, `extra="forbid"`)

Aditivos; **não** tocam `contracts.py`. O cliente Apollo vive em
`skills/apollo_client.py`; os schemas de controle em `apollo/schemas.py`.

```python
# src/socialselling/apollo/schemas.py
from __future__ import annotations
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field

class ApolloEndpoint(StrEnum):
    PEOPLE_SEARCH = "people_search"          # 0 crédito
    ORG_ENRICH    = "org_enrich"             # 1 data-credit
    PEOPLE_MATCH  = "people_match"           # 1 data + email/mobile (reveal)

class ApolloPersonHit(BaseModel):
    """Normalização do item de People Search (subset estável da resposta Apollo)."""
    model_config = ConfigDict(extra="forbid")
    apollo_id: str
    name: str
    title: str | None = None
    seniority: str | None = None
    linkedin_url: str | None = None
    # Empresa aninhada (firmografia que alimenta a triagem barata):
    organization_name: str | None = None
    organization_domain: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    location: str | None = None
    # Contato MASCARADO no tier grátis; reveal só no degrau 3:
    email_status: str | None = None          # "verified" | "locked" | None
    email_masked: bool = True

class ApolloRevealResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    apollo_id: str
    email: str | None = None
    phone: str | None = None
    revealed: bool = False                    # False ⇒ Apollo não tinha o dado (≠ erro)

class ApolloCaps(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_credits_cap: int = 100
    email_credits_cap: int = 100
    mobile_credits_cap: int = 5

class ApolloPlan(BaseModel):
    """Configuração de runtime.toml [apollo]."""
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False                     # opt-in (chave + ADR-004)
    base_url: str = "https://api.apollo.io/api/v1"
    ledger_path: str = "data/apollo_credit_ledger.json"
    caps: ApolloCaps = Field(default_factory=ApolloCaps)
    reveal_top_n: int = Field(ge=0, default=20)   # teto extra além do orçamento
    org_enrich_ttl_hours: int = 720           # 30 dias
    reveal_ttl_hours: int = 2160              # 90 dias
    per_minute_limit: int = 50                # premissa defensiva; backoff cobre o resto
```

**Normalização para o formato canônico** (para que M1/M2 não mudem):

```python
# src/socialselling/apollo/normalize.py
def person_hit_to_canonical(hit: ApolloPersonHit) -> dict:
    """ApolloPersonHit → item canônico {title,url,content,score} (formato Tavily).
    `content` carrega a firmografia em texto estável para o M2 e a triagem barata lerem."""
    facts = [
        f"empresa: {hit.organization_name or '—'}",
        f"setor: {hit.industry or '—'}",
        f"funcionarios: {hit.employee_count if hit.employee_count is not None else '—'}",
        f"cargo: {hit.title or '—'}", f"local: {hit.location or '—'}",
    ]
    return {
        "title": f"{hit.name} — {hit.organization_name or ''}".strip(" —"),
        "url": hit.linkedin_url or (f"https://{hit.organization_domain}" if hit.organization_domain else ""),
        "content": " | ".join(facts),         # determinístico: ordem fixa de campos
        "score": 0.9,                           # source_trust alto: vendor estruturado
    }
```

> **Camadas preservadas:** o `ObservedEvidence` resultante tem `source_trust≈0.9` (dado
> de vendor é mais confiável que um snippet de busca aberta), mas continua sendo
> **evidência observada** — a `Inference` só nasce no M2. A firmografia estruturada do
> Apollo é lida pela **triagem barata** (ADR-003 §2.2) diretamente do `content` canônico,
> melhorando a poda precoce **sem** virar inferência.

---

## 5. Integração no pipeline (dois pontos de plugue, ambos opt-in)

### 5.1 Caminho canônico v1.0 (M1/M2) — mínimo viável

- **M1:** `run_m1` ganha um parâmetro opcional `apollo: ApolloPeopleSearchClient | None`.
  Quando presente e `ApolloPlan.enabled`, o M1 executa as queries também no Apollo
  (degrau 1, 0 crédito), normaliza via `person_hit_to_canonical` e funde as evidências
  com as do Tavily (dedup por `evidence_id`, §SDD-LangGraph §5). Tavily permanece o
  default; Apollo é **aditivo**.
- **M2:** inalterado — recebe mais evidências (mais firmografia estruturada) e infere com
  maior confiança. Sem Apollo na conta, M2 é byte-idêntico ao atual.
- **Pós-M4 (novo passo `m_reveal`):** para o **top-N** do `RankedProspect[]`, chama
  `people/match` (degrau 3) e preenche `LeadCard.contact.email/phone`. É o único passo
  que debita email/mobile credits, e roda **depois** do ranking.

### 5.2 Caminho LangGraph (ADR-003) — onde os gates já existem

Apollo encaixa **sem nó novo de topologia**:
- `parallel_scout` ganha `ApolloPeopleSearchClient` como mais um `AsyncSearchClient`
  (degrau 1, concorrente com Tavily/Brave/CSE).
- `firmographic_triage` (já puro/zero-custo) lê a firmografia Apollo do `content`
  canônico → poda precoce **mais forte e mais barata** (Apollo dá `industry`/
  `employee_count` exatos que o snippet aberto raramente traz).
- `deep_enrich` ganha um passo **condicional** de Org Enrichment (degrau 2) antes do
  Gemini, **só** se `_missing_firmographics(inference)`.
- Um nó terminal `reveal` (degrau 3) após `finalize`, gated por `select_for_reveal`.
- `OperatingMode` ganha `DEGRADED_APOLLO`; `derive_operating_mode` trata Apollo ausente
  como degradação **não-fatal** (Tavily cobre a descoberta).

> **Recomendação:** entregar a **§5.1 primeiro** (PR pequeno, sem depender de LangGraph),
> e o plugue §5.2 quando a camada do ADR-003 estiver no `main`. Os dois compartilham
> `skills/apollo_client.py`, `apollo/*` e o `CreditLedger`.

---

## 6. Tolerância a falhas (Open-World) — específico do Apollo

| Evento | Política | Efeito no dado |
|---|---|---|
| **403 / sem acesso à API no tier** | provedor **ausente** (igual Brave sem chave); log único | descoberta cai p/ Tavily; `DEGRADED_APOLLO`; **não** quebra o run |
| **429 rate limit** | backoff+jitter (reusa `graph/retry.py`); se esgotar, `refund` do crédito reservado | `missing_evidence` p/ aquela query; demais seguem |
| **Crédito esgotado (ledger ou 402)** | **não chama** o endpoint pago; reconcilia ledger | degrau 2/3 viram `missing`; lead fica sem contato revelado, `gaps += ["contato_nao_revelado"]` |
| **reveal=false (Apollo não tem o dado)** | **não** é erro; `revealed=False` | `LeadCard.contact=None`, `gaps += ["sem_email_no_apollo"]` — Open-World fiel |
| **Parse inválido / schema drift** | descarta item, `SensorError(PARSE)` | demais itens da resposta seguem |

> **Open-World fiel ao CLAUDE.md §3.3:** crédito esgotado e contato não-revelado são
> **incerteza explícita** (`gaps`/`missing_evidence`/`confidence`↓), **nunca** um e-mail
> inventado. O XAIPayload recebe `missing_signals += ["contato_apollo_indisponivel"]`.

---

## 7. Determinismo e plano de testes (gate inalterado)

Apollo **sempre mockado** com fixtures gravadas (sem rede). Relógio e RNG injetados;
ledger usa `now` injetado (período mensal reproduzível); `asyncio.sleep` patcheado.

Novos diretórios: `tests/fixtures/apollo/{people_search,org_enrich,people_match}/`.

| Suite | Cenário-chave | Asserção |
|---|---|---|
| `features/apollo_search.feature` | People Search retorna 3 hits firmográficos | viram `ObservedEvidence` (`source_trust≈0.9`, `missing=False`); **0 crédito** debitado no ledger |
| `apollo_search.feature` | mesma `(query,url)` vinda de Tavily **e** Apollo | `evidence_id` idêntico → **deduplica p/ 1** (estabilidade do hash, §5 LangGraph) |
| `apollo_triage.feature` | Apollo traz `employee_count` fora do ICP | triagem barata poda **sem Gemini**; `gemini_calls==0` |
| `apollo_ladder.feature` | 100 leads, orçamento 20 data-credits | degrau 3 revela **exatamente 20** (top-20 do ranking); demais com `gaps=["contato_nao_revelado"]` |
| `apollo_ladder.feature` | lead com firmografia completa no People Search | degrau 2 (Org Enrich) **NÃO** roda p/ ele; `data_credits_used` não conta esse lead |
| `apollo_ledger` (unit) | `try_spend` excede `cap` | retorna `False`, ledger **inalterado**; chamada paga não ocorre |
| `apollo_ledger` (unit) | 2 runs no mesmo mês (now fixo) | contadores **acumulam** entre runs; reset só ao virar "YYYY-MM" |
| `apollo_ledger` (unit) | 429 após reserva | `refund` devolve crédito; `data_credits_used` volta ao valor anterior |
| `apollo_cache.feature` | reveal repetido do mesmo `apollo_id` (T<90d) | **cache HIT** → **0 crédito** na 2ª vez |
| `apollo_degradado.feature` | chave Apollo ausente (403) | `OperatingMode==DEGRADED_APOLLO`; descoberta via Tavily; run **completa** |
| `apollo_reveal.feature` | `people/match` com `revealed=False` | `LeadCard.contact=None`; `gaps=["sem_email_no_apollo"]`; **sem** dado fabricado |
| paridade núcleo | pipeline com vs sem Apollo, MESMAS fixtures de ranking | leads não-revelados têm `p_score`/ordem **idênticos** (Apollo não altera a matemática) |

**Invariante anti-regressão:** *"desligar o Apollo (`enabled=False`) reproduz o pipeline
atual byte-idêntico"* — garante que Apollo é **estritamente aditivo**.

---

## 8. WUs (cada uma = 1 PR verde), riscos e melhorias

### Plano de implementação

```
docs/decisions/ADR-004-sensor-apollo.md      # emenda ao ADR-000 §3 (2º sensor de busca)
src/socialselling/skills/apollo_client.py    # cliente REST (httpx); RateLimit/ApolloError
src/socialselling/apollo/
  schemas.py        # §4 (Pydantic extra=forbid)
  normalize.py      # person_hit_to_canonical (→ formato Tavily)
  ladder.py         # select_for_org_enrich / select_for_reveal (puros)
src/socialselling/core/credit_ledger.py      # §3 ledger mensal atômico
config/runtime.toml                          # [apollo] (enabled=false default)
.env.example                                 # APOLLO_API_KEY (opcional)
tests/fixtures/apollo/** + tests/features/apollo_*.feature + tests/apollo/
```

- **WU-A0** — ADR-004 + este SDD (docs). *(este PR.)*
- **WU-A1** — `apollo/schemas.py` + `[apollo]` em `runtime.toml`/`config.py` + `.env.example` + testes de contrato. *(sem rede.)*
- **WU-A2** — `credit_ledger.py` (mensal, atômico, `try_spend`/`refund`/reconciliação) + testes unitários determinísticos. *(o degrau de maior risco — priorizar.)*
- **WU-A3** — `apollo_client.py` + `normalize.py` + fixtures gravadas (supervisionado, 1 chave real) + testes de normalização e degradação (403/429).
- **WU-A4** — `ladder.py` + plugue **§5.1** no M1 (degrau 1) + passo `m_reveal` pós-M4 (degrau 3) + BDD `apollo_search`/`apollo_ladder`/`apollo_reveal` + **paridade núcleo**.
- **WU-A5** — Org Enrichment condicional (degrau 2) + cache TTL-por-volatilidade (§2) + BDD `apollo_cache`/`apollo_triage`.
- **WU-A6** *(após ADR-003 no main)* — plugue **§5.2** no LangGraph (`parallel_scout`/`firmographic_triage`/`reveal` node) + `DEGRADED_APOLLO` + medidor de saldo no Cockpit (ADR-002).
- Extra `[apollo]` (sem nova dep pesada; reusa `httpx`). Tags conforme `versioning-strategy.md`.

### Riscos e mitigações

- **Risco — acesso à API no tier gratuito é incerto/instável** (fontes divergem; alguns
  relatam API só em planos pagos). **Mitigação:** `enabled=False` por padrão e degradação
  para Tavily em 403 — o PoC **nunca depende** do Apollo para funcionar. Validar a chave
  real **uma vez** na WU-A3 antes de investir nas WUs seguintes.
- **Risco — limites/custos de crédito mudam** (números da §0 são premissa de 2026).
  **Mitigação:** caps são **config** (`[apollo].caps`), não hard-coded; o ledger
  reconcilia com a verdade da Apollo (402).
- **Risco — contato revelado é PII.** **Mitigação:** revelar **só** no degrau 3 (top-N),
  cachear localmente (não re-revelar), e manter fora de escopo qualquer outreach (ADR-000
  §1). O dado fica no `LeadCard` para ação **manual** do operador.
- **Risco — determinismo do ledger entre runs.** **Mitigação:** `now` injetado define o
  período "YYYY-MM"; testes fixam o relógio; persistência atômica evita estado corrompido.

### Melhorias propostas (diferidas — não no PoC inicial)

1. **Waterfall enrichment** (`run_waterfall_email/phone`) — só quando houver folga de
   crédito; custo variável por fonte, exige medição antes de adotar.
2. **`reveal_top_n` adaptativo ao saldo** — revelar mais cedo no mês, recuar quando o
   ledger aperta (espelha o `tau_finops` adaptativo do ADR-003).
3. **Pré-aquecimento de cache** entre meses — manter contatos revelados (TTL 90d) cruzando
   a virada do mês para não re-pagar.
4. **Cockpit (ADR-002):** painel "Saldo Apollo" (data/email/mobile usados vs cap) +
   `gaps` de contato por lead, como o painel de FinOps do ADR-003.
```
