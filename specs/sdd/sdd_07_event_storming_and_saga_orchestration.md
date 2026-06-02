# SDD-07 — Event Storming e Orquestração de Saga
## SocialSelling Intelligence System

**Versão:** 1.0.0
**Data:** 2026-06-01
**Status:** Aprovado para Implementação
**Autor:** Arquitetura de Sistema — SocialSelling

---

## Sumário

1. [Event Storming Operational Grid](#1-event-storming-operational-grid)
2. [Pipeline de Orquestração de Saga (LeadHydrationSaga)](#2-pipeline-de-orquestração-de-saga-leadhydrationsaga)
   - 2.1 [Definição e Justificativa do Padrão Saga](#21-definição-e-justificativa-do-padrão-saga)
   - 2.2 [Estrutura do LeadHydrationSaga — Definição de Estado](#22-estrutura-do-leadhydrationsaga--definição-de-estado)
   - 2.3 [Success Path — Caminho Feliz](#23-success-path--caminho-feliz)
   - 2.4 [Compensating Actions — Ações de Compensação](#24-compensating-actions--ações-de-compensação)
   - 2.5 [Diagrama de Fluxo Textual da Saga](#25-diagrama-de-fluxo-textual-da-saga)

---

## 1. EVENT STORMING OPERATIONAL GRID

O Event Storming Operational Grid mapeia as **18 transações canônicas do sistema** SocialSelling, cada uma descrita pelos seus comandos disparadores, eventos de domínio emitidos, políticas de negócio que as governam e os impactos físicos de mutação DML que produzem no banco de dados PostgreSQL 16+.

> **Convenções de leitura:** Comandos descrevem quem dispara a ação (verbo imperativo). Eventos de domínio descrevem o resultado já ocorrido (passado perfeito — fato imutável). Políticas descrevem a regra de negócio que governa a transação. DML descreve a instrução SQL resultante no banco.

---

### Tabela de Transações do Sistema

| # ID | Comando (Action) | Evento de Domínio (Result) | Política de Negócio Aplicada (Business Rule) | Impacto Físico de Mutação DML no Banco de Dados |
|------|-----------------|---------------------------|----------------------------------------------|--------------------------------------------------|
| **EV-01** | **InitiateCycle** — Operador dispara criação de novo ciclo de busca via `POST /api/v1/cycles`, fornecendo `seed_list`, `icp_contract_id` e `budget_brl` | `CycleInitiated` — ciclo de busca criado com `cycle_id` UUID, `status='STARTED'`, estimativas de custo e volume de leads calculadas e retornadas | Um ciclo só pode ser iniciado se o `icp_contract_id` referenciado existir com `status='ACTIVE'`. O `budget_brl` não pode ser inferior a R$5,00. Não pode haver outro ciclo com `status='IN_PROGRESS'` para o mesmo `icp_contract_id` simultaneamente — retorna HTTP 409 se violado. | `INSERT INTO search_cycles (cycle_id, icp_contract_id, status, budget_brl, seed_count, created_at) VALUES (gen_random_uuid(), $1, 'STARTED', $2, $3, NOW())` |
| **EV-02** | **ParametrizeICPContract** — Operador executa `PUT /api/v1/icp-contract` com pesos de scoring, anchor profiles, keyword taxonomy, segmentos-alvo e budget de queries por fonte | `ICPContractParametrized` — novo `contract_id` gerado com `version_hash` SHA-256, parâmetros validados e persistidos; contrato anterior marcado como `SUPERSEDED` | A soma dos pesos deve ser exatamente 1.000: `weight_fit + weight_intent + weight_reachability = 1.000` (tolerância ±0.001). Qualquer alteração gera nova versão imutável — o contrato anterior é marcado `SUPERSEDED` com `superseded_at`, nunca deletado. Requer API Key de admin no header `X-Admin-Key`. | `INSERT INTO icp_contracts (contract_id, version_hash, weight_fit, weight_intent, weight_reachability, anchor_profiles, keyword_taxonomy, segments, status, created_at) VALUES (..., 'ACTIVE', NOW()); UPDATE icp_contracts SET status='SUPERSEDED', superseded_at=NOW() WHERE contract_id=$old_id` |
| **EV-03** | **CollectInstagramEvidence** — SearchOrchestrator (M1) dispara `instagram_scraper` para perfis da seed list dentro do ciclo ativo, parametrizado pela keyword taxonomy do ICP contract ativo | `InstagramEvidenceCollected` — batch de evidências brutas coletadas: posts recentes, bio, engagement_rate, hashtags, frequência de publicação, menções de dor inferidas, growth signals detectados | O scraper opera em modo FULL apenas se não houver flag de bloqueio ativo no ciclo. Se Instagram estiver bloqueado, aciona Compensação C-02 imediatamente. Evidências só são aceitas se `source_url` for válida e parseável. Deduplicação por SHA-256 do conteúdo normalizado é executada antes de qualquer persistência. | `INSERT INTO observed_evidence (evidence_id, lead_id, cycle_id, source, source_url, content_hash, raw_payload, collected_at, ttl_hours) VALUES (..., 'INSTAGRAM', ...) ON CONFLICT (content_hash) DO NOTHING` |
| **EV-04** | **CollectLinkedInEvidence** — SearchOrchestrator (M1) dispara `linkedin_scraper` para perfis da seed list: página da empresa, perfis de membros candidatos ao comitê de compras, vagas abertas, artigos publicados recentemente | `LinkedInEvidenceCollected` — batch de evidências brutas: cargo atual, headcount declarado, vagas abertas por departamento, artigos e posts recentes, conexões qualificadas, interações recentes, seniority dos colaboradores identificados | LinkedIn tem rate limiting severo e imprevisível. Se rate-limited (HTTP 429 ou timeout > 15s), DEVE acionar Compensação C-01 imediatamente, sem retry automático no mesmo ciclo. Evidências coletadas em modo degradado recebem `uncertainty_additive=0.20`. Vagas abertas são evidências de alto valor para o componente `S_intent` do O_score. | `INSERT INTO observed_evidence (evidence_id, lead_id, cycle_id, source, source_url, content_hash, raw_payload, uncertainty_additive, collected_at, ttl_hours) VALUES (..., 'LINKEDIN', ...) ON CONFLICT (content_hash) DO NOTHING` |
| **EV-05** | **CollectCNPJData** — SearchOrchestrator (M1) dispara `cnpj_resolver` para o CNPJ de cada empresa da seed list, consultando a API pública da Receita Federal e bases enriquecidas de terceiros | `CNPJDataCollected` — dados cadastrais coletados: razão social, porte declarado, capital social, data de abertura, CNAE principal e secundários, quadro societário, endereço, situação cadastral, regime tributário (Simples/Lucro Presumido/Lucro Real) | CNPJ é dado público e imutável na origem — não possui TTL de frescor (ttl_hours=9999). Atua como âncora de identidade canônica para o processo de entity resolution. Se CNPJ for inválido ou a empresa estiver com situação `BAIXADA` ou `INAPTA`, o lead recebe `disqualified=true` e o pipeline é interrompido para este lead específico. | `INSERT INTO observed_evidence (evidence_id, lead_id, cycle_id, source, content_hash, raw_payload, is_anchor, collected_at) VALUES (..., 'CNPJ_GOV', ..., true, ...); UPDATE leads SET disqualified=true, disqualification_reason='CNPJ_INAPTO' WHERE lead_id=$1 AND cnpj_status IN ('BAIXADA','INAPTA')` |
| **EV-06** | **DeduplicateAndNormalizeEvidence** — NormalizationNode (M2) processa o `evidence_batch` bruto: normaliza strings, computa SHA-256, descarta duplicatas, aplica cálculo inicial de frescor `E_fresh` | `EvidenceNormalized` — Layer 1 (Observed Evidence) populada de forma append-only com evidências únicas, cada uma com `content_hash` SHA-256 único, `e_fresh` calculado e `ttl_hours` atribuído por fonte | Observed Evidence é imutável após persistência — nunca UPDATE ou DELETE sobre registros existentes. Apenas INSERT. Duplicata detectada por `content_hash` é descartada silenciosamente via `ON CONFLICT DO NOTHING`. `E_fresh` inicial calculado com `t½` por fonte: CNPJ=∞, LinkedIn=24h, Instagram=6h em FULL, 12h em DEGRADED_INSTAGRAM. Fórmula: `E_fresh = e^(-ln2/t½ × Δt)`. | `INSERT INTO observed_evidence (evidence_id, lead_id, cycle_id, source, content_hash, normalized_payload, e_fresh_initial, layer, collected_at) VALUES (..., 1, ...) ON CONFLICT (content_hash) DO NOTHING` |
| **EV-07** | **ResolveEntityAutoMerge** — EntityResolutionEngine (M2) executa pipeline RRF (Reciprocal Rank Fusion) + Jaro-Winkler + penalizadores sobre pares de entidades candidatas ao merge, e o RCS resultante supera o threshold de auto-merge | `EntityAutoMerged` — duas ou mais referências de entidade fundidas em único `entity_id` canônico com `canonical_name`, `canonical_cnpj`, `canonical_linkedin_url`, `canonical_instagram_handle` registrados e todos os `evidence_id` reatribuídos | Auto-merge ocorre exclusivamente quando `rcs_score >= 0.85`. O `entity_id` canônico é sempre o do registro mais antigo (menor `first_seen_at`). Todos os `evidence_id` das entidades fundidas são reatribuídos ao `entity_id` canônico. O merge é registrado em `entity_merge_log` com todos os scores para auditoria completa e rastreabilidade. | `UPDATE entity_nodes SET canonical_id=$canonical_id WHERE entity_id = ANY($merged_ids); INSERT INTO entity_merge_log (merge_id, canonical_id, merged_ids, rcs_score, merge_type, cycle_id, merged_at) VALUES (..., 'AUTO', ...); UPDATE observed_evidence SET lead_id=$canonical_id WHERE lead_id = ANY($merged_ids)` |
| **EV-08** | **ResolveEntityConflictDetected** — EntityResolutionEngine (M2) executa o mesmo pipeline RRF + Jaro-Winkler, mas o RCS calculado cai na zona de conflito (0.65 <= RCS < 0.85), indicando candidatos ambíguos sem confiança suficiente para auto-merge | `EntityConflictDetected` — candidatos de merge registrados em `conflict_resolution_log` com flag `PENDING_MANUAL_REVIEW`, entidades mantidas separadas, `rcs_score=null` no entity_node afetado, `u_additive` elevado | Conflitos NÃO bloqueiam o pipeline — o sistema DEVE continuar processando com as entidades separadas. `rcs_score` fica registrado como `null` na entidade não-fundida, o que forçará `RCS=0.0` no cálculo de C_score (pior cenário explícito, não silencioso). Incerteza acumulada `u_additive += 0.15` para cada conflito não resolvido. Revisão manual notificada ao operador via observability dashboard. | `INSERT INTO conflict_resolution_log (conflict_id, candidate_ids, rcs_score, conflict_type, status, cycle_id, detected_at) VALUES (..., 'AMBIGUOUS_MATCH', 'PENDING_MANUAL_REVIEW', ...); UPDATE entity_nodes SET rcs_score=null, uncertainty_elevated=true, u_additive=u_additive+0.15 WHERE entity_id = ANY($candidate_ids)` |
| **EV-09** | **GenerateInferences** — InferenceNode (M3) traduz evidências brutas da Layer 1 em inferências estruturadas da Layer 2: classifica evidências por tipo de sinal, infere segmento, pain signals, growth signals e urgency signals | `InferencesGenerated` — Layer 2 (Generated Inferences) populada com inferências versionadas, cada uma com `inference_id`, `source_evidence_ids[]`, `inference_type`, `confidence` e classificação `SUPPORTING/CONTRADICTING/NEUTRAL` | Inferências são versionadas — nunca sobrescritas em produção. Se uma inferência existente é atualizada, a versão anterior recebe `superseded_by=$new_inference_id` e `superseded_at=NOW()`. O campo `source_evidence_ids[]` DEVE conter ao menos um `evidence_id` válido — inferência sem evidência-origem é proibida pelo schema e rejeitada com constraint violation. | `INSERT INTO generated_inferences (inference_id, entity_id, cycle_id, inference_type, inferred_value, confidence, source_evidence_ids, classification, version, inferred_at) VALUES (...); UPDATE generated_inferences SET superseded_by=$new_id, superseded_at=NOW() WHERE inference_id=$old_id AND superseded_by IS NULL` |
| **EV-10** | **UpdateBayesianHypotheses** — HypothesisNode (M3) executa atualização bayesiana sobre as hipóteses de Layer 3 usando Subjective Logic: atualiza `posterior` com base nas inferências classificadas como Supporting ou Contradicting, propaga incerteza | `HypothesesUpdated` — Layer 3 (Evaluated Hypotheses) atualizada com novos valores de `posterior`, tripla Subjective Logic (`belief`, `disbelief`, `uncertainty`), `Hypothesis_Confidence` recalculado, hipóteses promovidas ou rebaixadas entre status CANDIDATE, ACTIVE e REJECTED | Cada hipótese tem `cycle_id` — atualização fora do ciclo ativo é rejeitada. `dominant_hypothesis` é a hipótese com maior `posterior` E `status='ACTIVE'`. Regras de transição: `posterior >= 0.50` → ACTIVE; `posterior < 0.20` → REJECTED; demais → CANDIDATE. Hipótese sem nenhuma evidência Supporting na Layer 1 permanece em CANDIDATE independentemente do `posterior` calculado. | `INSERT INTO evaluated_hypotheses (hypothesis_id, entity_id, cycle_id, hypothesis_text, prior, posterior, belief, disbelief, uncertainty, hypothesis_confidence, status, evaluated_at) VALUES (...) ON CONFLICT (entity_id, cycle_id, hypothesis_text) DO UPDATE SET posterior=$new, belief=$b, disbelief=$d, uncertainty=$u, hypothesis_confidence=$hc, status=$status, evaluated_at=NOW()` |
| **EV-11** | **MapAndScoreBuyingCommittee** — CommitteeNode (M4) identifica os membros do comitê de compras (SC, BMO, Influenciadores), calcula `bmo_momentum_score`, detecta e classifica `trigger_events` ativos por urgência | `CommitteeMapped` — `committee_map` construído com cada membro identificado: `member_id`, `entity_id`, `role` (SC/BMO/INFLUENCER/UNKNOWN), `confidence`, `bmo_momentum_score`, `trigger_events[]`, `linkedin_url`, `designation` | Comitê incompleto (1/3 ou 2/3 membros identificados) NÃO bloqueia o pipeline — `committee.completeness` reflete a situação real. O papel BMO é necessário para `dominant_hypothesis` atingir status ACTIVE — se BMO não identificado, hipóteses permanecem CANDIDATE. Trigger events com `urgency_level='ALTA'` elevam o componente `S_intent` no cálculo posterior do O_score. `bmo_momentum_score=null` (UNKNOWN) não penaliza o pipeline. | `INSERT INTO committee_members (member_id, entity_id, cycle_id, role, confidence, bmo_momentum_score, trigger_events, linkedin_url, designation, identified_at) VALUES (...) ON CONFLICT (entity_id, cycle_id, role) DO UPDATE SET confidence=$new, bmo_momentum_score=$new, trigger_events=$new, identified_at=NOW()` |
| **EV-12** | **ComputeOpportunityAndConfidenceScores** — ScoringNode (M5 parcial) calcula `O_score` e `C_score` com suas fórmulas completas, usando todos os componentes já disponíveis no LeadState neste ponto da saga | `ScoresComputed` — `O_score` e `C_score` calculados e persistidos em `analytical_feature_store` com todos os componentes intermediários: `Fit`, `S_intent`, `Reachability`, `E_fresh`, `RCS`, `C_s`, `Uncertainty_Committee`, `Hypothesis_Confidence`, `∏SRS_k` | Fórmulas canônicas obrigatórias e imutáveis: `O_score = (0.45×Fit + 0.35×S_intent + 0.20×Reachability) × E_fresh`; `C_score = RCS × C_s × (1 - Uncertainty_Committee) × Hypothesis_Confidence × ∏SRS_k`. Nenhum componente pode ser `null` em produção — se ausente, usa valor degradado documentado. O cálculo é determinístico e reprodutível dado o mesmo estado de input (sem randomização). | `INSERT INTO analytical_feature_store (entity_id, cycle_id, feat_fit, feat_s_intent, feat_reachability_hybrid, feat_e_fresh, feat_rcs, feat_c_s_shannon, feat_uncertainty_committee, feat_hypothesis_confidence, feat_srs_product, o_score, c_score, computed_at) VALUES (...) ON CONFLICT (entity_id, cycle_id) DO UPDATE SET o_score=$o, c_score=$c, feat_fit=$fit, feat_s_intent=$si, feat_rcs=$rcs, feat_c_s_shannon=$cs, feat_uncertainty_committee=$uc, feat_hypothesis_confidence=$hc, feat_srs_product=$srs` |
| **EV-13** | **ExecuteMatrixRankFunction** — RankingEngine (M5) executa `MatrixRankFunction` sobre o `O_score` e `C_score` de todos os leads do ciclo para computar `P_score` final, atribui `rank_position` relativo e `action_label` | `PScoreRanked` — `P_score` calculado para todos os leads do ciclo, `rank_position` atribuído (1 = mais prioritário), `action_label` determinado com base em thresholds definidos no ICP contract | Fórmula canônica obrigatória: `P_score = O_score × (1 - 0.60 × e^(-4.0 × C_score))`. Ranking determinístico — ordenado por `P_score DESC`. Desempate por `O_score DESC`, depois por `entity_id` lexicográfico (garante reprodutibilidade total). Labels por threshold: `P_score >= 0.65` → `PRIORITY_ACTION`; `0.45 <= P < 0.65` → `MONITOR`; `0.25 <= P < 0.45` → `DELTA_SEARCH`; `P < 0.25` → `PRUNED`. | `UPDATE analytical_feature_store SET p_score=$p, rank_position=$rank, data_quality_flag=$flag, total_leads_in_cycle=$total WHERE entity_id=$1 AND cycle_id=$2` |
| **EV-14** | **GenerateConversationBlueprint** — Copywriter Agent (M5 CBG) invoca `xai_payload_builder` com `dominant_hypothesis`, `committee_map`, `pain_signals`, `trigger_events` ativos e `sector` inferido para gerar o `ConversationBlueprint` completo | `BlueprintGenerated` — `ConversationBlueprint` produzido com todos os 5 componentes: `hook` (urgency_level + texto de abertura), `context_trigger` (evento específico detectado), `pain_narrative` (em primeira pessoa da empresa alvo), `credibility_anchor` (evidência de resultado análogo), `cta_suggestion` (canal + mensagem + contraindications) | O blueprint DEVE ser adaptado ao vocabulário do setor da empresa alvo — vocabulário de Advocacia Corporativa é estruturalmente diferente do vocabulário de SaaS ou Engenharia. `contraindications` são obrigatórias (mínimo 1 item sempre). Se `dominant_hypothesis.posterior < 0.25`, blueprint é gerado com `partial=true` e campos ausentes explicitamente nulos com `reason` textual em linguagem de negócio. Blueprint em qualquer modo degradado recebe `data_quality_warning=true`. | `UPDATE analytical_feature_store SET dominant_hypothesis_id=$h2 WHERE entity_id=$1 AND cycle_id=$2` — blueprint serializado como JSON no payload final do XAI; metadados de geração registrados no campo `data_quality_flag` e nos logs de observabilidade via `v_cognitive_observability` |
| **EV-15** | **TransitionToDeltaSearchMode** — Sistema detecta em qualquer nó do pipeline que a Dynamic Search Score (DSS) atingiu threshold de saturação, OU que o `budget_brl` consumido atingiu 90% do limite do ciclo | `DeltaSearchModeActivated` — lead marcado com `search_mode='DELTA'`, pipeline de coleta full suspenso para este lead, `pruned_reason_log` registrado com `stopping_rule` ativada, lead enfileirado para reativação futura por trigger event qualificante | Delta Search é ativado quando: (a) `DSS <= 0.10` (saturação de descoberta — margem informacional abaixo de 10%), OU (b) custo acumulado do lead >= 90% do `budget_brl` per-lead, OU (c) `operating_mode='CACHE_ONLY'` ativado. Em Delta Search, APENAS re-scraping de trigger events específicos é permitido — coleta full proibida até reativação via EV-16. | `INSERT INTO pruned_reason_log (prune_id, entity_id, cycle_id, primary_stopping_rule, o_score_partial, c_score_partial, p_score_estimated, p_score_threshold_band, data_quality_flag, mode_transition_from, mode_transition_to, delta_search_interval_days, delta_triggers, audit_total_api_calls, audit_cost_brl, reason_summary, generated_at) VALUES (...); UPDATE entity_nodes SET last_updated_at=NOW() WHERE entity_id=$1` |
| **EV-16** | **DetectTriggerEventReactivatingDeltaSearch** — Sistema monitora continuamente leads com `search_mode='DELTA'` via scheduled job; detecta trigger event qualificante como nova vaga relevante, post de dor pública, mudança de cargo do BMO ou publicação sobre expansão | `DeltaSearchReactivated` — lead retirado do modo DELTA (`search_mode='DELTA_ACTIVE'`), pipeline de coleta seletiva reativado apenas para a fonte do trigger event detectado, `urgency_level` do lead atualizado, notificação enviada ao operador via observability dashboard | Trigger event DEVE ser classificado com `urgency_level` (ALTA/MEDIA/BAIXA) antes de reativar. Apenas `urgency_level='ALTA'` ou `'MEDIA'` reativam automaticamente — `'BAIXA'` fica em fila de espera para revisão manual. Reprocessamento delta executa apenas os nós relevantes ao trigger (não a saga completa): máximo `InferenceNode → HypothesisNode → CommitteeNode → ScoringNode → BlueprintNode`. ScrapingNode executa apenas para a fonte do trigger. | `INSERT INTO behavioral_momentum_log (event_id, entity_id, trigger_type, trigger_source, trigger_weight, detected_at, window_days, is_active, cycle_id) VALUES (...); UPDATE entity_nodes SET last_updated_at=NOW() WHERE entity_id=$1` |
| **EV-17** | **ReceiveCRMWebhook** — Sistema recebe payload `POST /api/v1/webhooks/crm` com `lead_id`, `outcome` (CLOSED_WON ou CLOSED_LOST) e `feedback_notes` de integração com CRM externo, autenticado via HMAC-SHA256 no header `X-CRM-Signature` | `CRMFeedbackReceived` — lead marcado com `crm_outcome`, `feedback_notes` persistido em `crm_outcome_log` com `processed_at=NULL` (pendente), evento enfileirado em SQS para processamento assíncrono; resposta HTTP 202 Accepted retornada imediatamente ao CRM chamador | Assinatura HMAC-SHA256 no header `X-CRM-Signature` DEVE ser validada antes de qualquer processamento — payload inválido retorna 401 Unauthorized imediatamente. Processamento é 100% assíncrono após 202 — nunca bloqueia o ciclo ativo. `feedback_notes` é campo livre mas truncado em 2000 caracteres. CLOSED_WON dispara atualização positiva de SRS via EV-18. CLOSED_LOST dispara investigação de hipótese falsa via EV-18. | `INSERT INTO crm_outcome_log (outcome_id, entity_id, cycle_id, outcome_type, feedback_notes, received_at, processed_at) VALUES (..., 'CLOSED_WON|CLOSED_LOST', ..., NULL); UPDATE entity_nodes SET last_updated_at=NOW() WHERE entity_id=$1` — processamento completo assíncrono via SQS consumer (EV-18) |
| **EV-18** | **UpdateSRSAndSourceQualityFeedbackLoop** — SQS consumer processa o evento `CRMFeedbackReceived`: atualiza o Source Reliability Score (SRS) de cada fonte contribuidora, ajusta pesos de keyword taxonomy com base no outcome verificado | `SRSUpdated` — `srs_k` atualizado para cada fonte (INSTAGRAM, LINKEDIN, CNPJ_GOV) via fórmula de feedback bayesiano: CLOSED_WON aumenta SRS das fontes dominantes na hipótese correta, CLOSED_LOST reduz SRS das fontes que geraram hipótese falsa; `keyword_taxonomy` recebe ajuste de peso para keywords presentes no lead | SRS é bounded: `0.10 <= srs_k <= 1.00` — nunca ultrapassa esses limites (LEAST/GREATEST no SQL). Regras de ajuste: CLOSED_WON aplica `srs_k += 0.05 × contribution_weight`; CLOSED_LOST aplica `srs_k -= 0.03 × false_hypothesis_weight`. Ajuste de keyword taxonomy só é persistido quando o ciclo acumular `>= 5 feedbacks` para a mesma keyword (evita over-fitting por sinal insuficiente). | `UPDATE source_reliability SET srs_current=LEAST(1.00, GREATEST(0.10, srs_current + $delta)), last_recalculated=NOW() WHERE source_key=$source; INSERT INTO crm_outcome_log (outcome_id, entity_id, cycle_id, outcome_type, o_score_at_outcome, c_score_at_outcome, p_score_at_outcome, dominant_hypothesis_at_outcome, received_at) VALUES (...); UPDATE icp_contract SET keyword_taxonomy=jsonb_set(keyword_taxonomy, $path, $new_weight) WHERE contract_id=$contract_id AND (SELECT COUNT(*) FROM crm_outcome_log WHERE cycle_id IN (SELECT cycle_id FROM evaluated_hypotheses WHERE hypothesis_id=$h AND entity_id=$entity_id)) >= 5` |

---

## 2. PIPELINE DE ORQUESTRAÇÃO DE SAGA (LeadHydrationSaga)

### 2.1 Definição e Justificativa do Padrão Saga

#### Por Que Saga (e Não 2PC/Transação Distribuída)

O sistema SocialSelling opera sobre múltiplos serviços e fontes de dados heterogêneas: scrapers de Instagram, LinkedIn, API da Receita Federal, cache Redis, PostgreSQL 16+, AWS SQS e AWS Lambda. Nesse contexto, o Two-Phase Commit (2PC) é estruturalmente inviável pelos seguintes motivos:

**1. Ausência de suporte a bloqueio distribuído nas fontes externas.**
Scrapers de Instagram e LinkedIn são chamadas HTTP sem semântica transacional — não existe mecanismo para manter um lock coordenado sobre esses recursos enquanto outros participantes aguardam confirmação. A tentativa de coordenar 2PC com uma API de scraping resultaria em deadlock ou timeout garantido.

**2. Latência inaceitável para throughput de produção.**
2PC requer duas rodadas síncronas de comunicação com todos os participantes antes de qualquer commit. Com scrapers que têm latência de 2s a 15s e timeouts variáveis por IP e horário, o bloqueio seria catastrófico para o throughput do sistema.

**3. Falhas parciais são estado desejável, não excepcional.**
No SocialSelling, é perfeitamente válido — e esperado — que LinkedIn esteja rate-limited enquanto Instagram e CNPJ funcionam normalmente. O sistema deve produzir resultado degradado e auditável, não falhar completamente por indisponibilidade de uma fonte.

**4. Compensações lógicas são semanticamente suficientes.**
Não existe "desfazer" uma coleta de evidência — uma vez que um dado foi coletado, hashado e armazenado na Layer 1 (append-only), ele existiu. A compensação correta é marcar o dado como proveniente de modo degradado (`uncertainty_additive`), elevar a incerteza nos scores e prosseguir com rastreabilidade total.

#### Tipo de Saga Adotada

**Saga Baseada em Orquestração (Orchestration-Based Saga)** — um único Orchestrator central (`LeadHydrationSaga`) coordena todos os participantes. Cada participante (nó do grafo LangGraph) executa sua etapa e retorna o controle ao Orchestrator, que decide o próximo passo com base nas bordas condicionais do grafo de estados.

Esta escolha foi feita em detrimento da Saga Coreografada (Choreography-Based Saga) pelos seguintes motivos:

- O pipeline tem **ordem total estrita** entre os steps — scoring depende de inferências, que dependem de evidências normalizadas, que dependem de coleta. Não há paralelismo inter-step.
- A lógica de compensação é **centralizada e auditável** — o Orchestrator é o único ponto de decisão sobre compensações, sem lógica distribuída entre participantes.
- Debugging e observabilidade são significativamente mais simples com um único ponto de controle e um único log de decisões.
- O LangGraph implementa nativamente o grafo de estados com bordas condicionais, sendo a abstração arquitetural natural para este padrão.

#### Implementação: Comunicação Assíncrona via AWS SQS

Steps com efeitos colaterais de longa duração (ScrapingNode com chamadas HTTP externas, PersistenceNode com escrita em PostgreSQL) comunicam-se com serviços externos via mensagens SQS. O Orchestrator aguarda confirmação via polling do `LeadState` antes de avançar ao próximo nó. Steps puramente computacionais (ScoringNode, BlueprintNode, HypothesisNode) executam em memória síncrona dentro do processo Python/LangGraph sem I/O externo bloqueante.

---

### 2.2 Estrutura do LeadHydrationSaga — Definição de Estado

O `LeadState` é o dicionário Python/JSON que representa o estado completo do grafo LangGraph em memória volátil durante a execução da saga. É o "quadro negro" compartilhado por todos os agentes especialistas. É serializado para persistência definitiva apenas na conclusão bem-sucedida (PersistenceNode) ou parcialmente em falha catastrófica (enfileirado no SQS DLQ).

```python
# LeadState — Tipagem completa (TypedDict Python)
# Versão: 1.0.0

from typing import TypedDict, List, Dict, Any, Optional

class ObservedEvidence(TypedDict):
    evidence_id: str
    source: str                         # "INSTAGRAM" | "LINKEDIN" | "CNPJ_GOV"
    source_url: str
    content_hash: str                   # SHA-256 do conteúdo normalizado
    raw_payload: Dict[str, Any]
    normalized_payload: Dict[str, Any]
    e_fresh: float                      # E_fresh calculado no momento da coleta
    ttl_hours: int                      # TTL de frescor por fonte
    uncertainty_additive: float         # 0.0 em FULL, 0.20 para LinkedIn em DEGRADED_LINKEDIN
    is_anchor: bool                     # True apenas para CNPJ_GOV
    collected_at: str                   # ISO 8601

class EntityNode(TypedDict):
    entity_id: str
    canonical_name: str
    canonical_cnpj: Optional[str]
    canonical_linkedin_url: Optional[str]
    canonical_instagram_handle: Optional[str]
    rcs_score: Optional[float]          # None se conflito não resolvido (forçará RCS=0.0 no C_score)
    uncertainty_elevated: bool
    u_additive: float                   # Acumulado de penalidades de incerteza
    disqualified: bool
    disqualification_reason: Optional[str]
    error_state: bool                   # True se erro catastrófico ocorreu neste nó
    first_seen_at: str

class EntityEdge(TypedDict):
    edge_id: str
    source_entity_id: str
    target_entity_id: str
    edge_type: str                      # "MERGE" | "CONFLICT" | "RELATED"
    rcs_score: float
    created_at: str

class GeneratedInference(TypedDict):
    inference_id: str
    entity_id: str
    inference_type: str                 # "SEGMENT" | "PAIN_SIGNAL" | "GROWTH_SIGNAL" | "URGENCY_SIGNAL" | "REACHABILITY_SIGNAL"
    inferred_value: Any
    confidence: float                   # 0.0 a 1.0
    source_evidence_ids: List[str]      # Mínimo 1 evidence_id obrigatório
    classification: str                 # "SUPPORTING" | "CONTRADICTING" | "NEUTRAL"
    version: int
    superseded_by: Optional[str]
    inferred_at: str

class EvaluatedHypothesis(TypedDict):
    hypothesis_id: str
    hypothesis_text: str
    prior: float
    posterior: float
    belief: float                       # Subjective Logic — crença
    disbelief: float                    # Subjective Logic — descrença
    uncertainty: float                  # Subjective Logic — incerteza residual
    hypothesis_confidence: float        # Componente do C_score
    status: str                         # "CANDIDATE" | "ACTIVE" | "REJECTED"
    cycle_id: str
    evaluated_at: str

class TriggerEvent(TypedDict):
    trigger_id: str
    event_type: str
    urgency_level: str                  # "ALTA" | "MEDIA" | "BAIXA"
    source: str
    description: str
    detected_at: str

class CommitteeMember(TypedDict):
    member_id: str
    entity_id: str
    name: str
    role: str                           # "SC" | "BMO" | "INFLUENCER" | "UNKNOWN"
    designation: str
    linkedin_url: Optional[str]
    bmo_momentum_score: Optional[float] # None = UNKNOWN (não penaliza o pipeline)
    trigger_events: List[TriggerEvent]
    confidence: float
    identified_at: str

class CommitteeMap(TypedDict):
    members: List[CommitteeMember]
    completeness: int                   # Número de roles distintos identificados (0, 1, 2 ou 3)
    bmo: Optional[CommitteeMember]
    sc: Optional[CommitteeMember]
    influencers: List[CommitteeMember]

class ScoreVector(TypedDict):
    fit: float
    s_intent: float
    reachability: float
    e_fresh: float
    o_score: float
    rcs: float
    c_s: float
    uncertainty_committee: float
    hypothesis_confidence: float
    srs_product: float                  # ∏SRS_k — produto dos SRS de cada fonte contribuidora
    c_score: float
    p_score: float
    rank_position: Optional[int]
    action_label: Optional[str]         # "PRIORITY_ACTION" | "MONITOR" | "DELTA_SEARCH" | "PRUNED"

class ConversationBlueprint(TypedDict):
    hook: Dict[str, str]                # {text: str, urgency_level: "ALTA"|"MEDIA"|"BAIXA"}
    context_trigger: Dict[str, str]     # {event_description: str, source: str, detected_at: str}
    pain_narrative: Optional[str]       # Em primeira pessoa da empresa alvo — None se partial=True
    credibility_anchor: Optional[Dict]  # {evidence_text: str, result_metric: Optional[str]}
    cta_suggestion: Dict[str, Any]      # {channel: str, message_draft: str, contraindications: List[str]}
    partial: bool                       # True se blueprint incompleto por posterior < 0.25
    data_quality_warning: bool          # True se operating_mode != "FULL"
    missing_fields: Optional[Dict[str, str]]  # {campo: razão_da_ausência}

class AuditEntry(TypedDict):
    step: str
    action: str
    timestamp: str
    state_snapshot_hash: str            # SHA-256 do estado no momento da decisão

class LeadState(TypedDict):
    # --- Identidade e Contexto ---
    lead_id: str                        # Identificador canônico do lead (ex: "LE-2024-00123")
    cycle_id: str                       # UUID do ciclo de busca corrente
    entity_id: str                      # UUID da entidade resolvida (pode diferir de lead_id antes da resolução)
    icp_contract_id: str                # UUID do contrato ICP ativo

    # --- Modo Operacional ---
    operating_mode: str                 # "FULL" | "DEGRADED_LINKEDIN" | "DEGRADED_INSTAGRAM" | "CACHE_ONLY"
    search_mode: str                    # "FULL_SEARCH" | "DELTA" | "DELTA_ACTIVE"

    # --- Dados Coletados (Layer 1 — Observed Evidence) ---
    evidence_batch: List[ObservedEvidence]

    # --- Grafo de Entidades ---
    entity_nodes: Dict[str, EntityNode]
    entity_edges: List[EntityEdge]

    # --- Inferências (Layer 2 — Generated Inferences) ---
    inferences: List[GeneratedInference]

    # --- Hipóteses (Layer 3 — Evaluated Hypotheses) ---
    hypotheses: Dict[str, EvaluatedHypothesis]  # key = hypothesis_text
    dominant_hypothesis: Optional[EvaluatedHypothesis]

    # --- Comitê de Compras (M4) ---
    committee: Optional[CommitteeMap]

    # --- Scores (M5) ---
    scores: Optional[ScoreVector]

    # --- Conversation Blueprint (M5 CBG) ---
    blueprint: Optional[ConversationBlueprint]

    # --- Controle de Fluxo e Auditoria ---
    stopping_triggered: bool
    stopping_reason: Optional[str]
    errors: List[str]
    compensation_executed: List[str]    # Audit trail de compensações executadas
    current_step: str
    steps_completed: List[str]
    audit_trail: List[AuditEntry]
```

---

### 2.3 SUCCESS PATH — Caminho Feliz

O Success Path descreve o fluxo completo da LeadHydrationSaga quando todos os steps executam sem falhas e em modo FULL. Cada step é descrito com seus inputs esperados, a transformação aplicada ao LeadState, os outputs produzidos, e os critérios precisos de sucesso e falha.

---

#### Step 1 — SeedIngestionNode

**Responsabilidade:** Normalizar e validar a seed list de entrada, preparando o LeadState inicial para o pipeline.

**Input State Esperado:**
```json
{
  "lead_id": null,
  "cycle_id": "UUID-DO-CICLO",
  "icp_contract_id": "UUID-DO-CONTRATO",
  "operating_mode": "FULL",
  "search_mode": "FULL_SEARCH",
  "evidence_batch": [],
  "entity_nodes": {},
  "entity_edges": [],
  "inferences": [],
  "hypotheses": {},
  "dominant_hypothesis": null,
  "committee": null,
  "scores": null,
  "blueprint": null,
  "stopping_triggered": false,
  "stopping_reason": null,
  "errors": [],
  "compensation_executed": [],
  "current_step": "INIT",
  "steps_completed": [],
  "audit_trail": []
}
```

**Transformação do LeadState:**
1. Recebe `seed_list` do payload do ciclo (lista de handles Instagram, URLs LinkedIn, CNPJs ou nomes de empresas em texto livre)
2. Para cada seed: normaliza em lowercase, aplica trim, remove caracteres especiais não-alphanuméricos, valida formato de CNPJ (regex de 14 dígitos) e formato de URL (schema https)
3. Seeds inválidas são registradas em `errors` sem bloquear as válidas (falha parcial tolerada)
4. Para cada seed válida: cria `lead_id` provisório com prefixo `"LE-"` e UUID, cria `entity_id` inicial em `entity_nodes` com `canonical_name` normalizado
5. Valida `icp_contract_id` consultando o banco — se não encontrado ou `status != 'ACTIVE'`, emite `CycleAborted` e encerra saga imediatamente

**Output State:**
- `entity_nodes` populado com uma entrada por seed válida
- `lead_id` atribuído
- `current_step = "SeedIngestionNode"`
- `steps_completed = ["SeedIngestionNode"]`

**Critérios de Sucesso:**
- Ao menos 1 seed válida normalizada com `entity_id` criado em `entity_nodes`
- `icp_contract_id` validado como `status='ACTIVE'`
- Evento `SeedIngested` emitido no LeadState audit trail

**Critérios de Falha Fatal (encerra saga):**
- Zero seeds válidas após normalização → emitir `CycleAborted`, registrar em `errors` com razão `ZERO_VALID_SEEDS`, encerrar saga sem compensação
- `icp_contract_id` não encontrado ou `INACTIVE` → emitir `CycleAborted` com `reason='INVALID_ICP_CONTRACT'`

---

#### Step 2 — ScrapingNode

**Responsabilidade:** Coleta de evidências brutas em paralelo assíncrono de Instagram, LinkedIn e CNPJ para todos os leads do ciclo, com gestão de modos degradados.

**Input State Esperado:**
- `entity_nodes` com ao menos 1 entidade com seeds normalizadas (Instagram handle, LinkedIn URL ou CNPJ)
- `operating_mode = "FULL"`
- `evidence_batch = []`
- `icp_contract_id` válido (para carregar keyword taxonomy)

**Transformação do LeadState:**
1. Carrega `keyword_taxonomy` do ICP contract ativo para parametrizar os scrapers
2. Dispara 3 tarefas assíncronas em paralelo via `asyncio.gather` com timeout individual de 30s:
   - `instagram_scraper.collect(handles, keyword_taxonomy)` → posts recentes, bio, engagement, hashtags
   - `linkedin_scraper.collect(linkedin_urls, keyword_taxonomy)` → cargo, headcount, vagas, artigos
   - `cnpj_resolver.collect(cnpjs)` → dados cadastrais completos
3. Cada tarefa retorna uma lista de `ObservedEvidence` com `content_hash` SHA-256 pré-computado
4. Evidências de cada fonte são adicionadas ao `evidence_batch` do LeadState
5. Se qualquer fonte falha: aciona COMPENSATION correspondente (C-01, C-02 ou C-03 conforme a fonte)
6. `operating_mode` pode ser alterado por compensação neste step

**Output State:**
- `evidence_batch` populado com evidências brutas de fontes funcionais (com `content_hash` mas sem normalização definitiva ainda)
- `operating_mode` possivelmente alterado para `DEGRADED_LINKEDIN`, `DEGRADED_INSTAGRAM` ou `CACHE_ONLY`
- `compensation_executed` atualizado se houve degradação

**Critérios de Sucesso:**
- Ao menos 2 fontes retornam evidências em modo FULL
- Ao menos 1 fonte retorna evidências em qualquer modo degradado
- Evento `EvidenceBatchCollected` emitido

**Critérios de Falha Fatal:**
- Zero fontes retornam qualquer evidência → Compensação C-03 (CACHE_ONLY) ativada, alerta CloudWatch CRITICAL, lead enfileirado em SQS DLQ para reprocessamento em 1h

---

#### Step 3 — NormalizationNode

**Responsabilidade:** Deduplicação SHA-256, normalização definitiva de strings e persistência append-only na Layer 1 (Observed Evidence).

**Input State Esperado:**
- `evidence_batch` com evidências brutas de múltiplas fontes (com `content_hash` provisório)
- `operating_mode` definitivamente definido (incluindo possíveis degradações do Step 2)

**Transformação do LeadState:**
1. Para cada evidência em `evidence_batch`:
   - Normaliza `raw_payload`: lowercase em campos string, strip diacritics via unidecode, trim whitespace em todos os campos
   - Recomputa `content_hash = SHA256(json.dumps(normalized_payload, sort_keys=True, ensure_ascii=False))`
   - Verifica se `content_hash` já existe em `observed_evidence` no banco
   - Se duplicata: descarta silenciosamente (não adiciona ao estado final)
   - Se nova: calcula `E_fresh = e^(-ln2/t½ × Δt)` onde `Δt = now() - collected_at` em horas
   - Define `ttl_hours` por fonte: CNPJ=9999, LinkedIn=24, Instagram=6 (FULL) ou 12 (DEGRADED_INSTAGRAM)
   - Define `uncertainty_additive`: 0.0 para todas as fontes em FULL, 0.20 para fonte LINKEDIN em DEGRADED_LINKEDIN
2. Persiste batch de evidências únicas em `observed_evidence` via `INSERT ... ON CONFLICT (content_hash) DO NOTHING`
3. Atualiza `evidence_batch` no LeadState apenas com evidências únicas efetivamente persistidas

**Output State:**
- `evidence_batch` contém apenas evidências únicas com `content_hash` definitivo, `e_fresh`, `ttl_hours` e `uncertainty_additive` calculados
- Layer 1 populada no banco (append-only, imutável após este ponto)
- Evento `EvidenceNormalized` emitido

**Critérios de Sucesso:**
- Ao menos 1 evidência única persistida em Layer 1
- Nenhum `content_hash` duplicado no `evidence_batch` final do LeadState

**Critérios de Falha Não-Fatal:**
- Zero evidências únicas após deduplicação (todas eram duplicatas de ciclos anteriores) → registrar em `errors`, continuar pipeline; scores serão calculados com evidências antigas do banco — semanticamente válido para leads recorrentes

---

#### Step 4 — EntityResolutionNode

**Responsabilidade:** Resolver e fundir referências de entidade usando o pipeline RRF (Reciprocal Rank Fusion) + Jaro-Winkler + penalizadores de incerteza.

**Input State Esperado:**
- `evidence_batch` normalizado com evidências de múltiplas fontes (para extração de aliases e identificadores)
- `entity_nodes` com entidades iniciais criadas no SeedIngestionNode (pré-resolução)

**Transformação do LeadState:**
1. Para cada par de entidades candidatas ao merge (combinações O(n²) sobre `entity_nodes`):
   - Executa `jaro_winkler_scorer` sobre pares de `canonical_name` e todos os aliases detectados nas evidências
   - Executa `rrfusion_engine` combinando rankings de múltiplos critérios: similaridade de nome (peso 0.40), match de CNPJ (peso 0.35), similaridade de URL/handle (peso 0.15), correspondência de segmento inferido (peso 0.10)
   - Aplica penalizadores hard: CNPJ diferente entre candidatos → penalidade -0.30 no score final; segmento inferido divergente → -0.15
   - Computa `rcs_score` final no range [0.0, 1.0]
2. Decisão por `rcs_score`:
   - `rcs_score >= 0.85` → AutoMerge (EV-07): fundir entidades, eleger `entity_id` canônico, atualizar `entity_nodes`, registrar em `entity_merge_log`, registrar aresta `MERGE` em `entity_edges`
   - `0.65 <= rcs_score < 0.85` → ConflictDetected (EV-08): manter separadas, Compensação C-04, registrar aresta `CONFLICT` em `entity_edges`
   - `rcs_score < 0.65` → entidades distintas sem relação, sem merge, sem aresta criada
3. Atualiza `entity_nodes` com `rcs_score`, campos `canonical_*` preenchidos, `u_additive` acumulado pós-conflitos

**Output State:**
- `entity_nodes` com resolução aplicada (merges executados ou conflitos documentados)
- `entity_edges` populado com arestas de merge e conflito
- Evento `EntityResolved` emitido para merges, `ConflictDetected` para conflitos (não mutuamente exclusivos — podem ocorrer ambos em um mesmo ciclo)

**Critérios de Sucesso:**
- Todos os pares de candidatos avaliados com `rcs_score` computado
- Nenhuma entidade processada sem decisão documentada (merge, conflito ou distinção)

**Critérios de Falha Compensável (não fatal):**
- `rcs_score` na zona de conflito → Compensação C-04: `rcs_score=null`, `u_additive+=0.15`, flag `MANUAL_REVIEW`; pipeline continua

---

#### Step 5 — InferenceNode

**Responsabilidade:** Traduzir evidências observadas da Layer 1 em inferências estruturadas da Layer 2, classificando cada inferência pelo seu papel em relação à hipótese mais provável.

**Input State Esperado:**
- `evidence_batch` normalizado e deduplicado com `e_fresh` calculados
- `entity_nodes` com resolução de entidade aplicada (IDs canônicos definidos)

**Transformação do LeadState:**
1. Para cada evidência em `evidence_batch`, classifica o tipo de sinal inferido:
   - `SEGMENT`: inferência de segmento de mercado alvo (Advocacia Corporativa / Consultoria / SaaS / Engenharia) com base em CNAE, bio e keywords
   - `PAIN_SIGNAL`: menção explícita ou implícita de dor operacional detectada (ex: "sobrecarregada com processos manuais", "buscando escalar a equipe")
   - `GROWTH_SIGNAL`: indicador de expansão ou tração positiva (vagas abertas, novas sedes, lançamento de produto, contratações de liderança)
   - `URGENCY_SIGNAL`: trigger event que indica janela de urgência imediata (mudança de cargo do BMO, post sobre busca de solução específica)
   - `REACHABILITY_SIGNAL`: disponibilidade verificada de canal de contato qualificado (LinkedIn público, email direto, DM aberta)
2. Para cada inferência gerada:
   - Atribui `confidence` (0.0 a 1.0) baseado no número de evidências corroboradoras e na força do sinal
   - Classifica como `SUPPORTING` (corrobora a hipótese mais provável do ICP), `CONTRADICTING` (contradiz a hipótese) ou `NEUTRAL` (informacional sem impacto direto)
   - Registra `source_evidence_ids[]` — mínimo 1 `evidence_id` válido por inferência (constraint obrigatório)
   - Verifica versão: `version=1` para novas, incrementa para substituições de inferências existentes no mesmo `entity_id/cycle_id`
3. Persiste em `generated_inferences` (Layer 2) com versionamento controlado

**Output State:**
- `inferences` populado com lista de inferências classificadas com `source_evidence_ids` rastreáveis
- Layer 2 populada no banco com controle de versão ativo
- Evento `InferencesGenerated` emitido

**Critérios de Sucesso:**
- Ao menos 1 inferência gerada com `source_evidence_ids` não-vazio
- Ao menos 1 inferência classificada como `SUPPORTING`

**Critérios de Falha Compensável:**
- Zero inferências `SUPPORTING` geradas → `Hypothesis_Confidence` será degradado no passo seguinte; pipeline continua sem bloqueio

---

#### Step 6 — HypothesisNode

**Responsabilidade:** Executar a atualização bayesiana das hipóteses da Layer 3 usando Subjective Logic, propagando incerteza de forma matematicamente rigorosa.

**Input State Esperado:**
- `inferences` com classificação `SUPPORTING/CONTRADICTING/NEUTRAL` e `confidence` definidos
- `hypotheses` com priors carregados do `icp_contract` ativo (inicialização do ciclo)

**Transformação do LeadState:**
1. Para cada hipótese em `hypotheses`:
   - Conta evidências `SUPPORTING` (`n_s`) e `CONTRADICTING` (`n_c`) nas `inferences`, ponderadas por `confidence`
   - Aplica atualização bayesiana via fórmula: `posterior = (prior × Σw_s) / (prior × Σw_s + (1-prior) × Σw_c)` onde `w` é a `confidence` de cada inferência
   - Calcula tripla de Subjective Logic: `belief = n_s/(n_s+n_c+2)`, `disbelief = n_c/(n_s+n_c+2)`, `uncertainty = 2/(n_s+n_c+2)` onde `n_s` e `n_c` são contagens inteiras de inferências classificadas
   - Decide status de transição: `posterior >= 0.50` → `ACTIVE`; `posterior < 0.20` → `REJECTED`; demais → `CANDIDATE`
2. Identifica `dominant_hypothesis`: hipótese com `status='ACTIVE'` e maior `posterior` — se nenhuma ACTIVE, usa a CANDIDATE de maior `posterior`
3. Calcula `Hypothesis_Confidence = dominant_hypothesis.posterior × (1 - dominant_hypothesis.uncertainty)` — multiplicação explícita de força da crença pela complementar da incerteza
4. Propaga a incerteza da tripla Subjective Logic para `u_additive` do `entity_node` correspondente

**Output State:**
- `hypotheses` com `posterior`, tripla Subjective Logic, `status` e `hypothesis_confidence` atualizados para cada hipótese
- `dominant_hypothesis` identificado (ACTIVE ou melhor CANDIDATE)
- Layer 3 atualizada no banco com `ON CONFLICT ... DO UPDATE`

**Critérios de Sucesso:**
- Ao menos 1 hipótese com `status='ACTIVE'` e `posterior > 0.25`
- `Hypothesis_Confidence > 0.0`

**Critérios de Falha Compensável:**
- Todas as hipóteses em `CANDIDATE` ou `REJECTED` → Compensação C-05: `dominant_hypothesis` é o melhor CANDIDATE disponível, `Hypothesis_Confidence` degradado, pipeline continua com blueprint parcial esperado no Step 9

---

#### Step 7 — CommitteeNode

**Responsabilidade:** Identificar os membros do comitê de compras (SC, BMO, Influenciadores), calcular o `bmo_momentum_score` e detectar trigger events ativos com urgência classificada.

**Input State Esperado:**
- `inferences` com `SEGMENT` e `PAIN_SIGNAL` identificados (para guiar busca de personas)
- `hypotheses` com `dominant_hypothesis` definido (pode ser CANDIDATE)
- `entity_nodes` com `canonical_linkedin_url` resolvido (quando disponível)

**Transformação do LeadState:**
1. Executa `persona_scorer` sobre perfis LinkedIn e Instagram para classificar personas por papel:
   - **SC (Sponsoring Champion):** perfil com poder de influência na organização, dor articulada publicamente, provável champion interno da solução — frequentemente a própria fundadora em empresas de 5-30 pessoas
   - **BMO (Budget and Mobilization Owner):** perfil com autoridade declarada de decisão orçamentária — Sócia, CEO, Diretora Geral, Fundadora, CFO
   - **INFLUENCER:** perfis intermediários que amplificam a dor ou a solução sem autoridade de decisão final
2. Para cada membro identificado:
   - Calcula `bmo_momentum_score` via `momentum_cluster_engine` com base em atividade recente (posts, interações, mudanças de cargo nos últimos 90 dias)
   - Detecta `trigger_events` ativos sobre o membro: nova vaga aberta na área, post público sobre dor específica, mudança recente de cargo, publicação sobre expansão
   - Define `urgency_level` de cada trigger event (ALTA/MEDIA/BAIXA) com base em recência e especificidade
3. Computa `committee.completeness` = número de roles distintos identificados (0 a 3)
4. Atualiza `S_intent` nos scores intermediários com base em trigger events de `urgency_level='ALTA'` detectados

**Output State:**
- `committee` completamente populado com `members`, `bmo` (ou null), `sc` (ou null), `influencers`, `completeness`
- Scores intermediários com `s_intent` atualizado por trigger events de alta urgência
- Evento `CommitteeMapped` emitido

**Critérios de Sucesso:**
- Ao menos 1 membro do comitê identificado com qualquer role
- `committee.completeness >= 1`

**Critérios de Falha Não-Fatal:**
- Zero membros identificados → `committee.completeness = 0`, `bmo = null`, `sc = null`; `C_s = 0.0` no cálculo de C_score; `S_intent` não elevado por triggers; pipeline continua com scores degradados mas calculáveis

---

#### Step 8 — ScoringNode

**Responsabilidade:** Calcular `O_score`, `C_score` e `P_score` com as fórmulas canônicas e imutáveis do sistema, persistindo todos os componentes intermediários para auditoria.

**Input State Esperado:**
- `inferences` com `SEGMENT`, `PAIN_SIGNAL`, `REACHABILITY_SIGNAL` classificados
- `hypotheses` com `dominant_hypothesis` e `Hypothesis_Confidence` calculados
- `committee` com `completeness`, `bmo_momentum_score` e trigger events
- `entity_nodes` com `rcs_score` (ou null se conflito) e `u_additive` acumulado

**Transformação do LeadState:**
1. Extrai e calcula componentes do O_score:
   - `Fit`: score de compatibilidade com ICP — ponderação sobre segmento confirmado (0/1), porte dentro do range 5-30 (0/0.5/1), setor na lista-alvo (0/1), CNAE compatível (0/0.5/1) — range [0.0, 1.0]
   - `S_intent`: score de intenção de compra — combinação de `PAIN_SIGNAL.confidence` médio + elevação por trigger events `ALTA` (+0.25 cada, teto 1.0) — range [0.0, 1.0]
   - `Reachability`: disponibilidade de canal — derivada de `REACHABILITY_SIGNAL.confidence` + `bmo_momentum_score` normalizado — range [0.0, 1.0]
   - `E_fresh`: média ponderada dos `e_fresh` das evidências da Layer 1, ponderada por `confidence` das inferências derivadas
   - **Fórmula canônica:** `O_score = (0.45 × Fit + 0.35 × S_intent + 0.20 × Reachability) × E_fresh`

2. Extrai e calcula componentes do C_score:
   - `RCS`: `entity_node.rcs_score` se merge executado; `0.0` se `rcs_score=null` (conflito não resolvido)
   - `C_s`: `committee.completeness / 3` — completude do comitê normalizada
   - `Uncertainty_Committee`: `min(1.0, entity_node.u_additive)` — incerteza acumulada de todas as penalidades
   - `Hypothesis_Confidence`: valor calculado no HypothesisNode
   - `∏SRS_k`: produto dos `srs_value` de cada fonte que contribuiu com pelo menos 1 evidência `SUPPORTING`
   - **Fórmula canônica:** `C_score = RCS × C_s × (1 - Uncertainty_Committee) × Hypothesis_Confidence × ∏SRS_k`

3. Calcula P_score e atribui action_label:
   - **Fórmula canônica:** `P_score = O_score × (1 - 0.60 × e^(-4.0 × C_score))`
   - Labels por threshold: `P_score >= 0.65` → `PRIORITY_ACTION`; `0.45 <= P < 0.65` → `MONITOR`; `0.25 <= P < 0.45` → `DELTA_SEARCH`; `P < 0.25` → `PRUNED`

4. Persiste `analytical_feature_store` com todos os componentes e atualiza `analytical_feature_store`

**Output State:**
- `scores` completamente populado com todos os componentes intermediários e valores finais calculados
- `scores.action_label` definido
- Evento `ScoresComputed` emitido

**Critérios de Sucesso:**
- `P_score` calculado como float determinístico no range `[0.0, 1.0]`
- Todos os componentes intermediários registrados em `analytical_feature_store` para auditoria

**Critérios de Falha Fatal:**
- Qualquer componente retornando `NaN` ou `Infinity` → registrar em `errors`, marcar `entity_node.error_state=true`, não persistir dados inconsistentes, enfileirar em SQS DLQ

---

#### Step 9 — BlueprintNode

**Responsabilidade:** Gerar o `ConversationBlueprint` completo via Copywriter Agent (M5 CBG), atuando como um SDR de Elite especializado no setor da empresa alvo.

**Input State Esperado:**
- `dominant_hypothesis` definido (ACTIVE ou melhor CANDIDATE)
- `committee` com `bmo` e `sc` identificados (mesmo que parcialmente)
- `inferences` com `PAIN_SIGNAL` classificados e suas evidências-origem
- `scores` com `P_score` e `action_label` calculados
- `entity_nodes` com `canonical_name` e segmento inferido disponíveis

**Transformação do LeadState:**
1. `xai_payload_builder` lê o contexto completo do LeadState e determina o setor da empresa alvo a partir do segmento inferido
2. CBG (Conversation Blueprint Generator) gera cada componente com adaptação de vocabulário ao setor:
   - **Hook:** frase de abertura de alta relevância contextual (máximo 2 frases), `urgency_level` derivado dos trigger events ativos — vocabulário de Advocacia usa termos como "mandatos", "carteira", "clientes corporativos"; vocabulário de SaaS usa "churn", "ARR", "onboarding"
   - **Context Trigger:** descrição específica do evento que justifica o contato agora (ex: "Identificamos que a empresa abriu 3 vagas para área jurídica nos últimos 30 dias")
   - **Pain Narrative:** narrativa em primeira pessoa da empresa alvo, articulando a dor de dentro para fora — "Estamos crescendo rapidamente mas nossos processos de gestão de clientes ainda são manuais..."
   - **Credibility Anchor:** evidência concreta de resultado análogo com métrica quando disponível (ex: "Empresas similares de Advocacia Corporativa com 15-20 colaboradores reduziram tempo de prospecção em 40% nos primeiros 3 meses")
   - **CTA Suggestion:** canal recomendado com maior `Reachability` + rascunho de mensagem de abertura adaptado ao setor + lista de `contraindications` (o que NÃO fazer)
3. Verifica `dominant_hypothesis.posterior`:
   - `>= 0.25` → blueprint COMPLETO, `partial=false`, todos os 5 campos populados
   - `< 0.25` → blueprint PARCIAL, `partial=true`, campos dependentes de hipótese confirmada ficam `null` com `reason` textual em linguagem de negócio
4. Aplica `data_quality_warning=true` se `operating_mode != "FULL"`

**Output State:**
- `blueprint` populado (completo ou parcial conforme `posterior`)
- `analytical_feature_store.approach_blueprint` atualizado
- Evento `BlueprintGenerated` emitido

**Critérios de Sucesso:**
- `blueprint != null`
- Todos os 5 componentes populados OU `partial=true` com `missing_fields` documentado
- `cta_suggestion.contraindications` com ao menos 1 item (obrigatório em qualquer caso)

**Critérios de Falha Compensável:**
- `dominant_hypothesis.posterior < 0.25` → Compensação C-06: blueprint parcial com flags e razões por campo ausente; não bloqueia PersistenceNode

---

#### Step 10 — PersistenceNode

**Responsabilidade:** Escrita atômica do LeadState completo no Feature Store — único ponto de persistência definitiva do pipeline completo.

**Input State Esperado:**
- LeadState completamente populado com todos os 9 steps anteriores concluídos
- `blueprint` presente (completo ou parcial)
- `scores.p_score` calculado e não-nulo

**Transformação do LeadState:**
1. Serializa o LeadState completo para JSON canônico (`json.dumps(..., sort_keys=True, ensure_ascii=False)`)
2. Executa escrita atômica dentro de uma única transação PostgreSQL (`BEGIN ... COMMIT`):
   - `UPSERT` em `analytical_feature_store` com todos os scores, blueprint e metadados
   - `UPSERT` em `entity_nodes` com estado final de resolução de entidade
   - `INSERT` em `lead_hydration_log` com `timestamp`, `steps_completed[]`, `operating_mode` e `compensation_executed[]`
3. Emite evento `LeadHydrated` para fila SQS `socialselling-lead-hydrated` (notificação para downstream consumers da API)
4. Atualiza `leads.search_mode` e `leads.last_hydrated_at` e `leads.action_label`
5. Invalida entrada de cache Redis para `lead_id` (key: `lead:{lead_id}:xai_payload`) via `DEL` — força recarregamento na próxima consulta à API

**Output State:**
- `current_step = "PersistenceNode"`
- `steps_completed` contendo todos os 10 steps
- LeadState marcado como completo na saga

**Critérios de Sucesso:**
- Transação PostgreSQL commitada com sucesso (sem rollback)
- Evento `LeadHydrated` publicado em SQS com confirmação de entrega
- Cache Redis invalidado

**Critérios de Falha Recuperável:**
- Falha de conexão PostgreSQL → retry com backoff exponencial: tentativa 1 após 2s, tentativa 2 após 8s, tentativa 3 após 30s
- Se 3 retries falham → enfileirar payload completo em SQS DLQ `socialselling-persistence-dlq` com `retry_at = NOW() + 1h`; não marcar saga como completa; registrar alarme CloudWatch

---

### 2.4 COMPENSATING ACTIONS — Ações de Compensação/Rollback Lógico

As compensações na LeadHydrationSaga são ações de correção lógica que permitem ao pipeline prosseguir mesmo em condições degradadas, sem rollback atômico. Cada compensação é imediatamente registrada em `compensation_executed[]` para auditoria completa e rastreabilidade na observability dashboard.

---

#### Compensação C-01: ScrapingNode — LinkedIn Rate-Limited

**Trigger:** `linkedin_scraper` retorna HTTP 429 (Too Many Requests) ou timeout individual > 15 segundos

**Ações Executadas:**
1. Setar `operating_mode = "DEGRADED_LINKEDIN"` no LeadState imediatamente
2. Aplicar `uncertainty_additive = 0.20` em todas as evidências de fonte `LINKEDIN` já registradas no `evidence_batch` corrente
3. Definir flag global no LeadState para que os próximos passos saibam que campos derivados exclusivamente de LinkedIn têm incerteza elevada
4. Registrar em `compensation_executed`: `"C-01: DEGRADED_LINKEDIN_ACTIVATED — LinkedIn rate-limited at {timestamp}. u_additive=0.20 applied to all LINKEDIN evidence."`
5. Continuar pipeline com Instagram + CNPJ como fontes primárias; LinkedIn não será retentado neste ciclo
6. Publicar métrica `SocialSelling/LinkedInDegradedCount` no CloudWatch com dimensão `cycle_id`

**Impacto Calculado nos Scores:**
- Campos derivados exclusivamente de LinkedIn (cargo do BMO, headcount, vagas abertas) ficam com `confidence` reduzida nas inferências geradas
- `Uncertainty_Committee` aumentado proporcionalmente ao `u_additive` acumulado
- `P_score` reflete a degradação de forma transparente e auditável — nunca silenciosa

---

#### Compensação C-02: ScrapingNode — Instagram Bloqueado

**Trigger:** `instagram_scraper` retorna erro de bloqueio (HTTP 403, resposta de captcha detectada pelo parser, ou timeout > 30s)

**Ações Executadas:**
1. Setar `operating_mode = "DEGRADED_INSTAGRAM"` no LeadState
2. Ativar modo de cache: buscar evidências de Instagram da última coleta bem-sucedida para este `lead_id` com TTL ainda válido (dentro de 24h), buscando do cache Redis L1 (key: `evidence:instagram:{lead_id}:last`)
3. Alterar `ttl_hours` das evidências Instagram em cache para 12h (t₁/₂ acelerado — evidências em cache degradado envelhecem mais rápido)
4. Recalcular `E_fresh` de todas as evidências Instagram com o novo t₁/₂=12h aplicado retroativamente
5. Registrar em `compensation_executed`: `"C-02: DEGRADED_INSTAGRAM_ACTIVATED — Cache fallback with t½=12h at {timestamp}. {n} cached evidences loaded."`
6. Continuar pipeline com evidências em cache + LinkedIn + CNPJ

---

#### Compensação C-03: ScrapingNode — Dual-Source Failure (CACHE_ONLY)

**Trigger:** Tanto `linkedin_scraper` quanto `instagram_scraper` falham simultaneamente (ambos timeout ou ambos erro)

**Ações Executadas:**
1. Setar `operating_mode = "CACHE_ONLY"` no LeadState
2. Forçar `DSS = 0` no estado — nenhuma nova descoberta é possível neste ciclo para este lead
3. Tentar carregar evidências de Instagram e LinkedIn do cache Redis; se cache também vazio, operar apenas com CNPJ
4. Publicar alarme crítico CloudWatch: `SocialSelling/ScrapingDualFailure` com `severity='CRITICAL'`, `cycle_id` e `lead_id`
5. Enfileirar payload do lead em SQS DLQ `socialselling-scraping-dlq` com `retry_at = NOW() + 1h` para reprocessamento automático após recuperação do serviço
6. Registrar em `compensation_executed`: `"C-03: CACHE_ONLY_ACTIVATED — Dual-source failure at {timestamp}. Lead queued for retry in 1h."`
7. Continuar pipeline com dados disponíveis (CNPJ + cache se houver) — scores serão extremamente degradados mas matematicamente calculáveis e auditáveis

---

#### Compensação C-04: EntityResolutionNode — RCS na Zona de Conflito

**Trigger:** `rcs_score` calculado está no range `0.65 <= rcs < 0.85` (zona de conflito — ambíguo para auto-merge)

**Ações Executadas:**
1. Não executar merge das entidades candidatas — mantê-las separadas como entidades distintas no `entity_nodes`
2. Inserir registro detalhado em `conflict_resolution_log` com:
   - `status = "PENDING_MANUAL_REVIEW"`
   - `candidate_ids[]` das entidades em conflito
   - `rcs_score` exato calculado
   - `conflict_type = "AMBIGUOUS_MATCH"`
   - Scores componentes do RRF + Jaro-Winkler para auditoria da revisão manual
3. Setar `rcs_score = null` no `entity_node` afetado — null é explicitamente mapeado para `RCS=0.0` no cálculo de C_score (pior caso explícito, não silencioso)
4. Elevar `u_additive += 0.15` no `entity_node` (penalidade por incerteza de identidade não resolvida)
5. Setar `uncertainty_elevated = true` no `entity_node`
6. Registrar em `compensation_executed`: `"C-04: ENTITY_CONFLICT_UNRESOLVED — rcs={score}, candidates={ids}. Flagged for manual review. RCS=0.0 will be used in C_score."`
7. Pipeline continua com entidades separadas — scoring não é bloqueado, mas reflete a incerteza real

**Impacto Calculado nos Scores:**
- `RCS = 0.0` no cálculo de C_score → C_score significativamente reduzido
- Lead pode migrar de `PRIORITY_ACTION` para `MONITOR` ou `DELTA_SEARCH` após resolução do conflito

---

#### Compensação C-05: HypothesisNode — Evidências Insuficientes Para Hipótese ACTIVE

**Trigger:** Nenhuma hipótese alcança `posterior >= 0.50` para status `ACTIVE` — todas permanecem em `CANDIDATE` ou `REJECTED`

**Ações Executadas:**
1. Manter todas as hipóteses com `status = "CANDIDATE"` — nenhuma promovida para ACTIVE
2. Identificar a hipótese com maior `posterior` entre as CANDIDATE como `dominant_hypothesis` provisória
3. `Hypothesis_Confidence` é calculado com o `posterior` degradado — valor baixo mas matematicamente não-zero, refletindo o que foi possível inferir
4. Elevar `u_residual` no LeadState para refletir a ausência de hipótese confirmada
5. Registrar em `compensation_executed`: `"C-05: HYPOTHESIS_DEGRADED — No ACTIVE hypothesis. Best candidate: posterior={value}, text='{text}'. Blueprint will be partial."`
6. Pipeline continua — BlueprintNode será invocado e produzirá blueprint com `partial=true` (Compensação C-06 será acionada automaticamente)

---

#### Compensação C-06: BlueprintNode — Hipótese Dominante com Posterior Abaixo do Limiar

**Trigger:** `dominant_hypothesis.posterior < 0.25` (confiança insuficiente para blueprint completo)

**Ações Executadas:**
1. Gerar blueprint com `partial = true`
2. Campos que dependem de hipótese confirmada ficam explicitamente `null`:
   - `pain_narrative = null` com `reason = "Hipótese de dor não confirmada com confiança mínima (posterior={value} < 0.25) — evidências de LinkedIn e Instagram insuficientes para personalizar a narrativa de dor"`
   - `credibility_anchor = null` com `reason = "Sem hipótese dominante ACTIVE — impossível selecionar âncora de credibilidade específica ao contexto"`
3. Componentes que podem ser gerados com dados parciais são preenchidos:
   - `hook`: gerado com base apenas no segmento inferido (genérico mas presente)
   - `context_trigger`: preenchido se houver trigger events (mesmo sem hipótese confirmada)
   - `cta_suggestion`: gerado com canal de maior `Reachability` e mensagem genérica de segmento + `contraindications` obrigatórias
4. Popula `missing_fields` dict: `{"pain_narrative": "{reason}", "credibility_anchor": "{reason}"}`
5. `data_quality_warning = true` independente do `operating_mode`
6. Registrar em `compensation_executed`: `"C-06: BLUEPRINT_PARTIAL — dominant_hypothesis.posterior={value} < 0.25. pain_narrative and credibility_anchor set to null with reasons."`

---

#### Compensação C-07: FinOps Limit Atingido (Qualquer Step)

**Trigger:** Custo acumulado do processamento do lead >= 90% do `budget_brl` per-lead definido no ciclo, detectado pelo `finops_monitor` que é verificado a cada step

**Ações Executadas:**
1. Registrar estado atual em `pruned_reason_log` com payload completo:
   - `stopping_rule = "FINOPS_BUDGET_THRESHOLD_90PCT"`
   - `state_at_pruning` = snapshot JSON do LeadState no momento da detecção
   - `mode_transition = "FULL_SEARCH -> DELTA"`
   - `audit_trail` com todos os steps executados até o momento e seus custos unitários
2. Setar `stopping_triggered = true` no LeadState
3. Setar `stopping_reason = "FinOps limit reached: {actual_cost_brl} BRL >= 90% of {budget_brl} BRL"`
4. Emitir evento `FinOpsLimitReached` para métrica CloudWatch `SocialSelling/FinOpsLimitHits` com dimensão `cycle_id`
5. Transicionar lead para `search_mode = "DELTA"` (EV-15 é disparado como consequência)
6. Interromper execução de todos os steps subsequentes ao step atual — não executar os nós restantes da saga
7. Persistir o estado parcial processado até o momento como valid partial hydration (chama PersistenceNode diretamente com estado parcial)
8. Registrar em `compensation_executed`: `"C-07: FINOPS_LIMIT_TRIGGERED at step={current_step}. Pipeline suspended. Lead moved to DELTA mode. Partial state persisted."`

---

#### Compensação C-08: Erro Catastrófico (Exceção Não Tratada)

**Trigger:** Exceção Python não tratada em qualquer step da saga: `TypeError`, `ConnectionError`, `ValueError`, `KeyError` ou qualquer exceção não antecipada que não foi capturada pelas compensações específicas anteriores

**Ações Executadas:**
1. Capturar `stack_trace` completo via `traceback.format_exc()`
2. Enfileirar payload serializado do lead em SQS DLQ `socialselling-saga-errors-dlq` com:
   - `error_type`: nome da exceção
   - `stack_trace`: stack trace completo
   - `failed_step`: nome do nó onde a exceção ocorreu
   - `state_at_failure`: snapshot do LeadState no momento do erro (serializado como JSON)
   - `retry_at`: `NOW() + 2h` (retry automático após recuperação)
3. Registrar `stack_trace` em CloudWatch Logs com log group `/socialselling/saga/catastrophic-errors` e `lead_id` e `cycle_id` como dimensões
4. Marcar `entity_node.error_state = true` para o lead afetado — lead existe no sistema mas em estado de erro
5. NÃO persistir dados parciais potencialmente inconsistentes no Feature Store — integridade acima de disponibilidade
6. Publicar alarme CloudWatch: `SocialSelling/SagaCatastrophicFailure` com `severity='CRITICAL'`, `lead_id`, `cycle_id`, `failed_step`
7. Registrar em `errors[]` e `compensation_executed[]` com timestamp e step:
   - `errors[]`: `"{ExceptionType} at step {failed_step}: {message}"`
   - `compensation_executed[]`: `"C-08: CATASTROPHIC_ERROR at step={failed_step}. Lead marked ERROR. Queued in DLQ for retry at {retry_at}."`

---

### 2.5 Diagrama de Fluxo Textual da Saga

O diagrama abaixo representa o fluxo completo da LeadHydrationSaga com todas as bordas condicionais, caminhos de compensação e pontos de terminação.

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                      LEADHYDRATIONSAGA — FLUXO COMPLETO                         ║
║                   SocialSelling Intelligence System v1.0                         ║
╚══════════════════════════════════════════════════════════════════════════════════╝

[POST /api/v1/cycles] ─── Operador dispara ciclo ──────────────────────────────────
         │
         ▼
╔══════════════════════════╗
║   SeedIngestionNode      ║  Valida ICP contract ativo, normaliza seeds,
║   (Step 1)               ║  cria entity_nodes iniciais
╚══════════════════════════╝
         │
         ├─ [ZERO_SEEDS_VALID ou ICP_CONTRACT_INACTIVE] ──────────────────────────►
         │                                                             [CycleAborted]
         │                                                             [SAGA END — FAIL]
         ▼
╔══════════════════════════╗
║   ScrapingNode           ║  Instagram + LinkedIn + CNPJ em paralelo assíncrono
║   (Step 2)               ║  asyncio.gather com timeout=30s por fonte
╚══════════════════════════╝
         │
         ├─ [LINKEDIN_RATE_LIMITED] ──────────► [C-01: DEGRADED_LINKEDIN]
         │                                           operating_mode='DEGRADED_LINKEDIN'
         │                                           u_additive=+0.20 em evidências LinkedIn
         │                                           CloudWatch metric publicada
         │                                           ──────────────────────────[continua ▼]
         │
         ├─ [INSTAGRAM_BLOCKED] ─────────────► [C-02: DEGRADED_INSTAGRAM]
         │                                           operating_mode='DEGRADED_INSTAGRAM'
         │                                           cache fallback ativado, t½=12h
         │                                           ──────────────────────────[continua ▼]
         │
         ├─ [DUAL_SOURCE_FAILURE] ───────────► [C-03: CACHE_ONLY]
         │                                           operating_mode='CACHE_ONLY'
         │                                           DSS=0
         │                                           CloudWatch CRITICAL alarm
         │                                           Lead enfileirado em SQS DLQ (retry 1h)
         │                                           ──────────────────────────[continua ▼]
         │
         ▼
╔══════════════════════════╗
║   NormalizationNode      ║  SHA-256 dedup, normaliza strings, popula Layer 1
║   (Step 3)               ║  append-only no banco
╚══════════════════════════╝
         │
         ├─ [FINOPS_LIMIT_>=90%] ────────────────────────────────────────────────►
         │                                           [C-07: FinOps Compensation]
         │                                           stopping_triggered=true
         │                                           pruned_reason_log INSERT
         │                                           search_mode='DELTA'
         │                                           Partial state persistido
         │                                           [SAGA SUSPENDED — DELTA MODE]
         │
         ▼
╔══════════════════════════╗
║   EntityResolutionNode   ║  RRF + Jaro-Winkler + penalizadores
║   (Step 4)               ║  → rcs_score calculado para cada par
╚══════════════════════════╝
         │
         ├─ [rcs_score >= 0.85] ──────────────────────────────────────────────────►
         │                                           [EV-07: EntityAutoMerged]
         │                                           entity_nodes fundidos, MERGE edge criada
         │                                           ──────────────────────────[continua ▼]
         │
         ├─ [0.65 <= rcs < 0.85] ────────────► [C-04: CONFLICT_DETECTED]
         │                                           conflict_resolution_log INSERT
         │                                           rcs_score=null, u_additive+=0.15
         │                                           flag PENDING_MANUAL_REVIEW
         │                                           CONFLICT edge criada
         │                                           ──────────────────────────[continua ▼]
         │
         ├─ [rcs < 0.65] ─────────────────────────────────────────────────────────►
         │                                           Entidades distintas — sem merge
         │                                           ──────────────────────────[continua ▼]
         │
         ▼
╔══════════════════════════╗
║   InferenceNode          ║  Classifica evidências: SUPPORTING / CONTRADICTING
║   (Step 5)               ║  / NEUTRAL — popula Layer 2 com versionamento
╚══════════════════════════╝
         │
         ├─ [FINOPS_LIMIT_>=90%] ────────────────────────────────────────────────►
         │                                           [C-07: FinOps Compensation]
         │                                           [SAGA SUSPENDED — DELTA MODE]
         │
         ├─ [ZERO_SUPPORTING_INFERENCES] ─────────────────────────────────────────►
         │                                           Hypothesis_Confidence será degradado
         │                                           Blueprint será parcial
         │                                           ──────────────────────────[continua ▼]
         │
         ▼
╔══════════════════════════╗
║   HypothesisNode         ║  Bayes update + Subjective Logic
║   (Step 6)               ║  → posterior, belief/disbelief/uncertainty, status
╚══════════════════════════╝
         │
         ├─ [TODAS_HIPOTESES_CANDIDATE_OU_REJECTED] ──────────► [C-05: HYPOTHESIS_DEGRADED]
         │                                           dominant_hypothesis = melhor CANDIDATE
         │                                           Hypothesis_Confidence degradado
         │                                           u_residual elevado
         │                                           ──────────────────────────[continua ▼]
         │
         ▼
╔══════════════════════════╗
║   CommitteeNode          ║  S_persona scoring, BMO/SC/INFLUENCER detection
║   (Step 7)               ║  bmo_momentum_score, trigger_events com urgency
╚══════════════════════════╝
         │
         ├─ [ZERO_MEMBERS_IDENTIFIED] ─────────────────────────────────────────────►
         │                                           committee.completeness=0
         │                                           C_s=0.0 no cálculo de C_score
         │                                           S_intent não elevado por triggers
         │                                           ──────────────────────────[continua ▼]
         │
         ▼
╔══════════════════════════╗
║   ScoringNode            ║  O_score, C_score, P_score — fórmulas canônicas
║   (Step 8)               ║  action_label atribuído por threshold
╚══════════════════════════╝
         │
         ├─ [FINOPS_LIMIT_>=90%] ────────────────────────────────────────────────►
         │                                           [C-07: FinOps Compensation]
         │                                           Partial scores persistidos
         │                                           [SAGA SUSPENDED — DELTA MODE]
         │
         ├─ [P_SCORE_NaN_OU_INFINITY] ───────────────────────────────────────────►
         │                                           [C-08: CATASTROPHIC_ERROR]
         │                                           entity_node.error_state=true
         │                                           SQS DLQ enfileirado
         │                                           CloudWatch CRITICAL alarm
         │                                           [SAGA END — ERROR]
         │
         ▼
╔══════════════════════════╗
║   BlueprintNode          ║  Copywriter Agent (SDR de Elite):
║   (Step 9)               ║  Hook + Context Trigger + Pain Narrative + CTA
╚══════════════════════════╝
         │
         ├─ [dominant_hypothesis.posterior >= 0.25] ──────────────────────────────►
         │                                           Blueprint COMPLETO
         │                                           partial=false
         │                                           Todos os 5 componentes populados
         │                                           ──────────────────────────[continua ▼]
         │
         ├─ [dominant_hypothesis.posterior < 0.25] ──────────► [C-06: BLUEPRINT_PARTIAL]
         │                                           partial=true
         │                                           pain_narrative=null com reason
         │                                           credibility_anchor=null com reason
         │                                           Hook e CTA genéricos de segmento
         │                                           missing_fields populado
         │                                           ──────────────────────────[continua ▼]
         │
         ▼
╔══════════════════════════╗
║   PersistenceNode        ║  Escrita atômica PostgreSQL (BEGIN...COMMIT)
║   (Step 10)              ║  Invalida cache Redis, publica SQS LeadHydrated
╚══════════════════════════╝
         │
         ├─ [DB_CONNECTION_FAILURE] ─────────────────────────────────────────────►
         │                                           Retry backoff: 2s → 8s → 30s (3x)
         │                                           Se 3 falhas: SQS DLQ (retry 1h)
         │                                           CloudWatch alarm
         │                                           [SAGA END — QUEUED FOR RETRY]
         │
         ▼
[LeadHydrated EVENT] ── publicado em SQS socialselling-lead-hydrated
         │
         ▼
╔══════════════════════════════════════════════════════════════════════════════════╗
║                           SAGA COMPLETE                                          ║
║  Lead disponível via GET /api/v1/leads/{lead_id} com XAI Unified Payload         ║
║  Pronto para consumo pelo Operator Cockpit e integrações downstream              ║
╚══════════════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 FLUXO DELTA SEARCH (pós-suspensão por FinOps ou saturação DSS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Scheduled Monitor Job — executa a cada 30min]
         │
         │  Verifica entity_nodes com leads em Delta Search (via pruned_reason_log.mode_transition_to='DELTA_SEARCH')
         │  Consulta behavioral_momentum_log por novos trigger_events com is_active=true
         │
         ├─ [TRIGGER_URGENCY = 'ALTA' ou 'MEDIA'] ──────────────────────────────►
         │                                           [EV-16: DeltaSearchReactivated]
         │                                           search_mode='DELTA_ACTIVE'
         │                                           ScrapingNode (apenas fonte do trigger)
         │                                             ↓
         │                                           InferenceNode
         │                                             ↓
         │                                           HypothesisNode
         │                                             ↓
         │                                           CommitteeNode
         │                                             ↓
         │                                           ScoringNode
         │                                             ↓
         │                                           BlueprintNode
         │                                             ↓
         │                                           PersistenceNode
         │                                           [SAGA COMPLETE — DELTA UPDATE]
         │                                           Operador notificado via observability
         │
         └─ [TRIGGER_URGENCY = 'BAIXA'] ────────────────────────────────────────►
                                                     Enfileirado — sem reativação automática
                                                     Disponível para revisão manual
                                                     no observability dashboard

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 FLUXO CRM FEEDBACK LOOP (pós-LeadHydrated, completamente assíncrono)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[POST /api/v1/webhooks/crm] ── Chamado pelo CRM externo
         │
         ├─ [HMAC_SHA256_INVALID] ────────────────────────────────────────────────►
         │                                           HTTP 401 Unauthorized
         │                                           [REJECTED — sem processamento]
         │
         ▼ [HMAC válido]
[crm_outcome_log INSERT — processed_at=NULL]
[HTTP 202 Accepted] ── retorno imediato ao CRM (sem bloqueio)
         │
         ▼ (assíncrono — SQS consumer em Lambda separado)
[SRS Update Job — EV-18]
         │
         ├─ [outcome='CLOSED_WON'] ──────────────────────────────────────────────►
         │                                           srs_k += 0.05 × contribution_weight
         │                                           para cada fonte dominante na hipótese correta
         │                                           srs_k bounded: LEAST(1.00, ...)
         │
         ├─ [outcome='CLOSED_LOST'] ─────────────────────────────────────────────►
         │                                           srs_k -= 0.03 × false_hypothesis_weight
         │                                           para cada fonte da hipótese falsa
         │                                           srs_k bounded: GREATEST(0.10, ...)
         │
         ├─ [feedback_count >= 5 para keyword] ──────────────────────────────────►
         │                                           keyword_taxonomy atualizado
         │                                           no icp_contract.keyword_taxonomy (JSONB, anti-overfitting)
         │
         ▼
[SRSUpdated EVENT] ── feedback loop de qualidade de fonte encerrado
         │
         ▼
[crm_feedback_log UPDATE — status='PROCESSED']
```

---

*Documento: SDD-07 — Event Storming e Orquestração de Saga*
*Versão: 1.0.0 | Data: 2026-06-01*
*Próximo documento: SDD-08 — Multi-Agent Framework e Cockpit UX*
*Referências internas: SDD-01 (Arquitetura Geral), SDD-03 (Modelo de Dados), SDD-05 (Buying Committee & Motion)*
