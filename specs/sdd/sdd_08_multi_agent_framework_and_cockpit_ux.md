# SDD-08 — Multi-Agent Framework e Cockpit UX
## SocialSelling Intelligence System

**Versão:** 1.0.0
**Data:** 2026-06-01
**Status:** Aprovado para Implementação
**Autor:** Arquitetura de Sistema — SocialSelling

---

## Sumário

1. [Topologia de Coordenação Multiagente — Blackboard Architecture](#1-topologia-de-coordenação-multiagente--blackboard-architecture)
   - 1.1 [O Padrão Quadro Negro (Blackboard Architecture) sobre LangGraph](#11-o-padrão-quadro-negro-blackboard-architecture-sobre-langgraph)
   - 1.2 [Contrato Operacional — Scout Agent](#12-contrato-operacional--scout-agent)
   - 1.3 [Contrato Operacional — Triage Agent](#13-contrato-operacional--triage-agent)
   - 1.4 [Contrato Operacional — Copywriter Agent (SDR de Elite)](#14-contrato-operacional--copywriter-agent-sdr-de-elite)
2. [Design de Interface de API (DX Ergonomics)](#2-design-de-interface-de-api-dx-ergonomics)
   - 2.1 [Princípios de Design de Payloads](#21-princípios-de-design-de-payloads)
   - 2.2 [Especificação dos Endpoints FastAPI](#22-especificação-dos-endpoints-fastapi)
   - 2.3 [Estrutura de Nesting do JSON e Justificativa](#23-estrutura-de-nesting-do-json-e-justificativa)
3. [UX do Operator Cockpit](#3-ux-do-operator-cockpit)
   - 3.1 [Hierarquia Visual Orientada às 3 Perguntas Cardinais](#31-hierarquia-visual-orientada-às-3-perguntas-cardinais)
   - 3.2 [Princípios de Mitigação de Fadiga Cognitiva](#32-princípios-de-mitigação-de-fadiga-cognitiva)
4. [Gestão de Falhas e Incerteza na UX](#4-gestão-de-falhas-e-incerteza-na-ux)
   - 4.1 [Modos Degradados e Alertas Visuais](#41-modos-degradados-e-alertas-visuais)
   - 4.2 [Leads com C_score Baixo (< 0.35)](#42-leads-com-c_score-baixo--035)
   - 4.3 [Blueprint Parcial (partial:true)](#43-blueprint-parcial-partialtrue)
   - 4.4 [Contraindications — Anti-Patterns de Abordagem](#44-contraindications--anti-patterns-de-abordagem)

---

## 1. TOPOLOGIA DE COORDENAÇÃO MULTIAGENTE — BLACKBOARD ARCHITECTURE

### 1.1 O Padrão Quadro Negro (Blackboard Architecture) sobre LangGraph

#### Definição do Padrão

A Blackboard Architecture (Arquitetura de Quadro Negro) é um padrão de design de sistemas multi-agente no qual múltiplos agentes especialistas independentes colaboram para resolver um problema complexo através de um espaço de estado compartilhado e centralizado — o "quadro negro". Nenhum agente se comunica diretamente com outro. Toda a colaboração ocorre via leitura e escrita no estado compartilhado, mediada pelo Orchestrator.

#### O LangGraph como Quadro Negro

No sistema SocialSelling, o **LangGraph representa o quadro negro**: o `LeadState` (dicionário Python/TypedDict descrito no SDD-07) é o espaço de estado global compartilhado, acessível a todos os agentes especialistas que operam como nós do grafo. O grafo é o mecanismo de controle que define quais agentes têm acesso de escrita em quais momentos.

**Propriedades fundamentais do quadro negro no SocialSelling:**

1. **Estado global compartilhado:** O `LeadState` é a única fonte de verdade durante a execução da saga. Todos os agentes leem do mesmo estado e escrevem de volta ao mesmo estado. Não existem canais de comunicação ponto-a-ponto entre agentes.

2. **Isolamento de leitura/escrita por step:** Cada nó do LangGraph tem permissão de escrita apenas sobre os campos do `LeadState` que são sua responsabilidade. O Scout Agent escreve em `evidence_batch`, `entity_nodes` e `entity_edges`. O Triage Agent escreve em `inferences`, `hypotheses`, `committee` e `scores`. O Copywriter Agent escreve em `blueprint`. Isso previne condições de corrida e viola- ções de responsabilidade.

3. **Memória volátil durante a saga:** O `LeadState` existe em memória RAM durante a execução. Apenas o PersistenceNode transcreve o estado final para o banco de dados permanente. Isso maximiza a velocidade de processamento inter-step e evita I/O desnecessário.

4. **Orchestrator como controlador de fluxo:** O `LeadHydrationSaga` (Orchestrator) é o único agente que controla a sequência de execução e as bordas condicionais do grafo. Nenhum agente especialista pode invocar outro agente diretamente — apenas o Orchestrator pode avançar o grafo para o próximo nó.

#### Diagrama da Topologia

```
                    ╔══════════════════════════════════════════╗
                    ║         LEADSTATE (Quadro Negro)          ║
                    ║   Estado global compartilhado em memória  ║
                    ║                                           ║
                    ║  evidence_batch    entity_nodes           ║
                    ║  inferences        hypotheses             ║
                    ║  committee         scores                 ║
                    ║  blueprint         audit_trail            ║
                    ╚══════════════════════════════════════════╝
                         ▲ R/W       ▲ R/W        ▲ R/W
                         │           │             │
              ┌──────────┘  ┌────────┘   ┌─────────┘
              │             │            │
    ╔═════════════╗  ╔═════════════╗  ╔═════════════════╗
    ║ Scout Agent ║  ║ Triage Agent║  ║Copywriter Agent ║
    ║  (M1 + M2)  ║  ║ (M3+M4+M5p)║  ║   (M5 CBG)      ║
    ╚═════════════╝  ╚═════════════╝  ╚═════════════════╝
              │             │             │
              └──────┬───────┘─────────────┘
                     │
            ╔════════════════╗
            ║  ORCHESTRATOR  ║
            ║ LeadHydration  ║  ← Único controlador de fluxo
            ║     Saga       ║    Gerencia bordas condicionais
            ╚════════════════╝    Registra compensações
```

---

### 1.2 Contrato Operacional — Scout Agent

**Definição:** O Scout Agent é o agente especialista responsável pela fase de descoberta e coleta de evidências (Módulos M1 e M2). É o primeiro agente a operar sobre um `LeadState` vazio ou parcialmente populado (no caso de Delta Search reativada).

**Responsabilidade Principal:** Maximizar a cobertura de evidências de alta qualidade para cada lead da seed list, respeitando o orçamento FinOps do ciclo ativo, os limites dos modos degradados e as regras de resolução de entidade.

**Metas Quantificáveis:**
- Coletar ao menos 2 fontes ativas por lead em modo FULL
- Manter custo por lead abaixo de `budget_brl / seed_count` (budget per-lead)
- Resolver entidade com `rcs_score >= 0.85` para ao menos 70% dos leads do ciclo
- Produzir ao menos 1 evidência `SUPPORTING` por lead por ciclo

**Ferramentas Disponíveis:**

| Ferramenta | Responsabilidade | Timeout | Modo Degradado |
|------------|-----------------|---------|----------------|
| `instagram_scraper` | Coleta posts, bio, engagement, hashtags de perfis Instagram | 30s | DEGRADED_INSTAGRAM: cache TTL-24h, t½=12h |
| `linkedin_scraper` | Coleta cargo, headcount, vagas, artigos de perfis LinkedIn | 30s | DEGRADED_LINKEDIN: u+=0.20, sem retry |
| `cnpj_resolver` | Consulta dados cadastrais completos via CNPJ na Receita Federal | 15s | Sem degradação — dado público e estável |
| `query_builder` | Constrói queries otimizadas de busca com base na keyword taxonomy do ICP contract | Síncrono | N/A |
| `jaro_winkler_scorer` | Calcula similaridade de strings para entity resolution | Síncrono | N/A |
| `rrfusion_engine` | Combina rankings de múltiplos critérios via Reciprocal Rank Fusion | Síncrono | N/A |
| `graph_writer` | Persiste `entity_nodes` e `entity_edges` no banco PostgreSQL | 5s | Retry 3x backoff |
| `freshness_decay_scheduler` | Agenda jobs de atualização de `E_fresh` para evidências com TTL curto | Síncrono | N/A |

**Inputs do Agente:**
- `icp_contract`: contrato ativo com `seed_list`, `anchor_profiles`, `keyword_taxonomy`, `segments`, `budget_brl`
- `LeadState`: vazio no início de um ciclo FULL; parcialmente populado (com evidências anteriores em cache) no início de um ciclo Delta Search reativado

**Outputs do Agente (campos escritos no LeadState):**
- `LeadState.evidence_batch`: lista de `ObservedEvidence` coletadas e normalizadas
- `LeadState.entity_nodes`: mapa de entidades resolvidas com campos `canonical_*`
- `LeadState.entity_edges`: arestas de merge (MERGE) e conflito (CONFLICT) entre entidades
- `LeadState.inferences`: inferências iniciais de Layer 2 geradas a partir das evidências brutas
- Entradas em `conflict_resolution_log` (banco) para conflitos não resolvidos
- Atualização de `compensation_executed[]` quando compensações C-01, C-02, C-03 ou C-04 são ativadas

**Barramentos de Memória:**
- **Cache Redis L1 (leitura/escrita):** TTL=6h para respostas de scrapers em modo FULL; TTL=24h para cache de fallback em DEGRADED_INSTAGRAM. Keys: `evidence:instagram:{lead_id}:last`, `evidence:linkedin:{lead_id}:last`
- **Write-through para `observed_evidence` (Layer 1):** escrita imediata no banco PostgreSQL via INSERT append-only — a Layer 1 nunca é lida novamente pelo Scout Agent; apenas persiste para auditoria e consumo pelos agentes subsequentes

**Critérios de Sucesso do Agente:**
- `operating_mode` em qualquer estado funcional (FULL, DEGRADED_LINKEDIN, DEGRADED_INSTAGRAM) com ao menos 1 fonte ativa
- Ao menos 1 `ObservedEvidence` com `classification='SUPPORTING'` (após pré-classificação inicial)
- `entity_id` resolvido com `rcs_score >= 0.65` para ao menos 1 entidade (ou conflito documentado para auditoria)
- `steps_completed` inclui `SeedIngestionNode`, `ScrapingNode`, `NormalizationNode`, `EntityResolutionNode`, `InferenceNode`

**Critérios de Falha do Agente:**
- `operating_mode = "CACHE_ONLY"` com cache vazio + CNPJ falhando → Compensação C-03 completa ativada; agente encerra sua fase, passa o estado para o Triage Agent com o mínimo disponível
- Zero evidências após todas as compensações → lead marcado `error_state=true`, enfileirado em DLQ

**Invariantes do Agente (não podem ser violados):**
- O Scout Agent NUNCA modifica `inferences` geradas por ciclos anteriores — apenas adiciona novas com `version > 1` e `superseded_by` no registro antigo
- O Scout Agent NUNCA calcula scores — essa responsabilidade pertence exclusivamente ao Triage Agent
- O Scout Agent NUNCA gera blueprints — essa responsabilidade pertence exclusivamente ao Copywriter Agent

---

### 1.3 Contrato Operacional — Triage Agent

**Definição:** O Triage Agent é o agente especialista responsável pela fase de scoring e priorização (Módulos M3, M4 e M5 parcial — exceto o CBG). Opera sobre o `LeadState` já populado pelo Scout Agent com evidências e inferências.

**Responsabilidade Principal:** Maximizar a separabilidade do ranking entre leads do ciclo, identificar o membro do comitê de compras com maior momentum (SC/BMO) com a maior confiança possível, e detectar janelas de urgência através de trigger events ativos.

**Metas Quantificáveis:**
- Calcular `P_score` para 100% dos leads do ciclo (mesmo que degradado)
- Identificar BMO com `confidence >= 0.60` para ao menos 50% dos leads com `committee.completeness >= 1`
- Produzir `dominant_hypothesis` com `posterior > 0.25` para ao menos 60% dos leads do ciclo
- Manter separabilidade de ranking: desvio padrão de `P_score` entre leads do ciclo >= 0.10 (se todos iguais, ranking é inútil)

**Ferramentas Disponíveis:**

| Ferramenta | Responsabilidade | Input Principal | Output Principal |
|------------|-----------------|----------------|-----------------|
| `bayes_updater` | Executa atualização bayesiana sobre hipóteses com Subjective Logic | `inferences[]`, `hypotheses{}` com priors | `hypotheses{}` com posteriors atualizados |
| `evidence_classifier` | Reclassifica inferências em SUPPORTING/CONTRADICTING/NEUTRAL se necessário (step de revisão) | `inferences[]`, `dominant_hypothesis` | `inferences[]` reclassificadas |
| `subjective_logic_engine` | Propaga incerteza via tripla (belief, disbelief, uncertainty) | Posteriors calculados, `u_additive` | Tripla completa por hipótese |
| `persona_scorer` | Classifica perfis como SC/BMO/INFLUENCER com score de confiança | Perfis LinkedIn/Instagram, `entity_nodes` | `committee_members[]` com roles |
| `momentum_cluster_engine` | Calcula `bmo_momentum_score` via clustering de atividade recente | Posts, interações, mudanças de cargo 90d | `bmo_momentum_score` float ou null |
| `trigger_event_detector` | Detecta e classifica trigger events por urgência | `evidence_batch[]`, feeds de mudança | `trigger_events[]` com urgency_level |
| `matrix_rank_function` | Executa `MatrixRankFunction` para calcular P_score final | `O_score`, `C_score` | `P_score`, `rank_position`, `action_label` |
| `feature_store_writer` | Persiste scores e features calculadas no Feature Store PostgreSQL | `ScoreVector`, `committee_map` | Confirmação de persistência |

**Inputs do Agente:**
- `LeadState.inferences`: inferências da Layer 2 geradas pelo Scout Agent (leitura apenas)
- `LeadState.entity_nodes`: entidades resolvidas com `rcs_score` e `u_additive` (leitura apenas)
- `LeadState.hypotheses`: hipóteses com priors carregados do ICP contract (leitura inicial, escrita dos posteriors)
- Priors do `icp_contract`: pesos iniciais das hipóteses e parâmetros de scoring

**Outputs do Agente (campos escritos no LeadState):**
- `LeadState.hypotheses`: hipóteses com `posterior`, tripla Subjective Logic, `status` e `hypothesis_confidence` atualizados
- `LeadState.dominant_hypothesis`: hipótese com maior `posterior` entre as ACTIVE (ou melhor CANDIDATE)
- `LeadState.committee`: `CommitteeMap` completo com `bmo`, `sc`, `influencers`, `completeness`
- `LeadState.scores`: `ScoreVector` completo com todos os componentes intermediários e `P_score` final
- Escrita em banco: `evaluated_hypotheses` (Layer 3), `committee_members`, `score_snapshots`, `analytical_feature_store`

**Barramentos de Memória:**
- **Leitura de `generated_inferences` (Layer 2):** o Triage Agent lê as inferências versionadas da Layer 2 no banco para garantir consistência com o estado persisto anteriormente (especialmente em Delta Search reativada, onde evidências anteriores podem estar no banco mas não no `evidence_batch` em memória)
- **Escrita em `evaluated_hypotheses` (Layer 3):** via `ON CONFLICT DO UPDATE` — sempre mantém a versão mais recente do ciclo ativo
- **Escrita em `committee_members`:** via `ON CONFLICT (entity_id, cycle_id, role) DO UPDATE`
- **Escrita em `analytical_feature_store`:** via `UPSERT` com scores calculados — consumido pela API `GET /api/v1/leads`

**Critérios de Sucesso do Agente:**
- `P_score` calculado como float determinístico no range `[0.0, 1.0]` para 100% dos leads processados
- BMO identificado com `bmo_momentum_score` definido (mesmo que `null` = UNKNOWN — não penaliza)
- `Hypothesis_Confidence > 0.0` para todos os leads (pode ser muito baixo, mas não zero)
- `steps_completed` inclui `HypothesisNode`, `CommitteeNode`, `ScoringNode`

**Critérios de Falha do Agente:**
- `P_score` não calculável (componente `NaN` ou divisão por zero) → lead marcado `error_state=true`, Compensação C-08 ativada
- Falha na escrita do Feature Store após 3 retries → Compensação C-08, enfileirar em DLQ

**Invariantes do Agente (não podem ser violados):**
- O Triage Agent NUNCA modifica `observed_evidence` da Layer 1 — esses dados são imutáveis após o Scout Agent
- O Triage Agent NUNCA gera o `ConversationBlueprint` — apenas prepara todos os inputs necessários para o Copywriter Agent
- As fórmulas de scoring (`O_score`, `C_score`, `P_score`) são executadas exatamente como especificadas nas fórmulas canônicas — sem aproximações ou atalhos

---

### 1.4 Contrato Operacional — Copywriter Agent (SDR de Elite)

**Definição:** O Copywriter Agent é o agente especialista responsável pela geração do `ConversationBlueprint` (Módulo M5 CBG). Não é um "gerador de texto genérico" — é projetado para agir como um SDR de Elite que conhece profundamente o ICP do SocialSelling e o vocabulário específico de cada setor-alvo.

**Responsabilidade Principal:** Produzir um `ConversationBlueprint` contextualmente preciso, determinístico e acionável que minimize o ruído cognitivo do operador comercial — eliminando a necessidade de pesquisa adicional antes da primeira abordagem.

**Filosofia de Geração:** O blueprint é a resposta à Pergunta Cardinal 3 — "O que falar?". Cada componente é projetado para eliminar atrito entre o insight (score) e a ação (abordagem). O Copywriter Agent não inventa — ele sintetiza e articula o que já está nos dados coletados e pontuados.

**Metas Quantificáveis:**
- 100% dos blueprints gerados com ao menos `hook`, `context_trigger` e `cta_suggestion` populados
- 100% dos blueprints com ao menos 1 item em `contraindications`
- Cobertura de setor: 4 vocabulários distintos implementados (Advocacia Corporativa, Consultoria, SaaS/Software House, Engenharia)
- `partial=false` para leads com `dominant_hypothesis.posterior >= 0.25` e `committee.completeness >= 1`

**Ferramentas Disponíveis:**

| Ferramenta | Responsabilidade |
|------------|-----------------|
| `xai_payload_builder` | Constrói o XAI Unified Payload completo integrando todos os campos do LeadState; contém o sub-componente CBG |
| `cbg_engine` (sub-componente do xai_payload_builder) | Gera cada um dos 5 componentes do ConversationBlueprint com adaptação ao setor-alvo |
| `sector_vocabulary_selector` | Seleciona o vocabulário e os frames narrativos corretos com base no segmento inferido do lead |
| `contraindication_generator` | Gera a lista de anti-patterns de abordagem com base na hipótese dominante, setor e contexto comportamental detectado |
| `partial_blueprint_handler` | Gerencia a geração de blueprints parciais quando `posterior < 0.25`, populando `missing_fields` com razões em linguagem de negócio |

**Inputs do Agente:**
- `LeadState.dominant_hypothesis`: hipótese ACTIVE ou melhor CANDIDATE com `posterior`, `belief`, `uncertainty` (leitura apenas)
- `LeadState.committee`: `CommitteeMap` com `bmo`, `sc`, trigger events e `urgency_level` (leitura apenas)
- `LeadState.inferences`: inferências classificadas como `SUPPORTING` com `PAIN_SIGNAL` e `URGENCY_SIGNAL` (leitura apenas)
- `LeadState.scores`: `P_score`, `O_score`, `C_score`, `action_label` já calculados (leitura apenas)
- `LeadState.entity_nodes`: `canonical_name`, segmento inferido, `operating_mode` (leitura apenas)
- Evidências SUPPORTING da Layer 1 no banco (para extração de citações e referências factuais)

**Outputs do Agente (campos escritos no LeadState):**
- `LeadState.blueprint`: `ConversationBlueprint` completo (ou parcial com flags)
- Escrita em banco: `analytical_feature_store.approach_blueprint`, `blueprint_log`

**Barramentos de Memória:**
- **Read-only sobre `evaluated_hypotheses` (Layer 3):** o Copywriter Agent lê hipóteses mas nunca modifica scores ou posteriors
- **Read-only sobre `committee_members`:** lê o comitê para extrair contexto do BMO (cargo, trigger events, momentum)
- **Read-only sobre `observed_evidence` (Layer 1):** busca evidências específicas que corroboram o Pain Narrative e a Credibility Anchor (busca por `evidence_id` referenciados nas inferences SUPPORTING)
- **Write para `analytical_feature_store.approach_blueprint`:** único campo escrito pelo Copywriter Agent no banco de persistência

**Estrutura de Geração dos 5 Componentes do Blueprint:**

**1. Hook** — Frase de abertura de alta relevância contextual
- Derivado do trigger event de maior `urgency_level` ativo para o BMO/SC
- Contém referência específica ao evento detectado (não genérico)
- `urgency_level` derivado diretamente dos trigger events: ao menos 1 trigger `ALTA` → urgency_level=`ALTA`; apenas triggers `MEDIA` → urgency_level=`MEDIA`; apenas `BAIXA` ou sem triggers → urgency_level=`BAIXA`
- Vocabulário adaptado ao setor: Advocacia usa termos como "mandatos", "carteira de clientes corporativos", "captação"; SaaS usa "churn", "MRR", "pipeline de vendas"; Consultoria usa "projetos", "capacidade da equipe", "entregas"

**2. Context Trigger** — Evento específico que justifica o contato agora
- Referência factual ao evento detectado nas evidências (ex: "Identificamos 3 novas vagas abertas para área jurídica nos últimos 30 dias no LinkedIn da empresa")
- Inclui fonte do evento e data de detecção
- Proibido texto genérico sem referência a evento concreto — se nenhum trigger event detectado, campo fica com texto default de segmento mas com `confidence` baixo marcado

**3. Pain Narrative** — Narrativa da dor em primeira pessoa da empresa alvo
- Escrita como se a própria fundadora ou BMO estivesse articulando a dor internamente
- Ex (Advocacia): "Nosso escritório cresceu de 5 para 18 advogados em 18 meses e os processos de captação de novos mandatos ainda são 100% relacionais — dependemos de indicações e de networking individual. Não temos visibilidade de qual perfil de cliente fecha mais rápido e tem menor custo de captação."
- Baseada exclusivamente nos `PAIN_SIGNAL` classificados nas inferências SUPPORTING — não inventa dores não evidenciadas
- `null` quando `dominant_hypothesis.posterior < 0.25` (Compensação C-06)

**4. Credibility Anchor** — Evidência concreta de resultado análogo
- Referência a resultado verificável de empresa similar (mesmo setor, porte próximo, desafio análogo)
- Inclui métrica quando disponível no `icp_contract.anchor_profiles` ou no banco de resultados históricos
- Ex: "Escritórios de Advocacia Corporativa com 15-25 advogados que adotaram inteligência de prospecção estruturada reduziram o tempo de qualificação de prospect em 60% nos primeiros 90 dias"
- `null` quando `dominant_hypothesis.posterior < 0.25` (Compensação C-06)

**5. CTA Suggestion** — Canal recomendado + mensagem de abertura + contraindications
- Canal derivado do campo de maior `Reachability` nas evidências: `LINKEDIN_DM` se `canonical_linkedin_url` presente e `bmo_momentum_score` ativo; `EMAIL` como fallback; `INSTAGRAM_DM` apenas para segmentos com alta presença Instagram
- `message_draft`: rascunho de mensagem de abertura de 3-5 frases, adaptado ao canal e ao setor
- `contraindications`: lista de 1 a 5 anti-patterns de abordagem específicos ao contexto do lead — OBRIGATÓRIO ao menos 1 item mesmo em blueprints parciais

**Adaptação de Vocabulário por Setor:**

| Setor | Vocabulário Chave | Frame Narrativo | CTA Preferencial |
|-------|------------------|----------------|-----------------|
| Advocacia Corporativa | mandatos, carteira, sócios, captação, clientes corporativos, escritório | Crescimento de carteira + eficiência de captação | LinkedIn DM para sócia fundadora |
| Consultoria | projetos, capacidade, entregas, clientes, metodologia, proposta | Capacidade de venda + qualidade de pipeline | Email direto para sócia/diretora |
| Software House / SaaS | MRR, churn, pipeline, demos, ARR, onboarding, LTV | Qualificação de pipeline + redução de CAC | LinkedIn DM para CEO/founder |
| Engenharia | projetos, escopo, equipe técnica, contratantes, licitações, CAPEX | Prospecção de contratos + relacionamento com contratante | Email + LinkedIn combo |

**Critérios de Sucesso do Agente:**
- `blueprint != null` em 100% das execuções (pode ser parcial, mas NUNCA null)
- Ao menos `hook`, `context_trigger` e `cta_suggestion` populados em qualquer modo
- `cta_suggestion.contraindications` com ao menos 1 item em qualquer modo
- Vocabulário adaptado ao setor correto (verificável por presença de termos do vocabulário correspondente)

**Critérios de Falha Parcial (não fatal):**
- `dominant_hypothesis.posterior < 0.25` → Compensação C-06: `partial=true`, `pain_narrative=null`, `credibility_anchor=null` com `reason` em linguagem de negócio (não técnica para o operador)
- `data_quality_warning=true` quando `operating_mode != "FULL"` — visível para o operador no Cockpit

**Critérios de Falha Fatal:**
- Exceção não tratada no CBG → Compensação C-08: `blueprint=null` com `error_state=true`, `reason` registrada em `errors[]`

**Invariantes do Agente (não podem ser violados):**
- O Copywriter Agent NUNCA altera scores calculados pelo Triage Agent
- O Copywriter Agent NUNCA inventa evidências — toda afirmação no blueprint deve ser rastreável a um `evidence_id` na Layer 1 ou a um `anchor_profile` do ICP contract
- As `contraindications` DEVEM ser específicas ao contexto do lead — frases genéricas como "não seja agressivo" são proibidas

---

## 2. DESIGN DE INTERFACE DE API (DX ERGONOMICS)

### 2.1 Princípios de Design de Payloads

A API do SocialSelling é projetada segundo os princípios de DX Ergonomics (Developer Experience Ergonomics) — cada payload deve minimizar o esforço cognitivo necessário para consumir e interpretar os dados, tanto para integrações de software quanto para leitura humana via ferramentas de debug.

**Princípio 1: Payloads Autoexplicativos**
O payload de score não retorna apenas o valor numérico — retorna também a fórmula que o gerou e os componentes que o compõem. Um engenheiro de integração nunca precisa consultar documentação externa para entender o que um número significa.

```json
"scores": {
  "p_score": {
    "value": 0.7412,
    "formula": "O_score × (1 - 0.60 × e^(-4.0 × C_score))",
    "components": {
      "o_score": {
        "value": 0.8130,
        "formula": "(0.45×Fit + 0.35×S_intent + 0.20×Reachability) × E_fresh",
        "components": {
          "fit": 0.8500,
          "s_intent": 0.7200,
          "reachability": 0.9000,
          "e_fresh": 0.9440
        }
      },
      "c_score": {
        "value": 0.6210,
        "formula": "RCS × C_s × (1 - Uncertainty_Committee) × Hypothesis_Confidence × ∏SRS_k",
        "components": {
          "rcs": 0.9200,
          "c_s": 0.6667,
          "uncertainty_committee": 0.1500,
          "hypothesis_confidence": 0.7800,
          "srs_product": 0.8300
        }
      }
    }
  }
}
```

**Princípio 2: Nesting Semântico**
Campos relacionados são agrupados sob chaves de namespace semântico, não espalhados em estrutura flat. Evita colisão de namespace (`o_score` vs `p_score` como campos irmãos com nomes similares) e permite que consumidores de front-end extraiam apenas os sub-campos necessários sem parsing defensivo.

**Princípio 3: Tipagem Explícita**
Todos os campos numéricos são retornados em formato decimal com exata notação (`0.7412`, nunca `.74` ou `74.12%`). Campos de data são sempre ISO 8601 com timezone UTC (`2026-06-01T14:32:00Z`). Campos opcionais ausentes são explicitamente `null` (nunca omitidos da resposta).

**Princípio 4: Campos de Rastreabilidade Obrigatórios**
Todo payload retornado pela API inclui os 4 campos de rastreabilidade no nível raiz, independentemente do endpoint:
```json
{
  "lead_id": "LE-2024-00123",
  "generated_at": "2026-06-01T14:32:00Z",
  "cycle_id": "550e8400-e29b-41d4-a716-446655440000",
  "data_quality": {
    "operating_mode": "FULL",
    "degraded": false,
    "e_fresh_score": 0.9440
  }
}
```

**Princípio 5: Separação de Consumidores**
O payload é estruturado para servir três consumidores distintos com necessidades diferentes:
- **Computação (máquina):** `scores` em formato numérico puro, sem texto explicativo
- **Humanos (debug/auditoria):** `xai_drivers` em linguagem natural, separados dos scores
- **Operador comercial (ação):** `approach_blueprint` no nível raiz para acesso imediato

---

### 2.2 Especificação dos Endpoints FastAPI

#### POST /api/v1/cycles

**Propósito:** Iniciar um novo ciclo de busca de leads.

**Request Body:**
```json
{
  "seed_list": [
    "https://www.linkedin.com/company/escritorio-advocacia-exemplo",
    "instagram.com/consultoria_exemplo",
    "12.345.678/0001-90"
  ],
  "icp_contract_id": "550e8400-e29b-41d4-a716-446655440000",
  "budget_brl": 50.00
}
```

**Response 201 Created:**
```json
{
  "cycle_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "STARTED",
  "estimated_leads": 45,
  "estimated_cost_brl": 12.50,
  "created_at": "2026-06-01T14:32:00Z"
}
```

**Response 409 Conflict** (ciclo em progresso para o mesmo ICP contract):
```json
{
  "error": "CYCLE_IN_PROGRESS",
  "message": "Já existe um ciclo IN_PROGRESS para o icp_contract_id informado.",
  "active_cycle_id": "existing-uuid"
}
```

**Response 422 Unprocessable Entity** (ICP contract inativo ou budget insuficiente):
```json
{
  "error": "VALIDATION_ERROR",
  "details": [
    {"field": "icp_contract_id", "message": "ICP contract não encontrado ou status != ACTIVE"},
    {"field": "budget_brl", "message": "Budget mínimo é R$5.00"}
  ]
}
```

**Business Logic:**
1. Valida `icp_contract_id` ativo no banco
2. Verifica ausência de ciclo `IN_PROGRESS` para o mesmo contrato
3. Cria `cycle_id` UUID
4. Insere registro em `search_cycles` com `status='STARTED'`
5. Enfileira `ScrapingJob` em SQS com `cycle_id` e `seed_list`
6. Calcula estimativas de custo e volume com base em histórico do `icp_contract_id`

---

#### GET /api/v1/leads

**Propósito:** Listar leads ranqueados de um ciclo com filtros e paginação.

**Query Parameters:**
- `cycle_id` (UUID, obrigatório): ciclo de busca a consultar
- `min_p_score` (float, opcional, default=0.0): filtro de P_score mínimo
- `segment` (string, opcional): filtro por segmento — `Advocacia`, `Consultoria`, `SaaS`, `Engenharia`
- `action_label` (string, opcional): filtro por label — `PRIORITY_ACTION`, `MONITOR`, `DELTA_SEARCH`, `PRUNED`
- `limit` (int, opcional, default=20, max=100)
- `offset` (int, opcional, default=0)

**Response 200 OK:**
```json
{
  "cycle_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "total_leads": 45,
  "filtered_leads": 12,
  "page": {"limit": 20, "offset": 0},
  "generated_at": "2026-06-01T14:32:00Z",
  "data_quality": {
    "operating_mode": "FULL",
    "degraded": false
  },
  "leads": [
    {
      "lead_id": "LE-2024-00123",
      "company_name": "Escritório Advocacia Exemplo S/S",
      "segment": "Advocacia",
      "headcount_range": "15-25",
      "rank_position": 1,
      "scores": {
        "p_score": 0.7412,
        "o_score": 0.8130,
        "c_score": 0.6210
      },
      "action_label": "PRIORITY_ACTION",
      "data_quality_flag": "NORMAL",
      "dominant_hypothesis": {
        "text": "Escritório em fase de expansão de carteira corporativa com processo de captação manual",
        "posterior": 0.7800,
        "status": "ACTIVE"
      },
      "buying_committee": {
        "bmo_name": "Dra. Ana Lima",
        "bmo_designation": "Sócia Fundadora",
        "bmo_momentum_score": 0.8200,
        "completeness": 2
      },
      "trigger_urgency": "ALTA",
      "last_hydrated_at": "2026-06-01T12:00:00Z"
    }
  ]
}
```

**Ordenação Padrão:** `p_score DESC` — determinístico, sem randomização. Empate: `o_score DESC`, depois `lead_id` lexicográfico.

---

#### GET /api/v1/leads/{lead_id}

**Propósito:** Retornar o XAI Unified Payload completo de um lead específico.

**Response Headers:**
- `X-Degraded-Mode: false` (ou `true` se `operating_mode != "FULL"`)
- `X-Cycle-Id: {UUID do ciclo mais recente}`
- `ETag: sha256:{cycle_id}:{lead_id}:{generated_at}` (para cache condicional)
- `Cache-Control: max-age=300` (5 minutos)

**Response 200 OK — XAI Unified Payload:**
```json
{
  "lead_id": "LE-2024-00123",
  "cycle_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "generated_at": "2026-06-01T14:32:00Z",
  "data_quality": {
    "operating_mode": "FULL",
    "degraded": false,
    "e_fresh_score": 0.9440,
    "sources_active": ["INSTAGRAM", "LINKEDIN", "CNPJ_GOV"],
    "missing_evidence_impact": []
  },
  "target_entity": {
    "company_name": "Escritório Advocacia Exemplo S/S",
    "canonical_cnpj": "12.345.678/0001-90",
    "canonical_linkedin_url": "https://www.linkedin.com/company/escritorio-advocacia-exemplo",
    "canonical_instagram_handle": "@adv_exemplo",
    "segment": "Advocacia",
    "headcount_range": "15-25",
    "monthly_revenue_range": "R$150k-R$300k",
    "city": "São Paulo",
    "state": "SP"
  },
  "scores": {
    "p_score": {
      "value": 0.7412,
      "formula": "O_score × (1 - 0.60 × e^(-4.0 × C_score))",
      "rank_position": 1,
      "action_label": "PRIORITY_ACTION",
      "components": {
        "o_score": {
          "value": 0.8130,
          "formula": "(0.45×Fit + 0.35×S_intent + 0.20×Reachability) × E_fresh",
          "components": {
            "fit": 0.8500,
            "s_intent": 0.7200,
            "reachability": 0.9000,
            "e_fresh": 0.9440
          }
        },
        "c_score": {
          "value": 0.6210,
          "formula": "RCS × C_s × (1 - Uncertainty_Committee) × Hypothesis_Confidence × ∏SRS_k",
          "components": {
            "rcs": 0.9200,
            "c_s": 0.6667,
            "uncertainty_committee": 0.1500,
            "hypothesis_confidence": 0.7800,
            "srs_product": 0.8300
          }
        }
      }
    }
  },
  "xai_drivers": {
    "top_positive_factors": [
      {
        "factor": "Vagas abertas para área jurídica detectadas",
        "impact": "+0.18 no S_intent",
        "evidence_source": "LINKEDIN",
        "detected_at": "2026-05-28T09:15:00Z"
      },
      {
        "factor": "Bio do Instagram menciona expansão de equipe",
        "impact": "+0.12 no Fit",
        "evidence_source": "INSTAGRAM",
        "detected_at": "2026-05-27T14:00:00Z"
      }
    ],
    "top_negative_factors": [
      {
        "factor": "Comitê de compras incompleto — 2/3 membros identificados",
        "impact": "-0.11 no C_score (C_s = 0.6667)",
        "recommendation": "Identificar o terceiro membro do comitê no LinkedIn"
      }
    ],
    "uncertainty_flags": []
  },
  "buying_committee": {
    "completeness": 2,
    "completeness_label": "PARTIAL",
    "members": [
      {
        "member_id": "CM-001",
        "name": "Dra. Ana Lima",
        "role": "BMO",
        "designation": "Sócia Fundadora",
        "linkedin_url": "https://www.linkedin.com/in/ana-lima-adv",
        "bmo_momentum_score": 0.8200,
        "confidence": 0.9100,
        "trigger_events": [
          {
            "event_type": "JOB_POSTING",
            "urgency_level": "ALTA",
            "description": "3 vagas abertas para advogados sênior nos últimos 30 dias",
            "source": "LINKEDIN",
            "detected_at": "2026-05-28T09:15:00Z"
          }
        ]
      },
      {
        "member_id": "CM-002",
        "name": "Dr. Carlos Souza",
        "role": "SC",
        "designation": "Sócio — Direito Empresarial",
        "linkedin_url": "https://www.linkedin.com/in/carlos-souza-adv",
        "bmo_momentum_score": null,
        "confidence": 0.7200,
        "trigger_events": []
      }
    ]
  },
  "hypothesis_evaluation": {
    "dominant_hypothesis": {
      "hypothesis_id": "HYP-001",
      "text": "Escritório em fase de expansão de carteira corporativa com processo de captação manual",
      "posterior": 0.7800,
      "belief": 0.6500,
      "disbelief": 0.0800,
      "uncertainty": 0.2700,
      "hypothesis_confidence": 0.5694,
      "status": "ACTIVE"
    },
    "alternative_hypotheses": [
      {
        "text": "Escritório buscando ferramentas de gestão processual",
        "posterior": 0.2100,
        "status": "CANDIDATE"
      }
    ]
  },
  "approach_blueprint": {
    "hook": {
      "text": "Identificamos que o Escritório Advocacia Exemplo abriu 3 posições de advogado sênior nos últimos 30 dias — um sinal claro de expansão de carteira. Empresas nessa fase costumam sentir o gargalo de captação antes de sentir o gargalo de entrega.",
      "urgency_level": "ALTA"
    },
    "context_trigger": {
      "event_description": "3 vagas abertas para advogados sênior nos últimos 30 dias no LinkedIn da empresa",
      "source": "LINKEDIN",
      "detected_at": "2026-05-28T09:15:00Z"
    },
    "pain_narrative": "Nosso escritório cresceu de 8 para 22 advogados em 2 anos e os processos de captação de novos mandatos ainda são 100% relacionais — dependemos de indicações e networking individual das sócias. Não temos visibilidade de qual perfil de cliente fecha mais rápido e nem de onde nossos melhores mandatos vieram nos últimos 12 meses.",
    "credibility_anchor": {
      "evidence_text": "Escritórios de Advocacia Corporativa com 15-25 advogados que adotaram inteligência de prospecção estruturada reduziram o tempo de qualificação de prospect em 60% nos primeiros 90 dias, liberando as sócias para foco em fechamento de contratos de maior ticket.",
      "result_metric": "60% de redução no tempo de qualificação em 90 dias"
    },
    "cta_suggestion": {
      "channel": "LINKEDIN_DM",
      "message_draft": "Dra. Ana, vi que o escritório está ampliando a equipe com 3 novas posições — crescimento que geralmente traz junto o desafio de manter a qualidade da carteira de clientes. Ajudo escritórios nessa fase a mapear com precisão onde estão as próximas oportunidades de mandatos corporativos. Posso compartilhar como tem funcionado para escritórios similares em SP?",
      "contraindications": [
        "Não abordar com pitch de produto antes de validar a dor com a própria Dra. Ana — ela pode não ser a responsável pela decisão de investimento final, apenas a mais visível externamente",
        "Evitar mencionar ROI ou payback em primeira mensagem — Advocacia tem cultura de ceticismo a promessas numéricas de fornecedores não referenciados",
        "Não copiar o Dr. Carlos Souza na mesma mensagem inicial — trabalhar o BMO isoladamente antes de envolver o SC"
      ]
    },
    "partial": false,
    "data_quality_warning": false,
    "missing_fields": null
  }
}
```

---

#### GET /api/v1/leads/{lead_id}/blueprint

**Propósito:** Retornar apenas o `ConversationBlueprint` isolado de um lead, com metadados básicos de identificação. Endpoint otimizado para integrações de CRM e ferramentas de SDR que não precisam do payload completo.

**Response Headers:**
- `ETag: sha256:{cycle_id}:{lead_id}` — cache condicional baseado em cycle_id + lead_id; blueprint não muda dentro do mesmo ciclo a menos que Delta Search seja reativado
- `Cache-Control: max-age=600` (10 minutos)

**Response 200 OK:**
```json
{
  "lead_id": "LE-2024-00123",
  "company_name": "Escritório Advocacia Exemplo S/S",
  "cycle_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "generated_at": "2026-06-01T14:32:00Z",
  "p_score": 0.7412,
  "action_label": "PRIORITY_ACTION",
  "data_quality": {
    "operating_mode": "FULL",
    "degraded": false
  },
  "blueprint": {
    "hook": {
      "text": "Identificamos que o Escritório Advocacia Exemplo abriu 3 posições de advogado sênior nos últimos 30 dias — um sinal claro de expansão de carteira.",
      "urgency_level": "ALTA"
    },
    "context_trigger": {
      "event_description": "3 vagas abertas para advogados sênior nos últimos 30 dias",
      "source": "LINKEDIN",
      "detected_at": "2026-05-28T09:15:00Z"
    },
    "pain_narrative": "Nosso escritório cresceu de 8 para 22 advogados em 2 anos e os processos de captação de novos mandatos ainda são 100% relacionais...",
    "credibility_anchor": {
      "evidence_text": "Escritórios similares reduziram o tempo de qualificação de prospect em 60% nos primeiros 90 dias.",
      "result_metric": "60% de redução em 90 dias"
    },
    "cta_suggestion": {
      "channel": "LINKEDIN_DM",
      "message_draft": "Dra. Ana, vi que o escritório está ampliando a equipe...",
      "contraindications": [
        "Não abordar com pitch de produto antes de validar a dor com a própria Dra. Ana",
        "Evitar mencionar ROI ou payback em primeira mensagem"
      ]
    },
    "partial": false,
    "data_quality_warning": false,
    "missing_fields": null
  }
}
```

---

#### POST /api/v1/webhooks/crm

**Propósito:** Receber feedback de outcome de leads do CRM externo para alimentar o feedback loop de qualidade de fonte (EV-17 e EV-18).

**Autenticação:** HMAC-SHA256 do corpo da request no header `X-CRM-Signature: sha256={hex_digest}`. Chave compartilhada configurada em AWS Secrets Manager.

**Request Body:**
```json
{
  "lead_id": "LE-2024-00123",
  "outcome": "CLOSED_WON",
  "feedback_notes": "Fundadora confirmou que as vagas abertas era exatamente o momento certo. Dor de captação foi o vetor principal da venda.",
  "closed_at": "2026-06-01T10:00:00Z"
}
```

**Response 202 Accepted** (processamento assíncrono via SQS — retorno imediato):
```json
{
  "status": "QUEUED",
  "feedback_id": "FBK-001",
  "lead_id": "LE-2024-00123",
  "message": "Feedback recebido e enfileirado para processamento assíncrono."
}
```

**Response 401 Unauthorized** (assinatura HMAC inválida):
```json
{
  "error": "INVALID_SIGNATURE",
  "message": "Assinatura HMAC-SHA256 inválida ou ausente no header X-CRM-Signature."
}
```

**Business Logic:**
1. Valida assinatura HMAC-SHA256 imediatamente — se inválida, retorna 401 sem processar
2. Insere em `crm_feedback_log` com `status='QUEUED'`
3. Publica mensagem em SQS `socialselling-crm-feedback` com payload completo
4. Retorna 202 imediatamente — nunca bloqueia o ciclo ativo

---

#### PUT /api/v1/icp-contract

**Propósito:** Atualizar o contrato ICP com novos parâmetros de scoring, keyword taxonomy e segmentos-alvo.

**Autenticação:** API Key de admin no header `X-Admin-Key`. Chave configurada em AWS Secrets Manager.

**Request Body:**
```json
{
  "weight_fit": 0.4500,
  "weight_intent": 0.3500,
  "weight_reachability": 0.2000,
  "segments": ["Advocacia", "Consultoria", "SaaS", "Engenharia"],
  "headcount_range": {"min": 5, "max": 30},
  "monthly_revenue_range_brl": {"min": 80000, "max": 500000},
  "anchor_profiles": [
    {"linkedin_url": "https://www.linkedin.com/company/exemplo-advocacia", "label": "Ideal ICP"}
  ],
  "keyword_taxonomy": {
    "pain_keywords": ["captação", "prospecção", "mandatos", "pipeline", "escalabilidade"],
    "growth_keywords": ["expansão", "contratando", "crescimento", "novos clientes"],
    "urgency_keywords": ["busco", "precisamos", "sobrecarregados", "gargalo"]
  },
  "budget_per_lead_brl": 2.50
}
```

**Validação Crítica:** `weight_fit + weight_intent + weight_reachability` DEVE ser exatamente `1.000` (tolerância ±0.001). Retorna HTTP 422 se violado.

**Response 200 OK:**
```json
{
  "contract_id": "novo-uuid-contrato",
  "version_hash": "sha256:a3f2b1...",
  "supersedes_contract_id": "uuid-contrato-anterior",
  "status": "ACTIVE",
  "created_at": "2026-06-01T14:32:00Z",
  "validation": {
    "weights_sum": 1.0000,
    "valid": true
  }
}
```

---

#### GET /api/v1/observability

**Propósito:** Retornar métricas operacionais em tempo real do sistema para o Operator Cockpit e para dashboards de monitoramento.

**Response 200 OK:**
```json
{
  "generated_at": "2026-06-01T14:32:00Z",
  "system_status": {
    "operating_mode": "FULL",
    "active_cycles": 2,
    "scraper_status": {
      "instagram": "HEALTHY",
      "linkedin": "HEALTHY",
      "cnpj": "HEALTHY"
    }
  },
  "current_cycle_metrics": {
    "cycle_id": "7c9e6679-...",
    "leads_hydrated": 32,
    "leads_in_progress": 5,
    "leads_error": 1,
    "leads_delta_mode": 7,
    "budget_consumed_brl": 8.50,
    "budget_total_brl": 50.00,
    "budget_pct_consumed": 17.0
  },
  "quality_metrics": {
    "avg_p_score": 0.5210,
    "pct_priority_action": 28.5,
    "pct_monitor": 35.2,
    "pct_delta_search": 22.1,
    "pct_pruned": 14.2,
    "conflicts_pending_manual_review": 3
  },
  "sla_metrics": {
    "avg_hydration_time_seconds": 42.3,
    "p95_hydration_time_seconds": 78.1,
    "saga_error_rate_pct": 0.8
  }
}
```

---

### 2.3 Estrutura de Nesting do JSON e Justificativa

#### Por Que Scores Aninhados (Não Flat)

**Problema com estrutura flat:**
```json
{"o_score": 0.81, "c_score": 0.62, "p_score": 0.74, "fit": 0.85, "s_intent": 0.72}
```
Em estrutura flat, não há separação semântica entre scores de primeiro nível (`p_score`, `o_score`, `c_score`) e componentes intermediários (`fit`, `s_intent`). Um consumidor que quer exibir apenas o `P_score` precisa saber quais campos são principais e quais são sub-componentes — e essa distinção não está codificada na estrutura.

**Benefício com nesting semântico:**
```json
{"scores": {"p_score": {"value": 0.74, "components": {"o_score": {"value": 0.81, "components": {"fit": 0.85}}}}}}
```
O consumidor de front-end pode renderizar `scores.p_score.value` sem nunca precisar conhecer a existência de `fit` ou `srs_product`. A hierarquia da fórmula é refletida diretamente na hierarquia do JSON.

#### Por Que `xai_drivers` Separado de `scores`

`scores` são consumidos por computação — o sistema de ranking, integrações de CRM, dashboards de métricas. Esses consumidores precisam de valores numéricos precisos e determinísticos.

`xai_drivers` é consumido por humanos — o operador comercial que quer entender por que um lead está em PRIORITY_ACTION. Os drivers são em linguagem natural e têm granularidade qualitativa ("+0.18 no S_intent porque havia 3 vagas abertas") que é irrelevante e verbosa para consumidores de computação.

Separar os dois evita poluição de namespace, mantém o payload de `scores` enxuto para processamento automático, e permite que `xai_drivers` evolua em vocabulário e formato independentemente dos `scores` calculados.

#### Por Que `approach_blueprint` no Nível Raiz (Como `approach_blueprint` dentro de um campo renomeado)

No XAI Unified Payload, o `approach_blueprint` (retornado como campo `approach_blueprint` dentro do objeto raiz do payload) é posicionado no mesmo nível hierárquico que `scores`, `buying_committee` e `hypothesis_evaluation`. Não está aninhado sob nenhum desses campos.

**Justificativa:** O `approach_blueprint` é o conteúdo mais consumido pelo operador comercial — é a resposta direta à Pergunta Cardinal 3 ("O que falar?"). Aninhar o blueprint sob `scores` ou `buying_committee` criaria uma hierarquia falsa que não reflete a importância do campo. O operador que abre o lead no Cockpit deve chegar ao blueprint com o menor número possível de expansões de campos.

---

## 3. UX DO OPERATOR COCKPIT

### 3.1 Hierarquia Visual Orientada às 3 Perguntas Cardinais

O Operator Cockpit é projetado a partir das 3 Perguntas Cardinais do Negócio como estrutura primária de navegação e hierarquia visual. Cada pergunta cardinal mapeia diretamente para um bloco visual distinto, com hierarquia de atenção clara: o dado mais acionável aparece primeiro, o mais detalhado aparece sob demanda.

---

#### BLOCO 1 — "Onde Focar?" (Prioridade / Oportunidade)

**Propósito:** Responder em menos de 3 segundos se o lead merece atenção agora, depois ou nunca.

**Componentes visuais:**

**P_score como barra de progresso horizontal:**
- Range visual: 0% a 100% (mapeado de 0.0 a 1.0)
- Cores por threshold: 0.70+ verde (PRIORITY_ACTION), 0.45-0.69 amarelo (MONITOR), 0.25-0.44 azul claro (DELTA_SEARCH), abaixo de 0.25 cinza (PRUNED)
- Valor numérico exibido com 2 casas decimais ao lado da barra (`0.74`)
- Em modo degradado: asterisco (*) ao lado do valor com tooltip explicativo

**Action Label como badge colorido:**
- `PRIORITY ACTION` — badge verde com ícone de raio
- `MONITOR` — badge amarelo com ícone de relógio
- `DELTA SEARCH` — badge azul com ícone de radar
- `PRUNED` — badge cinza com ícone de arquivo

**Contexto da empresa:**
- Nome da empresa em destaque (maior fonte, bold)
- Segmento como tag pequena colorida por setor: Advocacia (roxo), Consultoria (verde), SaaS (azul), Engenharia (laranja)
- Faixa de colaboradores: exibida como `15-25 pessoas`
- Tempo de existência do negócio (calculado da data de abertura do CNPJ)

**Fit e S_intent separados:**
- Dois medidores mini lado a lado: `Fit 0.85` (ícone de puzzle — "match estrutural com ICP") e `Intenção 0.72` (ícone de pulso — "momento de compra")
- Tooltip no ícone de Fit: "Compatibilidade com perfil ideal: segmento, porte e setor"
- Tooltip no ícone de Intenção: "Evidências de urgência e intenção de compra detectadas"

---

#### BLOCO 2 — "Com Quem Falar?" (Comitê de Compras)

**Propósito:** Identificar a pessoa certa para o primeiro contato e o contexto de relacionamento dela.

**Card do BMO (Budget and Mobilization Owner):**
- Foto de perfil circular (quando disponível no LinkedIn) — placeholder com iniciais se ausente
- Nome em destaque + cargo em fonte secundária
- `bmo_momentum_score` como gauge circular (0-100%) — verde acima de 0.60, amarelo 0.30-0.59, cinza abaixo de 0.30, vazio (tracejado) se UNKNOWN/null
- Trigger events ativos exibidos como badges coloridos sobrepostos ao card: badge vermelho para urgência ALTA, laranja para MEDIA, azul para BAIXA
- Ícone de LinkedIn clicável que abre o perfil em nova aba

**Card do SC (Sponsoring Champion):**
- Design similar ao BMO mas com diferenciação visual clara: borda tracejada (ao invés de sólida), ícone de estrela (ao invés de raio), cor de fundo ligeiramente diferente
- Sem `bmo_momentum_score` — exibe apenas `confidence` da identificação como chip de texto ("Confiança: 72%")

**Completude do Comitê como Semáforo:**
- Indicador discreto no canto superior direito do Bloco 2
- `3/3 identificados` → círculo verde sólido + texto "Comitê Completo"
- `2/3 identificados` → círculo amarelo com ponto central + texto "Comitê Parcial"
- `1/3 identificados` → círculo laranja com exclamação + texto "Comitê Incompleto — investigar"
- `0/3 identificados` → círculo vermelho + texto "Comitê não mapeado"
- Tooltip em estados não-completos: lista os roles faltantes e ação recomendada

**Trigger Events:**
- Exibidos em linha abaixo dos cards como chips coloridos
- Cada chip: ícone do tipo de evento + texto curto (máximo 40 caracteres) + data relativa ("há 2 dias")
- Cores: vermelho para ALTA, laranja para MEDIA, azul para BAIXA
- Máximo 3 trigger events exibidos diretamente — botão "Ver mais" para os demais

---

#### BLOCO 3 — "O Que Falar?" (Conversation Blueprint)

**Propósito:** Entregar ao operador o roteiro de abordagem sem necessidade de pesquisa adicional.

**Hook:**
- Exibido em destaque — fonte maior, fundo levemente colorido (verde/amarelo/azul conforme urgency_level)
- `urgency_level` como chip colorido no canto superior direito do campo: "Urgência ALTA" (vermelho), "Urgência MÉDIA" (laranja), "Urgência BAIXA" (azul)
- Texto completo visível sem scroll (máximo 3 linhas)

**Pain Narrative:**
- Exibida em bloco de citação com aspas visuais e fundo cinza claro
- Prefixo "A perspectiva da empresa:" em itálico
- Texto em primeira pessoa — cria empatia visual para o operador
- Se `partial=true` e campo null: placeholder cinza com ícone de informação e texto: "Narrativa de dor não disponível — hipótese dominante com confiança insuficiente"

**CTA Suggestion:**
- Canal recomendado como badge: LinkedIn DM (azul LinkedIn), Email (cinza), WhatsApp (verde WhatsApp), Instagram DM (gradiente Instagram)
- `message_draft` em caixa de texto editável (o operador pode editar antes de copiar)
- Botão "Copiar mensagem" com feedback visual de confirmação ("Copiado!")

**Contraindications:**
- Card com fundo vermelho/laranja claro, borda esquerda vermelha, ícone de atenção
- Título em bold: "Atenção — evite estas abordagens:"
- Lista não-colapsável: o operador DEVE ver as contraindications antes de qualquer ação
- Cada item como bullet com ícone de X vermelho

---

### 3.2 Princípios de Mitigação de Fadiga Cognitiva

O design do Cockpit é orientado pela premissa de que o operador comercial precisa processar múltiplos leads por sessão de trabalho. A fadiga cognitiva é o principal inimigo da qualidade de execução. Os seguintes princípios são aplicados sistematicamente:

**Princípio 1: Hierarquia de 3 Segundos**
Qualquer lead deve ser avaliado em 3 segundos no modo de lista: P_score (barra + badge de ação), nome da empresa + segmento, e urgência do BMO (trigger events badge). Zero scroll necessário para essa avaliação inicial. Detalhes ficam em Bloco 2 e Bloco 3, acessíveis por clique.

**Princípio 2: Progressive Disclosure**
Informações técnicas que o operador não precisa para tomar a decisão de abordar — componentes intermediários do score (Fit separado do S_intent separado do Reachability), posteriors das hipóteses alternativas, stack de evidências brutas, audit trail de compensações — ficam atrás de toggles/accordions. Visíveis sob demanda, nunca na visão padrão.

**Princípio 3: Semáforo de Qualidade de Dados Sempre Visível**
O status de qualidade dos dados é exibido persistentemente no header da ficha de cada lead, nunca escondido:
- `NORMAL` — ícone verde, texto "Dados completos"
- `LOW` — ícone amarelo, texto "Dados com confiança reduzida"
- `DEGRADED` — ícone vermelho, texto "Dados de fonte degradada"

O semáforo calibra as expectativas do operador antes de qualquer leitura do blueprint — evita que o operador confie cegamente em dados que o sistema marcou como degradados.

**Princípio 4: Máximo 3 Highlights por Lead no Modo de Lista**
Na visão de lista ranqueada, cada card de lead exibe no máximo 3 informações além do nome:
1. P_score + Action Label
2. Nome do BMO + Urgência do trigger event
3. Segmento + completude do comitê

Tudo o mais fica no detalhe do lead. Evitar "painel de instrumentos de avião" onde tudo pisca ao mesmo tempo.

**Princípio 5: Linguagem de Negócio, Nunca Técnica**
Todos os textos visíveis para o operador usam linguagem de negócio. O operador nunca vê:
- "C_score = 0.62" → Vê: "Confiança nos dados: 62%"
- "DEGRADED_LINKEDIN" → Vê: "LinkedIn temporariamente indisponível"
- "partial=true" → Vê: "Informações parciais — clique para enriquecer"
- "posterior=0.23" → Vê: "Hipótese com baixa confiança — mais dados necessários"

---

## 4. GESTÃO DE FALHAS E INCERTEZA NA UX

### 4.1 Modos Degradados e Alertas Visuais

Os modos operacionais degradados são situações operacionais esperadas — não são erros. O Cockpit comunica claramente ao operador o que está disponível e o que está limitado, sem alarmar desnecessariamente.

---

#### Modo DEGRADED_LINKEDIN

**Banner permanente no topo da tela:**
```
⚠️ LinkedIn temporariamente indisponível — informações de cargo e vagas podem estar incompletas.
   Dados de Instagram e CNPJ continuam disponíveis. [Mais informações]
```
- Background amarelo (#FFF3CD), texto escuro, ícone de aviso
- Não-bloqueante: o operador pode continuar trabalhando normalmente
- O banner persiste enquanto o modo estiver ativo — não fecha automaticamente
- Link "Mais informações" expande um painel explicando quais campos foram afetados

**Campos afetados no card do lead:**
- Campos derivados exclusivamente de LinkedIn (cargo do BMO, vagas abertas, headcount) exibem o ícone `⚠️` ao lado do valor
- Tooltip no ícone: "Dado obtido de LinkedIn em modo degradado. Incerteza aumentada em +20%."
- Cor do valor afetado: cinza médio (ao invés de preto) — indica "disponível mas com ressalvas"

**P_score com asterisco e tooltip:**
- Valor exibido como `0.74*` — asterisco após o número
- Tooltip no asterisco: "Score calculado com dados de LinkedIn em modo degradado. Incerteza do C_score aumentada em +0.20 por field. O score real pode ser até 0.12 maior após recuperação do LinkedIn."

**CTA Suggestions que dependem de LinkedIn:**
- CTAs cujo canal recomendado é `LINKEDIN_DM` ficam visualmente desativados (cinza + opacity 50%)
- Tooltip na CTA desativada: "Abordagem via LinkedIn DM recomendada, mas LinkedIn está temporariamente indisponível. Considere Email como canal alternativo."
- Não removidos — o operador pode escolher tentar mesmo assim (botão "Tentar assim mesmo" com aviso adicional)

---

#### Modo DEGRADED_INSTAGRAM

**Banner permanente no topo da tela:**
```
⚠️ Instagram em modo de cache — dados de engajamento e posts podem não refletir atividade recente.
   Dados com frescor reduzido (t₁/₂ = 12h). [Mais informações]
```
- Background laranja claro (#FFE8CC), texto escuro

**E_fresh como barra de frescor:**
- Quando `E_fresh < 0.50` para evidências de Instagram, exibido em destaque
- Barra de frescor horizontal abaixo do nome da empresa: coloração gradiente de verde (E_fresh=1.0) para vermelho (E_fresh=0.0)
- Label: "Frescor dos dados de Instagram: {valor}%" — em vermelho quando abaixo de 50%

---

#### Modo CACHE_ONLY

**Banner de alerta crítico no topo da tela:**
```
🔴 Sistema em modo de cache total — nenhum dado novo está sendo coletado para este ciclo.
   Todos os leads exibem dados do cache. [Forçar novo ciclo]
```
- Background vermelho (#F8D7DA), texto escuro, borda vermelha
- Botão "Forçar novo ciclo" — visível apenas para operadores com permissão de admin
- Banner não pode ser fechado enquanto o modo estiver ativo

**Todos os leads do ciclo marcados como STALE:**
- Tag `STALE` vermelha sobre o Action Label de cada lead no modo de lista
- Ordenação do ranking mantida (P_score do último ciclo completo), mas visualmente demarcada como dados de ciclo anterior

---

### 4.2 Leads com C_score Baixo (< 0.35)

Leads com alta oportunidade (`O_score > 0.70`) mas baixa confiança (`C_score < 0.35`) representam um padrão específico: o sistema detectou sinais fortes de oportunidade, mas com dados insuficientes para confirmar. São os leads com maior potencial de surpresa positiva após enriquecimento — e também os com maior risco de abordagem prematura.

**Exibição do C_score em destaque:**
- Valor do C_score exibido com fundo laranja claro e texto laranja escuro (`0.28`)
- Label descritivo ao lado: "Confiança Baixa nos Dados"
- Não oculto — o operador DEVE saber que está operando com dados insuficientes

**Tooltip no P_score com mensagem de potencial:**
- "Alta oportunidade detectada, mas com baixa confiança nos dados de qualificação."
- "Investigação adicional pode aumentar o score estimado em até +0.18 pontos."
- "Ação recomendada: ver campos de dados faltantes abaixo."

**Campo `missing_evidence_impact` como lista de ações:**
O componente `missing_evidence_impact` do payload XAI é exibido como lista de ações recomendadas no Cockpit, em linguagem de negócio:

```
Dados ausentes que podem elevar o score deste lead:
  ☐  Perfil do LinkedIn do Diretor de Operações não encontrado — identificar o BMO pode elevar C_score em até +0.15
  ☐  Apenas 1/3 de membros do comitê de compras identificados — comitê completo pode elevar C_s de 0.33 para 1.00
  ☐  Evidências de LinkedIn obtidas em modo degradado — re-coletar após recuperação pode reduzir incerteza em -0.20
```

**Botão de ação:**
- "Enriquecer este Lead" — dispara reativação de Delta Search específica para este lead com prioridade elevada
- Exibido logo abaixo da lista de dados faltantes

**CTA Suggestion:**
- Não desativada — mas exibida com aviso adicional em bloco laranja abaixo do message_draft:
- "Abordagem baseada em dados parciais — personalização limitada. Risco de baixa relevância percebida pelo prospecto."

---

### 4.3 Blueprint Parcial (partial:true)

Blueprints parciais ocorrem quando a hipótese dominante do lead não atingiu confiança mínima suficiente (`posterior < 0.25`). O operador deve ser informado claramente sobre o que está disponível e o que não está, com caminho de ação para melhorar.

**Seções não populadas como placeholders cinzas:**
- Background cinza claro (#F8F9FA), borda tracejada cinza
- Ícone de informação (ⓘ) centralizado na área do placeholder
- Texto do placeholder: "Informação não disponível" (não "Dados insuficientes" — linguagem de negócio, não técnica)
- Tooltip no ícone de informação: razão em linguagem de negócio
  - Para `pain_narrative` null: "A narrativa de dor ainda não pôde ser personalizada — as evidências coletadas não confirmaram com confiança suficiente qual é o desafio principal desta empresa. Enriquecer o lead pode desbloquear este campo."
  - Para `credibility_anchor` null: "Sem hipótese confirmada, não é possível selecionar uma âncora de credibilidade específica ao contexto desta empresa."

**Componentes sempre disponíveis mesmo em blueprint parcial:**
- `hook` genérico de segmento — exibido com chip "Conteúdo genérico" em amarelo
- `cta_suggestion` com canal e mensagem genérica de segmento
- `contraindications` — SEMPRE presentes, nunca null

**Botão "Enriquecer este Lead":**
- Exibido em destaque no topo do Bloco 3 quando `partial=true`
- Cor: azul primário, ícone de atualização (seta circular)
- Texto: "Enriquecer este Lead — mais dados podem desbloquear blueprint completo"
- Ação: dispara Delta Search reativada para este lead
- Após clicar: botão muda para "Enriquecimento em andamento..." com spinner
- Quando Delta Search completa: notificação push no Cockpit "Blueprint do lead {nome} atualizado — verificar novos dados"

---

### 4.4 Contraindications — Anti-Patterns de Abordagem

As `contraindications` são o mecanismo de proteção do operador contra abordagens que o sistema detectou como potencialmente contraproducentes dado o contexto específico do lead. São geradas pelo Copywriter Agent com base na hipótese dominante, no setor, no perfil do BMO e no contexto comportamental detectado nas evidências.

**Posicionamento no Cockpit:**
- Sempre exibidas em card de atenção no final do Bloco 3
- Background vermelho claro (#F8D7DA) com borda esquerda vermelha sólida
- Ícone de atenção (⚠️) no título
- Título: "Atenção — Evite estas abordagens com este lead:"

**Regras de Exibição:**
- Lista **não-colapsável** — o operador DEVE ver as contraindications antes de qualquer ação
- Não há accordion ou toggle — contraindications nunca ficam escondidas
- Máximo 5 contraindications exibidas diretamente; acima de 5, botão "Ver mais ({n} restantes)"
- Cada item como bullet com ícone de X vermelho ao lado

**Exemplos de Contraindications por Contexto:**

*Para Advocacia Corporativa com BMO não totalmente identificado:*
- "Não abordar a fundadora como se ela fosse a única decisora — em escritórios com 2+ sócios, a decisão de investimento é geralmente colegiada. Inclua o sócio sênior da área relevante na conversa antes de propor."
- "Evitar pitch de ROI com números específicos em primeiro contato — a cultura jurídica é cética a promessas numéricas de fornecedores sem referência prévia. Comece pela dor, não pela solução."
- "Não mencionar concorrentes pelo nome — escritórios de advocacia são altamente discretos sobre suas escolhas tecnológicas."

*Para SaaS/Software House com trigger event de contratação:*
- "Não abordar como se o desafio fosse apenas tecnológico — para fundadoras de SaaS, o problema de prospecção tem componente de cultura e processo que precede a tecnologia. Validar se elas já tentaram outras soluções antes de posicionar."
- "Evitar jargões de Social Selling (SSI, ABM, intent data) em primeira abordagem — fundadoras técnicas podem ter resistência a terminologias de marketing/vendas percebidas como buzzwords."

*Para lead em DEGRADED_LINKEDIN:*
- "Dados de cargo e estrutura de equipe podem estar desatualizados — confirmar na conversa se a estrutura de liderança está como mapeado antes de referenciar cargos específicos."

**Baseadas em Dados (Nunca Inventadas):**
Cada contraindication DEVE ser rastreável a:
- Uma inferência CONTRADICTING na Layer 2 (contradiz abordagem direta), OU
- Um padrão de setor documentado no `icp_contract.anchor_profiles`, OU
- Um dado de contexto comportamental detectado nas evidências (ex: último post da fundadora criticou vendedores insistentes)

Contraindications genéricas sem rastreamento a dados são proibidas pelo contrato operacional do Copywriter Agent.

---

*Documento: SDD-08 — Multi-Agent Framework e Cockpit UX*
*Versão: 1.0.0 | Data: 2026-06-01*
*Documento anterior: SDD-07 — Event Storming e Orquestração de Saga*
*Próximo documento: SDD-09 — Cloud Infrastructure Terraform AWS*
*Referências internas: SDD-01 (Arquitetura Geral), SDD-02 (Mathematical Core Scoring), SDD-05 (Buying Committee & Motion)*
