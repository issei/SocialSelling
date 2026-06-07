# SDD — Borda do BaaS: API Gateway + autorizador JWT + injeção de contexto multi-tenant

> **Status:** **PROPOSTA (v1.0 — aguardando aprovação do dono)**.
> Deriva do **ADR-008** (§4 Modelo multi-tenant; §2 Step Functions). Spec-first: este documento
> precede o código. Segue o SDD-to-Code Loop do repositório (contrato → BDD+fixtures →
> implementação → gate `ruff`+`mypy --strict`+`pytest` → PR). Sensores externos **sempre
> mockados** por fixture nos testes; asserções numéricas com tolerância `1e-9`.
>
> **Foco:** especificar a **camada de entrada** do Backend-as-a-Service — como o API Gateway
> valida o JWT do Cognito, extrai o `user_id` da claim `sub` e estrutura o payload que aciona
> **síncronamente** a máquina de estados (M1→M5), e como a resposta unificada (`LeadCard` +
> `ProspectScore` + `XAIPayload`) é devolvida em HTTP. Inclui o tratamento **cru e acionável**
> de erros FinOps (cota/billing) sem mascarar a causa-raiz.

---

## 0. Premissas, invariantes e reaproveitamento

| Invariante (não negociável) | Origem | Como a borda respeita |
|---|---|---|
| Isolamento multi-tenant obrigatório | ADR-008 §4 | `user_id` vem **só** de `$context.authorizer.claims.sub` (token validado), **nunca** do corpo. |
| Determinismo byte-idêntico | CLAUDE.md §3.2 | A borda injeta `now` (relógio do gatilho) no payload do Step Functions; não há `datetime.now()` nos módulos. `icp_id`/`entity_id` derivados por hash estável. |
| Open-World: ausência/falha = incerteza, nunca falso | CLAUDE.md §3.3 | Falha de sensor/cota → resposta degradada com leads do corpus se houver; erro de billing → HTTP cru acionável, nunca tela falsamente vazia "limpa". |
| Core M1–M5 agnóstico de infra | ADR-008 §2/§5 | Os handlers de borda são *wrappers* finos; não importam regra de negócio dos módulos além de invocá-los via Step Functions. |
| Contratos `extra="forbid"` | `contracts.py` | Novos schemas desta SDD são **aditivos**; reusam `ICPCriteria`, `LeadCard`, `ProspectScore`, `XAIPayload`. |
| Custódia de segredos fora do código | ADR-008 §2 | Tokens (Tavily/Apollo/Gemini) lidos do Secrets Manager dentro dos Lambdas, nunca na borda. |

**Não-objetivo:** a borda **não** autentica usuário (delegado ao Cognito), **não** faz cadastro/senha, **não** implementa rate-limiting de negócio (FinOps mora nos ledgers, SDD-2).

---

## 1. Contexto e topologia da requisição

```
Cockpit externo
   │  Authorization: Bearer <JWT Cognito>
   ▼
API Gateway (REST)  ──[1] valida assinatura do JWT (autorizador Cognito)
   │                ──[2] injeta $context.authorizer.claims.sub  → user_id
   │                ──[3] mapping template monta o payload de gatilho
   ▼
StartSyncExecution (Step Functions express, síncrona)
   │   M1 → M2 → M3 → M4 → M5
   ▼
Saída do m5_xai (RankedProspect[] + LeadCard[])
   │  ──[4] mapping template / Lambda-proxy serializa
   ▼
HTTP 200  { run_id, operating_mode, leads:[...], generated_at }
HTTP 429 / 502  (erros FinOps crus e acionáveis — §5)
```

A integração é **síncrona** (`StartSyncExecution` em máquina de estados *express*) porque a requisição interativa do cockpit espera o ranking. As **ondas noturnas** (EventBridge → `StartExecution` *standard* assíncrono) usam a mesma máquina de estados, mas não passam por esta borda (SDD-2).

### Mapeamento de integração (extração do `user_id`)

O método do API Gateway (`POST /runs`) usa o autorizador JWT do Cognito. O *mapping template* (ou o evento do Lambda-proxy) extrai:

| Origem no API Gateway | Destino no payload | Obrigatório |
|---|---|---|
| `$context.authorizer.claims.sub` | `user_context.user_id` | **Sim** — ausente ⇒ 401 antes de qualquer Lambda. |
| `$context.requestId` | `run_id` (semente; `run_id` final = hash estável, §2) | Sim |
| `$context.requestTimeEpoch` | `now` (ISO-8601, UTC) | Sim — relógio injetado (determinismo). |
| corpo da requisição (`$input.json('$.icp')`) | `icp` (`ICPCriteria`) | Sim |

> **Regra de segurança:** se o corpo contiver um campo `user_id`, ele é **ignorado**. A única
> fonte de tenant é a claim do token. Garantido por contrato (`extra="forbid"` no `RunRequest`,
> que **não tem** campo `user_id` no corpo).

---

## 2. Contratos de dados (Pydantic)

Novos contratos em `src/socialselling/edge/contracts.py` (camada de borda), reaproveitando os de `contracts.py`.

### 2.1 Contexto do usuário (injetado pela borda)

```python
class UserContext(BaseModel):
    """Contexto multi-tenant derivado EXCLUSIVAMENTE do JWT validado (claim sub)."""
    model_config = ConfigDict(extra="forbid")

    user_id: str            # = $context.authorizer.claims.sub
    issued_at: str          # ISO-8601, claim iat (auditoria)
```

### 2.2 Entrada: corpo da requisição e payload de gatilho

```python
class RunRequest(BaseModel):
    """Corpo HTTP do POST /runs. NÃO contém user_id (anti-spoofing)."""
    model_config = ConfigDict(extra="forbid")

    icp: ICPCriteria        # contrato universal de entrada (contracts.py)
    max_leads: int | None = Field(default=None, ge=1)  # override de exibição (corpus)


class PipelineTrigger(BaseModel):
    """Payload que a borda monta e entrega ao Step Functions (StartSyncExecution)."""
    model_config = ConfigDict(extra="forbid")

    run_id: str             # hash SHA-256 estável de (user_id + icp_id + now-truncado)
    user_context: UserContext
    icp: ICPCriteria
    now: str                # ISO-8601 injetado (relógio do gatilho) — determinismo §3.2
    persistence_mode: str = "aws"   # paridade: a borda só existe no modo aws
    max_leads: int | None = None
```

> `run_id` é **derivado por hash estável**, nunca `uuid4()`. Mesma `(user_id, icp, now-truncado
> ao dia)` ⇒ mesmo `run_id` ⇒ idempotência da execução e do cache (SDD-2/SDD-3).

### 2.3 Saída unificada (scan-then-focus adaptado para REST)

O padrão *scan-then-focus* do cockpit (lista densa → drawer detalhado) é adaptado a **uma única
resposta consolidada**: o array `leads` já traz, por lead, o `LeadCard` (scan) com seu
`ProspectScore` e `XAIPayload` embutidos (focus). O cliente não precisa de uma segunda chamada.

```python
class LeadEnvelope(BaseModel):
    """Consolida, por lead, a saída do m5_xai: card + score + explicação."""
    model_config = ConfigDict(extra="forbid")

    card: LeadCard          # contracts.py — já embute ProspectScore em card.score
    explanation: XAIPayload # contracts.py — drivers +/-, missing_signals, degraded_mode


class RunResponse(BaseModel):
    """Resposta HTTP 200 do POST /runs."""
    model_config = ConfigDict(extra="forbid")

    run_id: str
    operating_mode: OperatingMode    # NORMAL | DEGRADED_TAVILY | DEGRADED_GEMINI | CACHE_ONLY
    generated_at: str                # ISO-8601 = now injetado
    leads: list[LeadEnvelope]        # ordenado por rank (determinístico)
    finops: FinOpsSummary            # saldos consolidados do run (do LEDGER#FINOPS)


class FinOpsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gemini_requests_used: int
    gemini_rpd_cap: int
    apollo_data_credits_used: int
    apollo_data_credits_cap: int


class ApiError(BaseModel):
    """Corpo de erro CRU e acionável (não mascara a causa-raiz — L-057)."""
    model_config = ConfigDict(extra="forbid")

    error_code: str         # ex: GEMINI_RPD_EXHAUSTED | GEMINI_BILLING_DEPLETED | UPSTREAM_5XX
    message: str            # mensagem CRUA do provedor (ex: "prepayment credits depleted")
    provider: str           # gemini | apollo | tavily
    actionable_hint: str    # ex: link de billing do AI Studio surfaciado pelo GeminiClient
    operating_mode: OperatingMode
```

> A saída unificada mapeia **exatamente** o que o `m5_xai.py` produz (`RankedProspect` =
> `rank` + `ProspectScore` + `XAIPayload`) acrescido do `LeadCard` da camada de apresentação. A
> borda **não recomputa** nada — só serializa a saída da máquina de estados.

---

## 3. Tratamento de erros FinOps (cru, limpo e acionável)

Princípio reitor herdado da **Lição L-057**: *degradação silenciosa esconde a causa acionável*.
A borda **propaga a mensagem crua do provedor** até o cliente, sem reescrevê-la em um genérico
"erro 429". A classificação é feita pelos Lambdas (que veem o corpo cru do provedor), carregada
pela máquina de estados como `error.Cause`, e traduzida pela borda no **status HTTP correto**.

| Situação (causa-raiz) | Detecção (Lambda) | Status HTTP | `error_code` | Open-World |
|---|---|---|---|---|
| Cota diária Gemini (RPD) esgotada | `request_ledger` estoura `rpd_cap` antes da chamada | **429** | `GEMINI_RPD_EXHAUSTED` | Se há corpus prévio do tenant → 200 degradado com os leads já conhecidos; senão 429. |
| Billing Gemini esgotado (`prepayment credits depleted`) | `GeminiClient` surfacia `error.message` cru do 429 do Google | **429** | `GEMINI_BILLING_DEPLETED` + link de billing | Não reseta no relógio → 429 acionável (não "vazio limpo"). |
| Crédito Apollo esgotado (`402`/limite mensal) | `credit_ledger` ou 402 do Apollo | **degrada, não falha** | — (mode `DEGRADED`) | Apollo é opt-in; ausência ⇒ degrada para Tavily, lead permanece visível. |
| Falha upstream 5xx (Tavily/Gemini/Apollo) | exceção capturada no Lambda do módulo | **502** | `UPSTREAM_5XX` | Degrada o `OperatingMode`; nunca quebra a máquina de estados (retry primeiro — SDD-2). |
| JWT ausente/inválido | autorizador Cognito | **401** | `UNAUTHORIZED` | n/a |

> A máquina de estados tem um estado `Catch` global que captura exceções dos Lambdas e roteia
> para um estado `FormatError` que devolve `{error_code, message, provider, actionable_hint}` —
> **a borda não inventa a mensagem**, apenas mapeia para o HTTP. O `_CapturingCognition`
> (wrapper do `GeminiClient`, L-057) garante que a mensagem crua não seja engolida pelo M2.

---

## 4. Cenários BDD (Gherkin)

Arquivo de feature: `tests/features/borda_api_gateway_jwt.feature`. APIs externas e o Step
Functions são **mockados por fixture** (sem rede, sem AWS — SDD-3).

```gherkin
# language: pt
Funcionalidade: Borda do BaaS — JWT, injeção de tenant e acionamento síncrono do pipeline

  Contexto:
    Dado um API Gateway com autorizador JWT do Cognito configurado
    E uma máquina de estados M1→M5 mockada por fixtures determinísticas
    E o relógio injetado "2026-06-07T03:00:00Z"

  # ---------- Caminho feliz ----------
  Cenário: Requisição autenticada gera ranking isolado por tenant
    Dado um JWT válido com claim sub "user-abc"
    E um corpo de requisição com um ICPCriteria válido "icp-talita"
    Quando o cliente faz POST /runs
    Então o API Gateway injeta user_context.user_id = "user-abc"
    E o run_id é o hash SHA-256 estável de (user-abc, icp-talita, 2026-06-07)
    E a máquina de estados é acionada com persistence_mode "aws"
    E a resposta é HTTP 200 com operating_mode "NORMAL"
    E cada item de leads contém card, card.score e explanation
    E leads está ordenado por rank de forma determinística

  Cenário: Mesma entrada produz resposta byte-idêntica (determinismo)
    Dado o mesmo JWT, ICP e relógio injetado de uma execução anterior
    Quando o cliente faz POST /runs novamente
    Então o run_id é idêntico ao anterior
    E a serialização de leads é byte-idêntica (tolerância numérica 1e-9)

  # ---------- Anti-spoofing de tenant ----------
  Cenário: user_id no corpo é ignorado em favor da claim do token
    Dado um JWT válido com claim sub "user-abc"
    E um corpo que tenta incluir o campo "user_id" = "user-victim"
    Quando o cliente faz POST /runs
    Então o contrato RunRequest rejeita o campo extra (extra=forbid)
    E nenhum dado do tenant "user-victim" é acessado

  Cenário: Requisição sem token é barrada antes de qualquer Lambda
    Dado uma requisição sem header Authorization
    Quando o cliente faz POST /runs
    Então a resposta é HTTP 401 com error_code "UNAUTHORIZED"
    E nenhum Lambda de módulo é invocado

  # ---------- Degradado por limites/billing (FinOps) ----------
  Cenário: Cota diária do Gemini (RPD) esgotada, sem corpus prévio
    Dado que o request_ledger do tenant "user-abc" já atingiu rpd_cap
    E o tenant não possui corpus acumulado
    Quando o cliente faz POST /runs
    Então a resposta é HTTP 429 com error_code "GEMINI_RPD_EXHAUSTED"
    E message contém a causa crua do provedor
    E nenhuma resposta é apresentada como "0 leads" silencioso

  Cenário: Billing do Gemini esgotado é surfaciado cru e acionável (L-057)
    Dado que o GeminiClient recebe um 429 "prepayment credits depleted" com link de billing
    Quando o cliente faz POST /runs
    Então a resposta é HTTP 429 com error_code "GEMINI_BILLING_DEPLETED"
    E message é exatamente a mensagem do provedor (não um genérico "429")
    E actionable_hint contém o link de billing do AI Studio

  Cenário: Falha upstream 5xx após retries vira 502 sem mascarar a causa
    Dado que o sensor Tavily responde 503 após todas as tentativas de retry
    Quando o cliente faz POST /runs
    Então a resposta é HTTP 502 com error_code "UPSTREAM_5XX"
    E operating_mode reflete a degradação

  # ---------- Open-World ----------
  Cenário: Cota do Gemini esgotada mas com corpus prévio degrada sem ocultar leads
    Dado que o tenant "user-abc" possui corpus acumulado de runs anteriores
    E a cognição do Gemini está indisponível neste ciclo
    Quando o cliente faz POST /runs
    Então a resposta é HTTP 200 com operating_mode "DEGRADED_GEMINI"
    E leads contém os leads previamente conhecidos do tenant
    E nenhum lead é marcado como falso por ausência de sinal novo

  Cenário: Ausência de sinal de intent não rebaixa lead a falso
    Dado um lead sem sinais de intent recentes
    Quando o pipeline executa e a borda serializa a resposta
    Então o lead permanece visível com confiança reduzida
    E explanation.missing_signals lista o sinal ausente
```

---

## 5. Work Units (rastreáveis — Run Noturno)

Cada WU é uma card que passa pelo DoR/DoD (`docs/governance/dor-dod.md`). Contratos e Gherkin
acima já satisfazem o DoR. Critérios de aceitação = gate verde + cenários 100% determinísticos.

| WU | Entrega | Critério de aceitação |
|---|---|---|
| **WU-B1** | `edge/contracts.py`: `UserContext`, `RunRequest`, `PipelineTrigger`, `RunResponse`, `LeadEnvelope`, `FinOpsSummary`, `ApiError` | `mypy --strict` limpo; `RunRequest` rejeita `user_id` no corpo (teste). |
| **WU-B2** | Handler de borda (`edge/run_handler.py`): monta `PipelineTrigger` a partir do evento do API Gateway (claim `sub`, `now`, `run_id` por hash) | Cenários "feliz", "determinismo" e "anti-spoofing" verdes. |
| **WU-B3** | Serializador da saída unificada (`m5_xai` → `RunResponse`) sem recomputar pipeline | Resposta byte-idêntica para mesma entrada (1e-9). |
| **WU-B4** | Classificador/mapeador de erros FinOps (`edge/errors.py`): `error.Cause` → `ApiError` + status HTTP | Cenários 429 (RPD), 429 (billing L-057), 502 verdes; mensagem crua preservada. |
| **WU-B5** | Estado `Catch`/`FormatError` da máquina de estados (definição declarada; testada por fixture do output do SFN) | Erro de módulo nunca quebra a borda; vira `ApiError` correto. |
| **WU-B6** | Contrato OpenAPI estrito (`openapi/socialselling.yaml`) de `POST /runs` + esquemas de erro | Lint OpenAPI; congruente com `RunRequest`/`RunResponse`/`ApiError`. |
| **WU-B7** | Cenário Open-World (degradação com corpus prévio) ponta-a-ponta com fixtures | Cenários Open-World verdes; nenhum "vazio silencioso". |

**Quality gate (inegociável):** todos os cenários rodam **offline** (Step Functions, Cognito e
provedores **mockados por fixture**); `ruff` + `mypy --strict` + `pytest` 100% verdes e
determinísticos. Nenhuma dependência de AWS real, chave de API real ou LocalStack (ver SDD-3).
