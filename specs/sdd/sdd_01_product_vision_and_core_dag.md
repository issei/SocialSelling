# SDD-01: Product Vision & Core DAG
## Sistema de Inteligência de Dados — SocialSelling
### Versão: 1.0 | Classificação: CONFIDENCIAL — ENGENHARIA

---

**Escopo do Documento:** Visão de produto, arquitetura evolutiva, pipeline de data flow completo (Fases 0–10), taxonomia linguística por setor e matriz de separação de capacidades por versão.

**Documentos relacionados:**
- `sdd_02_mathematical_core_scoring.md` — Fórmulas matemáticas, scoring, freshness, RCS
- `specs/SocialSelling_MVP_SDD_v1_1.md` — Solution Design Document principal (contém DDL, módulos, payloads)

---

## SEÇÃO 1: MATRIZ DE EVOLUÇÃO ARQUITETURAL

### 1.1 Premissa de Ruptura Arquitetural

O SocialSelling é, por definição, um sistema de inteligência de dados orientado a evidências comportamentais coletadas de forma assíncrona em múltiplas fontes públicas. A natureza do problema impõe restrições concretas que tornam pipelines lineares e síncronos — arquiteturas como n8n acoplado a planilhas Google Sheets ou fluxos sequenciais de webhook — estruturalmente inadequadas. Esta seção demonstra, dimensão por dimensão, por que o modelo State-Driven baseado em grafos de estados em memória volátil (LangGraph Engine) elimina cada uma dessas inadequações de forma mecanicamente provável.

A comparação abaixo não é de preferência de ferramenta: é de capacidade arquitetural mínima para que o sistema cumpra suas três perguntas estratégicas com integridade matemática.

### 1.2 Tabela Comparativa — 8 Dimensões Arquiteturais

| Dimensão | Pipeline Linear Síncrono (n8n + Google Sheets) | LangGraph State-Driven (Grafos de Estado em Memória Volátil) |
|---|---|---|
| **1. Modelo de Execução** | Sequencial bloqueante: cada nó aguarda o retorno completo do anterior antes de avançar. O tempo total de ciclo é a soma de todas as latências individuais. Um scraper lento bloqueia toda a cadeia. | Grafo de estados com borda condicional: cada nó transita por predicados de estado. Ramos independentes do DAG (ex.: scraping Instagram e scraping LinkedIn) executam em paralelo assíncrono via `asyncio`. O tempo de ciclo converge para o gargalo de maior latência, não para a soma. |
| **2. Concorrência e Race Conditions** | Planilhas Google Sheets como estado compartilhado: múltiplas execuções simultâneas escrevem na mesma célula/aba sem mecanismo de lock. Race conditions são estruturalmente inevitáveis quando dois runs paralelos atualizam o mesmo lead. Não existe controle de versão de célula nativo. | Estado do grafo é imutável dentro de cada step: cada nó recebe uma snapshot do `AgentState` e emite um delta. A fusão de deltas é serializada pelo scheduler do LangGraph. Zero race conditions por design — o estado nunca é acessado concorrentemente para escrita; apenas leitura concorrente é permitida. |
| **3. Propagação de Estado entre Fases** | Propagação via leitura/escrita de arquivo externo (planilha). Cada fase serializa o resultado em disco ou memória de planilha e a fase seguinte deserializa. O custo de I/O se acumula. Não há schema enforcement nativo: uma fase pode escrever um campo em formato inconsistente sem alerta. | Estado propagado em memória volátil como `TypedDict` com schema LangGraph. Cada node recebe `state: AgentState` e retorna `Dict[str, Any]` que é merged automaticamente. Zero serialização entre fases. Schema validation acontece em runtime na fronteira de cada nó. |
| **4. Backpressure e Controle de Fluxo** | Não existe mecanismo nativo de backpressure em n8n. Se a API Tavily ou o scraper do Instagram começa a responder lentamente, o pipeline inteiro desacelera proporcionalmente ou estoura o timeout configurado por nó, descartando a execução. | O scheduler do LangGraph suporta controle de concorrência por borda: é possível parametrizar `max_concurrency` por nó. Se o nó de scraping Instagram atingir o limite de workers paralelos, as entidades excedentes são enfileiradas internamente sem bloquear o subgrafo de scraping LinkedIn. Backpressure é aplicado na camada de scheduler, não no código de aplicação. |
| **5. Gestão de Exceções Transacionais** | Exceções em n8n interrompem o flow no nó que falhou. O estado parcial computado antes da falha é perdido ou fica corrompido na planilha. Reprocessar exige reexecutar o flow desde o início ou manualmente identificar o ponto de falha. Não há rollback de estado. | Cada nó do grafo declara seu próprio handler de exceção via `try/except` com politica de degradação (`operating_mode = 'DEGRADED_*'`). Exceções não propagam para o grafo inteiro — o nó emite um delta de estado com `error_flag=True` e `u_increment` para os atributos afetados. O grafo continua por borda alternativa (ex.: `SCRAPER_FAILED → DEGRADED_MODE`). O estado acumulado antes da falha é preservado integralmente. |
| **6. Rastreabilidade e Observabilidade** | Rastreabilidade depende de logs de execução do n8n (não estruturados por default) ou de colunas adicionais na planilha. Não existe proveniência de dado nativa: não é possível determinar, para um score produzido, qual evidência específica o influenciou sem inspeção manual. | Cada evidência no `AgentState` carrega `source_id`, `collected_at`, `SRS_k`, `e_fresh` e `hypothesis_linked`. O XAI Payload (Fase 9) reconstrói a cadeia causal completa de cada driver do P_score. O `v_cognitive_observability` registra cada mutação de estado com timestamp e nó de origem. Rastreabilidade é uma propriedade arquitetural de primeira classe, não um log ad-hoc. |
| **7. Escalabilidade Horizontal** | n8n escala verticalmente (mais CPU/RAM na instância). Escalar horizontalmente requer sharding manual de planilhas ou filas externas. O estado em Google Sheets impõe limite prático de ~50k linhas antes de degradação de performance de leitura/escrita. | O estado `AgentState` é passado por valor entre nós — não há estado compartilhado central. A instância de processamento pode ser distribuída horizontalmente: diferentes leads processados em workers distintos sem coordenação de estado. O limite de escala é o I/O das APIs externas, não a arquitetura interna. |
| **8. Extensibilidade e Evolução de Contrato** | Adicionar uma nova fonte de dados (ex.: CNPJ.ws) requer criar um novo nó no flow do n8n e adicionar colunas na planilha. Mudanças de schema quebram flows existentes. Não há mecanismo de migração de estado. Versionar o contrato ICP exige criar uma aba nova na planilha e atualizar manualmente todas as fórmulas dependentes. | O `AgentState` é um `TypedDict` versionado. Adicionar um novo campo é aditivo — campos novos têm default `None` e não quebram nós existentes que não os consomem. O `icp_contract` é uma entidade versionada por `version_hash` na tabela `icp_contract`. Novas fontes de dados são adicionadas como novos nós no grafo sem afetar o ramo de execução existente. |

### 1.3 Mecanismos Internos do LangGraph Engine

#### 1.3.1 Estrutura do AgentState

O `AgentState` é um `TypedDict` Python que serve como portador canônico de todo o estado do ciclo de inteligência. Ele transita entre nós do grafo por valor (shallow copy), garantindo imutabilidade dentro de cada step:

```python
class AgentState(TypedDict):
    # Identidade do ciclo
    run_id: str                          # UUID v4 do ciclo
    icp_contract_version: str            # version_hash do contrato ICP ativo
    operating_mode: str                  # NORMAL | DEGRADED_INSTAGRAM | DEGRADED_LINKEDIN | CACHE_ONLY

    # Entidades em processamento
    entities: List[EntityRecord]         # Lista de leads com todos os atributos e triplas omega
    entity_graph: Dict[str, List[Edge]]  # Grafo de relacionamentos entre entidades

    # Evidências coletadas
    raw_evidence_pool: List[RawEvidence]       # Layer 1: evidências brutas normalizadas
    semantic_inference_pool: List[Inference]   # Layer 2: inferências semânticas geradas
    hypothesis_posteriors: Dict[str, float]    # Layer 3: posteriors P(H|E) por hipótese

    # Scores computados
    o_scores: Dict[str, float]           # entity_id -> O_score
    c_scores: Dict[str, float]           # entity_id -> C_score
    p_scores: Dict[str, float]           # entity_id -> P_score
    ranked_prospects: List[RankedProspect]  # Output final ordenado

    # Controle de qualidade e observabilidade
    dss_window: List[str]                # Janela W=50 de evidence IDs para DSS
    finops_budget_remaining: int         # Queries Tavily restantes no ciclo
    cycle_errors: List[ErrorRecord]      # Erros de execução com nó de origem
    v_cognitive_log: List[MutationEvent] # Log de mutações de estado com timestamp
```

#### 1.3.2 Propagação de Estado e Merge de Deltas

Cada nó do grafo LangGraph segue o contrato:

```python
def node_name(state: AgentState) -> Dict[str, Any]:
    # 1. Lê do estado imutável (snapshot)
    entities = state["entities"]

    # 2. Computa resultado
    result = compute_something(entities)

    # 3. Retorna apenas o delta — o LangGraph faz o merge
    return {"field_name": result}
```

O LangGraph aplica `{**current_state, **delta}` de forma serializada antes de passar para o próximo nó. Isso garante que:
- Dois nós paralelos que escrevem em campos distintos do estado nunca colidem.
- Um nó que escreve em um campo que outro nó acabou de escrever só lê o estado mais recente após ambos os merges serem aplicados na sequência definida pelo DAG.

#### 1.3.3 Borda Condicional e Roteamento de Fluxo

O roteamento entre nós é determinado por funções de predicado sobre o estado:

```python
def route_after_scraping(state: AgentState) -> str:
    if state["operating_mode"] == "CACHE_ONLY":
        return "node_load_from_cache"
    elif state["operating_mode"].startswith("DEGRADED"):
        return "node_normalize_degraded"
    else:
        return "node_normalize_full"

graph.add_conditional_edges(
    "node_scrape",
    route_after_scraping,
    {
        "node_load_from_cache": node_load_from_cache,
        "node_normalize_degraded": node_normalize_degraded,
        "node_normalize_full": node_normalize_full,
    }
)
```

Isso garante que o roteamento é uma função pura do estado atual — sem variáveis globais, sem contexto implícito, sem efeitos colaterais.

---

## SEÇÃO 2: PIPELINE DE DATA FLOW — FASE 0 À FASE 10

### 2.0 Visão Geral do DAG

O pipeline de inteligência é um DAG (Directed Acyclic Graph) de 11 fases (0 a 10) implementado como um grafo LangGraph. Cada fase é um nó ou conjunto de nós paralelos. As transições entre fases são determinadas por predicados de estado (bordas condicionais). O estado é propagado em memória volátil como `AgentState`.

```
[Fase 0: Search Strategy Planner]
          |
          v
[Fase 1: Seed Ingestion & Anchor Profiling]
          |
          v
[Fase 2: Sensory Scraping] <-- paralelo assincrono (Instagram || LinkedIn || CNPJ.ws || Tavily)
          |
          v
[Fase 3: Evidence Normalization & Deduplication]
          |
          v
[Fase 4: Entity Resolution]
          |
          v
[Fase 5: Inference Generation]
          |
          v
[Fase 6: Bayesian Hypothesis Update]
          |
          v
[Fase 7: Committee Mapping]
          |
          v
[Fase 8: Score Computation]
          |
          v
[Fase 9: XAI Payload Assembly]
          |
          v
[Fase 10: Prospect Prioritization & Delta Search]
```

---

### 2.1 Fase 0 — Search Strategy Planner

**Objetivo:** Parametrizar o ciclo de inteligência com base no `icp_contract` ativo, calcular o budget de queries disponível e selecionar as fontes de dados prioritárias por segmento.

**Inputs do AgentState:**
- `icp_contract_version` — hash do contrato ICP que regerá o ciclo
- `finops_budget_remaining` — quota de queries Tavily disponível (inicializada pelo orquestrador com o budget do ciclo)
- `seed_list` — lista de seeds a processar (nomes de empresa, perfis Instagram, perfis LinkedIn)

**Processamento:**

1. **Leitura e validação do `icp_contract`:** o sistema carrega o contrato ICP pelo `version_hash`. Valida presença dos atributos mínimos obrigatórios: `target_segments[]`, `icp_team_size_range`, `icp_revenue_range_brl`, `icp_centralization_min`, `keyword_taxonomy.pain_keywords[]`, `icp_maturity_threshold`. Se algum atributo obrigatório estiver ausente, o ciclo é abortado com `CycleError(code='ICP_CONTRACT_INVALID')`.

2. **Cálculo do budget de queries por segmento:** o budget Tavily total é distribuído entre segmentos proporcionalmente ao seu peso no `icp_contract.segment_priority_weights`. Segmentos sem peso declarado recebem distribuição uniforme. Fórmula: `budget_seg_k = floor(budget_total × w_k / Σw_j)`. O cálculo garante que a soma dos budgets parciais não excede o budget total (arredondamento floor + verificação de resto).

3. **Seleção de fontes por segmento:** com base no `target_segments[]` do contrato, o planner seleciona quais scrapers são relevantes:
   - Advocacia Corporativa: LinkedIn (prioridade alta), Instagram (prioridade média), CNPJ.ws (para validação de razão social)
   - Consultorias Financeiras: LinkedIn (prioridade alta), Instagram (prioridade média), Tavily (para notícias e eventos setoriais)
   - Software Houses/SaaS: Instagram (prioridade alta), LinkedIn (prioridade alta), Tavily (para vagas e anúncios)
   - Engenharia: LinkedIn (prioridade alta), CNPJ.ws (prioridade alta para CAE/CNAE), Instagram (prioridade baixa)

4. **Parametrização de âncoras:** identifica perfis âncora do segmento (contas de referência conhecidas no ICP) que serão usados na Fase 1 para detecção de comentadores e seguidores mútuos.

5. **Verificação do DSS (Discovery Saturation Score):** se `DSS(W=50) < 0.05`, o planner emite alerta de saturação de descoberta e recomenda Delta Search em vez de full cycle. Não bloqueia a execução, mas registra `dss_saturation_warning=True` no estado.

**Outputs (delta do AgentState):**
```python
{
    "icp_contract": IcpContract,              # Contrato carregado e validado
    "query_budget_by_segment": Dict[str, int],# Budget Tavily por segmento
    "source_priority_map": Dict[str, List[str]], # Segmento -> [fonte1, fonte2, ...]
    "anchor_profiles": List[AnchorProfile],   # Perfis âncora por segmento
    "dss_saturation_warning": bool
}
```

**Estado do LangGraph mutado:** `icp_contract`, `query_budget_by_segment`, `source_priority_map`, `anchor_profiles`, `dss_saturation_warning`.

**Critério de transição de borda condicional:**
- `ICP_VALID -> node_seed_ingestion` (padrão)
- `ICP_INVALID -> node_abort_cycle` (emite `CycleError` e encerra)

---

### 2.2 Fase 1 — Seed Ingestion & Anchor Profiling

**Objetivo:** Normalizar a seed list recebida, construir os registros de entidade iniciais e identificar perfis âncora válidos por setor para uso como referência de comparação comportamental.

**Inputs do AgentState:**
- `seed_list` — lista bruta de seeds (pode conter nomes, handles Instagram, URLs LinkedIn, CNPJs)
- `icp_contract` — contrato validado com `target_segments[]` e `anchor_profiles` do planner
- `anchor_profiles` — lista de perfis âncora do planner

**Processamento:**

1. **Normalização da seed list:** cada seed é classificado por tipo:
   - Handle Instagram (`@username` ou `instagram.com/username`): extrai handle, cria `EntityRecord` com `primary_source='instagram'`
   - URL LinkedIn (`linkedin.com/in/` ou `linkedin.com/company/`): extrai slug, cria `EntityRecord` com `primary_source='linkedin'`
   - CNPJ (14 dígitos numéricos, formatados ou não): normaliza para 14 dígitos, cria `EntityRecord` com `primary_source='cnpj'`
   - Nome de empresa (texto livre): cria `EntityRecord` com `primary_source='name_only'`, requer resolução posterior

2. **Construção dos EntityRecords iniciais:** cada `EntityRecord` recebe:
   - `entity_id`: UUID v4 gerado no momento da ingestão
   - `seed_raw`: valor original da seed antes de normalização
   - `seed_type`: INSTAGRAM_HANDLE | LINKEDIN_URL | CNPJ | NAME_ONLY
   - `created_at`: timestamp do ciclo
   - `subjective_logic`: tripla omega inicial `(b=0.0, d=0.0, u=1.0)` — incerteza máxima, nenhum dado ainda
   - `operating_segment`: segmento inferido do contrato ICP (se houver apenas um segmento, atribui automaticamente; se houver múltiplos, deixa `null` até a resolução de entidade)

3. **Seleção e validação de perfis âncora:** para cada segmento no `icp_contract.target_segments[]`, o sistema verifica se há pelo menos 1 perfil âncora configurado. Perfis âncora sem handle Instagram válido ou sem URL LinkedIn válida são descartados e registrados como `AnchorWarning` no `v_cognitive_log`.

4. **Deduplicação prévia de seeds:** antes de criar `EntityRecord`s, compara cada seed contra seeds já existentes no ciclo usando Jaro-Winkler normalizado (`threshold = 0.92` para dedup de seeds). Seeds duplicadas dentro da mesma seed list são colapsadas em um único `EntityRecord` com `duplicate_seeds` listados.

**Outputs (delta do AgentState):**
```python
{
    "entities": List[EntityRecord],          # Registros iniciais normalizados
    "validated_anchors": List[AnchorProfile],# Âncoras validados por segmento
    "seed_ingestion_warnings": List[str]     # Avisos de âncoras inválidos, duplicatas
}
```

**Estado do LangGraph mutado:** `entities`, `validated_anchors`, `seed_ingestion_warnings`.

**Critério de transição de borda condicional:**
- `SEEDS_VALID (len(entities) > 0) -> node_sensory_scraping` (padrão)
- `SEEDS_EMPTY (len(entities) == 0) -> node_abort_cycle` (nada a processar)

---

### 2.3 Fase 2 — Sensory Scraping (Coleta Assíncrona Multi-Canal)

**Objetivo:** Coletar evidências brutas de todas as fontes configuradas para cada `EntityRecord`, de forma paralela e assíncrona, com gestão de falhas por fonte e modo degradado.

**Inputs do AgentState:**
- `entities` — lista de `EntityRecord`s com seeds normalizadas
- `validated_anchors` — perfis âncora validados para detecção de interações
- `source_priority_map` — fontes prioritárias por segmento
- `query_budget_by_segment` — budget Tavily disponível por segmento
- `operating_mode` — modo operacional atual (afeta comportamento dos scrapers)

**Processamento:**

O scraping é executado como um conjunto de corrotinas Python assíncronas (`asyncio.gather`), uma por fonte, com limite de concorrência configurável (`max_concurrency_per_source`). As fontes operam em paralelo independente:

**2.3.1 Instagram Scraper**

Para cada `EntityRecord` com `seed_type == INSTAGRAM_HANDLE`:
- Coleta de perfil: `biography`, `external_url`, `bio_links[]`, `follower_count`, `following_count`, `is_business`, `business_category`
- Posts recentes (últimas 12 semanas): `caption`, `media_type`, `timestamp`, `like_count`, `comment_count`
- Comentários do lead em perfis âncora: varre `edge_media_to_comment` dos posts dos âncoras validados, buscando `user_id` do lead
- Likes do lead em posts âncora: varre `edge_liked_by` dos posts dos âncoras validados

Falhas:
- HTTP 429 (rate limit): aguarda `retry_after` + jitter aleatório, reintenta até 3 vezes. Após 3 falhas: `operating_mode = 'DEGRADED_INSTAGRAM'`, `u += 0.20` para todos os atributos do lead derivados de Instagram.
- HTTP 403 / CAPTCHA: desativa scraper Instagram imediatamente, ativa modo cache (`t_half = 12h` para evidências Instagram em cache).
- HTTP 5xx: retry com backoff exponencial (1s, 2s, 4s). Após 5 falhas consecutivas: modo DEGRADED.

**2.3.2 LinkedIn Scraper**

Para cada `EntityRecord` com `seed_type == LINKEDIN_URL`:
- Perfil pessoal: `title`, `current_company`, `start_date` (para calcular tempo de empresa), `location`, `about`
- Perfil da empresa (se URL de company): `company_size` (ENUM de ranges), `industry`, `description`, `founded_year`, `specialties`
- Posts recentes (últimas 12 semanas): `text`, `published_at`, `reaction_count`, `comment_count`
- Vagas ativas: `job_title`, `posted_at`, `seniority_level`, `department`

Falhas: mesma lógica de retry do Instagram com `operating_mode = 'DEGRADED_LINKEDIN'` e `u += 0.20` para atributos LinkedIn.

**2.3.3 CNPJ.ws Resolver**

Para cada `EntityRecord` com `seed_type == CNPJ` ou quando o CNPJ foi identificado no scraping de Instagram/LinkedIn:
- Dados cadastrais: `razao_social`, `nome_fantasia`, `cnae_fiscal` (código + descrição), `cnae_secundarios[]`, `municipio`, `uf`, `capital_social`, `porte` (MEI/ME/EPP/etc.), `situacao_cadastral`, `data_abertura`, `socios[]`

Falha (timeout ou 5xx): `SRS_cnpj_resolver = 0.0` para o ciclo; `lambda_CNAE = 1.0` (neutro, não penaliza RCS); registrado no `v_cognitive_log`.

**2.3.4 Tavily API (Web Search — Complemento)**

Para leads onde as fontes primárias retornam evidências insuficientes (Fit < 0.30 após Instagram/LinkedIn) ou para coleta de eventos setoriais (vagas em sites de emprego, notícias, prêmios):
- Queries construídas com base no `keyword_taxonomy.pain_keywords[]` do ICP + nome da empresa
- Budget gerenciado por `query_budget_by_segment`
- Resultados armazenados como `RawEvidence` com `source_type='tavily_web'` e `SRS` default de 0.60

FinOps Stopping Rule aplicada antes de cada query Tavily: `EIG(S_k)/MIC(S_k) < tau_FinOps (0.15)` — se a query candidata não tem expected information gain suficiente em relação ao custo marginal, é descartada.

**Outputs (delta do AgentState):**
```python
{
    "raw_evidence_pool": List[RawEvidence],  # Todas as evidências brutas coletadas
    "operating_mode": str,                   # Atualizado se scraper falhou
    "finops_budget_remaining": int,          # Budget atualizado após queries Tavily
    "scraping_errors": List[ErrorRecord]     # Erros por fonte com severidade
}
```

**Estado do LangGraph mutado:** `raw_evidence_pool`, `operating_mode`, `finops_budget_remaining`, `scraping_errors`.

**Critério de transição de borda condicional:**
- `EVIDENCE_COLLECTED (len(raw_evidence_pool) > 0) -> node_normalize` (padrão)
- `CACHE_ONLY_MODE -> node_load_cache` (carrega evidências do ciclo anterior)
- `EVIDENCE_EMPTY -> node_abort_lead` (lead específico, não o ciclo inteiro)

---

### 2.4 Fase 3 — Evidence Normalization & Deduplication

**Objetivo:** Normalizar todas as evidências brutas para schema canônico, deduplicar por hash de conteúdo e construir a camada de evidências Layer 1 (append-only).

**Inputs do AgentState:**
- `raw_evidence_pool` — evidências brutas da Fase 2

**Processamento:**

1. **Normalização para schema canônico:** cada `RawEvidence` é transformada em `NormalizedEvidence`:
   - `evidence_id`: UUID v4 gerado no momento da normalização
   - `entity_id`: ID da entidade à qual a evidência pertence
   - `source_type`: INSTAGRAM_POST | INSTAGRAM_COMMENT | INSTAGRAM_LIKE | LINKEDIN_POST | LINKEDIN_JOB | CNPJ_CADASTRAL | TAVILY_WEB
   - `content_text`: texto da evidência (caption, bio, post, etc.) normalizado: strip, lowercase, remoção de caracteres de controle, unicode -> UTF-8
   - `collected_at`: timestamp de coleta (do scraper)
   - `evidence_timestamp`: timestamp do conteúdo original (data do post, data do cadastro, etc.)
   - `SRS_k`: Source Reliability Score do scraper que coletou
   - `e_fresh`: calculado via `E_fresh(delta_t)` com `delta_t = now - evidence_timestamp` e `t_half` específico do `source_type`

2. **Deduplicação por SHA-256:** para cada evidência normalizada, computa `SHA-256(entity_id + source_type + content_text)`. Se o hash já existe no `evidence_hash_set` do ciclo, a evidência é descartada (dedup exato). Isso previne dupla-contagem de evidências iguais coletadas por fontes diferentes.

3. **Append-only Layer 1:** evidências aprovadas pela dedup são inseridas no `raw_evidence_pool` normalizado. A Layer 1 é append-only: evidências nunca são deletadas, apenas marcadas com `is_superseded=True` quando uma versão mais recente é coletada.

4. **Cálculo de `E_fresh` por evidência:** aplicado imediatamente após normalização usando a tabela de meia-vidas por `source_type` (ver SDD-02 §7). Evidências com `e_fresh < 0.05` são marcadas com `is_stale=True` e não contribuem para scores (mas permanecem no pool para rastreabilidade).

**Outputs (delta do AgentState):**
```python
{
    "normalized_evidence_pool": List[NormalizedEvidence],  # Layer 1 normalizada e deduplicada
    "evidence_hash_set": Set[str],                         # SHA-256 hashes para dedup futura
    "stale_evidence_count": int,                           # Evidências marcadas como stale
    "dedup_discarded_count": int                           # Evidências descartadas por dedup
}
```

**Estado do LangGraph mutado:** `normalized_evidence_pool`, `evidence_hash_set`, `stale_evidence_count`, `dedup_discarded_count`.

**Critério de transição de borda condicional:**
- `NORMALIZED_OK -> node_entity_resolution` (padrão)
- Não há borda de falha nesta fase — evidências inválidas são descartadas individualmente com log.

---

### 2.5 Fase 4 — Entity Resolution

**Objetivo:** Determinar se múltiplos `EntityRecord`s distintos na seed list representam a mesma entidade real do mundo físico. Fusionar registros confirmados (auto-merge) e sinalizar candidatos para revisão manual.

**Inputs do AgentState:**
- `entities` — lista de `EntityRecord`s da Fase 1
- `normalized_evidence_pool` — evidências normalizadas, que podem revelar cross-references

**Processamento:**

1. **Extração de atributos de resolução:** para cada `EntityRecord`, coleta os valores disponíveis de:
   - `nome_fantasia` (do CNPJ.ws ou declarado em bio)
   - `razao_social` (do CNPJ.ws)
   - `instagram_handle`
   - `linkedin_slug`
   - `municipio` + `uf` (localização)
   - `cnae_fiscal` (código CNAE primário)

2. **Comparação par-a-par:** para cada par de `EntityRecord`s `(A, B)`:
   - Computa `RCS = JaroWinkler(normalize(name_A), normalize(name_B)) × lambda_spatial × lambda_CNAE`
   - `lambda_spatial`: penalizador espacial baseado na concordância de municípios/estados
   - `lambda_CNAE`: penalizador de atividade econômica baseado na concordância de código CNAE

3. **Decisão de fusão por threshold:**
   - `RCS >= 0.82`: Auto-merge — os dois registros são fundidos em um único `EntityRecord`. O registro resultante herda o `entity_id` do mais antigo, preserva o `entity_id` do mais novo como `merged_from[]`, e a tripla omega resultante é calculada pelo Consensus Operator da Subjective Logic.
   - `0.65 <= RCS < 0.82`: `MERGE_CANDIDATE` — registrado no `conflict_resolution_log` com `resolution_method='MANUAL_REVIEW'`. O par permanece como dois `EntityRecord`s separados, mas com `merge_candidate_partner_id` apontando um para o outro.
   - `RCS < 0.65`: entidades distintas — nenhuma ação.
   - Modo degradado (scraper Instagram down): threshold sobe para `RCS >= 0.90` (conservador — só funde com altíssima certeza).

4. **Propagação de atributos na fusão:** quando dois registros são fundidos, os atributos do registro com maior `SRS` são adotados como `authoritative_value`. Divergências acima do `delta_tolerance = 0.30` são tratadas pelo Conflict Resolution Policy, elevando `u` na tripla omega do atributo divergente.

5. **Atualização das referências de evidência:** todas as `NormalizedEvidence` do registro fundido (`merged_from`) têm `entity_id` atualizado para o `entity_id` canonical do registro resultante.

**Outputs (delta do AgentState):**
```python
{
    "entities": List[EntityRecord],              # Lista atualizada com fusões aplicadas
    "merge_log": List[MergeEvent],               # Log de fusões com RCS e método
    "manual_review_candidates": List[MergePair]  # Pares para revisão manual
}
```

**Estado do LangGraph mutado:** `entities` (atualizado com fusões), `merge_log`, `manual_review_candidates`.

**Critério de transição de borda condicional:**
- `RESOLUTION_COMPLETE -> node_inference_generation` (padrão, sempre)

---

### 2.6 Fase 5 — Inference Generation

**Objetivo:** Traduzir evidências brutas normalizadas (Layer 1) em inferências semânticas estruturadas (Layer 2), atribuindo a cada inferência uma tripla omega de Subjective Logic, o `hypothesis_linked` e a `pain_taxonomy_key`.

**Inputs do AgentState:**
- `normalized_evidence_pool` — Layer 1 completa
- `icp_contract` — para acesso ao `keyword_taxonomy.pain_keywords[]` e `sector_taxonomy`
- `entities` — para context de segmento por entidade

**Processamento:**

1. **Classificação de evidência por tipo de sinal:** cada `NormalizedEvidence` é classificada em:
   - `PAIN_SIGNAL`: contém keywords de dor do `icp_contract.keyword_taxonomy.pain_keywords[]`
   - `INTENT_SIGNAL`: vagas ativas sinalizadoras, posts sobre processo de seleção, menções a crescimento
   - `CAPACITY_SIGNAL`: menções a ferramentas, metodologias, processos internos
   - `CONTEXT_SIGNAL`: dados cadastrais, porte, CNAE, tempo de empresa
   - `SOCIAL_PROOF_SIGNAL`: comentários em âncoras, likes em âncoras, seguidores mútuos

2. **Geração de inferências por padrão:** regras baseadas em padrões (pattern matching + regex semântico) sobre o `content_text`:
   - Pattern "estamos em fase de estruturação" -> `Inference(pain_key='INTERNAL_CHAOS', hypothesis_linked='H2', omega=(b=0.65, d=0.10, u=0.25))`
   - Pattern "crescendo muito rápido" -> `Inference(pain_key='GROWTH_STRUCTURE_GAP', hypothesis_linked='H1', omega=(b=0.60, d=0.05, u=0.35))`
   - Pattern "envolvida nos projetos" -> `Inference(pain_key='DELEGATION_INCAPACITY', hypothesis_linked='H2', omega=(b=0.70, d=0.05, u=0.25))`
   - Pattern "preciso organizar melhor meu tempo" -> `Inference(pain_key='STRATEGIC_VS_OPERATIONAL', hypothesis_linked='H10', omega=(b=0.75, d=0.05, u=0.20))`
   - Pattern "montando um time incrível" -> `Inference(pain_key='HIRING_WITHOUT_PROCESS', hypothesis_linked='H3', omega=(b=0.55, d=0.10, u=0.35))`
   - Pattern "quero implementar IA" -> `Inference(pain_key='AI_READINESS_GAP', hypothesis_linked='H4', omega=(b=0.50, d=0.05, u=0.45))`
   - Vaga ativa para coordenador/gerente/supervisor -> `Inference(pain_key='LEADERSHIP_GAP', hypothesis_linked='H3', omega=(b=0.65, d=0.05, u=0.30))`
   - Vaga ativa para comercial/vendas/BDR -> `Inference(pain_key='SALES_PRESSURE', hypothesis_linked='H8', omega=(b=0.60, d=0.10, u=0.30))`

3. **Herança de `e_fresh`:** cada `Inference` herda o `e_fresh` da `NormalizedEvidence` que a originou. Inferências derivadas de evidências stale (`e_fresh < 0.10`) têm `b` multiplicado por `e_fresh` (decay de crença proporcional ao decay temporal).

4. **Acumulação de triplas omega por lead:** quando múltiplas evidências ativam o mesmo `pain_key` para o mesmo lead, as triplas omega são fundidas via Consensus Operator:
   ```
   b_fused = (b_A × u_B + b_B × u_A) / (u_A + u_B - u_A × u_B)
   d_fused = (d_A × u_B + d_B × u_A) / (u_A + u_B - u_A × u_B)
   u_fused = (u_A × u_B) / (u_A + u_B - u_A × u_B)
   ```

**Outputs (delta do AgentState):**
```python
{
    "semantic_inference_pool": List[Inference],       # Layer 2: inferências semânticas
    "pain_signal_counts": Dict[str, Dict[str, int]]   # entity_id -> pain_key -> count
}
```

**Estado do LangGraph mutado:** `semantic_inference_pool`, `pain_signal_counts`.

**Critério de transição de borda condicional:**
- `INFERENCES_GENERATED -> node_bayesian_update` (padrão, sempre)

---

### 2.7 Fase 6 — Bayesian Hypothesis Update

**Objetivo:** Atualizar os posteriors `P(H|E)` das 15 hipóteses de negócio (H1–H15) para cada lead, com base no conjunto de inferências geradas na Fase 5.

**Inputs do AgentState:**
- `semantic_inference_pool` — Layer 2 de inferências
- `entities` — para acesso ao segmento de cada lead

**Processamento:**

**6.1 Priors iniciais por hipótese:**

| Hipótese | Descrição | P_0 (Prior) |
|---|---|---|
| H1 | Expansão Operacional | 0.25 |
| H2 | Centralização Excessiva | 0.30 |
| H3 | Gargalo de Liderança Intermediária | 0.20 |
| H4 | Necessidade de Automação | 0.15 |
| H5 | Busca por Eficiência | 0.10 |
| H6 | Pré-Contratação Transformacional | 0.12 |
| H7 | Crise de Retenção | 0.10 |
| H8 | Pressão de Vendas | 0.18 |
| H9 | Transição de Modelo | 0.08 |
| H10 | Sobrecarga do Fundador | 0.22 |
| H11 | Dor de Qualidade de Entrega | 0.12 |
| H12 | Expansão Geográfica | 0.10 |
| H13 | Pressão Regulatória | 0.08 |
| H14 | Sócio Novo/Reestruturação | 0.07 |
| H15 | Dor de Visibilidade/Marca | 0.15 |

**6.2 Atualização Bayesiana:** para cada lead e cada hipótese ativa:

```
P(H_k | E_1, ..., E_n) proporcional a P(H_k) × produtório P(E_i | H_k)
```

Onde `P(E_i | H_k)` é a verossimilhança da evidência `E_i` dado que a hipótese `H_k` é verdadeira. Esta verossimilhança é parametrizada no `icp_contract.hypothesis_likelihood_matrix` (configurável) com defaults da engenharia. A crença `b` da tripla omega da inferência é usada como proxy de `P(E_i | H_k)` quando a verossimilhança explícita não está configurada.

**6.3 Normalização dos posteriors:** após a atualização, os posteriors são normalizados para que `Σ P(H_k | E) = 1` sobre todas as hipóteses ativas.

**6.4 Seleção da hipótese dominante:** a hipótese com maior posterior é marcada como `status='ACTIVE'` e `is_dominant=True`. Seu `b` da tripla omega é usado como `Hypothesis_Confidence` no C_score.

**6.5 Hipóteses contraditórias:** se a evidência atualiza o prior de uma hipótese para baixo (evidência contradizendo), isso se reflete no `d` da tripla omega da hipótese correspondente.

**Outputs (delta do AgentState):**
```python
{
    "hypothesis_posteriors": Dict[str, Dict[str, float]],  # entity_id -> hypothesis_id -> P(H|E)
    "dominant_hypothesis_per_entity": Dict[str, str],       # entity_id -> hypothesis_id dominante
    "hypothesis_confidence_per_entity": Dict[str, float]    # entity_id -> b da hipótese dominante
}
```

**Estado do LangGraph mutado:** `hypothesis_posteriors`, `dominant_hypothesis_per_entity`, `hypothesis_confidence_per_entity`.

**Critério de transição de borda condicional:**
- `POSTERIORS_UPDATED -> node_committee_mapping` (padrão, sempre)

---

### 2.8 Fase 7 — Committee Mapping

**Objetivo:** Mapear os perfis de pessoas identificadas nas evidências coletadas, diferenciando os papéis de S_persona (Stakeholder Persona — influenciador técnico/operacional) e BMO (Buying Motion Owner — agente real de decisão de mudança), e identificar trigger events comportamentais.

**Inputs do AgentState:**
- `semantic_inference_pool` — inferências com menções a pessoas
- `normalized_evidence_pool` — evidências brutas com atributos de pessoas
- `entities` — entidades consolidadas com segmento

**Processamento:**

**7.1 Identificação de pessoas mencionadas:** extração de nomes, cargos e papéis a partir de:
- Posts LinkedIn que mencionam colegas, sócios, contratações
- Posts Instagram que mencionam equipe
- Dados de sócios do CNPJ.ws
- Vagas ativas (inferem hierarquia de reporte)

**7.2 Classificação S_persona vs. BMO:**

`S_persona` (Stakeholder Persona — influenciador técnico/operacional):
- Não toma a decisão final de compra
- Executa critérios técnicos e operacionais
- Sinais: cargo operacional, posts sobre processo, linguagem de execução
- Em Advocacia: sócia-adjunta, advogada sênior
- Em Consultorias: gerente de projetos, coordenadora
- Em SaaS: CTO, head de produto
- Em Engenharia: engenheiro(a) sênior de projetos

`BMO` (Buying Motion Owner):
- Agente real da decisão de mudança organizacional
- Identifica o problema como sistêmico e tem autoridade para contratar solução
- Sinais comportamentais: posts sobre estratégia, visão de futuro, frustração com status quo, linguagem de liderança e identidade de fundadora
- Critério primário: fundadora/CEO com características do ICP (mulher, 3-10 anos de empresa, segmento alvo)
- Critério de desempate: quem posta publicamente sobre dor organizacional em primeira pessoa é o BMO

**7.3 Scoring de BMO Momentum:**

```
bmo_momentum_score = (post_frequency_pain × 0.40) + (recency_score × 0.35) + (engagement_score × 0.25)
```
Onde:
- `post_frequency_pain` = número de posts com pain_signal nas últimas 4 semanas / 4
- `recency_score` = `e_fresh` do post de pain_signal mais recente
- `engagement_score` = (likes + comentários) do post de pain_signal mais relevante, normalizado pelo benchmark do segmento

**7.4 Trigger Events:** eventos comportamentais que elevam a urgência de abordagem:
- Vaga de liderança intermediária ativa (H3 confirmada)
- Post público sobre frustração operacional (BMO momentum alto)
- Contratação recente de sócio(a) (H14)
- Menção a expansão de cidade/estado (H12)
- Post sobre mudança de modelo de negócio (H9)

**7.5 Uncertainty_Committee:** calculado como:
```
Uncertainty_Committee = u_bar_members + (1 - S_committee_Completeness) × 0.30
```
Onde:
- `u_bar_members` = média das `u` das triplas omega de cada membro identificado
- `S_committee_Completeness` = n_identified / n_expected_roles
- `n_expected_roles` = número de papéis esperados no comitê de compra do segmento (configurado no `icp_contract`)
- `Uncertainty_Committee` é truncado em `min(1.0)`

**Outputs (delta do AgentState):**
```python
{
    "committee_maps": Dict[str, CommitteeMap],        # entity_id -> mapa do comitê
    "bmo_candidates": Dict[str, List[Person]],        # entity_id -> candidatos a BMO ordenados
    "trigger_events": Dict[str, List[TriggerEvent]],  # entity_id -> trigger events detectados
    "uncertainty_committee": Dict[str, float]         # entity_id -> Uncertainty_Committee
}
```

**Estado do LangGraph mutado:** `committee_maps`, `bmo_candidates`, `trigger_events`, `uncertainty_committee`.

**Critério de transição de borda condicional:**
- `COMMITTEE_MAPPED -> node_score_computation` (padrão, sempre)

---

### 2.9 Fase 8 — Score Computation

**Objetivo:** Calcular os scores O_score, C_score e P_score para cada entidade qualificada, aplicando as fórmulas matemáticas completas documentadas no SDD-02.

**Inputs do AgentState:**
- `entities` — entidades com todos os atributos e triplas omega
- `semantic_inference_pool` — para cálculo de `S_intent` e `pain_affinity`
- `hypothesis_confidence_per_entity` — `Hypothesis_Confidence` por entidade
- `uncertainty_committee` — `Uncertainty_Committee` por entidade
- `bmo_candidates` — para `bmo_momentum_score`
- `icp_contract` — para pesos e centroide ICP

**Processamento:**

**8.1 Cálculo do Fit Score:** constrói o vetor de empresa `[seg, size_norm, rev_norm, centralization, maturity_proc, pain_affinity]` e computa similaridade cosseno ponderada com o vetor ICP do contrato. Detalhes completos em SDD-02 §3.

**8.2 Cálculo do S_intent:** média ponderada de:
- `post_frequency_pain`: proporção de posts com pain_signal nas últimas 4 semanas
- `job_signal_score`: presença de vagas sinalizadoras (booleano, ponderado por relevância da vaga)
- `anchor_engagement_score`: frequência de interação com posts de âncoras do segmento

**8.3 Cálculo do Reachability_Hybrid:**
```
Reachability = R_interactions × 0.40 + R_mutual_followers × 0.35 + R_org_proximity × 0.25
```
Onde:
- `R_interactions` = comentários + likes em perfis âncora (normalizado por benchmark do segmento)
- `R_mutual_followers` = número de seguidores em comum com âncoras (normalizado)
- `R_org_proximity` = distância organizacional via grafo de relacionamentos (1.0 = conexão direta, 0.0 = sem conexão)

**8.4 Cálculo do E_fresh:** `e_fresh` da evidência mais recente do lead que é não-stale.

**8.5 Cálculo do O_score:**
```
O_score = (0.45 × Fit + 0.35 × S_intent + 0.20 × Reachability_Hybrid) × E_fresh
```

**8.6 Cálculo do RCS:** computa Jaro-Winkler entre nome normalizado do lead e nome canônico da entidade, aplica `lambda_spatial` e `lambda_CNAE`. Detalhes completos em SDD-02 §6.

**8.7 Cálculo do C_s (Entropia de Shannon):** calcula distribuição de SQS por provedor e computa `C_s = 1 - H/H_max`. Detalhes completos em SDD-02 §5.

**8.8 Cálculo do C_score:**
```
C_score = RCS × C_s × (1 - Uncertainty_Committee) × Hypothesis_Confidence × produtório SRS_k
```

**8.9 Cálculo do P_score:**
```
P_score = O_score × (1 - 0.60 × e^(-4.0 × C_score))
```

**8.10 Classificação por quadrante:**
- Alto-O (>=0.70) / Alto-C (>=0.70): `QUALIFIED — PRIORITY ACTION`
- Alto-O (>=0.70) / Baixo-C (<0.35): `INVESTIGATION OPPORTUNITY` (emite `InvestigationOpportunity` event)
- Baixo-O (<0.40) / Alto-C (>=0.70): `DELTA SEARCH` se P>=0.25, `PRUNED` se P<0.25
- Baixo-O / Baixo-C: `DISQUALIFIED — PRUNED`

**Outputs (delta do AgentState):**
```python
{
    "o_scores": Dict[str, float],              # entity_id -> O_score
    "c_scores": Dict[str, float],              # entity_id -> C_score
    "p_scores": Dict[str, float],              # entity_id -> P_score
    "quadrant_classifications": Dict[str, str] # entity_id -> classificação de quadrante
}
```

**Estado do LangGraph mutado:** `o_scores`, `c_scores`, `p_scores`, `quadrant_classifications`.

**Critério de transição de borda condicional:**
- `SCORES_COMPUTED -> node_xai_assembly` (padrão, sempre)

---

### 2.10 Fase 9 — XAI Payload Assembly (Conversation Blueprint)

**Objetivo:** Gerar o payload de Explainable AI para cada lead qualificado, incluindo o Conversation Blueprint com as 5 saídas estruturadas: Hook, Context Trigger, Pain Narrative, Credibility Anchor e CTA Suggestion.

**Inputs do AgentState:**
- `entities` — entidades com todos os atributos
- `o_scores`, `c_scores`, `p_scores` — scores computados
- `hypothesis_posteriors` — posteriors das 15 hipóteses
- `semantic_inference_pool` — inferências com pain signals
- `trigger_events` — trigger events detectados
- `committee_maps`, `bmo_candidates` — para personalização por BMO

**Processamento:**

**9.1 Drivers Positivos do P_score (XAI):** identifica as 3 inferências com maior contribuição positiva ao P_score usando decomposição aditiva aproximada: para cada evidência, calcula `P_score_with - P_score_without`. As 3 inferências com maior delta positivo são listadas como `top_positive_drivers`.

**9.2 Drivers Negativos do P_score (XAI):** identifica os 3 fatores com maior contribuição negativa:
- Alta `Uncertainty_Committee` (C_score baixo)
- Baixo `e_fresh` (evidências stale)
- `SRS_k` baixo de fonte crítica
- Listados como `top_negative_drivers` com magnitude e recomendação de coleta adicional

**9.3 Missing Evidence:** lista estruturada de evidências ausentes que elevariam o P_score se coletadas. Calculado como: para cada dimensão com `u > 0.50`, estima o delta de P_score se `u` fosse reduzido para 0.20. Ordenada por potencial de melhoria do P_score.

**9.4 Conversation Blueprint — 5 saídas estruturadas:**

**Hook:** frase de abertura personalizada que demonstra conhecimento contextual sem revelar que foi pesquisado. Template: "Vi que vocês [observação_contextual_específica] — isso me fez pensar em [conexão_com_dor]". Preenchido com a evidência de pain_signal mais recente e de maior crença `b`.

**Context Trigger:** evento ou sinal específico que justifica a abordagem neste momento. Derivado do `trigger_event` de maior relevância (vaga ativa, post recente de dor, aniversário de empresa).

**Pain Narrative:** narrativa da dor hipotética em primeira pessoa, escrita na linguagem do setor do lead. Baseada na hipótese dominante (maior posterior) e no vocabulário setorial (ver Seção 3). Nunca usa termos proibidos pelo setor.

**Credibility Anchor:** prova social ou referência de autoridade relevante para o segmento. Conecta a dor identificada com um resultado concreto ou evidência de expertise. Parametrizado no `icp_contract.credibility_anchors_by_segment`.

**CTA Suggestion:** chamada para ação calibrada para a fase do funil:
- Lead em INVESTIGATION (C_score baixo): CTA de conteúdo (artigo, diagnóstico gratuito)
- Lead em PRIORITY ACTION (P_score alto): CTA de conversa direta (call de 30 minutos)

**Outputs (delta do AgentState):**
```python
{
    "xai_payloads": Dict[str, XAIPayload],                   # entity_id -> payload XAI completo
    "conversation_blueprints": Dict[str, ConversationBlueprint]  # entity_id -> blueprint
}
```

**Estado do LangGraph mutado:** `xai_payloads`, `conversation_blueprints`.

**Critério de transição de borda condicional:**
- `XAI_ASSEMBLED -> node_prioritization` (padrão, sempre)

---

### 2.11 Fase 10 — Prospect Prioritization & Delta Search

**Objetivo:** Ordenar todos os leads qualificados pelo ranking determinístico P_score (com regras de desempate em 5 níveis), emitir os payloads finais e identificar quais entidades devem entrar no modo Delta Search.

**Inputs do AgentState:**
- `p_scores`, `o_scores`, `c_scores` — scores completos
- `entities` — para acesso a `bmo_momentum_score` e `entity_id`
- `quadrant_classifications` — para filtro de leads a emitir
- `xai_payloads`, `conversation_blueprints` — payloads a emitir

**Processamento:**

**10.1 Filtro de elegibilidade para emissão:**
- Leads `DISQUALIFIED — PRUNED` (P < 0.25 e O < 0.40): não emitidos. Registrados no log com motivo de pruning.
- Leads `INVESTIGATION OPPORTUNITY` (O>=0.70, C<0.35, P>=0.30): emitidos com `data_quality_flag='LOW'` e recomendação de coleta adicional.
- Leads `DELTA SEARCH` (0.25 <= P < 0.45): emitidos com flag `delta_search_recommended=True`.
- Leads `PRIORITY ACTION` (P>=0.65): emitidos com prioridade máxima.

**10.2 Ordenação determinística em 5 níveis de desempate:**
```sql
ORDER BY
    p_score DESC,
    o_score DESC,
    c_score DESC,
    feat_e_fresh DESC,
    bmo_momentum_score DESC,
    entity_id ASC  -- UUID ASC como tiebreaker final determinístico
```

**10.3 Delta Search — Identificação de entidades para re-enriquecimento:**

Delta Search é o modo de busca incremental para leads que já foram processados anteriormente mas precisam de evidências adicionais para elevar o C_score. Critérios de entrada no Delta Search:
- Lead com O_score alto (>=0.70) mas C_score baixo (<0.35): alta oportunidade, baixa certeza
- Idade do ciclo anterior > `t_refresh_threshold` (configurável, default 14 dias)
- Lead com `missing_evidence` crítico identificado no XAI Payload

**10.4 Atualização do DSS (Discovery Saturation Score):**
```
DSS(W) = |E_new(W)| / |E_total(W)|
```
Onde `W = 50` (janela das últimas 50 entidades processadas). `E_new` são evidências com `SRS_k > 0.50` e `e_fresh > 0.30` que não existiam no ciclo anterior. Se `DSS < 0.05`, o sistema está saturando.

**10.5 Emissão de payloads:** cada lead elegível recebe um `ProspectPayload` final:
```python
class ProspectPayload:
    entity_id: str
    rank_position: int
    p_score: float
    o_score: float
    c_score: float
    quadrant: str
    data_quality_flag: str           # OK | LOW | DEGRADED
    conversation_blueprint: ConversationBlueprint
    xai_summary: XAIPayload
    delta_search_recommended: bool
    trigger_events: List[TriggerEvent]
    bmo_name: str
    bmo_role: str
    bmo_platform: str                # INSTAGRAM | LINKEDIN
```

**Outputs (delta do AgentState):**
```python
{
    "ranked_prospects": List[ProspectPayload],  # Output final ordenado
    "pruned_entities": List[str],               # entity_ids prunados com motivo
    "delta_search_queue": List[str],            # entity_ids para próximo ciclo incremental
    "dss_current": float,                       # DSS do ciclo atual
    "cycle_complete": True                      # Sinaliza fim do ciclo
}
```

**Estado do LangGraph mutado:** `ranked_prospects`, `pruned_entities`, `delta_search_queue`, `dss_current`, `cycle_complete`.

**Critério de transição de borda condicional:**
- `CYCLE_COMPLETE -> END` (grafo termina, payloads disponíveis para consumo)

---

## SEÇÃO 3: TAXONOMIA LINGUÍSTICA DOS SETORES-CHAVE

### 3.1 Premissa Interpretativa

A taxonomia linguística não é um dicionário de palavras-chave para regex simples. É um sistema interpretativo formal que reconhece que as fundadoras dos 4 setores-alvo do ICP comunicam suas dores de forma indireta, codificada na linguagem profissional do seu setor. A dor real raramente é nomeada diretamente. Ela é expressa através de vocabulário de status, de conquista, de movimento estratégico — e é nessa superfície linguística que o sistema deve operar.

Três princípios regulam o uso desta taxonomia:
1. **Princípio da Evidência Linguística Direta:** o sinal de dor tem validade máxima quando aparece em primeira pessoa, em contexto público, sem mediação (post orgânico, bio, comentário).
2. **Princípio da Não-Exposição Pública de Fraqueza:** fundadoras de negócios de alto ticket raramente admitem fraqueza diretamente. O sistema interpreta o que é dito, não o que não é dito.
3. **Princípio da Congruência Setorial:** um termo que indica oportunidade em um setor pode ser neutro ou negativo em outro. O vocabulário deve ser interpretado sempre em contexto setorial.

---

### 3.2 Escritórios de Advocacia Corporativa

**Vocabulário natural do setor:**

Advogadas corporativas operam com o vocabulário de sua profissão como escudo de autoridade técnica. O negócio não é "empresa" — é "escritório", "sociedade" ou "banca". Os clientes não são "clientes" — são "assistidos", "mandantes" ou simplesmente o nome da empresa cliente. A gestão não é "operação" — é "administração do escritório". Não existe "funil de vendas" — existe "captação de clientela" ou "desenvolvimento de negócios".

**Padrões comportamentais codificados:**
- Preservação de autoridade técnica: posts sobre expertise jurídica, decisões recentes, publicações em portais do Direito
- Não expõem fraqueza publicamente: nunca postam sobre dificuldades de gestão; expressam desafios como "crescimento" ou "expansão"
- Linguagem de conquista: "inauguramos", "aprovamos", "fechamos o contrato", "formalizamos"
- Linguagem de equipe: "nosso time", "nossas advogadas", "a banca" — nunca "funcionários" ou "colaboradores"

**Termos que o sistema NUNCA deve usar ao construir o Conversation Blueprint:**
- "empresa" -> usar "escritório" ou "banca"
- "vender" -> usar "captar" ou "desenvolver negócios"
- "produto" -> não existe; o produto é o parecer, a representação, a assessoria
- "escalar" -> usar "expandir", "crescer", "ampliar a atuação"
- "funil de vendas" -> usar "pipeline de prospecção" ou simplesmente não usar

**Tabela formal de mapeamento linguístico — Advocacia Corporativa:**

| O que ela diz | Tradução semântica | Hipótese ativada |
|---|---|---|
| "Estamos expandindo a equipe jurídica" | Crescimento não acompanhado de estrutura de gestão — ela ainda supervisiona tudo diretamente | H1, H3 |
| "Sou responsável pelas negociações de maior complexidade" | Centralização total nos casos estratégicos — não consegue delegar o que exige seu nível técnico | H2, H10 |
| "Abrimos uma nova área de prática" | Estrutura operacional nova sem processo — novo serviço sendo improvado na execução | H1, H11 |
| "Estamos formatando nossos processos internos" | Caos de processo já reconhecido — em fase de estruturação (dor ativa e consciente) | H2, H5 |
| "Precisamos de mais agilidade nas entregas" | Gargalo de capacidade — equipe ou processo não acompanha o volume | H11, H5 |
| "Contratamos dois advogados sênior este mês" | Pré-contratação transformacional — crescimento iminente sem gestão de onboarding | H6, H3 |
| "Trabalhando em um caso de grande impacto" | Sobrecarga do fundador no operacional — founder no projeto mais complexo, não na gestão | H10, H2 |
| "Desenvolvendo novos frentes de atuação" | Transição de modelo — mudança de prática jurídica exige nova estrutura de suporte | H9, H1 |
| "Nosso time está crescendo e estou muito feliz" | Recrutamento em curso — potencial H6 ou H3 dependendo do nível das contratações | H6, H3 |
| "Assessorando empresas em processo de M&A" | Alta complexidade operacional — founder como único ponto de expertise crítica | H2, H10 |
| "Implementando novas ferramentas de gestão" | Percepção de deficiência processual — tentativa de automação sem base estruturada | H4, H5 |

---

### 3.3 Consultorias Empresariais e Financeiras

**Vocabulário natural do setor:**

Consultorias vivem da venda de método e inteligência. Seu vocabulário é deliberadamente técnico e estruturado porque é o produto que vendem. O negócio é "a consultoria" ou "o escritório". O trabalho é "projeto", "entrega", "escopo". O tempo é "horas faturáveis" ou "capacidade alocada". A qualidade é intrínseca ao método: "nossa metodologia", "nosso framework", "nossa abordagem estruturada".

**Padrões comportamentais codificados:**
- Linguagem de metodologia e rigor: nunca admitem improviso; o que outros chamariam de "caos" elas chamam de "ajuste de escopo" ou "projeto em andamento"
- Dor codificada em alocação de capacidade: "não tenho capacidade de atender novos clientes este mês" = centralização total na gestora sênior
- Posts sobre cases (sem citar clientes): prove expertise via resultado, não via processo interno
- Expressam sobrecarga como virtude: "agenda cheia" = sucesso; o sistema interpreta como gargalo

**Termos que o sistema NUNCA deve usar ao construir o Conversation Blueprint:**
- "gerenciar" (no sentido operacional simplista) -> usar "coordenar", "estruturar", "governar"
- "vender consultoria" -> usar "desenvolver negócios", "ampliar o portfólio de projetos"
- "organizar" (tom simplista) -> usar "estruturar", "sistematizar", "institucionalizar"

**Tabela formal de mapeamento linguístico — Consultorias:**

| O que ela diz | Tradução semântica | Hipótese ativada |
|---|---|---|
| "Estamos com a agenda cheia até o próximo trimestre" | Gargalo de capacidade — não consegue crescer sem entrar ela mesma nos projetos | H2, H10 |
| "Cada projeto exige minha presença nas reuniões-chave" | Centralização excessiva — o cliente compra a consultora sênior, não a equipe | H2, H10 |
| "Expandindo nossa equipe de consultores" | Pré-contratação transformacional — novo consultor sem processo de onboarding e desenvolvimento | H6, H3 |
| "Finalizando um projeto complexo de reestruturação" | Sobrecarga do founder no operacional mais difícil — não consegue delegar os projetos âncora | H10, H2 |
| "Trabalhando com governança corporativa" | Alta exigência de entrega — processos do cliente rigorosos evidenciam processo interno também deve ser | H5, H11 |
| "Desenvolvendo novos módulos de capacitação" | Transição de modelo — migração de consultoria para produto/treinamento requer nova estrutura | H9, H1 |
| "Sem mim o projeto perde qualidade" | Centralização extrema declarada — impossibilidade de escalar sem replicar a fundadora | H2, H10 |
| "Estruturando nossa área comercial" | Pressão de vendas — crescimento de demanda exigindo processo comercial que não existe | H8, H5 |
| "Implementando novos indicadores de performance" | Busca por eficiência — reconhece necessidade de métricas mas ainda não tem processo para alimentá-las | H5, H4 |
| "Atendendo a uma grande empresa do setor X" | Prestígio de cliente ancora — pode ocultar dor de operação enxuta sob pressão de entrega | H11, H2 |
| "Montando meu time de analistas" | Contratação sem processo de desenvolvimento — novo time sem estrutura de capacitação | H3, H6 |
| "Quero sistematizar nosso processo de entrega" | Reconhecimento de caos operacional — dor consciente de falta de processo escalável | H5, H2 |

---

### 3.4 Software Houses e Empresas SaaS

**Vocabulário natural do setor:**

O vocabulário de tech é o mais codificado dos quatro setores. A linguagem de produto e de desenvolvimento de software carrega nuances de prioridade estratégica versus execução operacional. O produto é o "software", o "sistema", o "app", a "plataforma". A empresa é "a startup", "o SaaS". O time é "o squad", "a equipe de engenharia". O trabalho é "sprint", "deploy", "feature", "backlog". A medição é "MRR", "churn", "CAC", "LTV".

**Padrões comportamentais codificados:**
- Founder técnico no produto vs. no estratégico: a tensão mais comum é a fundadora que ainda "entra no código" ou "participa de todos os sprints" — sinal de centralização técnica extrema
- IA como gatilho de timing de altíssima conversão: quando a fundadora posta sobre "implementar IA" ou "automatizar com IA", o sistema interpreta como pré-requisito de processo não cumprido (querer IA sem ter processo é a dor explícita)
- Linguagem de growth: "MRR crescendo", "base de clientes expandindo" — quando acompanhada de posts operacionais, indica que o crescimento não está sendo gerenciado estruturalmente

**Termos que o sistema NUNCA deve usar ao construir o Conversation Blueprint:**
- "organizar a empresa" -> usar "estruturar os processos de produto/engenharia"
- "gestão" (tom genérico) -> usar "Product Operations", "Engineering Management", "Founder Mode"
- "funil de vendas" -> usar "pipeline de conversão", "jornada de onboarding", "activation rate"

**Tabela formal de mapeamento linguístico — Software Houses/SaaS:**

| O que ela diz | Tradução semântica | Hipótese ativada |
|---|---|---|
| "Participando de todos os sprints da equipe" | Founder no operacional técnico — não consegue sair do papel de tech lead para o estratégico | H2, H10 |
| "Trabalhando no roadmap do próximo trimestre" | Centralização do produto na founder — ausência de Product Manager com autonomia | H2, H3 |
| "Expandindo o squad de desenvolvimento" | Contratação técnica sem processo de engenharia — crescimento sem Engineering Playbook | H1, H3 |
| "MRR crescendo consistentemente" | Crescimento sem estrutura de suporte — operação sob pressão de manutenção de qualidade | H1, H11 |
| "Implementando IA no nosso produto" | Pré-requisito de processo não cumprido — querer IA sem processo estruturado é a dor explícita | H4, H5 |
| "Reduzindo o churn este trimestre" | Crise de retenção — produto ou onboarding com problema estrutural | H7, H11 |
| "Lançando nova funcionalidade de X" | Founder no produto operacionalmente — ausência de delegação de decisão de produto | H2, H10 |
| "Estruturando nossa área de Customer Success" | Reconhecimento de gap de processo — crescimento forçando profissionalização do pós-venda | H7, H5 |
| "Montando um time incrível de vendas" | Pressão comercial — crescimento de base exige escala de vendas sem processo | H8, H3 |
| "Quero automatizar nossos processos internos" | Busca por automação antes de processo — não tem o que automatizar ainda (dor de eficiência) | H4, H5 |
| "Transicionando de agência para produto" | Mudança de modelo de negócio — reestruturação total da operação e do time | H9, H1 |
| "Deploy toda semana" | Alta cadência técnica — Founder ainda envolvida em decisões de release | H2, H10 |

---

### 3.5 Empresas de Engenharia

**Vocabulário natural do setor:**

Engenharia tem o vocabulário mais formal e regulado dos quatro setores. O trabalho é "projeto", "obra", "laudo", "ART" (Anotação de Responsabilidade Técnica). A empresa é "o escritório de engenharia", "a empresa de projetos", "a consultoria técnica". O produto é a "planta", o "projeto executivo", o "laudo técnico". A regulação é onipresente: CONFEA, CREA, NBR, ABNT.

**Padrões comportamentais codificados:**
- Centralização em torno do engenheiro sênior como único rosto técnico confiável: a fundadora é frequentemente a única com registro CREA válido para assinar projetos — isso cria uma centralização estrutural forçada pelo modelo regulatório
- Não expõem dificuldades de gestão: postam sobre projetos concluídos, laudos emitidos, obras entregues — nunca sobre gestão interna
- Linguagem de diligência e responsabilidade técnica: "assinamos o projeto", "emitimos o laudo", "aprovamos junto à prefeitura"
- A dor de centralização é sistêmica e regulatória: não é apenas estilo de gestão — é estrutura de responsabilidade legal que ancora tudo na engenheira sênior

**Termos que o sistema NUNCA deve usar ao construir o Conversation Blueprint:**
- "empresa" (tom genérico) -> usar "escritório de engenharia", "empresa de projetos"
- "vender projetos" -> usar "captar projetos", "desenvolver o portfólio de obras"
- "organizar" -> usar "estruturar os processos de gestão de projetos", "sistematizar o controle de obras"
- "IA" sem contexto técnico -> contextualizar em "gestão de projetos com IA", "análise de dados de obra"

**Tabela formal de mapeamento linguístico — Engenharia:**

| O que ela diz | Tradução semântica | Hipótese ativada |
|---|---|---|
| "Assinando todos os projetos da carteira" | Centralização estrutural forçada pelo CREA — único rosto técnico responsável, sem delegação possível sem outro engenheiro registrado | H2, H10 |
| "Expandindo para novas cidades" | Expansão geográfica sem estrutura de gestão remota de obras | H12, H1 |
| "Entregando três obras simultaneamente" | Sobrecarga de gestão de projetos em paralelo — founder como PM de todas as obras | H10, H11 |
| "Contratando um engenheiro sênior" | Pré-contratação transformacional — nova contratação técnica com peso regulatório | H6, H3 |
| "Emitindo laudos para construtoras" | Volume de laudos sem processo de controle de qualidade e rastreabilidade | H5, H11 |
| "Gestão de projetos na prática" | Reconhecimento de gap de processo — está gerenciando projetos de forma improvisada | H5, H2 |
| "Aprovação de projeto na prefeitura" | Burocracia regulatória consumindo tempo da engenheira sênior que deveria estar no estratégico | H10, H2 |
| "Ampliando o escopo de serviços" | Expansão de portfólio sem processo — novo serviço sem metodologia sistematizada | H9, H1 |
| "Fazendo diligência técnica em aquisição" | Projeto de alto valor e complexidade — founder como única responsável técnica | H2, H10 |
| "Crescemos muito em 2024" | Crescimento não estruturado — volume de projetos aumentou sem aumento proporcional de processo | H1, H11 |
| "Montando o time de projetos" | Contratação sem processo de onboarding técnico — novo time sem playbook de projetos | H3, H6 |
| "Implementando BIM nos projetos" | Adoção de tecnologia sem base de processo — BIM requer processo maduro para funcionar | H4, H5 |

---

## SEÇÃO 4: ARQUITETURA EVOLUTIVA — MATRIZ DE SEPARAÇÃO DE CAPACIDADES

### 4.1 Princípio de Separação

A arquitetura do SocialSelling é versionada em 4 estágios: MVP, V1, V2 e Arquitetura Alvo (Autônoma). Cada estágio é uma extensão aditiva do anterior — não uma reescrita. As tabelas do DDL do MVP são projetadas com colunas NULL-safe para V1/V2, garantindo que a migração de versão seja uma operação de preenchimento de dados, não de refatoração de schema.

### 4.2 Matriz Completa de Separação de Capacidades

| Dimensão | MVP | V1 | V2 | Arquitetura Alvo (Autônoma) |
|---|---|---|---|---|
| **Modelo de Estado** | Memória volátil (AgentState em RAM). Estado não persiste entre ciclos — cada ciclo reinicia do zero. Histórico mantido apenas nas tabelas do banco. | Persistência incremental: AgentState serializado ao final de cada ciclo para `cycle_state_archive`. Ciclo seguinte carrega estado anterior para Delta Search e re-scoring. | Aprendizado contínuo: estado de ciclo anterior alimenta ajuste de pesos via Gradient Descent. O AgentState passa a ter `weight_snapshot` por ciclo. | Sistema completamente autônomo: estado é uma representação contínua do espaço de oportunidade, não de ciclos discretos. Memória episódica e semântica integradas. |
| **Fonte de Dados** | Tavily API + Instagram scraper + LinkedIn scraper + CNPJ.ws. Buscas single-hop: uma query por lead, sem encadeamento de resultados. | Multi-hop database: resultados de uma busca alimentam queries subsequentes (Dijkstra/BFS no grafo social). Novas fontes adicionadas via adapter pattern sem refatorar o pipeline. | Mutação semi-autônoma de fontes: o sistema identifica automaticamente novas fontes de dados relevantes baseado em coverage gaps detectados no `analytical_feature_store`. Propõe novas fontes para aprovação humana. | Self-healing data sources: o sistema detecta degradação de qualidade de fonte, pesquisa automaticamente fontes alternativas, valida e integra sem intervenção humana. |
| **Scoring** | Fórmulas fixas: `P_score = O × (1 - 0.60 × e^(-4.0 × C))`. Pesos configuráveis manualmente no `icp_contract`. Nenhum ajuste automático baseado em feedback de resultados. | Gradient Descent: após fechamento de ciclo comercial, os pesos `w_F`, `w_I`, `w_R` e `alpha`, `beta` são ajustados via descida de gradiente sobre os dados de `crm_outcome_log`. Convergência documentada por ciclo. | Online learning: pesos atualizados incrementalmente a cada novo dado de outcome, sem esperar o ciclo comercial completo. Regularização L2 para evitar overfitting em amostras pequenas. | Reinforcement learning: o sistema otimiza diretamente a taxa de conversão como função objetivo, não apenas a acurácia do P_score. Políticas de abordagem são otimizadas junto com os scores. |
| **Contrato ICP** | Manual: o `icp_contract` é editado manualmente por operador. Versionado por `version_hash`. Mudanças aplicadas no próximo ciclo. O sistema nunca muta o contrato automaticamente. | Re-ranqueamento adaptativo: após ciclos com dados de outcome suficientes (`n_outcomes >= 30`), o sistema gera relatório de sugestão de mutação de ICP com justificativa quantitativa. Mutação requer aprovação humana explícita. | Mutação semi-autônoma: o sistema muta o `icp_contract` em dimensões de baixo risco (ajuste de keywords, ajuste de pesos) automaticamente, com notificação. Mutações de alto risco (mudança de segmento-alvo) requerem aprovação humana. | Mutação 100% autônoma: o sistema redefine o ICP globalmente baseado em performance de outcomes e oportunidades de mercado detectadas. A supervisão humana é estratégica (define objetivos), não operacional (não aprova cada mutação). |
| **Mapeamento de Comitê** | Estático: classificação S_persona/BMO baseada em regras de cargo e vocabulário (Seção 3). Sem aprendizado de padrões de decisão. `S_committee_Completeness` calculado por regras fixas de `n_expected_roles`. | Inferência comportamental: padrões de decisão de compra aprendidos dos `crm_outcome_log`. O sistema aprende quais perfis de S_persona/BMO nas empresas do portfólio efetivamente decidiram pela compra. Re-ranqueia candidatos a BMO com base em padrões aprendidos. | Predição proativa: o sistema prediz o BMO antes de ter evidências diretas, com base no padrão de empresa (segmento, tamanho, maturidade) e nos padrões aprendidos. A predição é marcada com incerteza alta e usada apenas como hipótese inicial. | Sistema completo de inteligência de comitê: mapeamento de redes de influência, predição de timing de decisão, detecção de mudanças no comitê (saída de BMO, entrada de novo sócio) em tempo real. |
| **FinOps** | `tau_FinOps = 0.15` (fixo). Budget Tavily configurado manualmente por ciclo. EIG/MIC calculado por query antes de executar. Stopping rule aplicada de forma binária (executa ou não). | Adaptativo por ciclo: `tau_FinOps` ajustado automaticamente baseado no ROI de queries do ciclo anterior (`crm_outcome_log` cruza com queries que contribuíram para conversões). Budget Tavily alocado dinamicamente por segmento baseado em yield histórico. | Self-optimizing budget: o sistema aprende a distribuição ótima de budget entre fontes (Tavily vs. scrapers) e entre segmentos para maximizar yield de leads qualificados por real gasto. Recomenda aumento ou redução de budget com base em DSS por segmento. | Autonomous FinOps: o sistema negocia autonomamente budget de APIs, roda experimentos A/B de queries, e otimiza o custo por lead qualificado como KPI principal de operação. |
| **Observabilidade** | Logs estruturados: `v_cognitive_log` registra mutações de estado com timestamp e nó de origem. `conflict_resolution_log` registra arbitragens. Alertas de modo degradado emitidos. Outputs consultáveis manualmente via SQL. | `v_cognitive_observability`: dashboard operacional que agrega logs em métricas de ciclo (DSS, taxa de qualificação, distribuição de P_score, erros por fonte). Alertas automáticos por webhook quando DSS < 0.05 ou taxa de falha de scraper > 20%. | Dashboards preditivos: o sistema prediz saturação de descoberta (DSS) 2 ciclos antes de ocorrer, com base em tendência histórica. Sugere automaticamente novas fontes de seeds para combater a saturação. | Observabilidade autônoma: o sistema monitora sua própria performance, detecta degradação de qualidade de output, e ajusta parâmetros operacionais em tempo real sem intervenção humana. Relatórios estratégicos gerados autonomamente. |

### 4.3 Dependências de Evolução entre Versões

A evolução de MVP para V1 tem como pré-requisito inegociável a acumulação de dados no `crm_outcome_log`. Sem registros de outcome real (leads que foram abordados, convertidos ou rejeitados), os algoritmos de V1 não têm base de treinamento. A recomendação de engenharia é acumular no mínimo 30 outcomes com conversão conhecida antes de ativar qualquer componente de V1.

A evolução de V1 para V2 requer que a mutação semi-autônoma do ICP seja testada e validada em ambiente de staging com dados históricos antes de ser ativada em produção. A fórmula de Gradient Descent para ajuste de pesos deve ser monitorada em shadow mode (computada mas não aplicada) por pelo menos 2 ciclos antes de ser ativada.

A Arquitetura Alvo (Autônoma) é um horizonte de design, não um commitment de roadmap. Seu valor está em garantir que as decisões de schema, API e arquitetura do MVP não fechem caminhos para as capacidades autônomas — por isso o DDL do MVP já provisiona as colunas e tabelas que V1, V2 e a versão autônoma usarão.

---

*Documento gerado para uso interno pela equipe de engenharia do SocialSelling. Classificação: CONFIDENCIAL — ENGENHARIA.*
