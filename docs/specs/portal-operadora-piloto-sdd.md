# SDD — Portal da Operadora (piloto): motor local + publicação de carteira + loop de feedback

> **Status:** **APROVADA (v1.0 — 2026-06-09)** — **alvo de build do piloto**.
> Deriva do **ADR-010** (pivô: validar o produto com operadoras reais antes de infra multi-tenant;
> execução do roadmap AWS da ADR-008 arquivada — a ADR-008 segue como visão futura e a ADR-009 fica
> dormente). Spec-first: este documento precede o código e segue o SDD-to-Code Loop do repositório
> (contrato → BDD+fixtures → implementação → gate `ruff`+`mypy --strict`+`pytest` → PR). HTTP e
> APIs externas **sempre mockados** nos testes; asserções numéricas com tolerância `1e-9`.
>
> **Foco:** o **motor 100% local permanece inalterado** (M1–M5, corpus ADR-006, waves, aprendizado
> ADR-007). Esta SDD adiciona duas pontas finas: (a) um **portal web mínimo** (FastAPI + Jinja2 +
> JS vanilla, monorepo em `src/socialselling/portal/`) hospedado no **Render free** com **Neon
> Postgres free**, onde a operadora vê sua **carteira de leads** e tabula desfechos; (b) duas
> **CLIs no motor** (`publish` e `pull-feedback`) que conversam com o portal **exclusivamente via
> HTTP**. O motor **nunca** acessa o banco (`DATABASE_URL` existe só no Render). Pegada AWS do
> piloto = **zero**. A UI local existente (`socialselling/web`) **não muda** — vira utilitário de
> operador/dev.
>
> **Piloto:** começa só com a Talita; o desenho suporta N operadoras com **ICP por operadora**
> (ICP Profiles do WU-C, já entregue). Top-20 leads por onda, Tavily-only, **runs manuais**.

---

## 0. Premissas, invariantes e reaproveitamento

| Invariante (não negociável) | Origem | Como esta SDD honra |
|---|---|---|
| Determinismo byte-idêntico | CLAUDE.md §3.2 | `run_id` = hash SHA-256 estável do conteúdo do ranking (sem relógio); snapshot serializado com ordenação estável; mesmo corpus → mesmo snapshot byte-idêntico; consolidação do pull ordenada por `event_id`; relógio sempre injetado. |
| Isolamento de camadas semânticas | CLAUDE.md §3.1 | O portal recebe **só a camada de apresentação** (`PublishedLead` deriva de `LeadCard`/`XAIPayload`); eventos de feedback jamais tocam Evidence/Inference; reactions alimentam o `FeedbackStore` (apresentação) exatamente como na ADR-007. |
| Open-World: ausência de sinal = incerteza | CLAUDE.md §3.3 | Lead sem evento de status = `"novo"` (default explícito, nunca inferido); `missing_evidence` exibido no lead card da operadora; portal fora do ar → CLI `publish` degrada (snapshot fica local), nunca quebra o pipeline; evento órfão no pull não corrompe o aprendizado. |
| Persistência atômica (lado motor) | CLAUDE.md §3.4 | Cursor, registros de publicação e JSONL via `core/atomic.py` (`write-temp` + `os.replace`); JSONL append-only com linha completa por evento. |
| Append-only (lado portal) | ADR-010 | `feedback_events` **nunca** sofre `UPDATE`/`DELETE`; snapshots imutáveis por `(profile_id, run_id)` (republicação idêntica → 409 idempotente). |
| Gate 100% offline e determinístico | CLAUDE.md §4 | Contract tests rodam contra a **porta DAO** com `InMemoryDAO`; `PostgresDAO` é fino (1 SQL por método) com risco residual aceito + smoke pós-deploy (runbook §9); HTTP do motor mockado por fixture. |
| Motor nunca acessa o banco | ADR-010 | Integração motor↔portal **exclusivamente HTTP** (`POST /api/publish`, `GET /api/feedback`); `psycopg` importado **somente** em `portal/dao_postgres.py`. |
| Contratos `extra="forbid"` | `contracts.py` | Todos os novos modelos usam `ConfigDict(extra="forbid")`; `DataProvenance`/padrões reaproveitados de `socialselling.contracts`. |
| Sem score numérico exposto | ADR-010 (coerente com o CSV export) | O snapshot publicado **nem contém** score; o join score↔desfecho para calibração acontece no motor, que guarda os scores por `run_id` em `data/published/`. |

**Não-objetivo:** esta SDD **não** altera fórmulas de score/ranking nem os módulos M1–M5, **não**
liga desfecho de funil ao aprendizado automático (ADR futura, com dados na mão), **não** introduz
ORM/Alembic, **não** cria infra AWS.

---

## 1. Arquitetura

```
        MOTOR LOCAL (máquina do dono)                     PORTAL (Render free + Neon free)
┌────────────────────────────────────────────┐      ┌────────────────────────────────────────────┐
│ M1→M2→M3→M4→M5 · corpus (ADR-006) · waves  │      │ FastAPI + Jinja2 + JS vanilla              │
│ aprendizado ADR-007 · scores por run_id    │      │ src/socialselling/portal/                  │
│                                            │      │                                            │
│ CLI publish ── POST /api/publish ─────────────────▶ snapshots (Neon Postgres, JSONB)           │
│   (Bearer PORTAL_PUBLISH_TOKEN)            │      │                                            │
│   data/published/<profile>/<run>.json      │      │ feedback_events (append-only) ◀── UI ──┐   │
│                                            │      │                                        │   │
│ CLI pull-feedback ◀─ GET /api/feedback?since=N ──── operators (code_hash, sessão cookie)  │   │
│   data/feedback_events/events.jsonl        │      └────────────────────────────────────────│───┘
│   data/calibration/eventos.jsonl           │                                               │
│   FeedbackStore ADR-007 (por perfil)       │           Operadora (browser, após /login):   │
└────────────────────────────────────────────┘           /carteira · /lead/{entity_id} ──────┘
                                                          selling.issei.com.br (CNAME)
```

**Dois fluxos, ambos iniciados pelo motor (o portal nunca chama o motor):**

1. **Push de snapshot** — após um run manual do pipeline, o dono executa `publish`: o motor monta
   o `PublishedSnapshot` (top-20 do corpus ranqueado do perfil, **sem score**) e faz
   `POST /api/publish` com Bearer `PORTAL_PUBLISH_TOKEN`. Idempotente por `(profile_id, run_id)`.
2. **Pull de feedback** — o dono executa `pull-feedback`: o motor faz
   `GET /api/feedback?since=<cursor>` e persiste os eventos em JSONL append-only local
   (**backup primário do dado precioso** — a retenção curta do Neon free deixa de ser risco),
   consolida reactions no aprendizado ADR-007 (por perfil) e statuses de funil no arquivo de
   calibração offline.

**Quem é dono de qual dado:**

| Dado | Dono | Onde vive |
|---|---|---|
| Cognição, evidências, inferências, scores, corpus, pesos aprendidos | **Motor** | `data/` local (nunca sai score para o portal) |
| Snapshot publicado (camada de apresentação) | **Portal** | `snapshots` (Neon) |
| Eventos de feedback **até o pull** | **Portal** (trânsito) | `feedback_events` (Neon) |
| Eventos de feedback **após o pull** (cópia canônica) | **Motor** | `data/feedback_events/events.jsonl` + `data/calibration/eventos.jsonl` |
| Credenciais da operadora (`code_hash`) | **Portal** | `operators` (Neon; seed via SQL — runbook §9) |

---

## 2. Contratos de dados (Pydantic)

Modelos compartilhados entre motor e portal (**contrato sem deriva** — monorepo) em
`src/socialselling/portal/contracts.py`. Mesma regra de `contracts.py`: **apenas modelos de
dados**, sem lógica de negócio, sem import de FastAPI/psycopg. `DataProvenance` é **reusado** de
`socialselling.contracts` (não duplicar).

```python
"""Contratos do portal da operadora (SDD portal-operadora-piloto).

Compartilhados entre o motor (CLIs publish/pull-feedback) e o portal (API/UI).
REGRA: apenas modelos de dados; sem lógica de negócio (ver contracts.py).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from socialselling.contracts import DataProvenance

MAX_LEADS_PER_SNAPSHOT = 20


# --------------------------------------------------------------------------- #
# Publicação (motor → portal)                                                  #
# --------------------------------------------------------------------------- #
class PublishedDriver(BaseModel):
    """Driver XAI em linguagem natural, com proveniência (WU-A/WU-B)."""

    model_config = ConfigDict(extra="forbid")

    impact: str  # "positive" | "negative"
    text: str  # frase em linguagem natural (Driver.text do M5)
    references: list[DataProvenance] = Field(default_factory=list)


class PublishedLead(BaseModel):
    """Lead na camada de apresentação da operadora — SEM score numérico."""

    model_config = ConfigDict(extra="forbid")

    entity_id: str  # identidade canônica (§7.1)
    rank_position: int = Field(ge=1, le=MAX_LEADS_PER_SNAPSHOT)
    company: str
    segmento: str | None = None
    cidade: str | None = None
    uf: str | None = None
    instagram: str | None = None
    site: str | None = None
    email: str | None = None
    telefone: str | None = None
    drivers: list[PublishedDriver] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)  # Open-World explícito


class PublishedSnapshot(BaseModel):
    """Snapshot publicado de um run: top-20 do ranking do perfil."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    profile_id: str  # ICP Profile da operadora (WU-C)
    run_id: str  # hash estável do conteúdo do ranking (§7.2) — idempotência
    generated_at: str  # ISO-8601 UTC, relógio injetado
    leads: list[PublishedLead] = Field(max_length=MAX_LEADS_PER_SNAPSHOT)

    @model_validator(mode="after")
    def _ranks_estritos(self) -> PublishedSnapshot:
        ranks = [lead.rank_position for lead in self.leads]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("rank_position deve ser 1..N estrito, na ordem da lista")
        return self


# --------------------------------------------------------------------------- #
# Feedback (operadora → portal → motor)                                        #
# --------------------------------------------------------------------------- #
class FeedbackKind(StrEnum):
    STATUS = "status"
    REACTION = "reaction"


class Reaction(StrEnum):
    LIKE = "like"
    DISLIKE = "dislike"


class FeedbackEvent(BaseModel):
    """Evento append-only de feedback. event_id é o cursor do pull."""

    model_config = ConfigDict(extra="forbid")

    event_id: int = Field(ge=1)  # serial atribuído pelo portal
    operator_id: str
    profile_id: str
    entity_id: str
    run_id: str  # run do snapshot em que o lead foi exibido
    kind: FeedbackKind
    status_id: str | None = None  # obrigatório quando kind=status
    reaction: Reaction | None = None  # obrigatório quando kind=reaction
    note: str = ""
    created_at: str  # ISO-8601 UTC

    @model_validator(mode="after")
    def _kind_consistente(self) -> FeedbackEvent:
        if self.kind is FeedbackKind.STATUS and (
            self.status_id is None or self.reaction is not None
        ):
            raise ValueError("kind=status exige status_id e proíbe reaction")
        if self.kind is FeedbackKind.REACTION and (
            self.reaction is None or self.status_id is not None
        ):
            raise ValueError("kind=reaction exige reaction e proíbe status_id")
        return self


class FeedbackEventIn(BaseModel):
    """Corpo do POST /lead/{entity_id}/feedback (sessão da operadora).

    operator_id/profile_id vêm da sessão; entity_id do path; run_id do snapshot
    mais recente em que o lead aparece. NUNCA do corpo (anti-spoofing).
    """

    model_config = ConfigDict(extra="forbid")

    kind: FeedbackKind
    status_id: str | None = None
    reaction: Reaction | None = None
    note: str = ""


class FeedbackPage(BaseModel):
    """Resposta do GET /api/feedback — página de eventos por cursor."""

    model_config = ConfigDict(extra="forbid")

    events: list[FeedbackEvent]  # ordenados por event_id ASC
    next_since: int  # último event_id retornado; igual a `since` se vazio


# --------------------------------------------------------------------------- #
# Catálogo de status do funil (config/feedback_catalog.json)                   #
# --------------------------------------------------------------------------- #
class RotuloAprendizado(StrEnum):
    """Rótulo para a calibração offline (NÃO alimenta a ADR-007 na fase 1)."""

    NEUTRO = "neutro"
    POSITIVO = "positivo"
    POSITIVO_FORTE = "positivo_forte"
    NEGATIVO_FRACO = "negativo_fraco"
    NEGATIVO_FIT = "negativo_fit"
    QUALIDADE_DADO = "qualidade_dado"


class CatalogStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status_id: str  # estável, snake_case (nunca renomear; label é mutável)
    label: str
    terminal: bool  # terminal ⇒ lead sai da carteira
    rotulo_aprendizado: RotuloAprendizado
    ordem: int = Field(ge=1)


class FeedbackCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    statuses: list[CatalogStatus]

    @model_validator(mode="after")
    def _ids_e_ordens_unicos(self) -> FeedbackCatalog:
        ids = [s.status_id for s in self.statuses]
        ordens = [s.ordem for s in self.statuses]
        if len(set(ids)) != len(ids) or len(set(ordens)) != len(ordens):
            raise ValueError("status_id e ordem devem ser únicos no catálogo")
        return self


# --------------------------------------------------------------------------- #
# Operadora (auth do portal)                                                   #
# --------------------------------------------------------------------------- #
class Operator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator_id: str
    nome: str
    code_hash: str  # SHA-256 hex do código de acesso (§5.3)
    profile_id: str  # ICP Profile da operadora — escopo de TUDO que ela vê
```

> O default `"novo"` **não** é gravado como evento: é o estado Open-World de "nenhum evento de
> status ainda" (§5.2). Só transições explícitas da operadora geram `FeedbackEvent`.

---

## 3. `config/feedback_catalog.json` v1 (literal)

Mesmo padrão do `hypotheses_catalog.json`: **ids estáveis em snake_case** (contrato — nunca
renomear), labels mutáveis. Funil: `novo → interagindo → abordado → respondeu / nao_respondeu →
reuniao_marcada → cliente`; laterais **terminais**: `contato_invalido`, `fora_do_perfil`.
Status terminal ⇒ lead sai da carteira (§5.2). `rotulo_aprendizado` serve **só** à calibração
offline (consumidor: card "Calibração de pesos [persona]/priors com conversão real" do Backlog).

```json
{
  "schema_version": 1,
  "statuses": [
    {
      "status_id": "novo",
      "label": "Novo",
      "terminal": false,
      "rotulo_aprendizado": "neutro",
      "ordem": 1
    },
    {
      "status_id": "interagindo",
      "label": "Interagindo",
      "terminal": false,
      "rotulo_aprendizado": "neutro",
      "ordem": 2
    },
    {
      "status_id": "abordado",
      "label": "Abordado",
      "terminal": false,
      "rotulo_aprendizado": "neutro",
      "ordem": 3
    },
    {
      "status_id": "respondeu",
      "label": "Respondeu",
      "terminal": false,
      "rotulo_aprendizado": "positivo",
      "ordem": 4
    },
    {
      "status_id": "nao_respondeu",
      "label": "Não respondeu",
      "terminal": false,
      "rotulo_aprendizado": "negativo_fraco",
      "ordem": 5
    },
    {
      "status_id": "reuniao_marcada",
      "label": "Reunião marcada",
      "terminal": false,
      "rotulo_aprendizado": "positivo_forte",
      "ordem": 6
    },
    {
      "status_id": "cliente",
      "label": "Cliente",
      "terminal": true,
      "rotulo_aprendizado": "positivo_forte",
      "ordem": 7
    },
    {
      "status_id": "contato_invalido",
      "label": "Contato inválido",
      "terminal": true,
      "rotulo_aprendizado": "qualidade_dado",
      "ordem": 8
    },
    {
      "status_id": "fora_do_perfil",
      "label": "Fora do perfil",
      "terminal": true,
      "rotulo_aprendizado": "negativo_fit",
      "ordem": 9
    }
  ]
}
```

> **Aprendizado fase 1 (decisão do dono):** like/dislike continua sendo o **único** input da
> regressão ADR-007 (por perfil). Os status de funil são **coletados** para calibração offline;
> ligar desfecho→aprendizado automático é ADR futura, com dados na mão.

---

## 4. Endpoints do portal

Todos os responses carregam `X-Robots-Tag: noindex` (middleware global). Nenhuma página é servida
sem login (exceto `/login` e `/healthz`). Cookies de sessão: `HttpOnly`, `Secure`, `SameSite=Lax`.

| Método e rota | Auth | Semântica | Erros |
|---|---|---|---|
| `GET /healthz` | pública | Liveness para o Render e para o smoke (não toca dados de lead). | — |
| `POST /api/publish` | Bearer `PUBLISH_TOKEN` | Corpo = `PublishedSnapshot`. **Idempotente por `(profile_id, run_id)`**: `201` publicado agora; `409` já existia (o motor trata 409 como **sucesso idempotente**). | `401` token ausente/errado; `409` duplicado; `422` contrato violado (`extra="forbid"`, ranks não-estritos, >20 leads). |
| `GET /api/feedback?since=<event_id>&limit=<n>` | Bearer `PUBLISH_TOKEN` | Eventos com `event_id > since`, ordem ASC, paginado por cursor (`limit` default 500). Resposta = `FeedbackPage`. `since` além do fim → `events=[]`, `next_since=since` (idempotente). | `401`; `422` (`since`/`limit` inválidos). |
| `POST /login` | pública | Form com **um campo**: código de acesso. `sha256(código)` é procurado em `operators.code_hash`; achou → cookie de sessão assinado (`SECRET_KEY`) com `operator_id`+`profile_id`; não achou → `401` genérico ("código inválido", sem distinguir causa). | `401`. |
| `POST /logout` | sessão | Invalida o cookie e redireciona para `/login`. | — |
| `GET /carteira` | sessão | Carteira da operadora (§4.1), escopada ao `profile_id` da sessão. | `303 → /login` sem sessão. |
| `GET /lead/{entity_id}` | sessão | Lead card detalhado: contato/links, drivers em linguagem natural com proveniência (`PublishedDriver.references`), `missing_evidence`, status atual, histórico de eventos do lead, controles de tabulação e like/dislike. **Sem score numérico.** | `303 → /login`; `404` se o lead não pertence à carteira do perfil. |
| `POST /lead/{entity_id}/feedback` | sessão | Corpo = `FeedbackEventIn`. Grava `FeedbackEvent` **append-only** (correção = novo evento, nunca update). `operator_id`/`profile_id` da sessão; `run_id` = run do snapshot mais recente em que o lead aparece. `status_id` deve existir no catálogo. | `303 → /login`; `404` lead fora da carteira; `422` (kind inconsistente, `status_id` fora do catálogo). |

### 4.1 Semântica da CARTEIRA (não é "lista do dia")

**Visível** = `leads do snapshot mais recente` ∪ `leads com status NÃO-terminal vindos de
snapshots anteriores` (estes marcados **"em acompanhamento"**). Regras:

1. Lead **sem nenhum evento** de status → status `"novo"` (default Open-World; nunca inferido).
2. Status atual de um lead = `status_id` do evento `kind=status` de **maior `event_id`** do par
   `(profile_id, entity_id)`.
3. Status **terminal** (`cliente`, `contato_invalido`, `fora_do_perfil`) ⇒ o lead **sai** da
   carteira (em qualquer snapshot que apareça).
4. Lead presente no snapshot mais recente **e** em anteriores aparece **uma vez**, na posição do
   snapshot mais recente, mantendo seu status atual.
5. Ordenação determinística: primeiro os leads do snapshot mais recente por `rank_position`;
   depois os "em acompanhamento" por `company` (casefold), tie-break `entity_id`.

**Exemplo.** Snapshot `run_2` (mais recente) tem A, B, C. Snapshot `run_1` tinha C, D, E; a
operadora marcou D = `abordado` e E = `fora_do_perfil`. Carteira: **A, B, C** (ordem do ranking de
`run_2`; C mantém o status que tiver) + **D "em acompanhamento"** (não-terminal de snapshot
antigo). **E não aparece** (terminal). Se D depois virar `cliente`, sai da carteira no próximo
acesso.

Modelo de visão (portal-interno, montado pelo serviço da carteira):

```python
class CarteiraItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lead: PublishedLead
    status_id: str  # "novo" quando não há evento (Open-World)
    em_acompanhamento: bool  # True ⇐ veio só de snapshot anterior
    run_id: str  # snapshot de origem da versão exibida do lead
```

### 4.2 Autenticação e LGPD (piloto)

- **Código de acesso individual** por operadora, gerado pelo dono com alta entropia
  (`secrets.token_urlsafe(16)` ou superior). Armazena-se **só** `sha256(código)` em
  `operators.code_hash` (seed via SQL editor do Neon — runbook §9). SHA-256 puro é aceitável
  porque o código é aleatório de alta entropia (não é senha humana) — sem bcrypt/KDF no piloto
  (anti-overengineering; risco aceito e registrado).
- Sessão por **cookie assinado** (`SECRET_KEY`, `SessionMiddleware` do Starlette — dep
  `itsdangerous` no extra `[portal]`). Logout limpa a sessão.
- **LGPD:** dados pessoais de leads ficam **atrás de login**; `X-Robots-Tag: noindex` em tudo;
  TLS provido pelo Render. **Retenção:** a cópia canônica dos eventos vive no motor (JSONL);
  snapshots/eventos podem ser expurgados do Neon após pull confirmado (procedimento manual no
  runbook §9) — Neon free com retenção curta não é risco.

---

## 5. Storage do portal: porta DAO + adapters

Padrão Ports & Adapters (mesmo espírito da SDD de persistência): o app FastAPI conhece **só a
porta** `BasePortalDAO`. **Sem Alembic, sem ORM** — `CREATE TABLE IF NOT EXISTS` idempotente no
startup (`ensure_schema()`), SQL puro via `psycopg` (v3). Piloto = 1 operadora e dezenas de
leads: **sem índices extras** além das PKs (anti-overengineering).

### 5.1 DDL (literal — executado pelo bootstrap no startup)

```sql
CREATE TABLE IF NOT EXISTS snapshots (
    profile_id   TEXT        NOT NULL,
    run_id       TEXT        NOT NULL,
    payload      JSONB       NOT NULL,  -- PublishedSnapshot serializado
    published_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (profile_id, run_id)
);

CREATE TABLE IF NOT EXISTS feedback_events (
    id          BIGSERIAL PRIMARY KEY,   -- event_id = cursor do pull
    operator_id TEXT        NOT NULL,
    profile_id  TEXT        NOT NULL,
    entity_id   TEXT        NOT NULL,
    run_id      TEXT        NOT NULL,
    kind        TEXT        NOT NULL CHECK (kind IN ('status', 'reaction')),
    status_id   TEXT,
    reaction    TEXT        CHECK (reaction IN ('like', 'dislike')),
    note        TEXT        NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL
);  -- append-only: NUNCA UPDATE/DELETE

CREATE TABLE IF NOT EXISTS operators (
    operator_id TEXT PRIMARY KEY,
    nome        TEXT NOT NULL,
    code_hash   TEXT NOT NULL,  -- sha256 hex do código de acesso
    profile_id  TEXT NOT NULL
);
```

> `published_at`/`created_at` são **passados pelo aplicativo** (relógio injetado na borda do
> portal) — sem `DEFAULT now()`, para que os contract tests sejam determinísticos.

### 5.2 Porta `BasePortalDAO` (ABC — assinaturas imutáveis)

Em `src/socialselling/portal/dao.py`:

```python
from abc import ABC, abstractmethod

from socialselling.portal.contracts import (
    FeedbackEvent,
    FeedbackKind,
    Operator,
    PublishedSnapshot,
    Reaction,
)


class BasePortalDAO(ABC):
    """Porta de storage do portal. O app conhece SÓ esta interface."""

    @abstractmethod
    def ensure_schema(self) -> None:
        """CREATE TABLE IF NOT EXISTS idempotente (no-op no InMemory)."""

    # ------------------------------- snapshots ------------------------------
    @abstractmethod
    def put_snapshot(self, snapshot: PublishedSnapshot, *, now: str) -> bool:
        """Insere o snapshot. False se (profile_id, run_id) já existe (→ 409)."""

    @abstractmethod
    def list_snapshots(self, profile_id: str) -> list[PublishedSnapshot]:
        """Snapshots do perfil, mais recente primeiro (published_at DESC,
        tie-break run_id DESC) — base da carteira (§4.1)."""

    # -------------------------------- feedback ------------------------------
    @abstractmethod
    def append_event(
        self,
        *,
        operator_id: str,
        profile_id: str,
        entity_id: str,
        run_id: str,
        kind: FeedbackKind,
        status_id: str | None,
        reaction: Reaction | None,
        note: str,
        now: str,
    ) -> int:
        """Append-only; retorna o event_id atribuído (serial crescente)."""

    @abstractmethod
    def events_since(self, since: int, *, limit: int = 500) -> list[FeedbackEvent]:
        """Eventos com event_id > since, ordem ASC. Além do fim → lista vazia."""

    @abstractmethod
    def latest_status_by_entity(self, profile_id: str) -> dict[str, str]:
        """Último status_id por entity_id (kind=status, maior event_id vence).
        Entidade ausente do dict = sem evento = 'novo' (Open-World, no chamador)."""

    # ------------------------------- operadoras -----------------------------
    @abstractmethod
    def find_operator_by_code_hash(self, code_hash: str) -> Operator | None:
        """None se não encontrado (login responde 401 genérico)."""
```

### 5.3 Adapters

- **`InMemoryDAO`** (`portal/dao_memory.py`): dicts/listas em memória; serial de `event_id`
  incremental. É o adapter dos **contract tests** e do cenário e2e offline (WU-E5).
- **`PostgresDAO`** (`portal/dao_postgres.py`): **fino** — cada método é 1 statement SQL puro
  (`psycopg`), sem lógica de negócio. `psycopg` é importado **somente** neste módulo.
  `latest_status_by_entity` via `SELECT DISTINCT ON (entity_id) ... ORDER BY entity_id, id DESC`.

### 5.4 Estratégia de teste (gate 100% offline)

1. **Contract tests na porta** (`tests/features/portal_dao_contract.feature` + steps
   parametrizados): idempotência do `put_snapshot`, ordem do `list_snapshots`, serial e ordem de
   `events_since`, semântica do `latest_status_by_entity`, append-only. Rodam no **`InMemoryDAO`**.
2. Rotas/serviços do portal testados com `InMemoryDAO` injetado (FastAPI `TestClient` — sem rede).
3. **`PostgresDAO` fica fora do gate** (risco residual aceito: métodos de 1 SQL, revisados em PR)
   e é coberto pelo **smoke pós-deploy** (runbook §9). Proibido no CI: conexão de banco, rede,
   `DATABASE_URL` real.

---

## 6. Lado motor: CLIs `publish` e `pull-feedback`

Novo pacote `src/socialselling/sync/` (motor-side). Lê `PORTAL_BASE_URL` e
`PORTAL_PUBLISH_TOKEN` do `.env`. **HTTP sempre mockado nos testes** (fixtures gravadas).

### 6.1 Regra canônica de `entity_id` (pré-requisito do loop — WU-E1)

O feedback faz join por `entity_id`; órfãos corrompem o aprendizado **silenciosamente**. A regra
vive em **um único lugar** (`src/socialselling/core/identity.py`) e é consumida pelo corpus e
pelo publish:

```python
def canonical_entity_id(website: str | None, name: str, city: str | None) -> str:
    """Identidade canônica do lead — estável entre runs e entre provedores.

    1) Se há host válido no website: domínio normalizado é o entity_id.
       Normalização: urlsplit (aceita com/sem scheme), casefold, remove
       "www." inicial, remove porta, descarta path/query/fragment,
       remove "." final. Ex.: "https://www.Cliniq.com.br/sobre?x=1"
       -> "cliniq.com.br".
    2) Fallback determinístico (sem site): SHA-256 de
       f"{nome_normalizado}|{cidade_normalizada}" -> "sha256:<hex64>".
       Normalização de texto: NFKD -> ASCII (remove acentos), casefold,
       espaços colapsados para um, strip. Cidade ausente = "".
    """
```

Propriedades exigidas (teste BDD de estabilidade): mesmo lead com site
`https://www.cliniq.com.br/sobre` num run e `cliniq.com.br` em outro (ou vindo de outro provedor)
⇒ **mesmo** `entity_id`; mesmo nome+cidade sem site, com variação de acentos/caixa ⇒ mesmo hash;
leads distintos ⇒ ids distintos.

### 6.2 CLI `publish`

`py -m socialselling.sync.publish --profile <profile_id> [--dry-run]`

1. Carrega a visão ranqueada do corpus do perfil (ADR-006) e corta o **top-20**.
2. Mapeia cada lead para `PublishedLead`: `company`/`segmento`/`cidade`/`uf` (split best-effort de
   `location` em `"Cidade, UF"`), links e contato do `LeadCard`; `drivers` a partir de
   `XAIPayload.positive_signals`/`negative_signals` (texto natural + `references` de proveniência);
   `missing_evidence` = `XAIPayload.missing_signals`. **Nenhum campo de score.**
3. **`run_id` determinístico por conteúdo:** `sha256(profile_id + "|" + ",".join(f"{rank}:{entity_id}"))`
   truncado a 16 hex. Mesmo ranking ⇒ mesmo `run_id` ⇒ republicação vira `409` (sucesso
   idempotente, sem duplicar carteira) — sem relógio na identidade.
4. Grava **registro local atômico** `data/published/<profile_id>/<run_id>.json` contendo o
   snapshot **e** os scores por `entity_id` (`fit`, `intent`, `confidence`, `persona_fit`,
   `p_score`) — é aqui que o join score↔desfecho da calibração acontece (o portal nunca vê score).
5. `--dry-run`: **para aqui** (só o JSON local). Sem `--dry-run`: `POST /api/publish` com Bearer
   `PORTAL_PUBLISH_TOKEN`. `201` e `409` = sucesso; portal fora do ar / 5xx → mensagem crua e
   acionável, **exit code ≠ 0, pipeline e corpus intactos**, snapshot fica local para reenvio.

### 6.3 CLI `pull-feedback`

`py -m socialselling.sync.pull_feedback`

1. Lê o cursor de `data/feedback_events/cursor.json` (`{"since": N}`; ausente = 0).
2. `GET /api/feedback?since=N` em loop até página vazia.
3. Anexa cada evento em `data/feedback_events/events.jsonl` (**append-only**; dedupe por
   `event_id` ≤ cursor) — **backup primário do dado precioso**.
4. Consolida, em ordem de `event_id`:
   - `kind=reaction` → `FeedbackStore` ADR-007 **do perfil** (`data/feedback/<profile_id>.json`),
     com `FeedbackFeatures` lidas do registro local `data/published/<profile_id>/<run_id>.json`
     (scores capturados na publicação — nunca recomputados). **Evento órfão** (`run_id`/`entity_id`
     sem registro local) → linha em `data/feedback_events/orfaos.jsonl` + warning; **nunca**
     inventa features (Open-World), nunca entra no treino.
   - `kind=status` → `data/calibration/eventos.jsonl` (append-only), insumo da calibração offline.
5. Atualiza `cursor.json` **atomicamente, por último** (eventos persistidos antes do avanço do
   cursor ⇒ re-execução é idempotente por dedupe de `event_id`).

---

## 7. Cenários BDD (Gherkin)

Arquivos em `tests/features/`. Portal testado com `InMemoryDAO` + `TestClient`; CLIs do motor com
HTTP mockado por fixture. Relógio sempre injetado.

```gherkin
# language: pt
Funcionalidade: Publicação de snapshot (motor → portal)

  Cenário: Publicação feliz do top-20 sem score
    Dado o corpus ranqueado do perfil "talita" com 32 leads
    Quando executo publish --profile talita
    Então o snapshot enviado tem 20 leads com rank_position 1..20
    E nenhum campo numérico de score aparece no payload publicado
    E o registro local data/published/talita/<run_id>.json guarda os scores por entity_id
    E o portal responde 201 e persiste o snapshot

  Cenário: Republicação do mesmo ranking é idempotente
    Dado um snapshot já publicado para (talita, run_abc)
    Quando executo publish --profile talita com o corpus inalterado
    Então o run_id derivado por hash de conteúdo é idêntico
    E o portal responde 409
    E a CLI termina com sucesso idempotente, sem duplicar carteira

  Cenário: Portal fora do ar não quebra o motor (degradado)
    Dado que o POST /api/publish falha com erro de conexão
    Quando executo publish --profile talita
    Então o snapshot fica gravado localmente em data/published/
    E a CLI termina com exit code diferente de 0 e mensagem crua acionável
    E o pipeline e o corpus permanecem intactos

  Cenário: Snapshot preserva missing_evidence (Open-World)
    Dado um lead do ranking com sinais ausentes em XAIPayload.missing_signals
    Quando o snapshot é montado
    Então PublishedLead.missing_evidence lista os mesmos sinais ausentes
    E o lead permanece publicado (ausência de sinal não o rebaixa a falso)
```

```gherkin
# language: pt
Funcionalidade: API de publicação do portal

  Cenário: Token ausente ou inválido é barrado
    Dado um POST /api/publish sem header Authorization válido
    Então a resposta é 401 e nada é persistido

  Cenário: Contrato violado é rejeitado
    Dado um corpo com campo extra "score" em um lead
    Quando o motor faz POST /api/publish
    Então a resposta é 422 (extra=forbid) e nada é persistido
```

```gherkin
# language: pt
Funcionalidade: Tabulação de feedback pela operadora

  Cenário: Operadora registra status append-only
    Dado uma sessão válida da operadora "talita"
    Quando ela envia POST /lead/cliniq.com.br/feedback com kind=status e status_id=abordado
    Então um FeedbackEvent é anexado com operator_id e profile_id da sessão
    E o run_id do evento é o do snapshot mais recente que contém o lead
    E nenhum evento anterior é alterado (correção = novo evento)

  Cenário: Status fora do catálogo é rejeitado
    Dado uma sessão válida
    Quando ela envia kind=status com status_id "quase_cliente"
    Então a resposta é 422 e nada é gravado

  Cenário: Lead sem evento permanece "novo" (Open-World)
    Dado um lead publicado sem nenhum evento de status
    Quando a carteira é montada
    Então o status exibido é "novo"
    E nenhum evento é fabricado para representar esse default
```

```gherkin
# language: pt
Funcionalidade: Carteira da operadora

  Cenário: Lead não-terminal de snapshot antigo permanece em acompanhamento
    Dado o snapshot run_2 (mais recente) com os leads A, B, C
    E o snapshot run_1 com os leads C, D, E
    E D com status "abordado" e E com status "fora_do_perfil"
    Quando a operadora abre GET /carteira
    Então ela vê A, B, C na ordem de rank_position de run_2
    E vê D marcado "em acompanhamento"
    E não vê E (status terminal sai da carteira)
    E C aparece uma única vez

  Cenário: Status terminal remove o lead da carteira
    Dado o lead D com status "cliente"
    Quando a carteira é montada novamente
    Então D não aparece mais

  Cenário: Carteira é determinística
    Dado os mesmos snapshots e eventos
    Quando a carteira é montada duas vezes
    Então a ordem dos itens é idêntica (rank, depois company casefold, tie-break entity_id)
```

```gherkin
# language: pt
Funcionalidade: Autenticação por código de acesso

  Cenário: Login feliz cria sessão escopada ao perfil
    Dado uma operadora seedada com code_hash de "codigo-correto"
    Quando ela envia POST /login com "codigo-correto"
    Então recebe cookie de sessão assinado com operator_id e profile_id
    E é redirecionada para /carteira

  Cenário: Código errado recebe 401 genérico
    Quando alguém envia POST /login com "codigo-errado"
    Então a resposta é 401 com mensagem genérica
    E nenhuma sessão é criada

  Cenário: Página protegida sem sessão redireciona para login
    Quando um cliente sem cookie acessa GET /carteira
    Então é redirecionado para /login
    E nenhum dado de lead é exposto
```

```gherkin
# language: pt
Funcionalidade: Pull de feedback e consolidação no motor

  Cenário: Pull feliz consolida reactions e statuses
    Dado o cursor local em 0 e o portal com 3 eventos (1 reaction, 2 status)
    Quando executo pull-feedback
    Então os 3 eventos são anexados em data/feedback_events/events.jsonl
    E a reaction vira FeedbackRecord no FeedbackStore do perfil com features do registro local
    E os 2 status são anexados em data/calibration/eventos.jsonl
    E o cursor avança para o maior event_id, gravado atomicamente por último

  Cenário: Cursor além do fim retorna vazio e é idempotente
    Dado o cursor local em 42 e nenhum evento novo no portal
    Quando executo pull-feedback duas vezes
    Então as duas execuções recebem events=[] e next_since=42
    E nenhum arquivo local muda entre as execuções

  Cenário: Evento órfão não corrompe o aprendizado (Open-World)
    Dado um evento reaction com run_id sem registro local em data/published/
    Quando executo pull-feedback
    Então o evento vai para data/feedback_events/orfaos.jsonl com warning
    E nenhuma feature é inventada nem entra no FeedbackStore
    E os demais eventos do lote são consolidados normalmente
```

---

## 8. Operação (runbook resumido)

Detalhado em `docs/runbooks/portal-piloto.md` (WU-T6). Resumo:

1. **Neon (já criado em 2026-06-09):** projeto `socialselling`, região AWS `us-east-1`. Copiar a
   connection string (pooled) — vira `DATABASE_URL` **só no Render**.
2. **Render (ação do dono — WU-X2):** Web Service free, região **Virginia (US East)** (mesma
   região do Neon), via `render.yaml`. Build `pip install -e ".[portal]"`; start
   `uvicorn socialselling.portal.app:app --host 0.0.0.0 --port $PORT`; health check `/healthz`.
   Env vars: `DATABASE_URL`, `PUBLISH_TOKEN`, `SECRET_KEY` (gerar com
   `py -c "import secrets; print(secrets.token_urlsafe(32))"`). Free dorme após idle: primeiro
   acesso pode levar ~1 min (aceito).
3. **Seed da operadora** (após o primeiro start criar as tabelas), via SQL editor do Neon:
   ```sql
   INSERT INTO operators (operator_id, nome, code_hash, profile_id)
   VALUES ('talita', 'Talita', '<sha256 hex do código gerado>', '<profile_id da Talita>')
   ON CONFLICT (operator_id) DO UPDATE SET code_hash = EXCLUDED.code_hash;
   ```
   Código gerado localmente (`secrets.token_urlsafe(16)`); hash com
   `py -c "import hashlib; print(hashlib.sha256(b'<codigo>').hexdigest())"`. Entregar o código à
   operadora por canal privado.
4. **Domínio:** CNAME `selling.issei.com.br` → host `.onrender.com` do serviço; custom domain no
   Render (TLS automático).
5. **Smoke pós-deploy** (`scripts/smoke_portal.py` — única peça que toca o portal real; cobre o
   risco residual do `PostgresDAO`): `GET /healthz` 200 → `POST /api/publish` com snapshot
   sintético `profile_id="smoke"` → 201 → repetir → 409 → `GET /api/feedback?since=0` → 200.
6. **Ciclo manual do piloto** (sem agendamento): `pull-feedback` → rodar pipeline
   (`py -m socialselling.orchestrator --profile <id>`) → `publish --profile <id>` → avisar a
   operadora.
7. **Métricas de sucesso do piloto** — computadas **no motor, offline**, a partir de
   `data/feedback_events/` + `data/calibration/` + `data/published/`:
   - **Cobertura de tabulação:** % dos leads publicados com ≥ 1 evento;
   - **Taxa de resposta por faixa de ranking** (1–5, 6–10, 11–20) — valida o ranking
     ("quem devo abordar primeiro?");
   - **Taxa de `contato_invalido`** — qualidade do enriquecimento.

---

## 9. Work Units (rastreáveis — Run Noturno)

Cada WU é uma card que passa pelo DoR/DoD (`docs/governance/dor-dod.md`); contratos e Gherkin
acima já satisfazem o DoR. Ordem sugerida = ordem da tabela (E1→E2 destravam tudo; X2 destrava o
deploy real, não o desenvolvimento).

| WU | Escopo | Critério de aceitação |
|---|---|---|
| **WU-E1** | Regra canônica de `entity_id` em `core/identity.py` (`canonical_entity_id`, §6.1): normalização de domínio + fallback SHA-256 de nome_normalizado+cidade, adotada pelo corpus e pelo publish como **única** fonte de identidade. Pré-requisito do loop: o join do feedback depende dela. | Teste BDD de **estabilidade entre runs e provedores** verde (variações de scheme/www/caixa/acentos ⇒ mesmo id); `mypy --strict` limpo. |
| **WU-E2** | Contratos de publicação/feedback em `portal/contracts.py` (§2, transcritos literalmente) + `config/feedback_catalog.json` v1 (§3) + loader/validação do catálogo. Modelos compartilhados motor↔portal; `DataProvenance` reusado, sem duplicação. | Round-trip de (de)serialização verde; validadores (ranks estritos, kind consistente, ids/ordens únicos) testados; `extra="forbid"` rejeita campo `score`. |
| **WU-T1** | Scaffold do portal: pacote `src/socialselling/portal/` (app FastAPI, extra `[portal]` no `pyproject.toml`), porta `BasePortalDAO` (§5.2), `InMemoryDAO`, `PostgresDAO` fino (`psycopg`, 1 SQL/método) e bootstrap `ensure_schema()` com o DDL literal (§5.1) no startup. Middleware `X-Robots-Tag: noindex` + `GET /healthz`. | Contract tests da porta verdes no `InMemoryDAO`; `psycopg` importado só em `dao_postgres.py` (grep no gate); gate 100% offline. |
| **WU-T2** | `POST /api/publish`: Bearer `PUBLISH_TOKEN`, validação `PublishedSnapshot`, idempotência por `(profile_id, run_id)` com 201/409, erros 401/422 (§4). | Cenários da API de publicação verdes (`TestClient` + `InMemoryDAO`); 409 não duplica; 401 não persiste nada. |
| **WU-T3** | Auth por código: `POST /login` (sha256 do código → `find_operator_by_code_hash`), sessão por cookie assinado (`SECRET_KEY`) com `operator_id`+`profile_id`, `POST /logout`, guarda de sessão nas páginas (303 → `/login`). | Cenários de autenticação verdes (feliz, código errado 401 genérico, página protegida sem sessão); cookie `HttpOnly`/`Secure`/`SameSite=Lax`. |
| **WU-T4** | APIs de feedback: `POST /lead/{entity_id}/feedback` via sessão (corpo `FeedbackEventIn`; `operator_id`/`profile_id` da sessão; `run_id` resolvido pelo snapshot mais recente; validação contra o catálogo; append-only) e `GET /api/feedback?since&limit` via Bearer (cursor, `FeedbackPage`, vazio idempotente além do fim). | Cenários de tabulação e de cursor verdes; nenhum caminho de código faz UPDATE de evento; 422 para status fora do catálogo. |
| **WU-T5** | UI da operadora (Jinja2 + JS vanilla): `GET /carteira` com a regra de visibilidade §4.1 (união, "em acompanhamento", terminais fora, ordenação determinística) e `GET /lead/{entity_id}` (drivers em linguagem natural com proveniência, `missing_evidence`, status atual + histórico, controles de status e like/dislike, **sem score**). | Cenários da carteira verdes (incluindo lead antigo não-terminal e dedupe); lead card não renderiza nenhum número de score; serviço da carteira coberto por testes determinísticos. |
| **WU-E3** | CLI `publish` (`sync/publish.py`, §6.2): monta o top-20 do corpus ranqueado por perfil, `run_id` por hash de conteúdo, registro local atômico com scores em `data/published/`, `--dry-run` só grava local, POST com `PORTAL_PUBLISH_TOKEN`, degradação limpa quando o portal está fora do ar. | Cenários de publicação verdes com **HTTP mockado**; snapshot sem score (assert estrutural); 409 tratado como sucesso idempotente. |
| **WU-E4** | CLI `pull-feedback` (`sync/pull_feedback.py`, §6.3): cursor em `data/feedback_events/cursor.json`, JSONL append-only, dedupe por `event_id`, consolidação reactions→`FeedbackStore` ADR-007 **por perfil** (features do registro local), statuses→`data/calibration/eventos.jsonl`, órfãos isolados, cursor atualizado atomicamente por último. | Cenários de pull verdes (feliz, cursor além do fim idempotente, órfão isolado) com HTTP mockado; reexecução não duplica nem altera arquivos. |
| **WU-T6** | `render.yaml` (Web Service free, Virginia, build/start/health, env vars referenciadas sem valor) + runbook `docs/runbooks/portal-piloto.md` (§8 completo: Neon, seed SQL, DNS, ciclo manual, expurgo pós-pull) + `scripts/smoke_portal.py`. | `render.yaml` validado (lint YAML); runbook revisado pelo dono; smoke executável localmente contra URL arbitrária (sem rodar no gate). |
| **WU-E5** | Cenário **e2e offline do loop completo**: `publish --dry-run` → snapshot injetado no portal com `InMemoryDAO` (sem rede) → login → eventos de status e reaction → `pull-feedback` contra o app de teste → consolidação verificada (FeedbackStore + calibração + cursor). Prova o contrato ponta-a-ponta dentro do gate. | Cenário e2e verde, determinístico, 100% offline; é o "smoke test ponta-a-ponta" do piloto no CI. |
| **WU-X2** | **[Externo/dono]** Criar o Web Service no Render (região Virginia) a partir do `render.yaml`, configurar `DATABASE_URL`/`PUBLISH_TOKEN`/`SECRET_KEY`, CNAME `selling.issei.com.br`, rodar o smoke e fazer o seed da operadora Talita via SQL editor do Neon. | Smoke pós-deploy verde no domínio final; Talita loga com o código e vê a carteira publicada. |

**Quality gate (inegociável):** `ruff` + `mypy --strict` + `pytest` 100% verdes, offline e
determinísticos; HTTP/banco jamais reais na suíte; tolerância numérica `1e-9`; zero flakiness.

---

## 10. Fora de escopo do piloto

- **Agendamento de runs** (EventBridge, cron, scheduler local) — runs **manuais** durante a
  experimentação.
- **Apollo / enriquecimento pago** — Tavily-only. Roadmap registrado: *avaliar enriquecimento
  gratuito* (só entra se houver serviço sem custo).
- **Ligar desfecho de funil ao aprendizado automático** — ADR futura, com dados de calibração na
  mão (fase 1 coleta; like/dislike segue como único input da ADR-007).
- **Cognito/OAuth** — WU-X1 e OIDC ficam provisionados na prateleira (ADR-008 visão futura;
  ADR-009 dormente).
- **Self-service de operadoras** (cadastro, reset de código, convites) — seed manual via SQL.
- **Multi-idioma**, **mobile app**, **notificações** (e-mail/push) e qualquer pegada AWS.
