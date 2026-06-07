# SDD — Ports & Adapters para persistência bimodal (local JSON ⇄ AWS DynamoDB)

> **Status:** **PROPOSTA (v1.0 — aguardando aprovação do dono)**.
> Deriva do **ADR-008** (§5 Ports & Adapters; restrição de bimodalidade). Spec-first: este
> documento precede o código. **Esta é a SDD vital para a manutenção da execução local:** define a
> interface abstrata que isola o motor (M1–M5, corpus, learning) do meio de armazenamento físico,
> permitindo trocar JSON local por DynamoDB **sem tocar uma linha de regra de negócio**.
>
> **Foco:** definir os **Ports** (interfaces), os dois **Adapters** (`LocalJSONRepository`,
> `DynamoDBRepository`), a fábrica de seleção por `[runtime].persistence_mode` e o **plano de
> testes** que mantém o quality gate 100% offline e determinístico.

---

## 0. Premissas, invariantes e reaproveitamento

| Invariante (não negociável) | Origem | Como os Adapters respeitam |
|---|---|---|
| Persistência atômica, sem escrita parcial | CLAUDE.md §3.4 | `LocalJSONRepository` → `core/atomic.py` (`write-temp`+`os.replace`). `DynamoDBRepository` → *Conditional Expressions* atômicas. |
| Core M1–M5 agnóstico de infra | ADR-008 §5 | Os módulos conhecem **só os Ports** (classes abstratas); nunca `boto3` nem caminhos de arquivo. |
| Determinismo byte-idêntico | CLAUDE.md §3.2 | Upsert idempotente por `entity_id` (SHA-256 estável); ordenação estável; `now` injetado, não interno. |
| Open-World: falha ≠ falso | CLAUDE.md §3.3 | Leitura ausente retorna `None`/vazio (incerteza), nunca exceção que oculte o lead. |
| Isolamento de camadas | CLAUDE.md §3.1 | `BaseFeedbackRepository` (ADR-007) é separado de `BaseCorpusRepository`; feedback nunca grava Evidence/Inference. |
| Paridade do modo `local` | ADR-008 §5 | Com `persistence_mode = "local"` o comportamento é **idêntico** ao baseline; o gate roda offline. |

**Não-objetivo:** esta SDD **não** altera as fórmulas de score/ranking, **não** muda contratos de
domínio (`contracts.py`), **não** introduz ORM. É puramente a camada de isolamento de I/O.

---

## 1. Arquitetura Ports & Adapters

```
            ┌──────────────────────────────────────────────────────┐
            │   Núcleo (regras de negócio) — agnóstico de infra      │
            │   M1..M5 · corpus/integration · learning/model         │
            └───────────────────────┬──────────────────────────────┘
                                     │ depende SÓ de Ports (ABCs)
        ┌────────────────────────────┴───────────────────────────────┐
        │   Ports:  BaseCorpusRepository  BaseCacheRepository           │
        │           BaseLedgerRepository  BaseFeedbackRepository        │
        └───────┬───────────────────────────────────────────┬──────────┘
                │ (persistence_mode = "local")               │ (persistence_mode = "aws")
        ┌───────▼─────────────┐                     ┌─────────▼───────────────┐
        │  LocalJSONRepository │                     │  DynamoDBRepository      │
        │  core/atomic.py      │                     │  boto3 + Conditional Expr│
        │  data/*.json / NDJSON│                     │  Single Table (SDD-2)    │
        └──────────────────────┘                     └──────────────────────────┘
```

A seleção é feita por uma **fábrica** (`core/repositories/factory.py`) que lê
`[runtime].persistence_mode` uma única vez na composição (composition root) e devolve as instâncias
concretas das Ports. O núcleo recebe os repositórios por **injeção de dependência** — nunca os
instancia.

---

## 2. Contratos: Ports (interfaces abstratas)

Em `src/socialselling/core/repositories/base.py`. Assinaturas **imutáveis** (mudá-las é mudança de
contrato e exige nova versão). Todos os métodos de escrita são **atômicos** e **idempotentes por
`entity_id`**.

```python
from abc import ABC, abstractmethod
from socialselling.contracts import LeadCard  # exemplo; tipos de domínio reusados

class BaseCorpusRepository(ABC):
    """Corpus acumulativo (ADR-006). Chave estável = entity_id (SHA-256)."""

    @abstractmethod
    def get(self, user_id: str, entity_id: str) -> LeadCard | None: ...

    @abstractmethod
    def list_ranked(self, user_id: str, *, limit: int | None = None) -> list[LeadCard]:
        """Visão ordenada por score, deduplicada por entity_id (determinística)."""

    @abstractmethod
    def upsert(self, user_id: str, entity_id: str, card: LeadCard, *, now: str) -> None:
        """Insere/atualiza idempotentemente. now injetado (determinismo §3.2)."""


class BaseCacheRepository(ABC):
    """Cache atômico T-24h de respostas de sensores. Chave = hash do prompt/query."""

    @abstractmethod
    def get(self, user_id: str, key_hash: str, *, now: str) -> str | None:
        """Retorna o payload cacheado se não expirado (T-24h); senão None."""

    @abstractmethod
    def put(self, user_id: str, key_hash: str, payload: str, *, now: str, ttl_hours: int) -> None: ...


class BaseLedgerRepository(ABC):
    """Ledgers FinOps: créditos mensais Apollo + RPD diário Gemini (LEDGER#FINOPS)."""

    @abstractmethod
    def read(self, user_id: str) -> dict: ...

    @abstractmethod
    def consume(self, user_id: str, *, provider: str, amount: int, now: str) -> bool:
        """Debita atomicamente. Retorna False se excederia o cap (sem escrita parcial)."""


class BaseFeedbackRepository(ABC):
    """Votos like/dislike (ADR-007). Chave = company_id. Camada de APRESENTAÇÃO apenas."""

    @abstractmethod
    def record(self, user_id: str, company_id: str, vote: dict, *, now: str) -> None: ...

    @abstractmethod
    def all_votes(self, user_id: str) -> list[dict]:
        """Ordenado por company_id (treino determinístico full-batch, ADR-007)."""
```

> **Isolamento de camadas garantido pelo tipo:** `BaseFeedbackRepository` opera com `dict` de
> componentes de score capturados no clique (`fit`,`intent`,`confidence`,`persona_fit`) — **não**
> aceita `ObservedEvidence` nem `Inference`. Impossível, por contrato, o feedback corromper as
> camadas 1/2.

---

## 3. Adapters (implementações concretas)

### 3.1 `LocalJSONRepository` (`persistence_mode = "local"`)

Consome a infraestrutura local existente — **paridade total com o baseline**.

- **Atomicidade:** toda escrita via `core/atomic.py` (`atomic_write_text`: grava em arquivo
  temporário e faz `os.replace`). Nenhuma escrita parcial, mesmo sob crash.
- **Layout físico:** arquivos flat JSON/NDJSON já existentes — `data/corpus/leads_corpus.json`,
  `data/cache/*`, `data/apollo_credit_ledger.json`, `data/gemini_request_ledger.json`,
  `data/feedback.json`, `data/corpus/waves.json`.
- **Multi-tenant no local:** `user_id` é um único tenant lógico (ex.: `local`) — os caminhos não
  mudam; o argumento `user_id` é aceito e ignorado/fixo, preservando byte-paridade do baseline.
- **Idempotência:** `upsert` lê o dict, substitui a entrada por `entity_id`, reescreve atômico —
  exatamente o comportamento de `corpus/store.py` atual.

### 3.2 `DynamoDBRepository` (`persistence_mode = "aws"`)

Implementação `boto3` sobre a Single Table (SDD-2). Mapeia os métodos da Port para chamadas nativas:

| Método da Port | Chamada DynamoDB | Chave / condição |
|---|---|---|
| `corpus.get` | `GetItem` | PK `USER#user_id`, SK `LEAD#entity_id` |
| `corpus.list_ranked` | `Query` | PK `USER#user_id`, `begins_with(SK, "LEAD#")`, ordenação estável por score no cliente |
| `corpus.upsert` | `UpdateItem` | `ConditionExpression: attribute_not_exists(PK) OR version < :v` (concorrência otimista) |
| `cache.get/put` | `GetItem`/`PutItem` | SK `CACHE#key_hash`, atributo TTL `expires_at` |
| `ledger.consume` | `UpdateItem` | SK `LEDGER#FINOPS`, `ConditionExpression: balance >= :amount` (impede saldo negativo / escrita parcial) |
| `feedback.record` | `PutItem` | SK `FEEDBACK#company_id` |

- **Atomicidade/idempotência estritas:** *Conditional Expressions* asseguram que reescrever o
  mesmo `entity_id` não duplica nem corrompe estado, e que débitos de crédito nunca passam o cap
  nem deixam estado meio-escrito — o análogo serverless do `os.replace`.
- **Sem vazamento de infra:** `boto3` vive **somente** aqui. Nenhum import de `boto3` fora de
  `core/repositories/dynamodb.py`.

---

## 4. Chaveamento bimodal (`runtime.toml`)

Único ponto de controle, conforme ADR-008 §5:

```toml
[runtime]
persistence_mode = "local"   # "local" | "aws"
```

```python
# core/repositories/factory.py (resumo)
def build_repositories(cfg) -> Repositories:
    mode = cfg.runtime.persistence_mode
    if mode == "local":
        return Repositories.local()      # LocalJSON* sobre core/atomic.py
    if mode == "aws":
        return Repositories.dynamodb()   # DynamoDB* sobre boto3
    raise ValueError(f"persistence_mode inválido: {mode!r}")
```

Regra de paridade: `mode == "local"` ⇒ comportamento **idêntico** ao baseline anterior à ADR-008.

---

## 5. Plano de testes e Quality Gate (inegociável)

A suíte testa **regras de negócio injetando dublês das Ports** — nunca a infraestrutura real.

### 5.1 Princípios

1. **Testes contra as Ports, não contra os Adapters reais.** O núcleo é testado com um
   **`FakeRepository`** em memória (implementa as ABCs). Rápido, determinístico, offline.
2. **Contract tests compartilhados.** Uma mesma bateria de comportamento
   (`tests/features/persistence_contract.feature`) roda contra `LocalJSONRepository` **e** contra
   `FakeRepository`, garantindo que ambos honram idempotência, atomicidade e ordenação. O
   `DynamoDBRepository` é coberto pela **mesma bateria** usando um *fake* de `boto3`
   (stub das chamadas `PutItem/GetItem/UpdateItem/Query`) — **sem rede**.
3. **Proibições explícitas no CI:**
   - ❌ Nenhum teste nativo abre conexão com a AWS.
   - ❌ Nenhuma chave de API real ou credencial AWS no ambiente de CI.
   - ❌ Nenhuma instalação/execução de LocalStack ou emulador pesado.
4. **Determinismo:** `now`/RNG injetados; asserções numéricas com tolerância `1e-9`; ordenação
   estável por `entity_id`/`company_id`. Flakiness = falha (zero tolerância).

### 5.2 Comando do gate

`./scripts/gate.ps1` (Win) ou `./scripts/gate.sh` (WSL) — executa `ruff` + `mypy --strict` +
`pytest`, **100% offline, ágil e determinístico**, mantendo a meta de cobertura e o orçamento de
erro zero para quebras/flakiness, **em ambos os modos** (o gate roda o modo `local` por padrão;
o `DynamoDBRepository` é exercido com `boto3` stubado).

---

## 6. Cenários BDD (Gherkin)

```gherkin
# language: pt
Funcionalidade: Persistência bimodal via Ports & Adapters

  # ---------- Caminho feliz ----------
  Cenário: Upsert idempotente é byte-idêntico em ambos os adapters
    Dado um LeadCard com entity_id "sha256:abc"
    Quando faço upsert duas vezes no LocalJSONRepository com o mesmo card
    E faço upsert duas vezes no FakeRepository com o mesmo card
    Então o corpus resultante é idêntico nos dois (uma só entrada, 1e-9)
    E a ordenação por score é estável e determinística

  Cenário: Escrita atômica não deixa estado parcial sob falha
    Dado um LocalJSONRepository
    Quando uma escrita é interrompida após o arquivo temporário e antes do replace
    Então o arquivo final permanece a versão anterior íntegra
    E nenhuma leitura observa conteúdo parcial

  Cenário: Modo local preserva paridade com o baseline
    Dado persistence_mode = "local"
    Quando o pipeline roda o smoke ponta-a-ponta
    Então a saída é byte-idêntica à do baseline anterior à ADR-008

  # ---------- Degradado por limites/billing ----------
  Cenário: Débito de crédito além do cap é recusado sem escrita parcial
    Dado um LEDGER#FINOPS com saldo Apollo = 1
    Quando consume(provider="apollo", amount=2) é chamado
    Então o retorno é False
    E o saldo permanece 1 (nenhuma escrita parcial)

  Cenário: Cache expirado (T-24h) retorna None e força nova evidência
    Dado um item CACHE# gravado em now-25h
    Quando cache.get é chamado com now atual
    Então o retorno é None
    E o lead não é fabricado a partir de cache vencido

  # ---------- Open-World ----------
  Cenário: Leitura ausente retorna None, não exceção
    Dado um entity_id inexistente para o tenant
    Quando corpus.get é chamado
    Então o retorno é None
    E o pipeline trata como incerteza (Open-World), sem ocultar nem quebrar

  Cenário: Feedback não pode tocar Evidence/Inference (isolamento de camadas)
    Dado um BaseFeedbackRepository
    Quando se tenta gravar um voto
    Então o tipo aceito é apenas componentes de score (fit/intent/confidence/persona_fit)
    E é impossível, por contrato, gravar ObservedEvidence ou Inference

  # ---------- Gate offline ----------
  Cenário: Suíte roda sem AWS, sem chaves reais e sem LocalStack
    Dado o ambiente de CI sem credenciais AWS e sem LocalStack
    Quando ./scripts/gate.sh é executado
    Então ruff, mypy --strict e pytest passam 100% verdes
    E nenhum teste abre conexão de rede
```

---

## 7. Work Units (rastreáveis — Run Noturno)

| WU | Entrega | Critério de aceitação |
|---|---|---|
| **WU-P1** | `core/repositories/base.py`: as 4 Ports (ABCs) com assinaturas imutáveis | `mypy --strict` limpo; ABCs não instanciáveis. |
| **WU-P2** | `LocalJSONRepository` sobre `core/atomic.py`, reusando `corpus/store.py`/`cache.py`/ledgers | Cenário "paridade com baseline" e "atomicidade" verdes. |
| **WU-P3** | `FakeRepository` em memória (dublê para testar o núcleo) | Núcleo testável sem I/O; contract tests passam. |
| **WU-P4** | Bateria de **contract tests** compartilhada (`persistence_contract.feature`) | Roda contra Local e Fake; idempotência/ordenação/atomicidade verdes. |
| **WU-P5** | `DynamoDBRepository` (`boto3`, Conditional Expressions) isolado em um único módulo | Mesma bateria com `boto3` **stubado**; `boto3` não importado fora do módulo. |
| **WU-P6** | `core/repositories/factory.py` + leitura de `[runtime].persistence_mode` | Modo inválido falha cedo; seleção correta por flag. |
| **WU-P7** | Refactor do núcleo (M1–M5, corpus, learning) para receber Ports por injeção | Nenhum import de `boto3`/caminho de arquivo nos módulos puros (lint/grep no gate). |
| **WU-P8** | Guard de CI: proíbe rede/credenciais/LocalStack na suíte nativa | Cenário "gate offline" verde; CI falha se algum teste tentar rede. |

**Quality gate (inegociável):** `ruff` + `mypy --strict` + `pytest` 100% verdes, **offline**,
ágeis e determinísticos; cobertura mantida; zero flakiness. Proibido depender de AWS real, chaves
reais ou LocalStack na suíte nativa.
