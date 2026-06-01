# SDD-06 — Database Schema & Graph-Ready DDL

**Projeto:** SocialSelling — Intelligence Data System  
**Versão:** 1.0.0  
**Data:** 2026-06-01  
**Escopo:** Schema completo PostgreSQL 16+, DDL executável, separação em três camadas semânticas, índices de alta performance e view de observabilidade cognitiva.

---

## Índice

1. [Separação Semântica de Três Camadas](#1-separação-semântica-de-três-camadas)
2. [DDL ANSI SQL Completo — PostgreSQL 16+](#2-ddl-ansi-sql-completo--postgresql-16)
3. [Índices de Alta Performance](#3-índices-de-alta-performance)
4. [View de Observabilidade Cognitiva](#4-view-de-observabilidade-cognitiva)

---

## 1. Separação Semântica de Três Camadas

O schema do SocialSelling segue uma arquitetura de três camadas semânticas explícitas. Esta separação não é apenas organizacional — é uma garantia de integridade epistêmica: evidências brutas nunca são sobrescritas, inferências são versionadas, e hipóteses são probabilísticas e rastreáveis por ciclo.

### Camada 1 — Observed Evidence (Fatos Observados)

**Tabela principal:** `observed_evidence`

**Características:**
- **Imutável e append-only:** nenhum registro pode ser atualizado ou deletado após inserção. Qualquer "correção" deve ser um novo registro com classificação diferente.
- **Hash SHA-256 de integridade:** o campo `sha256_hash CHAR(64) UNIQUE NOT NULL` é calculado sobre o conteúdo bruto da evidência (`raw_value + source_key + collected_at`) antes da inserção. Impossibilita alteração retroativa sem detecção — qualquer tentativa de UPDATE geraria violação de constraint UNIQUE.
- **Representa realidade observada:** posts coletados do Instagram, bios do LinkedIn, dados do CNPJ, vagas abertas, interações em âncoras. São os fatos que o sistema observou diretamente, sem interpretação.
- **Vinculação a hipóteses:** o campo `hypothesis_linked CHAR(2)` referencia `hypothesis_catalog(hypothesis_id)`. A COLLATION dos dois campos deve ser idêntica (recomendado: `COLLATE "C"` para CHAR fixo) para evitar falha silenciosa no FK planner do PostgreSQL — o planner pode ignorar o FK em query plans se as collations divergirem, causando full scans não detectados.

**Princípio:** nada que existiu como evidência pode ser apagado. Evidências contraditórias coexistem na base — a Lógica Subjetiva é quem reconcilia contradições na Camada 3.

---

### Camada 2 — Generated Inferences (Inferências Geradas)

**Tabela principal:** `generated_inferences`

**Características:**
- **Mutáveis com versionamento temporal:** inferências podem ser supersedidas por versões mais recentes, mas a versão anterior é preservada.
- **Campo `superseded_by`:** quando uma inferência é atualizada, o novo registro aponta para o anterior via `superseded_by UUID REFERENCES generated_inferences(inference_id)`. A versão mais recente tem `is_current = TRUE`; as anteriores têm `is_current = FALSE`. Isso permite auditoria completa da evolução das inferências.
- **Derivações computadas a partir da Camada 1:** padrões detectados (ex.: "pessoa posta regularmente sobre dor X"), classificações geradas (ex.: "seniority_score = 0.80 inferido do título 'Diretora'"), scores parciais calculados a partir de evidências brutas.
- **Não é interpretação probabilística:** inferências são derivações determinísticas ou semi-determinísticas a partir de regras. A probabilidade entra apenas na Camada 3.

---

### Camada 3 — Evaluated Hypotheses (Hipóteses Avaliadas)

**Tabela principal:** `evaluated_hypotheses`

**Características:**
- **Probabilísticas e indexadas por `cycle_id`:** cada ciclo de execução do LangGraph Engine produz um novo conjunto de avaliações de hipóteses para cada entidade. Avaliações de ciclos anteriores são preservadas para análise de evolução temporal.
- **Base para propagação de Lógica Subjetiva:** os triplets (belief, disbelief, uncertainty) desta camada alimentam os cálculos de fusão de opinião que compõem o `C_score` final.
- **Hipóteses como unidades atômicas de raciocínio:** cada hipótese (ex.: H1 = "empresa em expansão", H2 = "gestora sobrecarregada centralizando decisões") é avaliada independentemente, com prior vindo do `hypothesis_catalog` e posterior calculado via atualização bayesiana sobre evidências da Camada 1.
- **Constraint UNIQUE(entity_id, hypothesis_id, cycle_id):** garante que haja no máximo uma avaliação por hipótese por entidade por ciclo — reavaliações de mesmos ciclos são UPDATE, não INSERT.

---

## 2. DDL ANSI SQL Completo — PostgreSQL 16+

```sql
-- =============================================================================
-- SocialSelling Intelligence Data System — Database Schema
-- PostgreSQL 16+  |  Versão 1.0.0  |  2026-06-01
-- =============================================================================

-- Extensões necessárias
CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- CREATE EXTENSION IF NOT EXISTS vector;  -- Ativar na V1 para embeddings 1536-dim

-- =============================================================================
-- CAMADA DE CONFIGURAÇÃO — ICP Contract & Catálogo de Hipóteses
-- =============================================================================

-- -----------------------------------------------------------------------------
-- icp_contract
-- Contrato de configuração do ICP ativo. Define todos os parâmetros do sistema:
-- segmentos alvo, pesos de score, thresholds, taxonomia de keywords e regras de
-- evidência. Apenas um registro pode ter is_active = TRUE por vez.
-- A constraint de soma de pesos garante que weight_fit + weight_intent +
-- weight_reachability = 1.000 (tolerância de 0.001 para aritmética decimal).
-- -----------------------------------------------------------------------------
CREATE TABLE icp_contract (
    contract_id              UUID            NOT NULL DEFAULT gen_random_uuid(),
    version_hash             VARCHAR(64)     NOT NULL,   -- SHA-256 do contrato serializado
    created_at               TIMESTAMPTZ     NOT NULL DEFAULT now(),
    is_active                BOOLEAN         NOT NULL DEFAULT FALSE,

    -- Segmentos ICP alvo
    target_segments          TEXT[]          NOT NULL DEFAULT '{}',

    -- Pesos do O_score: devem somar 1.000 (±0.001)
    weight_fit               DECIMAL(4,3)    NOT NULL,
    weight_intent            DECIMAL(4,3)    NOT NULL,
    weight_reachability      DECIMAL(4,3)    NOT NULL,

    -- Parâmetros FinOps e Dynamic Search Stop
    tau_finops               DECIMAL(6,4)    NOT NULL DEFAULT 0.1500,   -- threshold de EIG/MIC ratio
    delta_dss                DECIMAL(4,3)    NOT NULL DEFAULT 0.0500,   -- variação mínima de P_score para continuar
    dss_window_size          INTEGER         NOT NULL DEFAULT 50,        -- janela de leads para cálculo do DSS
    dss_consecutive_req      INTEGER         NOT NULL DEFAULT 2,         -- janelas consecutivas abaixo do delta para parar

    -- Perfis âncora e taxonomia de keywords
    anchor_profiles          JSONB           NOT NULL DEFAULT '[]',      -- lista de perfis âncora ICP
    keyword_taxonomy         JSONB           NOT NULL DEFAULT '{}',      -- pain_keywords, transformation_keywords por segmento
    evidence_rules           JSONB           NOT NULL DEFAULT '{}',      -- regras de coleta por sensor

    -- Parâmetros de ranking Beta-PERT
    alpha_rank               DECIMAL(4,3)    NOT NULL DEFAULT 0.600,    -- alpha para distribuição de ranking
    beta_rank                DECIMAL(4,3)    NOT NULL DEFAULT 4.000,    -- beta para distribuição de ranking

    -- Filtros de qualificação do ICP
    icp_team_size_min        INTEGER,
    icp_team_size_max        INTEGER,
    icp_revenue_min_brl      BIGINT,
    icp_revenue_max_brl      BIGINT,
    icp_centralization_min   DECIMAL(4,3),
    icp_maturity_threshold   DECIMAL(4,3),

    -- Parâmetros de penalidade e biblioteca de casos
    delta_penalty            DECIMAL(4,3)    NOT NULL DEFAULT 0.150,    -- penalidade por conflito de evidência
    case_library             JSONB           NOT NULL DEFAULT '{}',      -- casos de referência por segmento
    mic_per_sensor           JSONB           NOT NULL DEFAULT '{}',      -- custo marginal de informação por sensor (BRL)

    CONSTRAINT icp_contract_pkey
        PRIMARY KEY (contract_id),
    CONSTRAINT icp_contract_version_hash_unique
        UNIQUE (version_hash),
    CONSTRAINT icp_contract_weights_sum
        CHECK (ABS(weight_fit + weight_intent + weight_reachability - 1.000) < 0.001),
    CONSTRAINT icp_contract_tau_range
        CHECK (tau_finops BETWEEN 0.0 AND 1.0),
    CONSTRAINT icp_contract_alpha_positive
        CHECK (alpha_rank > 0),
    CONSTRAINT icp_contract_beta_positive
        CHECK (beta_rank > 0)
);

COMMENT ON TABLE icp_contract IS
    'Contrato de configuração do ICP. Apenas um registro com is_active=TRUE por vez. '
    'Versionado por SHA-256 para rastreabilidade de mudanças de configuração.';
COMMENT ON COLUMN icp_contract.tau_finops IS
    'Threshold do ratio EIG/MIC abaixo do qual a busca é interrompida por critério FinOps.';
COMMENT ON COLUMN icp_contract.dss_consecutive_req IS
    'Número de janelas consecutivas com variação de P_score abaixo de delta_dss para acionar o Dynamic Search Stop.';


-- -----------------------------------------------------------------------------
-- hypothesis_catalog
-- Catálogo de hipóteses probabilísticas sobre os leads. Cada hipótese representa
-- uma teoria sobre o estado do prospect (ex.: H1=expansão, H2=centralização).
-- Os campos de impacto definem como a ativação da hipótese afeta os scores.
-- -----------------------------------------------------------------------------
CREATE TABLE hypothesis_catalog (
    hypothesis_id                CHAR(2)         NOT NULL,   -- ex.: 'H1', 'H2', 'H3'
    contract_id                  UUID            NOT NULL,
    label                        VARCHAR(100)    NOT NULL,
    description                  TEXT,

    -- Probabilidade a priori (Bayesian prior)
    prior_probability            DECIMAL(6,5)    NOT NULL CHECK (prior_probability BETWEEN 0 AND 1),

    -- Regras de ativação e desativação
    min_supporting_for_active    INTEGER         NOT NULL DEFAULT 3,  -- evidências mínimas para status ACTIVE
    supporting_evidence_rules    JSONB           NOT NULL DEFAULT '{}',
    contradicting_evidence_rules JSONB           NOT NULL DEFAULT '{}',
    missing_evidence_list        JSONB           NOT NULL DEFAULT '{}',

    -- Impacto nos scores quando hipótese está ACTIVE
    impact_o_score_min           DECIMAL(5,4),   -- range de impacto no O_score
    impact_o_score_max           DECIMAL(5,4),
    impact_target                VARCHAR(20)     CHECK (impact_target IN ('fit', 's_intent')),
    impact_c_score_direction     VARCHAR(10)     CHECK (impact_c_score_direction IN ('positive', 'negative', 'neutral')),

    -- Hipóteses que tendem a co-ocorrer (para análise de padrão)
    co_occurring_hypotheses      TEXT[]          NOT NULL DEFAULT '{}',

    CONSTRAINT hypothesis_catalog_pkey
        PRIMARY KEY (hypothesis_id),
    CONSTRAINT hypothesis_catalog_contract_fkey
        FOREIGN KEY (contract_id) REFERENCES icp_contract(contract_id) ON DELETE RESTRICT,
    CONSTRAINT hypothesis_catalog_impact_range
        CHECK (
            impact_o_score_min IS NULL
            OR impact_o_score_max IS NULL
            OR impact_o_score_min <= impact_o_score_max
        )
);

COMMENT ON TABLE hypothesis_catalog IS
    'Catálogo estático de hipóteses probabilísticas. Define priors, regras de evidência '
    'e impacto nos scores. Referenciado por evaluated_hypotheses a cada ciclo de execução.';
COMMENT ON COLUMN hypothesis_catalog.hypothesis_id IS
    'Identificador curto de 2 caracteres (ex: H1, H2). CHAR(2) com COLLATE padrão — '
    'deve coincidir com o COLLATE de observed_evidence.hypothesis_linked para FK planner.';


-- =============================================================================
-- CAMADA DE CONFIABILIDADE DAS FONTES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- source_reliability
-- Registro de confiabilidade histórica de cada fonte de dados (sensor).
-- O SRS (Source Reliability Score) é atualizado continuamente com base em
-- verdadeiros positivos/negativos versus falsos. Inicializado com srs=0.50
-- (prior neutro) e ajustado via feedback do crm_outcome_log.
-- -----------------------------------------------------------------------------
CREATE TABLE source_reliability (
    source_id                    UUID            NOT NULL DEFAULT gen_random_uuid(),
    source_key                   VARCHAR(64)     NOT NULL,   -- ex.: 'instagram_scraper', 'linkedin_api', 'cnpj_ws'

    -- Contadores de acurácia (atualizados pelo feedback loop do CRM)
    true_positives               BIGINT          NOT NULL DEFAULT 0 CHECK (true_positives >= 0),
    true_negatives               BIGINT          NOT NULL DEFAULT 0 CHECK (true_negatives >= 0),
    false_positives              BIGINT          NOT NULL DEFAULT 0 CHECK (false_positives >= 0),
    false_negatives              BIGINT          NOT NULL DEFAULT 0 CHECK (false_negatives >= 0),
    total_observations           BIGINT          NOT NULL DEFAULT 0 CHECK (total_observations >= 0),

    -- Scores derivados
    srs_current                  DECIMAL(6,5)    NOT NULL DEFAULT 0.50000
                                     CHECK (srs_current BETWEEN 0 AND 1),
    srs_gamma                    DECIMAL(5,4)    NOT NULL DEFAULT 0.0500,   -- taxa de decaimento temporal do SRS
    coverage_last_cycle          DECIMAL(5,4)    NOT NULL DEFAULT 0.50000
                                     CHECK (coverage_last_cycle BETWEEN 0 AND 1),
    historical_accuracy_weighted DECIMAL(5,4)    NOT NULL DEFAULT 0.50000
                                     CHECK (historical_accuracy_weighted BETWEEN 0 AND 1),

    last_recalculated            TIMESTAMPTZ,
    created_at                   TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT source_reliability_pkey
        PRIMARY KEY (source_id),
    CONSTRAINT source_reliability_source_key_unique
        UNIQUE (source_key)
);

COMMENT ON TABLE source_reliability IS
    'Confiabilidade histórica de cada sensor/fonte de dados. '
    'SRS inicializado em 0.50 (prior neutro) e ajustado continuamente via feedback CRM.';
COMMENT ON COLUMN source_reliability.srs_gamma IS
    'Taxa de decaimento temporal do SRS — fontes com dados antigos têm confiabilidade reduzida.';

-- Inserção inicial das 3 fontes do MVP com prior neutro
INSERT INTO source_reliability (source_key, srs_current, srs_gamma, coverage_last_cycle, historical_accuracy_weighted)
VALUES
    ('instagram_scraper', 0.50000, 0.0500, 0.50000, 0.50000),  -- Instagram scraping via Apify
    ('linkedin_api',      0.50000, 0.0500, 0.50000, 0.50000),  -- LinkedIn via RapidAPI ou scraping
    ('cnpj_ws',           0.50000, 0.0200, 0.90000, 0.50000);  -- CNPJ.ws — dados estruturados, menor decaimento


-- =============================================================================
-- CAMADA DE GRAFO — Nós e Arestas (Graph-Ready)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- entity_nodes
-- Nós do grafo — representa empresas e pessoas. Cada nó carrega um triplet de
-- Lógica Subjetiva (belief, disbelief, uncertainty) que expressa a confiança
-- do sistema sobre o valor do prospect. O campo merge_parent_id permite
-- deduplicação: quando duas entidades são identificadas como a mesma, o
-- registro duplicado aponta para o canônico.
-- -----------------------------------------------------------------------------
CREATE TABLE entity_nodes (
    entity_id                UUID            NOT NULL DEFAULT gen_random_uuid(),
    entity_type              VARCHAR(20)     NOT NULL CHECK (entity_type IN ('COMPANY', 'PERSON')),
    canonical_name           VARCHAR(255)    NOT NULL,

    -- Identificadores de fonte por plataforma
    cnpj                     VARCHAR(18),    -- formato: XX.XXX.XXX/XXXX-XX
    instagram_handle         VARCHAR(100),
    linkedin_url             VARCHAR(300),

    -- Localização geográfica
    location_city            VARCHAR(100),
    location_state           CHAR(2),        -- sigla UF ex.: 'SP', 'RJ'

    -- Segmentação ICP
    segment                  VARCHAR(50),    -- ex.: 'Advocacia', 'Consultoria', 'Software House', 'Engenharia'
    declared_team_size       VARCHAR(20)     CHECK (declared_team_size IN ('1-10', '11-50', '51-200', '201-500', '500+')),

    -- Triplet de Lógica Subjetiva para o nó (opinião sobre o valor do lead)
    belief                   DECIMAL(5,4)    NOT NULL DEFAULT 0.5000 CHECK (belief BETWEEN 0 AND 1),
    disbelief                DECIMAL(5,4)    NOT NULL DEFAULT 0.1000 CHECK (disbelief BETWEEN 0 AND 1),
    uncertainty              DECIMAL(5,4)    NOT NULL DEFAULT 0.4000 CHECK (uncertainty BETWEEN 0 AND 1),
    CONSTRAINT entity_nodes_opinion_triple_valid
        CHECK (ABS(belief + disbelief + uncertainty - 1.000) < 0.001),

    -- Scores de confiança e entropia
    rcs_score                DECIMAL(5,4)    CHECK (rcs_score BETWEEN 0 AND 1),   -- Relative Confidence Score
    c_s_shannon              DECIMAL(5,4)    CHECK (c_s_shannon BETWEEN 0 AND 1), -- Entropia de Shannon normalizada

    -- Modo operacional do motor de busca para este lead
    operating_mode           VARCHAR(30)     NOT NULL DEFAULT 'FULL'
                                 CHECK (operating_mode IN ('FULL', 'DELTA_SEARCH', 'DORMANT', 'DISQUALIFIED')),

    -- Metadados de ciclo de vida
    first_seen_at            TIMESTAMPTZ     NOT NULL DEFAULT now(),
    last_updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    is_active                BOOLEAN         NOT NULL DEFAULT TRUE,

    -- Deduplicação: entidade duplicada aponta para a canônica
    merge_parent_id          UUID            REFERENCES entity_nodes(entity_id) ON DELETE SET NULL,

    -- Qualidade e rastreabilidade
    data_quality_flag        VARCHAR(20)     NOT NULL DEFAULT 'NORMAL'
                                 CHECK (data_quality_flag IN ('NORMAL', 'LOW', 'DEGRADED')),
    cycle_id_last_processed  UUID,

    CONSTRAINT entity_nodes_pkey
        PRIMARY KEY (entity_id),
    CONSTRAINT entity_nodes_cnpj_unique
        UNIQUE (cnpj),
    CONSTRAINT entity_nodes_instagram_unique
        UNIQUE (instagram_handle),
    CONSTRAINT entity_nodes_linkedin_unique
        UNIQUE (linkedin_url)
);

COMMENT ON TABLE entity_nodes IS
    'Nós do grafo. Representa empresas (COMPANY) e pessoas (PERSON). '
    'Carrega triplet de Lógica Subjetiva e suporta deduplicação via merge_parent_id.';
COMMENT ON COLUMN entity_nodes.belief IS
    'Componente belief do triplet ω = (b, d, u). b+d+u deve ser 1.000 (±0.001).';
COMMENT ON COLUMN entity_nodes.merge_parent_id IS
    'Referência à entidade canônica quando este nó é detectado como duplicado. '
    'NULL indica que o nó é ele mesmo o canônico.';
COMMENT ON COLUMN entity_nodes.operating_mode IS
    'FULL: coleta completa ativa. DELTA_SEARCH: apenas triggers. '
    'DORMANT: pausado. DISQUALIFIED: descartado permanentemente.';


-- -----------------------------------------------------------------------------
-- entity_edges
-- Arestas do grafo — relações entre entidades. Tipadas (WORKS_AT, INTERACTED_WITH,
-- etc.) e ponderadas com triplet de Lógica Subjetiva próprio. O campo e_fresh
-- é o fator de frescor da aresta — arestas não reconfirmadas decaem ao longo do
-- tempo. Projetado para travessia multi-hop (Dijkstra na V1).
-- -----------------------------------------------------------------------------
CREATE TABLE entity_edges (
    edge_id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
    source_entity_id         UUID            NOT NULL,
    target_entity_id         UUID            NOT NULL,
    edge_type                VARCHAR(50)     NOT NULL
                                 CHECK (edge_type IN (
                                     'WORKS_AT',
                                     'FORMER_EMPLOYEE',
                                     'INTERACTED_WITH',
                                     'MUTUAL_FOLLOWER',
                                     'MENTIONED',
                                     'COMMENTED_ON',
                                     'LIKED'
                                 )),

    -- Peso da aresta para algoritmos de grafo
    weight                   DECIMAL(5,4)    NOT NULL DEFAULT 1.0000
                                 CHECK (weight BETWEEN 0 AND 1),

    -- Triplet de Lógica Subjetiva da aresta
    belief                   DECIMAL(5,4)    CHECK (belief BETWEEN 0 AND 1),
    disbelief                DECIMAL(5,4)    CHECK (disbelief BETWEEN 0 AND 1),
    uncertainty              DECIMAL(5,4)    CHECK (uncertainty BETWEEN 0 AND 1),
    CONSTRAINT entity_edges_opinion_valid
        CHECK (
            belief IS NULL
            OR disbelief IS NULL
            OR uncertainty IS NULL
            OR ABS(belief + disbelief + uncertainty - 1.000) < 0.001
        ),

    -- Frescor e rastreabilidade temporal
    e_fresh                  DECIMAL(5,4)    NOT NULL DEFAULT 1.0000
                                 CHECK (e_fresh BETWEEN 0 AND 1),  -- decai ao longo do tempo
    last_evidence_at         TIMESTAMPTZ,    -- última vez que a aresta foi confirmada por evidência
    created_at               TIMESTAMPTZ     NOT NULL DEFAULT now(),

    -- Fonte e papel inferido da relação
    source_key               VARCHAR(64),    -- qual sensor originou esta aresta
    role_inferred            VARCHAR(100),   -- papel inferido da pessoa na relação (ex.: 'CTO at Company X')

    CONSTRAINT entity_edges_pkey
        PRIMARY KEY (edge_id),
    CONSTRAINT entity_edges_source_fkey
        FOREIGN KEY (source_entity_id) REFERENCES entity_nodes(entity_id) ON DELETE CASCADE,
    CONSTRAINT entity_edges_target_fkey
        FOREIGN KEY (target_entity_id) REFERENCES entity_nodes(entity_id) ON DELETE CASCADE,
    CONSTRAINT entity_edges_no_self_loop
        CHECK (source_entity_id <> target_entity_id)
);

COMMENT ON TABLE entity_edges IS
    'Arestas tipadas e ponderadas do grafo. Suporta travessia multi-hop (Dijkstra V1). '
    'e_fresh decai temporalmente — arestas não reconfirmadas perdem peso.';
COMMENT ON COLUMN entity_edges.e_fresh IS
    'Fator de frescor da aresta [0,1]. 1.0 = recém-confirmada. Decai com o tempo '
    'segundo half-life configurado. Usado como multiplicador no peso de traversal.';


-- =============================================================================
-- CAMADA 1 — OBSERVED EVIDENCE (Imutável / Append-Only)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- observed_evidence
-- Camada 1 do modelo de três camadas. Registra todos os fatos observados pelas
-- coletas dos sensores. Imutável após inserção — o SHA-256 garante integridade.
-- hypothesis_linked deve ter COLLATION idêntica ao hypothesis_catalog.hypothesis_id
-- para evitar falha silenciosa no FK planner do PostgreSQL.
-- -----------------------------------------------------------------------------
CREATE TABLE observed_evidence (
    evidence_id              UUID            NOT NULL DEFAULT gen_random_uuid(),
    entity_id                UUID            NOT NULL,

    -- Fonte e tipo
    source_key               VARCHAR(64)     NOT NULL,   -- referência à source_reliability.source_key
    evidence_type            VARCHAR(50)     NOT NULL,   -- ex.: 'instagram_post', 'linkedin_bio', 'cnpj_data', 'job_posting'
    raw_value                TEXT,                       -- conteúdo bruto observado

    -- Temporalidade da coleta
    collected_at             TIMESTAMPTZ     NOT NULL DEFAULT now(),

    -- Integridade: SHA-256 de (raw_value || source_key || collected_at::text)
    sha256_hash              CHAR(64)        NOT NULL,

    -- Confiabilidade da fonte no momento da coleta
    srs_at_collection        DECIMAL(5,4)    CHECK (srs_at_collection BETWEEN 0 AND 1),

    -- Frescor da evidência
    freshness_initial        DECIMAL(5,4)    NOT NULL DEFAULT 1.0000 CHECK (freshness_initial BETWEEN 0 AND 1),
    freshness_current        DECIMAL(5,4)    NOT NULL DEFAULT 1.0000 CHECK (freshness_current BETWEEN 0 AND 1),
    half_life_days           DECIMAL(6,1),   -- dias até freshness decair para 0.5 (NULL = sem decaimento)

    -- Vinculação a hipótese — COLLATION deve ser idêntica a hypothesis_catalog.hypothesis_id
    hypothesis_linked        CHAR(2) COLLATE "C",   -- ex.: 'H1', 'H2'

    -- Classificação da evidência em relação à hipótese vinculada
    classification           VARCHAR(20)     CHECK (classification IN ('Supporting', 'Contradicting', 'Missing', 'Neutral')),

    -- Rastreabilidade de ciclo
    cycle_id                 UUID,

    CONSTRAINT observed_evidence_pkey
        PRIMARY KEY (evidence_id),
    CONSTRAINT observed_evidence_sha256_unique
        UNIQUE (sha256_hash),       -- integridade imutável: hash único impossibilita duplicação ou alteração
    CONSTRAINT observed_evidence_entity_fkey
        FOREIGN KEY (entity_id) REFERENCES entity_nodes(entity_id) ON DELETE RESTRICT,
    CONSTRAINT observed_evidence_hypothesis_fkey
        FOREIGN KEY (hypothesis_linked) REFERENCES hypothesis_catalog(hypothesis_id) ON DELETE SET NULL
);

COMMENT ON TABLE observed_evidence IS
    'Camada 1 — Fatos Observados. Append-only e imutável. '
    'SHA-256 calculado sobre (raw_value || source_key || collected_at) antes da inserção. '
    'hypothesis_linked usa COLLATE "C" para coincidir com hypothesis_catalog e evitar '
    'falha silenciosa no FK planner.';
COMMENT ON COLUMN observed_evidence.sha256_hash IS
    'Hash SHA-256 do conteúdo bruto. UNIQUE garante que a mesma evidência não seja '
    'inserida duas vezes e que nenhuma evidência possa ser alterada sem violação.';
COMMENT ON COLUMN observed_evidence.freshness_current IS
    'Frescor atual da evidência. Decai exponencialmente com base em half_life_days. '
    'Recalculado a cada ciclo. Evidências com freshness_current < 0.30 são consideradas stale.';


-- =============================================================================
-- CAMADA 2 — GENERATED INFERENCES (Mutável com Versionamento)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- generated_inferences
-- Camada 2 do modelo de três camadas. Registra derivações computadas a partir
-- das evidências brutas (Camada 1). Mutável mas versionada: inferências
-- supersedidas mantêm is_current=FALSE e apontam para a versão mais recente.
-- -----------------------------------------------------------------------------
CREATE TABLE generated_inferences (
    inference_id             UUID            NOT NULL DEFAULT gen_random_uuid(),
    entity_id                UUID            NOT NULL,

    -- Rastreabilidade: quais evidências geraram esta inferência
    derived_from_evidence    UUID[]          NOT NULL DEFAULT '{}',   -- array de evidence_ids da Camada 1

    -- Tipo e valor da inferência
    inference_type           VARCHAR(100)    NOT NULL,   -- ex.: 'seniority_score', 'role_alignment', 'pain_post_cluster'
    inferred_value           TEXT            NOT NULL,   -- valor inferido (serializado como texto)

    -- Qualidade da inferência
    confidence               DECIMAL(5,4)    CHECK (confidence BETWEEN 0 AND 1),
    method                   VARCHAR(100),   -- ex.: 'keyword_matching', 'cosine_similarity_tfidf', 'rule_based'

    -- Versionamento
    is_current               BOOLEAN         NOT NULL DEFAULT TRUE,
    superseded_by            UUID            REFERENCES generated_inferences(inference_id) ON DELETE SET NULL,

    -- Metadados
    created_at               TIMESTAMPTZ     NOT NULL DEFAULT now(),
    cycle_id                 UUID,

    CONSTRAINT generated_inferences_pkey
        PRIMARY KEY (inference_id),
    CONSTRAINT generated_inferences_entity_fkey
        FOREIGN KEY (entity_id) REFERENCES entity_nodes(entity_id) ON DELETE RESTRICT,
    CONSTRAINT generated_inferences_no_self_supersede
        CHECK (superseded_by <> inference_id)
);

COMMENT ON TABLE generated_inferences IS
    'Camada 2 — Inferências Geradas. Derivações computadas a partir de evidências brutas. '
    'Versionadas via superseded_by: is_current=TRUE aponta para a versão mais recente. '
    'Versões antigas são preservadas para auditoria.';
COMMENT ON COLUMN generated_inferences.derived_from_evidence IS
    'Array de UUIDs referenciando observed_evidence.evidence_id. '
    'Mantém rastreabilidade completa da cadeia evidência → inferência.';


-- =============================================================================
-- CAMADA 3 — EVALUATED HYPOTHESES (Probabilística / Ciclo)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- evaluated_hypotheses
-- Camada 3 do modelo de três camadas. Avaliação probabilística de cada hipótese
-- para cada entidade por ciclo de execução. Triplet de Lógica Subjetiva calculado
-- via fusão de evidências da Camada 1. Base para o C_score e O_score finais.
-- UNIQUE(entity_id, hypothesis_id, cycle_id) garante uma avaliação por hipótese
-- por entidade por ciclo.
-- -----------------------------------------------------------------------------
CREATE TABLE evaluated_hypotheses (
    eval_id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
    entity_id                UUID            NOT NULL,
    hypothesis_id            CHAR(2)         NOT NULL,
    cycle_id                 UUID            NOT NULL,

    -- Probabilidades Bayesianas
    prior_probability        DECIMAL(6,5)    CHECK (prior_probability BETWEEN 0 AND 1),
    posterior_probability    DECIMAL(6,5)    CHECK (posterior_probability BETWEEN 0 AND 1),

    -- Status da hipótese para este ciclo
    status                   VARCHAR(20)     NOT NULL DEFAULT 'CANDIDATE'
                                 CHECK (status IN ('CANDIDATE', 'ACTIVE', 'REJECTED')),

    -- Triplet de Lógica Subjetiva para a hipótese
    belief                   DECIMAL(5,4)    CHECK (belief BETWEEN 0 AND 1),
    disbelief                DECIMAL(5,4)    CHECK (disbelief BETWEEN 0 AND 1),
    uncertainty              DECIMAL(5,4)    CHECK (uncertainty BETWEEN 0 AND 1),

    -- Contagem de evidências por classificação
    supporting_evidence_count    INTEGER     NOT NULL DEFAULT 0 CHECK (supporting_evidence_count >= 0),
    contradicting_evidence_count INTEGER     NOT NULL DEFAULT 0 CHECK (contradicting_evidence_count >= 0),
    missing_evidence_count       INTEGER     NOT NULL DEFAULT 0 CHECK (missing_evidence_count >= 0),

    last_updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT evaluated_hypotheses_pkey
        PRIMARY KEY (eval_id),
    CONSTRAINT evaluated_hypotheses_entity_fkey
        FOREIGN KEY (entity_id) REFERENCES entity_nodes(entity_id) ON DELETE RESTRICT,
    CONSTRAINT evaluated_hypotheses_hypothesis_fkey
        FOREIGN KEY (hypothesis_id) REFERENCES hypothesis_catalog(hypothesis_id) ON DELETE RESTRICT,
    CONSTRAINT evaluated_hypotheses_unique_per_cycle
        UNIQUE (entity_id, hypothesis_id, cycle_id)
);

COMMENT ON TABLE evaluated_hypotheses IS
    'Camada 3 — Hipóteses Avaliadas. Uma linha por hipótese × entidade × ciclo. '
    'Triplet de Lógica Subjetiva calculado via fusão de evidências. '
    'Base para propagação dos scores O_score e C_score.';


-- =============================================================================
-- MÓDULO DE COMITÊ DE COMPRA
-- =============================================================================

-- -----------------------------------------------------------------------------
-- committee_members
-- Membros identificados do comitê de compra de cada empresa prospect.
-- Cada linha representa a avaliação de um indivíduo (PERSON entity) dentro
-- do contexto de compra de uma empresa (COMPANY entity).
-- Persiste o vetor S_persona completo e o bmo_momentum_score para auditoria.
-- -----------------------------------------------------------------------------
CREATE TABLE committee_members (
    member_id                UUID            NOT NULL DEFAULT gen_random_uuid(),
    entity_id                UUID            NOT NULL,   -- COMPANY entity
    person_entity_id         UUID            NOT NULL,   -- PERSON entity (nó da pessoa)

    -- Cargo declarado e inferido
    role_declared            VARCHAR(200),               -- cargo como aparece na fonte
    role_inferred            VARCHAR(100),               -- papel ICP inferido (ex.: 'Economic Buyer')
    role_probability         DECIMAL(5,4)    CHECK (role_probability BETWEEN 0 AND 1),

    -- Vetor S_persona completo
    seniority_score          DECIMAL(5,4)    CHECK (seniority_score BETWEEN 0 AND 1),
    role_alignment_score     DECIMAL(5,4)    CHECK (role_alignment_score BETWEEN 0 AND 1),
    engagement_frequency     DECIMAL(5,4)    CHECK (engagement_frequency BETWEEN 0 AND 1),

    -- Score combinado: 0.40×seniority + 0.35×role_align + 0.25×engagement
    member_score             DECIMAL(5,4)    CHECK (member_score BETWEEN 0 AND 1),

    -- Designação no comitê de compra
    designation              VARCHAR(30)     NOT NULL DEFAULT 'UNKNOWN'
                                 CHECK (designation IN (
                                     'STRUCTURAL_CHAMPION',
                                     'BUYING_MOTION_OWNER',
                                     'GATEKEEPER',
                                     'MEMBER',
                                     'UNKNOWN'
                                 )),

    -- Score de momentum do BMO: 0.50×post_cluster + 0.30×anchor_interaction + 0.20×trigger_event
    bmo_momentum_score       DECIMAL(5,4)    NOT NULL DEFAULT 0.0000
                                 CHECK (bmo_momentum_score BETWEEN 0 AND 1),

    -- Triplet de Lógica Subjetiva do membro (incerteza sobre a identificação)
    belief                   DECIMAL(5,4)    CHECK (belief BETWEEN 0 AND 1),
    disbelief                DECIMAL(5,4)    CHECK (disbelief BETWEEN 0 AND 1),
    uncertainty              DECIMAL(5,4)    CHECK (uncertainty BETWEEN 0 AND 1),

    -- Justificativa textual da designação (para auditoria e consumo por agente de outreach)
    rationale                TEXT,

    -- Indicador de recência dos posts ICP (dias desde o último post de dor)
    last_post_iq_days_ago    INTEGER         CHECK (last_post_iq_days_ago >= 0),

    -- Rastreabilidade de ciclo
    cycle_id                 UUID,
    created_at               TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT committee_members_pkey
        PRIMARY KEY (member_id),
    CONSTRAINT committee_members_company_fkey
        FOREIGN KEY (entity_id) REFERENCES entity_nodes(entity_id) ON DELETE RESTRICT,
    CONSTRAINT committee_members_person_fkey
        FOREIGN KEY (person_entity_id) REFERENCES entity_nodes(entity_id) ON DELETE RESTRICT
);

COMMENT ON TABLE committee_members IS
    'Membros do comitê de compra por empresa prospect. '
    'Persiste o vetor S_persona completo, bmo_momentum_score e designação SC/BMO/GATEKEEPER. '
    'member_score = 0.40×seniority + 0.35×role_alignment + 0.25×engagement_frequency.';
COMMENT ON COLUMN committee_members.bmo_momentum_score IS
    'bmo_momentum = 0.50×post_cluster_score + 0.30×anchor_interaction_score + 0.20×trigger_event_score. '
    'Threshold BMO: >= 0.55. Threshold SC: < 0.55 com role_alignment_score > 0.60.';
COMMENT ON COLUMN committee_members.rationale IS
    'Justificativa textual legível. Ex.: "BMO coincide com SC — decisor formal com momentum ativo". '
    'Consumido pelo agente de outreach para definir estratégia de abordagem.';


-- -----------------------------------------------------------------------------
-- behavioral_momentum_log
-- Log de trigger events detectados para cada entidade (pessoa ou empresa).
-- Cada linha representa um evento estrutural ou comportamental que indica
-- que a organização está em janela de mudança ativa.
-- Quatro tipos: SENIOR_HIRE, PERSISTENT_JOB_POSTING, TRANSFORMATION_POST,
-- ANCHOR_INTERACTION.
-- -----------------------------------------------------------------------------
CREATE TABLE behavioral_momentum_log (
    event_id                 UUID            NOT NULL DEFAULT gen_random_uuid(),
    entity_id                UUID            NOT NULL,   -- PERSON ou COMPANY entity

    -- Tipo e fonte do trigger
    trigger_type             VARCHAR(50)     NOT NULL
                                 CHECK (trigger_type IN (
                                     'SENIOR_HIRE',
                                     'PERSISTENT_JOB_POSTING',
                                     'TRANSFORMATION_POST',
                                     'ANCHOR_INTERACTION'
                                 )),
    trigger_source           VARCHAR(50),    -- ex.: 'linkedin_connections', 'linkedin_jobs', 'instagram_posts'

    -- Evidência que originou o trigger
    evidence_reference       UUID            REFERENCES observed_evidence(evidence_id) ON DELETE SET NULL,

    -- Peso do trigger no trigger_event_score do bmo_momentum_score
    trigger_weight           DECIMAL(5,4)    NOT NULL CHECK (trigger_weight BETWEEN 0 AND 1),

    -- Janela temporal do trigger
    detected_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),
    window_days              INTEGER         NOT NULL CHECK (window_days > 0),   -- ex.: 30 para SENIOR_HIRE

    -- Status de atividade (triggers têm janela de validade)
    is_active                BOOLEAN         NOT NULL DEFAULT TRUE,

    -- Rastreabilidade de ciclo
    cycle_id                 UUID,

    CONSTRAINT behavioral_momentum_log_pkey
        PRIMARY KEY (event_id),
    CONSTRAINT behavioral_momentum_log_entity_fkey
        FOREIGN KEY (entity_id) REFERENCES entity_nodes(entity_id) ON DELETE RESTRICT
);

COMMENT ON TABLE behavioral_momentum_log IS
    'Log de trigger events de momentum comportamental e estrutural. '
    'Quatro tipos: SENIOR_HIRE (peso 0.60), PERSISTENT_JOB_POSTING (0.40), '
    'TRANSFORMATION_POST (0.80), ANCHOR_INTERACTION (0.50). '
    'Alimenta o trigger_event_score do bmo_momentum_score.';
COMMENT ON COLUMN behavioral_momentum_log.is_active IS
    'FALSE quando o evento saiu da janela temporal válida (window_days expirado). '
    'Triggers inativos não contam para o trigger_event_score corrente.';


-- =============================================================================
-- FEATURE STORE E RANKING
-- =============================================================================

-- -----------------------------------------------------------------------------
-- analytical_feature_store
-- Feature store desnormalizado para ranking e análise. Contém todos os features
-- computados (oportunidade, confiança, comitê) e os scores finais (O_score,
-- C_score, P_score) para cada entidade no último ciclo processado.
-- UNIQUE(entity_id) garante uma linha por entidade (substituída a cada ciclo).
-- Campos V1 (gradient_descent_target, embedding_vector_1536) são NULL no MVP.
-- -----------------------------------------------------------------------------
CREATE TABLE analytical_feature_store (
    feature_id               UUID            NOT NULL DEFAULT gen_random_uuid(),
    entity_id                UUID            NOT NULL,   -- UNIQUE: uma linha por entidade (último ciclo)
    cycle_id                 UUID,

    -- FEATURES DE OPORTUNIDADE (O_score)
    feat_fit                 DECIMAL(6,5)    CHECK (feat_fit BETWEEN 0 AND 1),
    feat_s_intent            DECIMAL(6,5)    CHECK (feat_s_intent BETWEEN 0 AND 1),
    feat_reachability_hybrid DECIMAL(6,5)    CHECK (feat_reachability_hybrid BETWEEN 0 AND 1),
    feat_r_interactions      DECIMAL(5,4)    CHECK (feat_r_interactions BETWEEN 0 AND 1),
    feat_r_mutual_followers  DECIMAL(5,4)    CHECK (feat_r_mutual_followers BETWEEN 0 AND 1),
    feat_r_org_proximity     DECIMAL(5,4)    CHECK (feat_r_org_proximity BETWEEN 0 AND 1),
    feat_e_fresh             DECIMAL(6,5)    CHECK (feat_e_fresh BETWEEN 0 AND 1),  -- frescor médio das evidências
    o_score                  DECIMAL(6,5)    CHECK (o_score BETWEEN 0 AND 1),       -- Opportunity Score final

    -- FEATURES DE CONFIANÇA (C_score)
    feat_rcs                 DECIMAL(6,5)    CHECK (feat_rcs BETWEEN 0 AND 1),      -- Relative Confidence Score
    feat_c_s_shannon         DECIMAL(6,5)    CHECK (feat_c_s_shannon BETWEEN 0 AND 1),
    feat_uncertainty_committee DECIMAL(6,5)  CHECK (feat_uncertainty_committee BETWEEN 0 AND 1),
    feat_hypothesis_confidence DECIMAL(6,5)  CHECK (feat_hypothesis_confidence BETWEEN 0 AND 1),
    feat_srs_product         DECIMAL(6,5)    CHECK (feat_srs_product BETWEEN 0 AND 1),  -- produto dos SRS das fontes usadas
    c_score                  DECIMAL(6,5)    CHECK (c_score BETWEEN 0 AND 1),       -- Confidence Score final

    -- RANKING P_score
    p_score                  DECIMAL(6,5)    CHECK (p_score BETWEEN 0 AND 1),       -- Prospect Score = f(O_score, C_score, alpha, beta)
    rank_position            INTEGER         CHECK (rank_position > 0),
    total_leads_in_cycle     INTEGER         CHECK (total_leads_in_cycle > 0),
    alpha_used               DECIMAL(4,3),   -- alpha Beta-PERT usado no ciclo
    beta_used                DECIMAL(4,3),   -- beta Beta-PERT usado no ciclo

    -- FEATURES DE COMITÊ
    committee_completeness   DECIMAL(5,4)    CHECK (committee_completeness BETWEEN 0 AND 1),   -- |roles_identified| / |roles_expected|
    committee_confidence     DECIMAL(5,4)    CHECK (committee_confidence BETWEEN 0 AND 1),     -- 1 - ū_committee
    committee_uncertainty    DECIMAL(5,4)    CHECK (committee_uncertainty BETWEEN 0 AND 1),    -- ū_members + (1-completeness)×0.30

    -- QUALIDADE E MODO OPERACIONAL
    data_quality_flag        VARCHAR(20)     CHECK (data_quality_flag IN ('NORMAL', 'LOW', 'DEGRADED')),
    operating_mode           VARCHAR(30)     CHECK (operating_mode IN ('FULL', 'DELTA_SEARCH', 'DORMANT', 'DISQUALIFIED')),

    -- READINESS PARA V1 — NULL NO MVP
    gradient_descent_target  DECIMAL(6,5)    NULL,       -- target para gradient descent de parâmetros (V1)
    embedding_vector_1536    JSONB           NULL,       -- embedding semântico 1536-dim (V1, substituir por vector type)

    -- META
    computed_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),
    dominant_hypothesis_id   CHAR(2)         REFERENCES hypothesis_catalog(hypothesis_id) ON DELETE SET NULL,

    CONSTRAINT analytical_feature_store_pkey
        PRIMARY KEY (feature_id),
    CONSTRAINT analytical_feature_store_entity_unique
        UNIQUE (entity_id),   -- uma linha por entidade — substituída a cada ciclo de ranking
    CONSTRAINT analytical_feature_store_entity_fkey
        FOREIGN KEY (entity_id) REFERENCES entity_nodes(entity_id) ON DELETE RESTRICT
);

COMMENT ON TABLE analytical_feature_store IS
    'Feature store desnormalizado. Uma linha por entidade (última atualização). '
    'Contém todos os features e scores finais (O_score, C_score, P_score) para ranking. '
    'Campos V1 (gradient_descent_target, embedding_vector_1536) são NULL no MVP.';
COMMENT ON COLUMN analytical_feature_store.p_score IS
    'Prospect Score final. Função de O_score, C_score, parâmetros alpha/beta Beta-PERT. '
    'Principal campo de ordenação para priorização de outreach.';
COMMENT ON COLUMN analytical_feature_store.committee_uncertainty IS
    'Uncertainty_Committee = ū_members + (1 - committee_completeness) × 0.30, truncado em 1.0. '
    'Separado semanticamente do O_score — representa incerteza epistêmica sobre o comitê.';


-- =============================================================================
-- LOGS OPERACIONAIS E AUDITORIA
-- =============================================================================

-- -----------------------------------------------------------------------------
-- search_logs
-- Log de execuções de busca por ciclo e sensor. Registra custo, latência,
-- variação do DSS e modo operacional. Usado para monitoramento FinOps e
-- auditoria de cobertura de coleta.
-- -----------------------------------------------------------------------------
CREATE TABLE search_logs (
    log_id                   UUID            NOT NULL DEFAULT gen_random_uuid(),
    cycle_id                 UUID,
    source_key               VARCHAR(64)     NOT NULL,
    query_executed           TEXT,           -- query ou parâmetros enviados ao sensor
    result_count             INTEGER         CHECK (result_count >= 0),
    new_entities_found       INTEGER         CHECK (new_entities_found >= 0),
    cached                   BOOLEAN         NOT NULL DEFAULT FALSE,
    http_status              INTEGER,
    latency_ms               INTEGER         CHECK (latency_ms >= 0),
    cost_brl                 DECIMAL(8,4)    CHECK (cost_brl >= 0),   -- custo em BRL desta execução
    dss_before               DECIMAL(5,4)    CHECK (dss_before BETWEEN 0 AND 1),
    dss_after                DECIMAL(5,4)    CHECK (dss_after BETWEEN 0 AND 1),
    operating_mode           VARCHAR(30)     CHECK (operating_mode IN ('FULL', 'DELTA_SEARCH', 'DORMANT', 'DISQUALIFIED')),
    executed_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT search_logs_pkey
        PRIMARY KEY (log_id)
);

COMMENT ON TABLE search_logs IS
    'Log de execuções de busca por ciclo e sensor. '
    'Registra custo BRL, latência, contagem de resultados e variação do DSS (Dynamic Search Stop). '
    'Base para monitoramento FinOps e auditoria de cobertura.';


-- -----------------------------------------------------------------------------
-- conflict_resolution_log
-- Log de conflitos de evidência detectados entre fontes ou ciclos diferentes.
-- Um conflito ocorre quando dois valores diferentes para o mesmo atributo de
-- uma entidade são observados com divergência acima do threshold configurado.
-- Conflitos críticos são encaminhados para revisão manual.
-- -----------------------------------------------------------------------------
CREATE TABLE conflict_resolution_log (
    conflict_id              UUID            NOT NULL DEFAULT gen_random_uuid(),
    entity_id                UUID            NOT NULL,
    attribute_key            VARCHAR(100)    NOT NULL,   -- ex.: 'declared_team_size', 'segment', 'seniority_score'
    value_authoritative      TEXT,           -- valor considerado correto (fonte de maior SRS)
    value_challenger         TEXT,           -- valor conflitante (fonte de menor SRS)
    source_authoritative     VARCHAR(64),    -- source_key da fonte autoritativa
    source_challenger        VARCHAR(64),    -- source_key da fonte conflitante
    divergence_delta         DECIMAL(6,5)    CHECK (divergence_delta >= 0),   -- magnitude da divergência
    conflict_severity        VARCHAR(10)     NOT NULL DEFAULT 'LOW'
                                 CHECK (conflict_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    resolution_method        VARCHAR(50),    -- ex.: 'srs_weighted', 'recency_wins', 'manual'
    residual_uncertainty_delta DECIMAL(5,4) CHECK (residual_uncertainty_delta >= 0),   -- delta adicionado à incerteza do nó
    requires_manual_review   BOOLEAN         NOT NULL DEFAULT FALSE,
    cycle_id                 UUID,
    detected_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT conflict_resolution_log_pkey
        PRIMARY KEY (conflict_id),
    CONSTRAINT conflict_resolution_log_entity_fkey
        FOREIGN KEY (entity_id) REFERENCES entity_nodes(entity_id) ON DELETE RESTRICT
);

COMMENT ON TABLE conflict_resolution_log IS
    'Log de conflitos de evidência detectados entre fontes. '
    'Conflitos CRITICAL ou HIGH com requires_manual_review=TRUE são encaminhados para revisão humana. '
    'residual_uncertainty_delta é adicionado à incerteza do nó afetado em entity_nodes.';


-- -----------------------------------------------------------------------------
-- pruned_reason_log
-- Log de decisões de poda (pruning) do motor de busca. Registra quando e por
-- qual motivo um lead foi movido de FULL para DELTA_SEARCH, DORMANT ou
-- DISQUALIFIED. Inclui todos os parâmetros decisórios para auditoria completa
-- do processo de parada.
-- -----------------------------------------------------------------------------
CREATE TABLE pruned_reason_log (
    prune_id                 UUID            NOT NULL DEFAULT gen_random_uuid(),
    pruning_event_id         VARCHAR(30)     NOT NULL,   -- identificador legível: ex. 'PRUNE-20260601-00042'
    entity_id                UUID            NOT NULL,
    cycle_id                 UUID,

    -- Regra de parada aplicada
    primary_stopping_rule    VARCHAR(50)     NOT NULL,   -- ex.: 'DSS_THRESHOLD', 'TAU_FINOPS', 'P_SCORE_LOW'
    sensor_evaluated         VARCHAR(100),
    eig_bits                 DECIMAL(8,6),               -- Expected Information Gain em bits
    mic_brl                  DECIMAL(8,4),               -- Marginal Information Cost em BRL
    eig_mic_ratio            DECIMAL(10,6),              -- ratio EIG/MIC (comparado com tau_finops)
    tau_finops               DECIMAL(6,4),               -- threshold tau usado na decisão

    -- Estado do DSS no momento da poda
    dss_current              DECIMAL(5,4)    CHECK (dss_current BETWEEN 0 AND 1),
    dss_threshold            DECIMAL(5,4)    CHECK (dss_threshold BETWEEN 0 AND 1),
    consecutive_windows_below INTEGER        CHECK (consecutive_windows_below >= 0),

    -- Scores parciais no momento da poda
    o_score_partial          DECIMAL(6,5)    CHECK (o_score_partial BETWEEN 0 AND 1),
    c_score_partial          DECIMAL(6,5)    CHECK (c_score_partial BETWEEN 0 AND 1),
    p_score_estimated        DECIMAL(6,5)    CHECK (p_score_estimated BETWEEN 0 AND 1),

    -- Transição de modo operacional
    mode_transition_from     VARCHAR(30)     CHECK (mode_transition_from IN ('FULL', 'DELTA_SEARCH', 'DORMANT', 'DISQUALIFIED')),
    mode_transition_to       VARCHAR(30)     CHECK (mode_transition_to IN ('FULL', 'DELTA_SEARCH', 'DORMANT', 'DISQUALIFIED')),

    -- Parâmetros do próximo ciclo de reativação (para DELTA_SEARCH)
    delta_search_interval_days INTEGER       NOT NULL DEFAULT 7,   -- dias até próxima verificação de triggers
    delta_triggers           JSONB           NOT NULL DEFAULT '[]', -- lista de triggers que reativariam busca completa

    -- Auditoria de custo total da entidade até a poda
    audit_total_api_calls    INTEGER         CHECK (audit_total_api_calls >= 0),
    audit_cost_brl           DECIMAL(8,4)    CHECK (audit_cost_brl >= 0),

    -- Resumo legível da decisão
    reason_summary           TEXT,
    generated_at             TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT pruned_reason_log_pkey
        PRIMARY KEY (prune_id),
    CONSTRAINT pruned_reason_log_pruning_event_unique
        UNIQUE (pruning_event_id),
    CONSTRAINT pruned_reason_log_entity_fkey
        FOREIGN KEY (entity_id) REFERENCES entity_nodes(entity_id) ON DELETE RESTRICT
);

COMMENT ON TABLE pruned_reason_log IS
    'Log de decisões de poda do motor de busca. '
    'Registra transições de modo operacional (FULL→DELTA_SEARCH, DELTA_SEARCH→DORMANT, etc.) '
    'com todos os parâmetros decisórios para auditoria XAI completa.';
COMMENT ON COLUMN pruned_reason_log.eig_mic_ratio IS
    'Ratio EIG/MIC comparado com tau_finops do icp_contract. '
    'Se eig_mic_ratio < tau_finops, a busca é interrompida por critério FinOps.';


-- -----------------------------------------------------------------------------
-- crm_outcome_log
-- Log de outcomes do CRM — feedback loop para atualização dos SRS e calibração
-- dos priors do modelo. Registra o resultado comercial de cada lead quando
-- disponível, junto com os scores no momento do outcome para análise de
-- calibração retrospectiva.
-- -----------------------------------------------------------------------------
CREATE TABLE crm_outcome_log (
    outcome_id               UUID            NOT NULL DEFAULT gen_random_uuid(),
    entity_id                UUID            NOT NULL,
    lead_id                  VARCHAR(30),    -- identificador no CRM externo
    cycle_id                 UUID,

    -- Resultado comercial
    outcome_type             VARCHAR(20)     NOT NULL
                                 CHECK (outcome_type IN ('CLOSED_WON', 'CLOSED_LOST', 'NO_SHOW', 'DISQUALIFIED')),

    -- Scores no momento do outcome (para análise de calibração)
    o_score_at_outcome       DECIMAL(6,5)    CHECK (o_score_at_outcome BETWEEN 0 AND 1),
    c_score_at_outcome       DECIMAL(6,5)    CHECK (c_score_at_outcome BETWEEN 0 AND 1),
    p_score_at_outcome       DECIMAL(6,5)    CHECK (p_score_at_outcome BETWEEN 0 AND 1),
    dominant_hypothesis_at_outcome CHAR(2)   REFERENCES hypothesis_catalog(hypothesis_id) ON DELETE SET NULL,
    operating_mode_at_outcome VARCHAR(30)    CHECK (operating_mode_at_outcome IN ('FULL', 'DELTA_SEARCH', 'DORMANT', 'DISQUALIFIED')),

    -- Fonte e contexto do feedback
    feedback_source          VARCHAR(50),    -- ex.: 'crm_webhook', 'manual_import', 'sales_team'
    feedback_notes           TEXT,

    -- Temporalidade
    received_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),
    processed_at             TIMESTAMPTZ     NULL,   -- NULL até o feedback ser processado pelo modelo

    CONSTRAINT crm_outcome_log_pkey
        PRIMARY KEY (outcome_id),
    CONSTRAINT crm_outcome_log_entity_fkey
        FOREIGN KEY (entity_id) REFERENCES entity_nodes(entity_id) ON DELETE RESTRICT
);

COMMENT ON TABLE crm_outcome_log IS
    'Feedback loop CRM. Registra outcomes comerciais para calibração dos SRS e priors. '
    'processed_at NULL indica que o feedback ainda não foi processado pelo motor de atualização. '
    'CLOSED_WON incrementa true_positives; CLOSED_LOST incrementa false_positives em source_reliability.';
```

---

## 3. Índices de Alta Performance

```sql
-- =============================================================================
-- ÍNDICES B-TREE — entity_nodes
-- =============================================================================

-- Filtro primário por tipo e segmento (queries de ranqueamento por segmento)
CREATE INDEX idx_entity_nodes_type_segment
    ON entity_nodes (entity_type, segment);

-- Lookup por CNPJ (deduplicação e enriquecimento)
CREATE INDEX idx_entity_nodes_cnpj
    ON entity_nodes (cnpj)
    WHERE cnpj IS NOT NULL;

-- Filtro de leads ativos por tipo (queries operacionais mais frequentes)
CREATE INDEX idx_entity_nodes_active
    ON entity_nodes (is_active, entity_type)
    WHERE is_active = TRUE;

-- Ordenação por qualidade e recência (monitoramento de degradação de dados)
CREATE INDEX idx_entity_nodes_quality
    ON entity_nodes (data_quality_flag, last_updated_at DESC);


-- =============================================================================
-- ÍNDICES B-TREE — entity_edges (multi-hop traversal)
-- =============================================================================

-- Traversal a partir da origem: "quais arestas saem deste nó?"
CREATE INDEX idx_edges_source
    ON entity_edges (source_entity_id, edge_type);

-- Traversal a partir do destino: "quais arestas chegam neste nó?"
CREATE INDEX idx_edges_target
    ON entity_edges (target_entity_id, edge_type);

-- Ordenação por peso dentro de um tipo (selecionar arestas mais fortes)
CREATE INDEX idx_edges_type_weight
    ON entity_edges (edge_type, weight DESC);

-- Índice composto para algoritmo de Dijkstra na V1 — cobre source+target+type+weight
-- em uma única varredura de índice sem heap fetch para queries de traversal
CREATE INDEX idx_edges_multihop
    ON entity_edges (source_entity_id, target_entity_id, edge_type, weight DESC);


-- =============================================================================
-- ÍNDICES B-TREE — observed_evidence (Camada 1)
-- =============================================================================

-- Recuperação de evidências por entidade e tipo (query mais comum na Camada 1)
CREATE INDEX idx_evidence_entity_type
    ON observed_evidence (entity_id, evidence_type);

-- Ordenação cronológica por ciclo (reconstrução de estado por ciclo)
CREATE INDEX idx_evidence_cycle
    ON observed_evidence (cycle_id, collected_at DESC);

-- Evidências vinculadas a hipóteses e sua classificação (atualização bayesiana)
CREATE INDEX idx_evidence_hypothesis
    ON observed_evidence (hypothesis_linked, classification)
    WHERE hypothesis_linked IS NOT NULL;

-- Evidências stale: frescor < 0.30 (alerta de dados desatualizados)
CREATE INDEX idx_evidence_freshness
    ON observed_evidence (freshness_current)
    WHERE freshness_current < 0.30;


-- =============================================================================
-- ÍNDICES B-TREE — analytical_feature_store (queries de ranking)
-- =============================================================================

-- Ordenação de ranking: P_score DESC com O_score e C_score como tiebreakers
CREATE INDEX idx_features_pscore
    ON analytical_feature_store (p_score DESC, o_score DESC, c_score DESC);

-- Ranking por ciclo específico (re-ranking histórico ou comparação entre ciclos)
CREATE INDEX idx_features_cycle
    ON analytical_feature_store (cycle_id, p_score DESC);

-- Segmentação de leads por qualidade com ranking interno
CREATE INDEX idx_features_quality
    ON analytical_feature_store (data_quality_flag, p_score DESC);


-- =============================================================================
-- ÍNDICES GIN — Trigrama (Jaro-Winkler / fuzzy matching de nomes)
-- =============================================================================

-- Busca fuzzy de nome canônico — deduplicação e enriquecimento por similaridade
CREATE INDEX idx_entity_nodes_name_trgm
    ON entity_nodes
    USING gin (canonical_name gin_trgm_ops);

-- Busca fuzzy de Instagram handle — match parcial e deduplicação
CREATE INDEX idx_entity_nodes_instagram_trgm
    ON entity_nodes
    USING gin (instagram_handle gin_trgm_ops)
    WHERE instagram_handle IS NOT NULL;


-- =============================================================================
-- ÍNDICES PARCIAIS — Observabilidade e Triagem Operacional
-- =============================================================================

-- Leads em modo DELTA_SEARCH — monitoramento de reativação
CREATE INDEX idx_pruned_delta_active
    ON pruned_reason_log (mode_transition_to, generated_at DESC)
    WHERE mode_transition_to = 'DELTA_SEARCH';

-- Conflitos pendentes de revisão manual — triagem operacional
CREATE INDEX idx_conflicts_manual
    ON conflict_resolution_log (requires_manual_review, detected_at DESC)
    WHERE requires_manual_review = TRUE;

-- Hipóteses ativas por entidade com ordenação por probabilidade posterior
CREATE INDEX idx_hypotheses_active
    ON evaluated_hypotheses (entity_id, posterior_probability DESC)
    WHERE status = 'ACTIVE';
```

---

## 4. View de Observabilidade Cognitiva

A view `v_cognitive_observability` agrega métricas operacionais e epistêmicas por dia. Serve como painel de controle de saúde do sistema: qualidade dos dados, distribuição de P_score, custos de coleta, conflitos detectados e hipóteses ativas. Projetada para consumo por dashboards de monitoramento (Metabase, Grafana, ou similar).

```sql
CREATE OR REPLACE VIEW v_cognitive_observability AS
SELECT
    DATE_TRUNC('day', oe.collected_at)                          AS day,

    -- VOLUME DE PROCESSAMENTO
    COUNT(DISTINCT oe.entity_id)                                AS leads_processed,
    COUNT(DISTINCT CASE
        WHEN en.data_quality_flag = 'NORMAL'   THEN oe.entity_id
    END)                                                        AS leads_full_quality,
    COUNT(DISTINCT CASE
        WHEN en.data_quality_flag = 'DEGRADED' THEN oe.entity_id
    END)                                                        AS leads_degraded,
    COUNT(DISTINCT prl.entity_id)                               AS leads_pruned,

    -- SCORES MÉDIOS DO DIA
    AVG(afs.p_score)                                            AS avg_p_score,
    AVG(afs.o_score)                                            AS avg_o_score,
    AVG(afs.c_score)                                            AS avg_c_score,

    -- DISTRIBUIÇÃO DE PRIORIDADE (bandas de P_score)
    COUNT(DISTINCT CASE
        WHEN afs.p_score >= 0.65                 THEN afs.entity_id
    END)                                                        AS leads_priority_action,    -- ação imediata
    COUNT(DISTINCT CASE
        WHEN afs.p_score >= 0.45
         AND afs.p_score <  0.65                 THEN afs.entity_id
    END)                                                        AS leads_monitor,            -- acompanhamento
    COUNT(DISTINCT CASE
        WHEN afs.p_score <  0.25                 THEN afs.entity_id
    END)                                                        AS leads_disqualified,       -- descarte

    -- CUSTOS DE COLETA
    AVG(sl.cost_brl)                                            AS avg_cost_per_search,
    SUM(sl.cost_brl)                                            AS total_cost_brl,

    -- QUALIDADE DE EVIDÊNCIAS
    AVG(afs.feat_e_fresh)                                       AS avg_evidence_freshness,

    -- CONFLITOS DE DADOS
    COUNT(DISTINCT crl.conflict_id)                             AS conflicts_detected,
    COUNT(DISTINCT CASE
        WHEN crl.requires_manual_review = TRUE   THEN crl.conflict_id
    END)                                                        AS conflicts_manual_review,

    -- HIPÓTESES ATIVAS (sinais de ICP)
    COUNT(DISTINCT CASE
        WHEN eh.status = 'ACTIVE'
         AND eh.hypothesis_id = 'H2'             THEN eh.entity_id
    END)                                                        AS h2_centralizacao_active,  -- gestora sobrecarregada/centralizando
    COUNT(DISTINCT CASE
        WHEN eh.status = 'ACTIVE'
         AND eh.hypothesis_id = 'H1'             THEN eh.entity_id
    END)                                                        AS h1_expansao_active         -- empresa em expansão

FROM observed_evidence oe
JOIN entity_nodes en
    ON oe.entity_id = en.entity_id
LEFT JOIN analytical_feature_store afs
    ON oe.entity_id = afs.entity_id
LEFT JOIN pruned_reason_log prl
    ON  oe.entity_id  = prl.entity_id
    AND DATE_TRUNC('day', prl.generated_at) = DATE_TRUNC('day', oe.collected_at)
LEFT JOIN search_logs sl
    ON sl.cycle_id = oe.cycle_id
LEFT JOIN conflict_resolution_log crl
    ON  crl.entity_id  = oe.entity_id
    AND DATE_TRUNC('day', crl.detected_at) = DATE_TRUNC('day', oe.collected_at)
LEFT JOIN evaluated_hypotheses eh
    ON  eh.entity_id = oe.entity_id
    AND DATE_TRUNC('day', eh.last_updated_at) = DATE_TRUNC('day', oe.collected_at)

GROUP BY DATE_TRUNC('day', oe.collected_at)
ORDER BY day DESC;

COMMENT ON VIEW v_cognitive_observability IS
    'Painel de observabilidade cognitiva diária. Agrega volume de processamento, '
    'distribuição de P_score, custos de coleta, qualidade de evidências, conflitos '
    'e hipóteses ativas por dia. Consumido por dashboards de monitoramento operacional.';
```

---

*Fim do SDD-06 — Database Schema & Graph-Ready DDL*
