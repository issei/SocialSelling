# SOLUTION DESIGN DOCUMENT
## Sistema de Inteligência de Dados: SocialSelling MVP
### Versão: 1.1-MVP | Classificação: CONFIDENCIAL — ENGENHARIA

---
**Autores:** Comitê de Engenharia de Elite — Principal Enterprise Architect · Arquiteto de Sistemas Cognitivos · Especialista em Information Retrieval · Graph Theorist · Especialista em Bayesian Inference · Engenheiro de FinOps · Especialista em Explainable AI

**Data de emissão:** 2024-11-15 | **Data de revisão:** 2024-11-15 (v1.1) | **Ciclo de revisão:** A cada mutação de contrato ICP

---

### Registro de Alterações — v1.0 → v1.1

| ID | Tipo | Seção | Descrição Resumida |
|---|---|---|---|
| FIX-DDL-01 | Cirúrgica | §4.4 DDL | Remoção do token espúrio `KEY_U` na coluna `subjective_opinion_u` de `tbl_edge_employed_at`; adicionada nota de correção no DDL de `entity_edges` |
| FIX-RT-01 | Cirúrgica | §2.8 | Adicionada Nota de Implementação obrigatória de guarda `if u_A == 0 and u_B == 0` antes das frações de fusão (mitigação de `ZeroDivisionError`) |
| FIX-FK-01 | Cirúrgica | §4.4 DDL | Adicionado comentário de restrição de Charset/Collation na coluna `hypothesis_linked CHAR(2)` da tabela `observed_evidence` |
| ARCH-01 | Arquitetural | §2.1, §2.2 | Migração de `S_committee_Completeness` do `O_score` para `Uncertainty_Committee` no `C_score`; justificativa matemática formal; fórmula de `O_score` atualizada |
| ARCH-02 | Arquitetural | §2.1.1 | Formalização completa do `Fit Score`: ICP Feature Vector, Company Feature Vector, Similaridade Cosseno Ponderada, atributos mínimos obrigatórios do ICP no MVP |
| ARCH-03 | Arquitetural | §2.3 | Substituição da definição abstrata do `P_score` por `MatrixRankFunction` completa: fórmula, regras de ordenação, tratamento de empates, quadrantes O/C, thresholds operacionais |
| ARCH-04 | Arquitetural | §3-Mod3 | Expansão do Catálogo de Hipóteses de 5 para 15 hipóteses, cada uma com: descrição, Supporting/Contradicting/Missing Evidence, Prior P₀, impacto em O_score e C_score |
| ARCH-05 | Arquitetural | §2.10.1 | Introdução do Source Quality Model: Credibility Score, Freshness Score, Coverage Score, Historical Accuracy Score — fórmulas, processo de atualização, influência no `C_s` |
| ARCH-06 | Arquitetural | §4.3.1 | Formalização do Conversation Blueprint Generator: entradas obrigatórias, 5 saídas estruturadas (Hook, Context Trigger, Pain Narrative, Credibility Anchor, CTA Suggestion), estrutura de dados completa e lógica de geração |

---

## SEÇÃO 1: PREMISSAS OPERACIONAIS DO MVP

### 1.1 Matriz de Realidade de Dados

#### 1.1.1 Sinais Reais Disponíveis — Instagram

| Atributo | Tipo Físico | Observabilidade | Scraper Target |
|---|---|---|---|
| Bio: CNPJ / Nome fantasia | `VARCHAR` | Direta | Campo `biography` via profile endpoint |
| Links externos (bio/posts) | `URI[]` | Direta | `external_url` + `bio_links[]` |
| Posts orgânicos — caption | `TEXT` | Direta | `edge_media_to_caption.text` |
| Carrosséis — caption + slide count | `TEXT + INTEGER` | Direta | `__typename == GraphSidecar` |
| Stories — presença booleana | `BOOLEAN` | Direta | `has_stories` no header de perfil |
| Comentários em perfis âncora | `TEXT + user_id` | Direta | `edge_media_to_comment` em targets âncora |
| Likes em perfis âncora | `user_id` | Direta | `edge_liked_by` em targets âncora |

#### 1.1.2 Sinais Reais Disponíveis — LinkedIn

| Atributo | Tipo Físico | Observabilidade | Scraper Target |
|---|---|---|---|
| Cargo atual (título declarado) | `VARCHAR(200)` | Direta | `title` no endpoint de experiência |
| Tempo de empresa | `INTEGER` (meses) | Direta | Calculado de `startDate` → NOW |
| Posts recentes (últimas 12 semanas) | `TEXT + TIMESTAMPTZ` | Direta | `ugcPosts` ou `shares` feed do perfil |
| Tamanho declarado da empresa | `ENUM` ranges | Direta | `company_size` no perfil da empresa |
| Vagas de emprego ativas | `JSONB estruturado` | Direta | `jobPostings` via company jobs endpoint |

#### 1.1.3 Sinais Inferidos no MVP

| Sinal | Proxy de Derivação | Método de Inferência | Incerteza Default |
|---|---|---|---|
| Faixa de faturamento | Team size range + volume aparente de clientes em posts | Heurística de benchmark setorial + regex semântico | `u ≥ 0.45` |
| Nível de centralização | Ausência de menção a equipe + único rosto público + tom de posts | Pattern matching de vocabulário + presença de perfis secundários | `u ≈ 0.35` |
| Maturidade de processos | Vocabulário operacional em posts + cadência de publicação + menção a ferramentas | Léxico de maturidade configurável no `icp_contract` | `u ≈ 0.40` |

#### 1.1.4 Sinais Não Observáveis — Incerteza Pura

- Organograma corporativo formal (exceto quando declarado explicitamente em posts)
- Faturamento contábil real (dados de Receita Federal não acessíveis sem CNPJ + consentimento)
- Stack tecnológico interno sem rastro público (exceto menções orgânicas em posts)
- Estrutura societária completa além do que está disponível via API pública de CNPJ

**Tratamento arquitetural:** todos estes sinais são representados como `Missing Evidence` na taxonomia de evidências, elevando a Entropia de Shannon e reduzindo o `C_score`. O sistema nunca substitui a ausência de sinal por suposição afirmativa.

#### 1.1.5 Capacidades Diferidas — V1/V2

| Capacidade | Versão | Prontidão Arquitetural no MVP |
|---|---|---|
| Meta-learning loops automatizados | V1 | Tabela `crm_outcome_log` e `analytical_feature_store` provisionadas; schema completo |
| Re-ranqueamento adaptativo por Gradient Descent | V1 | Coluna `gradient_descent_target` em `analytical_feature_store` (NULL no MVP) |
| Mutação autônoma do contrato ICP global | V2 | Tabela `icp_contract` versionada por `version_hash`; mutação manual disponível no MVP |
| Dijkstra / BFS multi-hop no grafo social | V1 | Índices compostos B-Tree multi-hop já criados; query templates documentados |

---

### 1.2 Conflict Resolution Policy (CRP)

**Trigger:** dois ou mais provedores/scrapers fornecem valores divergentes para o mesmo par `(entity_id, attribute_key)`.

**Algoritmo de Arbitragem Determinística (5 passos):**

**Passo 1 — Ordenação por confiabilidade:** ordenar todas as afirmações concorrentes por `SRS` descendente. A afirmação com maior `SRS` é designada `authoritative_value`.

**Passo 2 — Cálculo do delta de divergência:**
- Atributos numéricos: `divergence_delta = |value_A - value_B| / max(|value_A|, |value_B|)`
- Atributos textuais: `divergence_delta = 1 - JaroWinkler(normalize(value_A), normalize(value_B))`

**Passo 3 — Avaliação contra tolerância:**
- Se `divergence_delta ≤ δ_tolerance` (default: 0.30): aceitar `authoritative_value` sem penalidade
- Se `divergence_delta > δ_tolerance`: elevar `u` na tripla ω do nó (ver Passo 4)

**Passo 4 — Penalização de incerteza:**
```
u_new = min(1.0, u_current + divergence_delta * 0.40)
b_new = b_current * (1 - divergence_delta * 0.20)
d_new = 1 - b_new - u_new
```

**Passo 5 — Registro obrigatório em `conflict_resolution_log`:**
- Campos: `conflict_severity` (LOW/MEDIUM/HIGH/CRITICAL), `resolution_method`, `residual_uncertainty_delta`
- Classificação de severidade: `LOW` (delta ≤ 0.30), `MEDIUM` (0.30–0.60), `HIGH` (0.60–0.85), `CRITICAL` (> 0.85)

---

### 1.3 Failure Modes & Degraded Operation — Sparse Signals First

| Modo de Falha | Trigger de Detecção | Resposta do Sistema | Ajuste de Parâmetros |
|---|---|---|---|
| LinkedIn scraper rate-limited | HTTP 429 ou timeout > 30s em 3 tentativas | Chavear para Instagram-only mode | `u += 0.20` para todos os atributos derivados de LinkedIn; `operating_mode = 'DEGRADED_LINKEDIN'` |
| LinkedIn scraper down (5xx) | HTTP 5xx em 5 tentativas consecutivas | Instagram-only + cache L1 de último ciclo | Mesmo que acima + alerta de observabilidade |
| Instagram scraper bloqueado | HTTP 403 / CAPTCHA detectado | Operar com cache T-24h | `freshness_decay` acelerado: `t₁/₂ = 12h`; `operating_mode = 'DEGRADED_INSTAGRAM'` |
| Ambos scrapers inoperantes | Dual-source failure simultâneo | Modo somente-cache; zero novos leads qualificados | `DSS = 0` forçado; alerta crítico emitido; `operating_mode = 'CACHE_ONLY'` |
| API CNPJ.ws indisponível | Timeout na resolução de CNPJ | Manter RCS sem penalizador de CNAE | `SRS_cnpj_resolver = 0.0` para o ciclo; `λ_CNAE = 1.0` (neutro) |
| RCS abaixo do threshold de fusão | `0.65 ≤ RCS < 0.82` | Marcar como `MERGE_CANDIDATE`; não fundir automaticamente | Registrar em `conflict_resolution_log` com flag `MANUAL_REVIEW` |

**Princípio Sparse Signals First:** nenhum modo de falha bloqueia o fluxo de processamento das evidências já coletadas. O sistema propaga os multiplicadores de incerteza aumentados para camadas posteriores e continua produzindo scores (com `data_quality_flag = 'DEGRADED'`).

---

## SEÇÃO 2: FUNDAMENTOS MATEMÁTICOS FORMAIS

### 2.1 Opportunity Score (O_score)

$$O_{score} = \left(w_F \cdot Fit + w_I \cdot S_{intent} + w_R \cdot Reachability_{Hybrid}\right) \cdot E_{fresh}$$

| Variável | Domínio | Descrição Formal |
|---|---|---|
| `w_F, w_I, w_R` | `[0,1]`, Σw = 1 | Pesos configuráveis no `icp_contract`; defaults: `w_F=0.45`, `w_I=0.35`, `w_R=0.20` |
| `Fit` | `[0,1]` | Similaridade cosseno entre vetor de atributos do lead e centroide do ICP; ver §2.1.1 |
| `S_intent` | `[0,1]` | Média ponderada de: (a) frequência de posts sobre dor nas últimas 4 semanas, (b) presença de vagas sinalizadoras, (c) engajamento em conteúdo do domínio ICP |
| `Reachability_Hybrid` | `[0,1]` | Função híbrida de acessibilidade social (§2.6); baseada exclusivamente em dados observáveis |
| `E_fresh` | `(0,1]` | Multiplicador de frescor da evidência mais recente do lead (§2.7) |

**Propriedade formal:** `O_score` tende a zero quando `E_fresh → 0` (dados stale eliminam a oportunidade computada).

**Decisão arquitetural — remoção de `S_committee_Completeness` do O_score:**

`S_committee_Completeness` foi deliberadamente migrado do `O_score` para o `C_score`, onde compõe o fator `Uncertainty_Committee`. Justificativa matemática: a completude do comitê não mede o valor comercial intrínseco do lead (dimensão de Oportunidade), mas sim a confiança epistemológica com que o sistema conhece o mapa decisório do cliente (dimensão de Confiança). Incluí-la como multiplicador em `O_score` introduzia contaminação cruzada: um lead genuinamente promissor recebia penalização artificial por limitação de observabilidade pública, não por ausência de oportunidade real. Com `S_committee_Completeness` contribuindo para `Uncertainty_Committee` no `C_score`, o efeito é corretamente modelado como penalização de ranking via `P_score = O × f(C)`, preservando a separabilidade semântica entre "o lead tem valor?" e "temos dados para sustentar essa afirmação?".

#### 2.1.1 Fit Score — Formalização Completa

**ICP Feature Vector (centroide configurado no `icp_contract`):**

$$\vec{ICP} = \left[ seg, \; size_{norm}, \; rev_{norm}, \; centralization, \; maturity_{proc}, \; pain\_affinity \right]$$

| Dimensão | Tipo | Derivação no MVP |
|---|---|---|
| `seg` | Categórica (one-hot) | Segmento declarado do ICP; encoding por `icp_contract.target_segments` |
| `size_norm` | `[0,1]` | `declared_team_size` mapeado: 1-10→0.10, 11-50→0.35, 51-200→0.65, 201-500→0.85, 500+→1.00 |
| `rev_norm` | `[0,1]` | Faixa de faturamento inferida (§1.1.3), normalizada por range do segmento-alvo |
| `centralization` | `[0,1]` | Derivado de sinal inferido de nível de centralização (§1.1.3); `u ≈ 0.35` default |
| `maturity_proc` | `[0,1]` | Derivado de sinal inferido de maturidade de processos (§1.1.3); `u ≈ 0.40` default |
| `pain_affinity` | `[0,1]` | Proporção de posts classificados com keywords de dor do `icp_contract.keyword_taxonomy` nas últimas 4 semanas |

**Company Feature Vector (computado por lead):**

$$\vec{company} = \left[ seg_c, \; size_{c,norm}, \; rev_{c,norm}, \; centralization_c, \; maturity_{c,proc}, \; pain_{c,affinity} \right]$$

Cada dimensão é computada aplicando os mesmos mapeamentos acima sobre os atributos observados/inferidos do lead. Para dimensões com `u > 0.50`, o valor preenche com o neutro da dimensão (0.50) ponderado pela crença `b` da tripla ω do atributo correspondente.

**Método de comparação — Similaridade Cosseno Ponderada:**

$$Fit = \frac{\vec{company} \cdot \vec{ICP}}{\|\vec{company}\| \cdot \|\vec{ICP}\|} \cdot \prod_{k} (1 - u_k \cdot \delta_{penalty})$$

Onde:
- `u_k` é a incerteza da dimensão `k` do vetor da empresa
- `δ_penalty = 0.15`: penalidade por dimensão de alta incerteza (configurável no `icp_contract`)
- O produto garante que incertezas elevadas em múltiplas dimensões degradam o Fit progressivamente

**Atributos mínimos do ICP do MVP** (obrigatórios no `icp_contract`):

| Atributo | Campo | Obrigatório |
|---|---|---|
| Segmento(s) alvo | `target_segments[]` | Sim |
| Faixa de team size | `icp_team_size_range` | Sim |
| Faixa de faturamento estimado | `icp_revenue_range_brl` | Sim |
| Nível de centralização esperado | `icp_centralization_min` | Sim |
| Keywords de dor | `keyword_taxonomy.pain_keywords[]` | Sim |
| Maturidade de processo esperada | `icp_maturity_threshold` | Sim |

**Nota:** dimensões com sinais não observáveis no MVP (§1.1.4) são preenchidas com `u = 1.0` e contribuem com valor neutro para o vetor, preservando a integridade matemática do cosseno sem introduzir afirmações espúrias.

---

### 2.2 Confidence Score (C_score)

$$C_{score} = RCS \cdot C_s \cdot (1 - Uncertainty_{Committee}) \cdot Hypothesis_{Confidence} \cdot \prod_{k=1}^{n} SRS_k$$

| Variável | Domínio | Descrição Formal |
|---|---|---|
| `RCS` | `[0,1]` | Resolution Confidence Score via Jaro-Winkler penalizado (§2.5) |
| `C_s` | `[0,1]` | Data Confidence Score multi-provedor via Entropia de Shannon (§2.4) |
| `Uncertainty_Committee` | `[0,1]` | Componente `u` agregado do comitê de compras; `= mean(u_i)` ponderado por `role_probability_i`; incorpora `S_committee_Completeness` via mapeamento: `Uncertainty_Committee += (1 - S_committee_Completeness) × 0.30` |
| `Hypothesis_Confidence` | `[0,1]` | Componente `b` da tripla ω da hipótese com maior `posterior_probability` no status `ACTIVE` |
| `∏ SRS_k` | `(0,1]` | Produto dos SRS de todas as `n` fontes que contribuíram com evidências para o lead no ciclo |

**Incorporação de `S_committee_Completeness` no `Uncertainty_Committee`:**

$$Uncertainty_{Committee} = \bar{u}_{members} + (1 - S_{committee\_Completeness}) \cdot 0.30$$

truncado em `min(Uncertainty_Committee, 1.0)`, onde `S_committee_Completeness = n_identified / n_expected_roles`. Este formulation captura dois efeitos distintos: (a) a incerteza epistêmica sobre os membros já identificados (`ū_members`) e (b) a incerteza estrutural decorrente de papéis esperados ainda não mapeados, degradando o `C_score` sem contaminar o `O_score`.

**Propriedade formal:** `C_score` é estritamente multiplicativo. Um único SRS próximo de zero (fonte completamente não confiável) colapsa todo o score, independente da qualidade das demais fontes. Isso impõe rigor de qualidade de fonte como condição necessária, não suficiente.

---

### 2.3 Priority Score (P_score) — MatrixRankFunction: Especificação Completa

#### 2.3.1 Fórmula Matemática

$$P_{score} = O_{score} \cdot \left(1 - \alpha \cdot e^{-\beta \cdot C_{score}}\right)$$

Onde:
- `α = 0.60`: amplitude máxima de penalização por baixa confiança (configurável no `icp_contract.alpha_rank`)
- `β = 4.0`: taxa de crescimento da recompensa de confiança (configurável no `icp_contract.beta_rank`)

#### 2.3.2 Tabela de Comportamento

| O_score | C_score | P_score | Interpretação |
|---|---|---|---|
| 0.90 | 0.10 | ≈ 0.35 | Alto valor, dados ruins → prioridade baixa |
| 0.90 | 0.50 | ≈ 0.71 | Alto valor, confiança moderada → prioridade média-alta |
| 0.90 | 0.80 | ≈ 0.86 | Alto valor, dados sólidos → prioridade máxima |
| 0.50 | 0.80 | ≈ 0.48 | Valor moderado, dados sólidos → supera leads de alto valor com dados ruins |
| 0.70 | 0.20 | ≈ 0.42 | Valor médio-alto, baixa confiança → prioridade moderada |

#### 2.3.3 Regras de Ordenação

O ranking final é **determinístico de estágio único**, sem MMR. A ordenação primária é `P_score DESC`. Empates e casos especiais são resolvidos pelas regras de desempate abaixo.

#### 2.3.4 Tratamento de Empates

Quando dois ou mais leads apresentam `|P_score_A - P_score_B| < 0.005` (tolerância de empate), a ordenação de desempate aplica os seguintes critérios em sequência:

| Prioridade | Critério de Desempate | Direção |
|---|---|---|
| 1 | `O_score` | DESC |
| 2 | `C_score` | DESC |
| 3 | `feat_e_fresh` (frescor médio das evidências) | DESC |
| 4 | `bmo_momentum_score` do BMO identificado | DESC |
| 5 | `entity_id` (UUID determinístico) | ASC (quebra final; reprodutível) |

#### 2.3.5 Tratamento de Alta Oportunidade com Baixa Confiança

Define-se **Quadrante Alto-O/Baixo-C** como: `O_score ≥ 0.70` E `C_score < 0.35`.

Comportamento:
- Lead **não é excluído** do ranking; sua posição reflete a penalização via `f(C)`.
- O XAI payload deve incluir obrigatoriamente o campo `missing_evidence_impact` com ganho estimado de `C_score` se as evidências ausentes fossem coletadas.
- O campo `data_quality_flag` é definido como `'LOW'`.
- O sistema emite um **InvestigationOpportunity** event no log operacional, sinalizando ao operador que enriquecimento adicional deste lead pode desbloquear alto P_score.

Threshold operacional para emissão do evento: `O_score ≥ 0.70 AND C_score < 0.35 AND P_score ≥ 0.30`.

#### 2.3.6 Tratamento de Baixa Oportunidade com Alta Confiança

Define-se **Quadrante Baixo-O/Alto-C** como: `O_score < 0.40` E `C_score ≥ 0.70`.

Comportamento:
- Lead permanece no ranking mas com `rank_position` naturalmente baixo dado o `P_score` resultante.
- Não há boosts artificiais: alta confiança em baixa oportunidade não justifica priorização.
- O lead é candidato a **Delta Search imediato** se `P_score < 0.25`, poupando recursos de investigação em entidades bem-caracterizadas mas fora do ICP.
- O campo `data_quality_flag` permanece `'NORMAL'`; a explicação é capturada no XAI como "lead bem caracterizado, fora do perfil de oportunidade atual".

#### 2.3.7 Thresholds Operacionais

| Threshold | Valor | Semântica |
|---|---|---|
| `P_score ≥ 0.65` | **QUALIFIED — PRIORITY ACTION** | Lead acionável imediatamente; entrada no pipeline de prospecção ativa |
| `0.45 ≤ P_score < 0.65` | **QUALIFIED — MONITOR** | Lead com potencial; aguarda evento de trigger para ativação ou enriquecimento de dados |
| `0.25 ≤ P_score < 0.45` | **CANDIDATE — DELTA SEARCH** | Lead marginal; transicionar para Delta Search Mode; reativar por trigger |
| `P_score < 0.25` | **DISQUALIFIED — PRUNED** | Lead abaixo do limiar de viabilidade; registrar em `pruned_reason_log`; não acionar Delta Search automaticamente |

**Ausência de MMR:** não existe diversificação por Maximal Marginal Relevance. A diversidade de segmento, se necessária, é configurada upstream como filtro no `icp_contract`, nunca como componente do P_score.

**Auditabilidade:** todo `P_score` é completamente reproduzível a partir de (`O_score`, `C_score`, `α`, `β`) armazenados no `analytical_feature_store`. O Módulo 5 persiste esses quatro valores atomicamente, garantindo rastreabilidade total em auditorias.

---

### 2.4 Data Confidence Score via Entropia de Shannon (C_s)

Para um conjunto de `m` provedores com distribuição de probabilidade de assertividade histórica `{p₁, ..., p_m}`:

**Entropia do sistema de provedores:**

$$H = -\sum_{i=1}^{m} p_i \cdot \log_2(p_i)$$

**Data Confidence Score:**

$$C_s = 1 - \frac{H}{H_{max}} \quad \text{onde} \quad H_{max} = \log_2(m)$$

**Cálculo de `p_i`:**

```
p_i = SRS_i / Σ SRS_j   (para j = 1..m)
```

| Cenário | H | C_s | Interpretação |
|---|---|---|---|
| Todos provedores concordam e têm SRS alto | H → 0 | C_s → 1 | Máxima confiança nos dados |
| Dois provedores divergem igualmente | H = 1 bit | C_s = 0 (m=2) | Máxima incerteza com 2 fontes |
| Um único provedor disponível | H = 0 | C_s = 1 | Alta confiança (sem divergência), mas SRS do provedor único aplica-se via ∏ SRS |

**Caso de borda (m=1):** `H=0`, portanto `C_s=1`. A confiança é controlada exclusivamente pelo `SRS` desse provedor no produto final do `C_score`. Isso evita que a ausência de divergência com um único provedor ruim resulte em `C_score` artificialmente alto.

---

### 2.5 Resolution Confidence Score (RCS) via Jaro-Winkler Penalizado

**Passo 1 — Normalização de strings:**

```python
normalize(s) = s.strip().lower()
               .replace('.', '').replace(',', '').replace('-', '')
               .translate(unicode_to_ascii)  # remoção de diacríticos
```

**Passo 2 — Score base Jaro-Winkler:**

$$JW(s_1, s_2) = \text{JaroWinkler}(\text{normalize}(s_1), \text{normalize}(s_2))$$

**Passo 3 — Penalizadores:**

$$RCS = JW(s_1, s_2) \cdot \lambda_{spatial} \cdot \lambda_{CNAE}$$

| Penalizador | Valor | Condição |
|---|---|---|
| `λ_spatial` | 1.00 | Mesma cidade declarada |
| `λ_spatial` | 0.85 | Mesmo estado, cidades distintas |
| `λ_spatial` | 0.70 | Regiões / estados distintos |
| `λ_spatial` | 0.70 | Localização não disponível (degradado) |
| `λ_CNAE` | 1.00 | CNAE idêntico (4 dígitos) |
| `λ_CNAE` | 0.85 | Mesma divisão CNAE (2 dígitos) |
| `λ_CNAE` | 0.70 | Mesma seção CNAE (letra) |
| `λ_CNAE` | 0.50 | Seções incompatíveis |
| `λ_CNAE` | 1.00 | CNPJ não disponível (penalizador neutro para não bloquear fusão) |

**Thresholds de decisão de fusão:**

| RCS | Decisão | Ação |
|---|---|---|
| `RCS ≥ 0.82` | Auto-merge | `UPDATE entity_nodes SET merge_parent_id` |
| `0.65 ≤ RCS < 0.82` | Merge candidato | `INSERT conflict_resolution_log` com `MANUAL_REVIEW` |
| `RCS < 0.65` | Entidades distintas | Nenhuma fusão |
| `RCS ≥ 0.90` (modo degradado) | Auto-merge conservador | Threshold elevado quando qualquer scraper em falha |

---

### 2.6 Reachability Híbrida

$$Reachability_{Hybrid} = w_1 \cdot R_{interactions} + w_2 \cdot R_{mutual\_followers} + w_3 \cdot R_{org\_proximity}$$

| Componente | Peso | Fórmula | Saturação |
|---|---|---|---|
| `R_interactions` | w₁ = 0.40 | `min(n_public_interactions / 5, 1.0)` | 5 interações públicas observadas |
| `R_mutual_followers` | w₂ = 0.35 | `min(n_mutual_anchors / 3, 1.0)` | 3 perfis âncora mútuos |
| `R_org_proximity` | w₃ = 0.25 | Escalar discreto (tabela abaixo) | — |

| Condição de `R_org_proximity` | Valor |
|---|---|
| Mesma empresa atual | 1.00 |
| Ex-empresa em comum | 0.60 |
| Mesmo segmento/setor apenas | 0.30 |
| Sem conexão organizacional detectada | 0.00 |

**Nota arquitetural:** Dijkstra e BFS no grafo social documentados como evolução V1. No MVP, `Reachability_Hybrid` opera exclusivamente sobre sinais observáveis sem traversal de grafo. Os índices compostos B-Tree criados no DDL (§4.4) suportam esta evolução sem schema migration.

---

### 2.7 Freshness Decay — Decaimento Temporal de Evidência

$$E_{fresh}(\Delta t) = e^{-\ln(2) \cdot \frac{\Delta t}{t_{1/2}}}$$

Onde `Δt` é o tempo decorrido desde a coleta em dias e `t₁/₂` é a meia-vida configurável por tipo.

**Tabela de meia-vida padrão:**

| Tipo de Evidência | `t₁/₂` (dias) | `E_fresh` em 14d | `E_fresh` em 30d |
|---|---|---|---|
| `comment_on_anchor_profile` | 7 | 0.25 | 0.06 |
| `post_caption_instagram` | 14 | 0.50 | 0.25 |
| `post_linkedin` | 21 | 0.63 | 0.37 |
| `job_posting_active` | 30 | 0.72 | 0.50 |
| `mutual_follower_anchor` | 45 | 0.82 | 0.63 |
| `cargo_title_linkedin` | 90 | 0.90 | 0.79 |
| `bio_instagram` | 90 | 0.90 | 0.79 |
| `company_size_declared` | 120 | 0.92 | 0.84 |
| `cnpj_cadastral_data` | 180 | 0.95 | 0.89 |

**Modo degradado (Instagram scraper down):** `t₁/₂` reduzido para 12h para todas as evidências de Instagram em cache, refletindo que dados de scraper em cache envelhecem mais rápido do que dados recém-coletados.

---

### 2.8 Subjective Logic — Opinion Triple (ω)

$$\omega = (b, d, u) \quad \text{onde} \quad b + d + u = 1, \quad b, d, u \in [0,1]$$

**Semântica:**
- `b` (belief): evidência afirma positivamente a proposição
- `d` (disbelief): evidência nega a proposição
- `u` (uncertainty): ausência de evidência suficiente para afirmar ou negar

**Regra de Desconto (Agent Discounting — fonte com SRS):**

Para uma fonte com `SRS_k` propagando evidência `ω_B = (b_B, d_B, u_B)`:

$$\omega_{discounted} = \left( SRS_k \cdot b_B, \quad SRS_k \cdot d_B, \quad 1 - SRS_k \cdot (b_B + d_B) \right)$$

**Regra de Consenso (Fusion de duas fontes independentes A e B):**

$$b_{A \oplus B} = \frac{b_A \cdot u_B + b_B \cdot u_A}{u_A + u_B - u_A \cdot u_B}$$

$$d_{A \oplus B} = \frac{d_A \cdot u_B + d_B \cdot u_A}{u_A + u_B - u_A \cdot u_B}$$

$$u_{A \oplus B} = \frac{u_A \cdot u_B}{u_A + u_B - u_A \cdot u_B}$$

**Caso de borda:** se `u_A = u_B = 0` (certeza absoluta de ambas as fontes), o denominador é zero. Neste caso, a fusão resulta em vacuidade dogmática — tratado como `ω = (b_A, d_A, 0)` (domínio da fonte A por SRS superior).

> **Nota de Implementação:** O código da Camada de Aplicação (FastAPI/Python) deve obrigatoriamente validar uma cláusula de guarda explícita (`if u_A == 0 and u_B == 0`) antes de computar as frações de fusão, mitigando de forma preventiva exceções de runtime do tipo `ZeroDivisionError`.

**Cadeia Causal de Propagação:**

```
ω_SRS[fonte]
    → ω_evidence[evidência coletada]
        → ω_entity[nó de entidade]
            → ω_inference[inferência gerada]
                → ω_hypothesis[hipótese avaliada]
                    → ω_decision[P_score final]
```

---

### 2.9 Expected Information Gain (EIG) & FinOps Stopping Rule

**Divergência KL para EIG de sensor `S_k`:**

$$EIG(S_k) = D_{KL}\left(P_{posterior} \| P_{prior}\right) = \sum_{x} P_{posterior}(x) \cdot \log \frac{P_{posterior}(x)}{P_{prior}(x)}$$

**FinOps Stopping Rule:**

$$\frac{EIG(S_k)}{MIC(S_k)} < \tau_{FinOps}$$

| Parâmetro | Descrição | Default |
|---|---|---|
| `EIG(S_k)` | Ganho esperado em bits da hipótese dominante se `S_k` for acionado | Calculado por sensor |
| `MIC(S_k)` | Custo marginal do sensor `S_k` em R$ por chamada de API | Configurado por sensor no `icp_contract` |
| `τ_FinOps` | Threshold de viabilidade informacional | `0.15 bits / R$0.01` |

**Consequência:** se `EIG/MIC < τ_FinOps` para o sensor `S_k`, ele é desativado para aquele lead e o evento é registrado em `pruned_reason_log`. O lead transiciona para **Delta Search Mode** (monitoramento incremental passivo).

**Delta Search Mode:** ciclos reduzidos de apenas 3 verificações — novos posts sobre dor, nova vaga aberta, nova interação em perfil âncora. Qualquer um desses eventos reativa o ciclo completo de investigação.

---

### 2.10 Source Reliability Score (SRS)

$$SRS_k = \frac{TP_k + TN_k}{TP_k + TN_k + FP_k + FN_k} \cdot \left(1 - e^{-\gamma \cdot n_k}\right)$$

| Parâmetro | Descrição |
|---|---|
| `TP_k, TN_k` | Verdadeiros positivos e negativos históricos da fonte `k` |
| `FP_k, FN_k` | Falsos positivos e negativos históricos da fonte `k` |
| `n_k` | Total de observações históricas da fonte `k` |
| `γ = 0.05` | Coeficiente de confiança bootstrap (penaliza fontes com poucos registros) |

**Cold Start:** `SRS_k⁰ = 0.50` (incerteza máxima simétrica). Um provedor novo precisa de aproximadamente `n = 46` observações para atingir `SRS > 0.80 × accuracy`.

**Atualização:** `SRS` é recalculado após cada ciclo em que feedback de CRM (`CLOSED_WON/CLOSED_LOST`) permite correlacionar acertos/erros de previsão com a fonte que forneceu a evidência determinante.

---

### 2.10.1 Source Quality Model — Framework Formal de Qualidade de Fontes

Cada fonte de dados `k` possui quatro dimensões de qualidade independentes, além do `SRS` (§2.10). Juntas, essas dimensões compõem o **Source Quality Vector (SQV_k)** e influenciam diretamente o `C_s` (Data Confidence Score via Entropia de Shannon, §2.4).

#### Dimensões de Qualidade

**1. Credibility Score (CRED_k)**

$$CRED_k = SRS_k \cdot \left(1 - \frac{FP_k + FN_k}{TP_k + TN_k + FP_k + FN_k + 1}\right)$$

Mede a confiabilidade histórica corrigida pelo viés de tipo de erro. Fontes com alto SRS mas padrão sistêmico de falsos positivos recebem desconto adicional. Domínio: `[0, 1]`. Cold start: `CRED_k⁰ = 0.50`.

**2. Freshness Score (FRESH_k)**

$$FRESH_k = e^{-\ln(2) \cdot \frac{\Delta t_{last\_update}}{t_{1/2,source}}}$$

Onde `Δt_last_update` é o tempo desde a última validação bem-sucedida da fonte (em dias) e `t_{1/2,source}` é a meia-vida de relevância da fonte:

| Fonte | `t_{1/2,source}` (dias) | Justificativa |
|---|---|---|
| `instagram_scraper` | 3 | Dados de comportamento social mudam diariamente |
| `linkedin_scraper` | 7 | Cargos e vagas atualizam semanalmente |
| `cnpj_resolver` | 30 | Dados cadastrais mudam lentamente |

Domínio: `(0, 1]`. Degrada automaticamente quando a fonte não é acionada ou retorna cache.

**3. Coverage Score (COV_k)**

$$COV_k = \frac{|A_{k,observed}|}{|A_{k,expected}|}$$

Onde `A_{k,observed}` é o conjunto de atributos do ICP retornados com sucesso pela fonte `k` no último ciclo, e `A_{k,expected}` é o conjunto de atributos que essa fonte deveria cobrir conforme a especificação do `icp_contract`. Domínio: `[0, 1]`. Penaliza fontes que retornam dados parciais (ex: LinkedIn scraper bloqueado que retorna apenas nome, sem posts ou vagas).

**4. Historical Accuracy Score (HACC_k)**

$$HACC_k = \frac{\sum_{t=1}^{T} w_t \cdot acc_t}{\sum_{t=1}^{T} w_t} \quad \text{onde} \quad w_t = e^{-\lambda \cdot (T - t)}$$

Média de acurácia histórica ponderada exponencialmente: ciclos mais recentes têm peso maior. `λ = 0.10` (decaimento de relevância histórica). `acc_t` = proporção de evidências da fonte `k` no ciclo `t` confirmadas como corretas via feedback CRM. Cold start: `HACC_k⁰ = 0.50`.

#### Source Quality Vector e Influência no C_s

O **SQV_k** de uma fonte é:

$$SQV_k = (CRED_k, \; FRESH_k, \; COV_k, \; HACC_k)$$

O **Source Quality Score Agregado (SQS_k)** para uso no cálculo de `C_s` é:

$$SQS_k = w_{CRED} \cdot CRED_k + w_{FRESH} \cdot FRESH_k + w_{COV} \cdot COV_k + w_{HACC} \cdot HACC_k$$

Pesos padrão (configuráveis no `icp_contract`): `w_CRED = 0.35`, `w_FRESH = 0.25`, `w_COV = 0.25`, `w_HACC = 0.15`.

**Influência no Data Confidence Score (C_s):**

O `SQS_k` substitui o `SRS_k` como peso no cálculo de `p_i` para a Entropia de Shannon quando ambos estão disponíveis:

$$p_i = \frac{SQS_i}{\sum_j SQS_j} \quad \text{(no lugar de } \frac{SRS_i}{\sum_j SRS_j}\text{)}$$

Esta substituição garante que fontes com alta acurácia histórica mas com cobertura parcial no ciclo atual (ex: LinkedIn scraper rate-limited que retornou apenas 30% dos atributos esperados) recebam peso proporcional à sua contribuição real, não apenas à sua confiabilidade nominal.

#### Processo de Atualização das Dimensões

| Dimensão | Quando Atualiza | Trigger | Destino |
|---|---|---|---|
| `CRED_k` | Após feedback de CRM | `RECEIVE_CRM_WEBHOOK` → `UPDATE_SRS` | `source_reliability` (recalcular com FP/FN) |
| `FRESH_k` | A cada ciclo de coleta | `DECAY_FRESHNESS` diário | Calculado on-the-fly; não persistido separadamente |
| `COV_k` | Após cada execução de coleta | `COLLECT_EVIDENCE` batch completo | `source_reliability.coverage_last_cycle` (campo a adicionar em V1; no MVP: calculado em memória) |
| `HACC_k` | Após feedback de CRM | `RECEIVE_CRM_WEBHOOK` com correlação de fonte | `source_reliability` (campo `historical_accuracy_weighted`) |

**Nota de MVP:** `COV_k` e `HACC_k` são calculados em memória durante o ciclo e usados no `SQS_k` da execução. A persistência completa do SQV por ciclo é uma evolução V1 (requer extensão do schema de `source_reliability`).

---

### 2.11 Discovery Saturation Score (DSS)

$$DSS(W) = \frac{|\mathcal{E}_{new}(W)|}{|\mathcal{E}_{total}(W)|}$$

| Parâmetro | Descrição | Default |
|---|---|---|
| `E_new(W)` | Entidades inéditas descobertas na janela deslizante `W` | — |
| `E_total(W)` | Total de entidades processadas na janela `W` | — |
| `|W|` | Tamanho da janela deslizante | 50 entidades |
| `δ_DSS` | Threshold de saturação | 0.05 (5% de novidade) |

**Regra de Ativação do Delta Search:**

Se `DSS(W) < δ_DSS` por `N_consecutive ≥ 2` janelas consecutivas → **DiscoveryWindowSaturated** emitido → Delta Search Mode ativado.

**Interpretação:** abaixo de 5% de entidades novas em 100 processamentos consecutivos, a fronteira de descoberta está saturada. Continuar na mesma estratégia de query é ineficiente; mutação do `icp_contract` ou nova seed list é necessária.

---

## SEÇÃO 3: MÓDULOS FUNCIONAIS DO MVP

---

### MÓDULO 1: Sensory Search & Data Discovery Core

**Objetivo:** Descobrir e coletar evidências brutas a partir de sinais públicos observáveis nos canais configurados no `icp_contract`, respeitando os limites de FinOps e os modos de operação degradada.

**Responsabilidades:**
1. Compilar e executar queries DSL determinísticas parametrizadas pelo `icp_contract` vigente — sem componente estocástico (ε-Greedy eliminado; exploração é governada pelo DSS, não por aleatoriedade)
2. Calcular DSS em janela deslizante de `W` entidades após cada batch de coleta
3. Avaliar a Stopping Rule de FinOps `EIG/MIC < τ_FinOps` para cada sensor antes de cada chamada custosa
4. Detectar falhas dos scrapers e acionar o modo de operação degradada correspondente
5. Persistir evidências brutas como `observed_evidence` imutáveis (append-only) na Camada 1

**Agente Responsável:** `SearchOrchestrator`

**Ferramentas:**

| Ferramenta | Descrição | Fallback |
|---|---|---|
| `instagram_scraper` | API REST via proxy rotativo; targets: bio, posts, interações em âncoras | Cache L1 Redis (TTL = 6h) |
| `linkedin_scraper` | Playwright headless + cookie pool; targets: perfil, posts, vagas | Instagram-only mode |
| `cnpj_resolver` | API pública CNPJ.ws / ReceitaWS para enriquecimento cadastral | λ_CNAE neutro (1.0) |
| `query_builder` | DSL engine com templates parametrizados por segmento ICP | Templates padrão hard-coded |

**Entradas:**

| Input | Tipo | Origem |
|---|---|---|
| `icp_contract` | `JSON` | Banco de dados, tabela `icp_contract` |
| `seed_list` | `CSV / JSON array` | Operador via API ou upload |
| `anchor_profiles` | `LIST[str]` | Configurado no `icp_contract.anchor_profiles` |

**Saídas:**

| Output | Destino | Tabela |
|---|---|---|
| `raw_evidence_batch` | Camada 1 do grafo | `observed_evidence` |
| `search_execution_log` | Log operacional | `search_logs` |
| `stopping_event` | Auditoria de parada | `pruned_reason_log` |

**Memória:** Stateless por execução. Cache L1 Redis para respostas de scrapers `(url_hash, timestamp)`, TTL = 6h.

**Critérios de Ativação:**
- Execução scheduled (cron diário) ou sob demanda via `POST /api/v1/cycles`
- Trigger manual pelo operador com `seed_list` explícita
- Reativação por Delta Search quando trigger event detectado

**Critérios de Parada:**
- `DSS(W) < δ_DSS` por 2 janelas consecutivas → Delta Search Mode
- `EIG(S_k) / MIC(S_k) < τ_FinOps` para sensor específico → desativar sensor para o lead
- Dual-source failure → suspensão com alerta crítico de observabilidade

**Comportamento sob Escassez de Dados:**
- Operar com Instagram-only; `u += 0.20` em todos os atributos LinkedIn-derivados
- Não bloquear processamento downstream; propagar incerteza aumentada para Módulo 2
- Leads produzidos com `data_quality_flag = 'DEGRADED'` no Feature Store

---

### MÓDULO 2: Entity Resolution & Evidence Graph Architecture

**Objetivo:** Resolver identidades de entidades a partir de evidências brutas de múltiplas fontes, construir e manter o grafo de conhecimento, e garantir a separação estrita das três camadas semânticas.

**Responsabilidades:**
1. Executar deduplicação via RCS (Jaro-Winkler penalizado, §2.5) e RRF
2. Aplicar a Conflict Resolution Policy para atributos contraditórios entre fontes
3. Manter e atualizar o SRS de cada fonte com base em feedback histórico via CRM
4. Separação estrita das três camadas semânticas:
   - **Camada 1 — Observed Evidence:** fatos imutáveis, append-only, hash SHA-256 de integridade
   - **Camada 2 — Generated Inferences:** derivações computadas, atualizáveis por novo ciclo com versionamento (`superseded_by`)
   - **Camada 3 — Evaluated Hypotheses:** avaliações bayesianas, versionadas por `cycle_id`
5. Aplicar Freshness Decay em ciclo diário independente
6. Calcular `C_s` (Entropia de Shannon, §2.4) para cada nó de entidade com múltiplos provedores

**Agente Responsável:** `EntityResolutionEngine`

**Ferramentas:**

| Ferramenta | Descrição |
|---|---|
| `jaro_winkler_scorer` | Biblioteca `jellyfish` (Python); cálculo de RCS com penalizadores |
| `rrfusion_engine` | Implementação custom de Reciprocal Rank Fusion para fusão de rankings de scrapers |
| `graph_writer` | Módulo de persistência de nós e arestas com suporte a opinion triples |
| `freshness_decay_scheduler` | Processo batch diário; aplica `E_fresh` a `observed_evidence` e `entity_edges` |

**Reciprocal Rank Fusion (RRF):**

$$RRF\_Score(d) = \sum_{r \in \text{rankings}} \frac{1}{k + r(d)}$$

Onde `k = 60` (constante de suavização), `r(d)` é a posição do documento `d` no ranking da fonte `r`. Usado para fundir múltiplas listas de candidatos de entidade de scrapers distintos antes do cálculo do RCS.

**Entradas:**

| Input | Origem |
|---|---|
| `raw_evidence_batch` | Módulo 1 — tabela `observed_evidence` |
| `source_reliability_registry` | Tabela `source_reliability` |

**Saídas:**

| Output | Tabela |
|---|---|
| Nós de entidade resolvidos | `entity_nodes` |
| Arestas atributadas | `entity_edges` |
| Inferências | `generated_inferences` |
| Log de conflitos | `conflict_resolution_log` |

**Critérios de Ativação:**
- Após cada batch do Módulo 1
- Freshness decay: processo batch diário às 03:00 UTC

**Comportamento sob Escassez de Dados:**
- Entidades com menos de 2 evidências: `u = 0.70` por default
- RCS calculado com `λ_spatial = 0.70` quando localização não disponível
- Modo degradado: threshold de auto-merge elevado para `RCS ≥ 0.90`

---

### MÓDULO 3: Bayesian Opportunity & Hypothesis Management Engine

**Objetivo:** Manter o Catálogo Formal de Hipóteses, calcular e atualizar probabilidades bayesianas para cada lead, e propagar a confiança ao longo da cadeia causal de Lógica Subjetiva.

**Catálogo Formal de Hipóteses do MVP — 15 Hipóteses de Negócio:**

#### H1 — Expansão Operacional

| Campo | Valor |
|---|---|
| **Descrição** | A empresa está em fase ativa de crescimento e busca estrutura para suportar o aumento de demanda sem colapso operacional |
| **Supporting Evidence** | Vagas ativas ≥ 2; posts sobre crescimento/escala/novos clientes; time crescendo; faturamento sinalizado como crescente |
| **Contradicting Evidence** | Equipe estável > 12 meses sem vagas; posts de contenção de custos; demissões declaradas |
| **Missing Evidence** | Organograma formal; dados de faturamento contábil; metas de crescimento declaradas |
| **Prior P₀** | 0.25 |
| **Impacto no O_score** | ↑ `S_intent` (+0.08 a +0.15 conforme cluster de vagas) |
| **Impacto no C_score** | Neutro; hipótese razoavelmente observável via LinkedIn Jobs |

#### H2 — Centralização Excessiva

| Campo | Valor |
|---|---|
| **Descrição** | O fundador/sócio-principal concentra decisões operacionais e estratégicas, criando gargalo estrutural de escala |
| **Supporting Evidence** | Founder como único rosto público; ausência de time visível em posts; posts sobre sobrecarga solitária; cargo único declarado há > 18 meses |
| **Contradicting Evidence** | Múltiplos colaboradores com presença pública regular; delegação declarada explicitamente em posts; organograma compartilhado |
| **Missing Evidence** | Número real de decisores internos; nível real de delegação operacional |
| **Prior P₀** | 0.30 |
| **Impacto no O_score** | ↑ `Fit` (+0.10 a +0.18 quando ICP tem centralização_min > 0.60) |
| **Impacto no C_score** | ↑ `Hypothesis_Confidence` quando posterior > 0.65 |

#### H3 — Gargalo de Liderança Intermediária

| Campo | Valor |
|---|---|
| **Descrição** | Gestores intermediários (Coordenadores, Gerentes) estão sobrecarregados ou ausentes, impedindo execução operacional eficiente |
| **Supporting Evidence** | Coordenadora/Manager postando sobre sobrecarga; vagas de liderança abertas > 45 dias; posts sobre burnout de equipe |
| **Contradicting Evidence** | Estrutura hierárquica clara declarada publicamente; múltiplos líderes com presença visível e posts consistentes |
| **Missing Evidence** | Organograma formal; cargos de liderança não listados publicamente; stack de comunicação interna |
| **Prior P₀** | 0.20 |
| **Impacto no O_score** | ↑ `S_intent` (+0.06 a +0.12) quando cluster de vaga de Manager ativo |
| **Impacto no C_score** | ↓ quando evidência vem exclusivamente de Instagram (H3 depende de LinkedIn para validação de cargo) |

#### H4 — Necessidade de Automação de Processos

| Campo | Valor |
|---|---|
| **Descrição** | A empresa opera com processos predominantemente manuais ou em ferramentas básicas, gerando retrabalho e perda de eficiência |
| **Supporting Evidence** | Posts sobre processos manuais/planilhas; ferramentas básicas observáveis (Excel, WhatsApp como CRM); queixas de retrabalho; vaga de Analista de Processos ativa |
| **Contradicting Evidence** | Menções a stack avançado (ERPs, CRMs enterprise, automações implementadas); parceiro de consultoria de processos contratado |
| **Missing Evidence** | Stack tecnológico real sem menção pública; nível de maturidade de ferramentação interno |
| **Prior P₀** | 0.15 |
| **Impacto no O_score** | ↑ `Fit` (+0.12 a +0.20 quando ICP_maturity_threshold < 0.40) |
| **Impacto no C_score** | ↓ `Hypothesis_Confidence` quando Contradicting Evidence presente (consultor de processos ativo) |

#### H5 — Busca por Eficiência sem Crescimento

| Campo | Valor |
|---|---|
| **Descrição** | A empresa está estabilizada em crescimento mas sente pressão de eficiência e margem, buscando fazer mais com o mesmo time |
| **Supporting Evidence** | Engajamento em conteúdo de produtividade; tempo de empresa longo sem crescimento evidente; posts sobre otimização sem narrativa de expansão |
| **Contradicting Evidence** | Crescimento recente e acelerado visível em posts; novas contratações consistentes |
| **Missing Evidence** | Dados de margem operacional; metas internas de produtividade |
| **Prior P₀** | 0.10 |
| **Impacto no O_score** | ↑ `S_intent` (+0.04 a +0.08); efeito moderado — eficiência sem expansão é pain de menor urgência |
| **Impacto no C_score** | Neutro |

#### H6 — Pré-Contratação de Líder Transformacional

| Campo | Valor |
|---|---|
| **Descrição** | A empresa contratou recentemente (< 90 dias) um novo executivo com perfil transformacional, criando janela de mudança organizacional |
| **Supporting Evidence** | Nova conexão LinkedIn de cargo ≥ Director nos últimos 60 dias; post de boas-vindas ao novo líder; vaga de liderança recentemente fechada |
| **Contradicting Evidence** | Novo executivo com histórico conservador/de continuidade; ausência de posts sobre mudança de direção |
| **Missing Evidence** | Briefing do novo líder; mandato real da contratação |
| **Prior P₀** | 0.12 |
| **Impacto no O_score** | ↑↑ `S_intent` (+0.15 a +0.25 — janela de mudança é o sinal de urgência mais alto do modelo) |
| **Impacto no C_score** | ↑ quando evidência de LinkedIn Jobs confirma fechamento da vaga |

#### H7 — Crise de Retenção de Talentos

| Campo | Valor |
|---|---|
| **Descrição** | A empresa enfrenta rotatividade elevada, perdendo conhecimento operacional e gerando custo de recontratação recorrente |
| **Supporting Evidence** | Múltiplas vagas abertas simultaneamente para mesmos cargos; posts de ex-colaboradores sobre saída; posts da empresa sobre cultura/retenção |
| **Contradicting Evidence** | Time estável > 18 meses sem vagas recorrentes; posts sobre longevidade de equipe |
| **Missing Evidence** | Taxa de turnover real; causas de saída; clima organizacional interno |
| **Prior P₀** | 0.10 |
| **Impacto no O_score** | ↑ `S_intent` (+0.06 a +0.10) quando padrão de recontratação recorrente detectado |
| **Impacto no C_score** | ↑ quando múltiplas vagas do mesmo cargo detectadas via LinkedIn Jobs com intervalo < 6 meses |

#### H8 — Pressão de Vendas sem Estrutura Comercial

| Campo | Valor |
|---|---|
| **Descrição** | A empresa cresceu via indicações/boca-a-boca mas não tem estrutura comercial para gerar demanda previsível e escalável |
| **Supporting Evidence** | Posts sobre meta de vendas; vaga de SDR/BDR/Vendedor ativa; founder com papel comercial declarado; ausência de equipe comercial visível |
| **Contradicting Evidence** | Equipe de vendas estruturada mencionada; CRM declarado; posts sobre pipeline e funil |
| **Missing Evidence** | Processo comercial interno; mix de canais de aquisição |
| **Prior P₀** | 0.18 |
| **Impacto no O_score** | ↑ `Fit` (+0.08 a +0.14) quando ICP inclui empresas pré-estruturação comercial |
| **Impacto no C_score** | Neutro |

#### H9 — Transição de Modelo de Negócio

| Campo | Valor |
|---|---|
| **Descrição** | A empresa está migrando de um modelo de negócio para outro (ex: serviços→produto, projeto→recorrência, B2C→B2B), gerando necessidade de nova infraestrutura operacional |
| **Supporting Evidence** | Posts declarando novo produto/serviço; mudança de messaging no perfil; vaga de perfil incompatível com modelo atual; bio atualizada com novo posicionamento |
| **Contradicting Evidence** | Posicionamento estável > 24 meses; ausência de qualquer sinal de mudança de direção |
| **Missing Evidence** | Roadmap de produto; decisão interna sobre migração de modelo |
| **Prior P₀** | 0.08 |
| **Impacto no O_score** | ↑↑ `S_intent` (+0.12 a +0.20) — transição de modelo cria necessidade urgente de estrutura |
| **Impacto no C_score** | ↓ `Hypothesis_Confidence` — alta incerteza sobre timing e comprometimento da transição |

#### H10 — Sobrecarga do Fundador como Gargalo de Inovação

| Campo | Valor |
|---|---|
| **Descrição** | O fundador está operacionalmente sobrecarregado com tarefas de execução, sem bandwidth para inovação estratégica ou desenvolvimento de produto |
| **Supporting Evidence** | Posts sobre falta de tempo para estratégia; menção a trabalho operacional pelo fundador (cargo não-operacional); posts de fim de semana/madrugada |
| **Contradicting Evidence** | COO ou equivalente declarado e com presença pública; equipe de operações visível com autonomia |
| **Missing Evidence** | Estrutura de governança real; distribuição de responsabilidades executivas |
| **Prior P₀** | 0.22 |
| **Impacto no O_score** | ↑ `S_intent` (+0.08 a +0.14) — correlacionado com H2; co-ocorrência eleva multiplicador |
| **Impacto no C_score** | ↑ quando evidência de Instagram reforça padrão comportamental consistente |

#### H11 — Dor de Qualidade de Entrega

| Campo | Valor |
|---|---|
| **Descrição** | A empresa enfrenta problemas de consistência e qualidade de entrega para clientes, com risco de churn e reputação |
| **Supporting Evidence** | Posts sobre padrão de qualidade como desafio; menções a reclamações de clientes (veladas); vaga de Quality Assurance; posts de cliente insatisfeito em comentários |
| **Contradicting Evidence** | Depoimentos positivos recentes de clientes; NPS declarado alto; certificações de qualidade mencionadas |
| **Missing Evidence** | Dados de satisfação do cliente; taxa de churn; processos internos de QA |
| **Prior P₀** | 0.12 |
| **Impacto no O_score** | ↑ `Fit` (+0.06 a +0.12) quando ICP inclui empresas com dor de padronização |
| **Impacto no C_score** | ↓ — evidências de qualidade de entrega são difíceis de observar publicamente; `u` elevado |

#### H12 — Expansão Geográfica Planejada

| Campo | Valor |
|---|---|
| **Descrição** | A empresa planeja ou está executando expansão para novas regiões/estados, criando necessidade de processos replicáveis |
| **Supporting Evidence** | Post sobre nova filial/escritório; vaga com localização diferente da sede; post de engajamento em eventos de outra região; bio com múltiplas localizações |
| **Contradicting Evidence** | Operação declaradamente local e sem planos de expansão; equipe 100% remota sem âncora geográfica nova |
| **Missing Evidence** | Plano de expansão formal; timing de abertura de novas unidades |
| **Prior P₀** | 0.10 |
| **Impacto no O_score** | ↑ `S_intent` (+0.10 a +0.16) — expansão geográfica cria urgência de padronização de processos |
| **Impacto no C_score** | ↑ quando vaga com nova localização detectada via LinkedIn Jobs (evidência objetiva) |

#### H13 — Pressão Regulatória ou de Conformidade

| Campo | Valor |
|---|---|
| **Descrição** | A empresa opera em setor com nova regulamentação ou auditoria próxima, criando urgência de estruturação e documentação de processos |
| **Supporting Evidence** | Posts sobre conformidade/auditoria/certificação; vaga de Compliance/DPO; menção a prazo regulatório; segmento com regulação recente conhecida |
| **Contradicting Evidence** | Certificações já obtidas e publicadas; declaração de auditoria concluída |
| **Missing Evidence** | Escopo real da regulação aplicável; maturidade atual de conformidade |
| **Prior P₀** | 0.08 |
| **Impacto no O_score** | ↑↑ `S_intent` (+0.15 a +0.22) — prazo regulatório é o trigger de urgência mais concreto e imediato |
| **Impacto no C_score** | ↑ quando segmento ICP correlaciona com regulação conhecida (validação por keyword_taxonomy) |

#### H14 — Sócio Novo ou Reestruturação Societária

| Campo | Valor |
|---|---|
| **Descrição** | A empresa passou por mudança societária recente (novo sócio, saída de sócio, reestruturação), criando necessidade de realinhamento operacional |
| **Supporting Evidence** | Anúncio de novo sócio em post; mudança de CNPJ cadastral; novo perfil com cargo de Sócio/Partner conectado à empresa; posts sobre novos rumos e parceria |
| **Contradicting Evidence** | Estrutura societária estável > 24 meses declarada; ausência de qualquer sinal de mudança |
| **Missing Evidence** | Quadro societário formal (CNPJ completo); termos do acordo societário |
| **Prior P₀** | 0.07 |
| **Impacto no O_score** | ↑ `S_intent` (+0.08 a +0.14) — reestruturação societária frequentemente inicia revisão de processos e fornecedores |
| **Impacto no C_score** | ↑ quando CNPJ resolver confirma alteração cadastral recente |

#### H15 — Dor de Visibilidade e Posicionamento de Marca

| Campo | Valor |
|---|---|
| **Descrição** | A empresa tem produto/serviço de qualidade mas dificuldade de comunicar valor e gerar visibilidade no mercado, impactando a captação de clientes |
| **Supporting Evidence** | Posts sobre dificuldade de chegar em novos clientes; baixo engajamento orgânico nas redes apesar de conteúdo técnico; menção a dependência de indicação; vaga de Marketing/Growth |
| **Contradicting Evidence** | Alta frequência de posts com engajamento consistente; presença em mídias especializadas; budget de mídia declarado |
| **Missing Evidence** | Estratégia de marketing atual; budget alocado; mix de canais |
| **Prior P₀** | 0.15 |
| **Impacto no O_score** | ↑ `Fit` (+0.06 a +0.10) quando ICP inclui empresas em fase de aceleração de captação |
| **Impacto no C_score** | ↑ quando baixo engajamento observável diretamente nas métricas de perfil público |

**Responsabilidades:**
1. Instanciar e manter uma tripla ω por hipótese por lead por ciclo
2. Aplicar atualização bayesiana para cada novo batch de evidências:

$$P(H_i \mid E) = \frac{P(E \mid H_i) \cdot P(H_i)}{P(E)} = \frac{P(E \mid H_i) \cdot P(H_i)}{\sum_j P(E \mid H_j) \cdot P(H_j)}$$

3. Classificar cada evidência como `Supporting`, `Contradicting` ou `Missing`
4. Traduzir posteriores bayesianos em triplas ω via mapeamento:
   - `b = P(H_i|E) × (1 - u_residual)`
   - `d = (1 - P(H_i|E)) × (1 - u_residual)`
   - `u = u_residual` (derivado da escassez de evidências)
5. Propagar confiança na cadeia causal (§2.8)

**Agente Responsável:** `HypothesisEngine`

**Ferramentas:**

| Ferramenta | Descrição |
|---|---|
| `bayes_updater` | Motor de atualização bayesiana incremental; mantém estado de posterior entre ciclos |
| `evidence_classifier` | Classificador determinístico por regras configuráveis no `icp_contract.evidence_rules` |
| `subjective_logic_engine` | Implementação das regras de desconto e consenso de Lógica Subjetiva (§2.8) |

**Entradas:**

| Input | Origem |
|---|---|
| `generated_inferences` (Camada 2) | Módulo 2 |
| `hypothesis_catalog` | Tabela `hypothesis_catalog` (15 hipóteses do MVP conforme §3-Módulo3) |
| `conflict_resolution_log` | Módulo 2 — para elevação de `u` quando conflitos persistem |

**Saídas:**

| Output | Destino |
|---|---|
| `evaluated_hypotheses` (Camada 3) | Tabela `evaluated_hypotheses` |
| `Fit` parcial e `S_intent` | `analytical_feature_store` |

**Critérios de Ativação:**
- Após cada atualização do Módulo 2
- Re-avaliação forçada quando nova evidência desloca posterior > 0.15 (2σ do prior)

**Comportamento sob Escassez de Dados:**
- `Missing Evidence` → `u` aumenta; hipótese permanece em `CANDIDATE`
- Mínimo de 3 evidências `Supporting` para transição de `CANDIDATE` para `ACTIVE`
- Modo somente-Instagram: hipóteses H3 e H4 congeladas em `u = 0.80` (sem evidências suficientes de LinkedIn para validar cargos operacionais)

---

### MÓDULO 4: Buying Committee & Motion Analytics

**Objetivo:** Mapear o comitê de compras parcialmente observável, calcular vetores de papel e seniority por profissional, e identificar formalmente o Structural Champion e o Buying Motion Owner.

**Responsabilidades:**

1. **Vetor de Persona:**

$$S_{persona} = (seniority\_score, \; role\_alignment\_score, \; engagement\_frequency)$$

| Componente | Derivação |
|---|---|
| `seniority_score` | Normalização de hierarquia de título (C-level=1.0, Director=0.80, Manager=0.60, Coordinator=0.45, Analyst=0.20) |
| `role_alignment_score` | Similaridade semântica entre `role_inferred` e papéis esperados do ICP para o segmento |
| `engagement_frequency` | Frequência de posts relacionados à dor ICP nas últimas 4 semanas (normalizado por saturação em 5 posts) |

2. **Modelagem probabilística de papéis executivos** baseada exclusivamente em sinais públicos (sem organograma formal)

3. **Métricas formais do comitê:**

$$CommitteeCompleteness = \frac{|roles\_identified|}{|roles\_expected\_for\_segment|}$$

$$CommitteeConfidence = 1 - \bar{u}_{committee}$$

Onde `ū_committee` = média ponderada de `u_i` × `role_probability_i` para todos os membros identificados.

4. **Diferenciação formal SC vs. BMO:**

| Critério | Structural Champion (SC) | Buying Motion Owner (BMO) |
|---|---|---|
| Cargo | Estático — sem mudança nos últimos 6 meses | Irrelevante para o critério |
| Alinhamento funcional | `role_alignment_score > 0.60` | Secundário |
| Presença pública | Frequência moderada; tom operacional | Cluster ativo (≥ 3 posts em 21 dias sobre dor ICP) |
| Momentum | Baixo; situação estável mas dolorosa | Alto; sinais ativos de busca por transformação |
| Exemplo | Fundadora com burnout crônico sem movimento | Coordenadora postando ativamente sobre automação |
| Pode coincidir? | Sim, quando SC também demonstra momentum ativo | Sim, sem penalidade |

5. **Detector de Trigger Events:**

| Trigger | Sinal | Janela |
|---|---|---|
| Contratação sênior recente | Nova conexão LinkedIn de cargo ≥ Manager | 30 dias |
| Vaga aberta persistente | Job posting ativo > 60 dias | Atual |
| Post de transformação ativo | ≥ 2 posts sobre mudança de processo | 14 dias |
| Novo engajamento em âncora | Comentário em perfil âncora do ICP | 7 dias |

**Agente Responsável:** `CommitteeAnalytics`

**Ferramentas:**

| Ferramenta | Descrição |
|---|---|
| `persona_scorer` | Calcula `S_persona` para cada profissional identificado |
| `momentum_cluster_engine` | Agrupa posts por temática ICP; calcula `bmo_momentum_score` |
| `trigger_event_detector` | Monitora os 4 tipos de trigger events; gera `behavioral_momentum_log` |

**Entradas:**

| Input | Origem |
|---|---|
| `entity_nodes` (pessoas vinculadas ao nó empresa) | Módulo 2 |
| `entity_edges` (relações pessoa-empresa) | Módulo 2 |
| `evaluated_hypotheses` (hipóteses ativas) | Módulo 3 |

**Saídas:**

| Output | Tabela |
|---|---|
| Mapa do comitê com papéis probabilísticos | `committee_members` |
| Identificação SC/BMO | `committee_members.designation` |
| Métricas do comitê | `analytical_feature_store` |

**Comportamento sob Escassez de Dados:**
- 1 membro identificado: `CommitteeCompleteness = 0.25`; `u_committee = 0.75`
- BMO marcado como `UNKNOWN` se nenhum cluster de momentum detectado
- SC pode ser inferido de bio/cargo mesmo sem posts recentes (designação com `role_probability` reduzida)

---

### MÓDULO 5: Multi-Attribute Matrix Ranking, XAI & Future Readiness Layer

**Objetivo:** Executar o ranking determinístico final em estágio único, produzir payloads explicáveis estruturados e manter prontidão arquitetural para evolução V1/V2.

**Responsabilidades:**

1. **Cálculo de O_score final:** combinar `Fit`, `S_intent` (do Módulo 3), `Reachability_Hybrid` e `E_fresh` — conforme fórmula §2.1 (sem `S_committee_Completeness`, migrado para C_score)
2. **Cálculo de C_score final:** combinar `RCS`, `C_s`, `Uncertainty_Committee` (incluindo contribuição de `S_committee_Completeness` via §2.2), `Hypothesis_Confidence`, `∏ SRS_k`
3. **Execução da MatrixRankFunction** com penalização não-linear (§2.3); sem MMR; estágio único
4. **Geração do XAI payload** estruturado com `observed_evidence`, `generated_inferences`, `evaluated_hypotheses` e `approach_blueprint`
5. **Geração do `pruned_reason_payload`** quando Stopping Rules acionadas (§4.3)
6. **Recepção de webhooks CRM** e persistência em `crm_outcome_log`
7. **Escrita atômica no Feature Store** com todos os features de oportunidade e confiança separados

**Agente Responsável:** `RankingEngine` + `XAITranslator`

**Ferramentas:**

| Ferramenta | Descrição |
|---|---|
| `matrix_rank_function` | Implementação completa da `MatrixRankFunction` conforme §2.3: fórmula `P = O × (1 - α × e^(-β × C))`, regras de ordenação, desempate, thresholds operacionais e quadrantes O/C; α=0.60, β=4.0 |
| `xai_payload_builder` | Serialização estruturada das razões de scoring em JSON explicável |
| `crm_webhook_listener` | FastAPI endpoint receptor de `CLOSED_WON/CLOSED_LOST` |
| `feature_store_writer` | Escrita atômica desnormalizada em `analytical_feature_store` |

**Entradas:**

| Input | Origem |
|---|---|
| `analytical_feature_store` (parcial) | Módulos 3 e 4 |
| `committee_scores` | Módulo 4 |
| `evaluated_hypotheses` | Módulo 3 |

**Saídas:**

| Output | Destino |
|---|---|
| Lista ranqueada por `P_score` | API + `analytical_feature_store` |
| XAI Unified Payload | API response (ver §4.2) |
| Pruned Reason Payload | `pruned_reason_log` (ver §4.3) |

**Comportamento sob Escassez de Dados:**
- `C_score < 0.20`: lead ranqueado mas `data_quality_flag = 'LOW'`
- XAI payload inclui `missing_evidence_impact` com ganho estimado de `O_score` se evidências ausentes fossem coletadas

---

## SEÇÃO 4: ARTEFATOS TÉCNICOS

### 4.1 Visão Arquitetural Consolidada — Diagrama de Fluxo Lógico

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                         EXTERNAL DATA LAYER                                  ║
║  [Instagram Scraper]    [LinkedIn Scraper]    [CNPJ Resolver API]            ║
║   proxy rotativo         Playwright+cookie      CNPJ.ws / ReceitaWS          ║
╚════════════════╤═════════════════╤═══════════════════╤═══════════════════════╝
                 │                 │                   │
           raw HTML/JSON     raw profile/posts    cadastral JSON
                 │                 │                   │
                 ▼                 ▼                   ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║          MODULE 1: SENSORY SEARCH & DATA DISCOVERY CORE                      ║
║                                                                              ║
║  [DSL Query Builder]  →  [Scraper Orchestrator]  →  [DSS Monitor]           ║
║  (parametrizado ICP)     (determinístico, sem ε)   (janela W=50)            ║
║                                                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  FinOps Stopping Core: EIG(S_k)/MIC(S_k) < τ → DELTA SEARCH MODE   │    ║
║  │  Failure Detector: HTTP 429/403/5xx → Degraded Operation Policy     │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
╚═══════════════════════════════════╤════════════════════════════════════════╝
                                    │ raw_evidence_batch
                          (INSERT observed_evidence)
                                    │
                                    ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║          MODULE 2: ENTITY RESOLUTION & EVIDENCE GRAPH                        ║
║                                                                              ║
║  ┌──────────────────────────────────────────────────────────────────────┐   ║
║  │  LAYER 1 — OBSERVED EVIDENCE  (Immutable / Append-Only / SHA-256)   │   ║
║  └──────────────────────────────────────────────────────────────────────┘   ║
║  ┌──────────────────────────────────────────────────────────────────────┐   ║
║  │  LAYER 2 — GENERATED INFERENCES  (Versionadas / superseded_by)      │   ║
║  └──────────────────────────────────────────────────────────────────────┘   ║
║                                                                              ║
║  [RRF Fusion]  →  [RCS via JW Penalizado]  →  [Conflict Resolution]        ║
║  [SRS Calculator]  →  [Shannon Entropy C_s]  →  [Freshness Decay]          ║
║  [Opinion Triple Propagation via Subjective Logic]                          ║
╚═══════════════════════════════════╤════════════════════════════════════════╝
                                    │ resolved_entities + inferences
                                    ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║          MODULE 3: BAYESIAN OPPORTUNITY & HYPOTHESIS ENGINE                  ║
║                                                                              ║
║  ┌──────────────────────────────────────────────────────────────────────┐   ║
║  │  LAYER 3 — EVALUATED HYPOTHESES  (Bayesian ω-triples / cycle_id)    │   ║
║  └──────────────────────────────────────────────────────────────────────┘   ║
║                                                                              ║
║  [H1-H5 Catalog]  →  [Bayes Updater P(H|E)]  →  [ω Triple Manager]        ║
║  [Evidence Classifier: Supporting/Contradicting/Missing]                    ║
║  Output parcial: Fit, S_intent → analytical_feature_store                   ║
╚═══════════════════════════════════╤════════════════════════════════════════╝
                                    │ hypotheses + partial O_score features
                                    ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║          MODULE 4: BUYING COMMITTEE & MOTION ANALYTICS                       ║
║                                                                              ║
║  [Persona Scorer S_persona]  →  [Momentum Cluster Engine]                  ║
║  [SC/BMO Differentiator]  →  [Trigger Event Detector]                      ║
║  [CommitteeCompleteness + CommitteeConfidence + Uncertainty]                ║
╚═══════════════════════════════════╤════════════════════════════════════════╝
                                    │ committee_map + scores
                                    ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║          MODULE 5: MATRIX RANKING + XAI + FUTURE READINESS LAYER            ║
║                                                                              ║
║  [O_score final]  →  [C_score final]  →  [MatrixRankFunction P=O×f(C)]    ║
║  [XAI Payload Builder]  →  [Pruned Reason Builder]                         ║
║  [Analytical Feature Store Writer]  →  [CRM Webhook Listener]              ║
╚══════════════╤═══════════════════════════════════╤═══════════════════════╝
               │                                   │
               ▼                                   ▼
  ┌────────────────────────────┐     ┌─────────────────────────────────┐
  │  RANKED LEAD LIST          │     │  PRUNED REASON PAYLOAD          │
  │  + XAI UNIFIED PAYLOAD     │     │  (Auditoria de parada)          │
  │  (Respostas às 3 perguntas)│     │  → pruned_reason_log            │
  └────────────────────────────┘     └─────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
RETROALIMENTAÇÃO FUTURA (V1/V2) — PROVISIONADA NO MVP, NÃO IMPLEMENTADA
═══════════════════════════════════════════════════════════════════════════════

  crm_outcome_log ──────────────→ calibração de SRS + Priors (V1)
  analytical_feature_store ─────→ Gradient Descent re-ranking (V1)
  hypothesis_catalog ────────────→ mutação autônoma de ICP (V2)
  entity_edges (índices B-Tree) ─→ Dijkstra/BFS multi-hop (V1)
```

---

### 4.2 Payload JSON de Explicabilidade Unificada (Contrato de Saída do MVP)

```json
{
  "lead_id": "LE-2024-00143",
  "generated_at": "2024-11-15T14:32:00Z",
  "cycle_id": "CYC-20241115-003",

  "scores": {
    "opportunity_score": {
      "value": 0.7412,
      "components": {
        "fit": 0.8200,
        "s_intent": 0.7100,
        "reachability_hybrid": {
          "value": 0.5750,
          "r_interactions": 0.6000,
          "r_mutual_followers": 0.6667,
          "r_org_proximity": 0.3000,
          "weights": { "w1": 0.40, "w2": 0.35, "w3": 0.25 }
        },
        "committee_completeness": 0.7500,
        "e_fresh": 0.9100
      },
      "weights": { "w_F": 0.45, "w_I": 0.35, "w_R": 0.20 }
    },
    "confidence_score": {
      "value": 0.6143,
      "components": {
        "rcs": 0.8700,
        "c_s_shannon": 0.7400,
        "uncertainty_committee": 0.2800,
        "hypothesis_confidence": 0.7900,
        "srs_product": {
          "instagram_scraper": 0.8200,
          "linkedin_scraper": 0.7700,
          "cnpj_resolver": 0.9500,
          "computed_product": 0.6003
        }
      }
    },
    "priority_score": {
      "value": 0.6879,
      "formula": "O × (1 - 0.60 × e^(-4.0 × C))",
      "alpha": 0.60,
      "beta": 4.0,
      "rank_position": 3,
      "total_leads_in_cycle": 47
    }
  },

  "xai_drivers": {
    "top_positive_signals": [
      {
        "signal": "3 vagas ativas para posições operacionais sênior (Analista de Processos, Coordenador Administrativo, Analista Financeiro)",
        "contribution_to_o_score": "+0.12",
        "evidence_type": "Supporting",
        "source": "linkedin_scraper",
        "freshness": 0.9600,
        "hypothesis_linked": "H1",
        "evidence_id": "EV-00459"
      },
      {
        "signal": "Fundadora publicou 4 posts sobre sobrecarga de gestão isolada nos últimos 21 dias",
        "contribution_to_o_score": "+0.09",
        "evidence_type": "Supporting",
        "source": "instagram_scraper",
        "freshness": 0.8700,
        "hypothesis_linked": "H2",
        "evidence_id": "EV-00441"
      },
      {
        "signal": "2 perfis âncora do segmento de Advocacia seguem mutuamente o perfil da empresa",
        "contribution_to_o_score": "+0.06",
        "evidence_type": "Supporting",
        "source": "instagram_scraper",
        "freshness": 0.9200,
        "hypothesis_linked": null,
        "evidence_id": "EV-00451"
      }
    ],
    "top_negative_signals": [
      {
        "signal": "Empresa menciona parceiro de consultoria de processos contratado há 3 meses em post do LinkedIn",
        "contribution_to_c_score": "-0.08",
        "evidence_type": "Contradicting",
        "source": "linkedin_scraper",
        "freshness": 0.7100,
        "hypothesis_linked": "H4",
        "evidence_id": "EV-00467"
      }
    ],
    "missing_evidence_impact": {
      "description": "Cargo e histórico detalhado da Diretora de Operações não encontrado no LinkedIn; perfil privado ou inexistente",
      "estimated_o_score_gain_if_collected": "+0.04",
      "estimated_c_score_gain_if_collected": "+0.07",
      "evidence_type": "Missing",
      "shannon_entropy_contribution": "+0.18 bits",
      "recommendation": "Busca direta via nome completo + empresa em query LinkedIn alternativa; verificar menções no Instagram corporativo"
    }
  },

  "target_entity": {
    "company_id": "CO-00892",
    "entity_type": "COMPANY",
    "company_name": "Lex & Associados Advocacia Empresarial",
    "cnpj": "42.XXX.XXX/0001-XX",
    "segment": "Advocacia",
    "declared_team_size": "11-50",
    "inferred_revenue_range": {
      "min_brl": 1200000,
      "max_brl": 3500000,
      "confidence": 0.42,
      "method": "team_size_proxy + apparent_client_volume"
    },
    "location": { "city": "São Paulo", "state": "SP" },
    "linkedin_url": "linkedin.com/company/lex-associados",
    "instagram_handle": "@lexassociados",
    "entity_opinion_triple": { "b": 0.81, "d": 0.05, "u": 0.14 }
  },

  "buying_committee": {
    "committee_confidence": 0.7200,
    "committee_completeness": 0.7500,
    "committee_uncertainty": 0.2800,
    "roles_expected_for_segment": ["Economic Buyer", "Operational Champion", "IT Owner"],
    "roles_identified": ["Economic Buyer", "Operational Champion"],
    "roles_unresolved": ["IT Owner / Technology Gatekeeper"],
    "bmo_distinct_from_champion": true,
    "members": [
      {
        "person_id": "PE-01122",
        "name": "Dra. Fernanda Melo",
        "role_declared": "Sócia-Fundadora",
        "role_inferred": "Economic Buyer / Signer",
        "role_probability": 0.8300,
        "s_persona": {
          "seniority_score": 1.00,
          "role_alignment_score": 0.72,
          "engagement_frequency": 0.41
        },
        "opinion_triple": { "b": 0.79, "d": 0.04, "u": 0.17 },
        "designation": "STRUCTURAL_CHAMPION",
        "bmo_momentum_score": 0.3200,
        "rationale": "Única presença pública consistente; cargo estático há 4+ anos; posts recorrentes sobre sobrecarga mas sem cluster de momentum ativo de transformação na janela de 21 dias",
        "linkedin_url": "linkedin.com/in/fernanda-melo-adv",
        "instagram_handle": "@dra.fernandamelo",
        "last_post_iq_days_ago": 3
      },
      {
        "person_id": "PE-01198",
        "name": "Marcos Teixeira",
        "role_declared": "Coordenador Administrativo",
        "role_inferred": "Operational Process Owner",
        "role_probability": 0.7100,
        "s_persona": {
          "seniority_score": 0.45,
          "role_alignment_score": 0.88,
          "engagement_frequency": 0.95
        },
        "opinion_triple": { "b": 0.65, "d": 0.08, "u": 0.27 },
        "designation": "BUYING_MOTION_OWNER",
        "bmo_momentum_score": 0.8700,
        "rationale": "5 posts nos últimos 18 dias sobre automação de contratos e sobrecarga de tarefas manuais. Comentou em 2 perfis âncora do segmento há menos de 7 dias. Cluster de momentum ativo detectado acima do threshold (0.87 > 0.55).",
        "linkedin_url": "linkedin.com/in/marcos-teixeira-coord",
        "instagram_handle": "@marcos.teixeira.ops",
        "last_post_iq_days_ago": 1
      }
    ]
  },

  "hypothesis_evaluation": {
    "dominant_hypothesis_id": "H2",
    "hypotheses": [
      {
        "id": "H2",
        "label": "Centralização Excessiva",
        "status": "ACTIVE",
        "prior": 0.3000,
        "posterior": 0.7400,
        "opinion_triple": { "b": 0.70, "d": 0.08, "u": 0.22 },
        "freshness": 0.8900,
        "supporting_evidence_count": 5,
        "contradicting_evidence_count": 1
      },
      {
        "id": "H1",
        "label": "Expansão Operacional",
        "status": "ACTIVE",
        "prior": 0.2500,
        "posterior": 0.6100,
        "opinion_triple": { "b": 0.57, "d": 0.12, "u": 0.31 },
        "freshness": 0.9400,
        "supporting_evidence_count": 3,
        "contradicting_evidence_count": 0
      },
      {
        "id": "H4",
        "label": "Necessidade de Automação",
        "status": "CANDIDATE",
        "prior": 0.1500,
        "posterior": 0.2900,
        "opinion_triple": { "b": 0.24, "d": 0.15, "u": 0.61 },
        "freshness": 0.7100,
        "supporting_evidence_count": 2,
        "contradicting_evidence_count": 1
      }
    ]
  },

  "approach_blueprint": {
    "primary_pain_hypothesis": "H2 — Centralização Excessiva: fundadora como gargalo decisório em empresa em aceleração, delegação estruturalmente insuficiente, risco de burnout de liderança",
    "secondary_pain_hypothesis": "H1 — Expansão Operacional: empresa crescendo mas sem estrutura processual para suportar o crescimento sem multiplicar o caos",
    "bmo_first_touch_strategy": "Engajar inicialmente o BMO (Marcos Teixeira) com reconhecimento técnico do trabalho operacional visível via Instagram/LinkedIn antes de qualquer contato direto",
    "recommended_first_action": "Comentar post de Marcos Teixeira sobre automação de contratos com insight técnico específico e contextualizado. Aguardar 48-72h para engajamento orgânico antes de DM.",
    "champion_activation_path": "Dra. Fernanda (SC) deve ser ativada via endosso interno do BMO após validação do problema operacional. Pitch direto à fundadora sem validação interna tem probabilidade estimada de conversão significativamente menor.",
    "key_message_anchors": [
      "Gestão de crescimento sem multiplicar as horas da fundadora",
      "Estrutura de delegação que preserva o padrão de excelência da Dra. Fernanda sem tirá-la do controle",
      "Cases de escritórios jurídicos médios (11-50 pessoas) que reduziram centralização preservando qualidade técnica"
    ],
    "contraindications": [
      "Não abordar a fundadora diretamente com proposta de valor do programa antes do rapport estabelecido com BMO",
      "Evitar pitch de ROI financeiro antes de validar o problema de gestão — o segmento Advocacia responde melhor a dor de processo que a ganho financeiro",
      "Não mencionar o consultor de processos contratado recentemente como razão para não precisar do programa — usar como ângulo de complementaridade"
    ],
    "trigger_urgency": "ALTA — janela ativa: 3 vagas abertas + cluster de posts do BMO nos últimos 18 dias + vaga de Analista de Processos aberta há 67 dias"
  },

  "evidence_layers": {
    "observed_evidence": [
      {
        "evidence_id": "EV-00441",
        "source": "instagram_scraper",
        "evidence_type": "post_caption",
        "raw_value": "Mais um mês correndo atrás de tudo sozinha. Preciso aprender a delegar de verdade.",
        "collected_at": "2024-11-02T09:14:00Z",
        "freshness": 0.8900,
        "srs_at_collection": 0.8200
      },
      {
        "evidence_id": "EV-00459",
        "source": "linkedin_scraper",
        "evidence_type": "job_posting",
        "raw_value": "Vaga: Analista de Processos Jurídicos Sênior — aberta há 67 dias — Lex & Associados",
        "collected_at": "2024-11-10T11:30:00Z",
        "freshness": 0.9600,
        "srs_at_collection": 0.7700
      }
    ],
    "generated_inferences": [
      {
        "inference_id": "INF-00203",
        "derived_from": ["EV-00441", "EV-00459"],
        "inference_type": "team_centralization_signal",
        "inferred_value": "Centralização alta — fundadora sem estrutura de delegação visível; vaga persistente indica dificuldade de escala operacional",
        "confidence": 0.7100,
        "method": "semantic_pattern_match + vacancy_duration_heuristic",
        "is_current": true
      }
    ],
    "evaluated_hypotheses": [
      {
        "hypothesis_id": "H2",
        "label": "Centralização Excessiva",
        "status": "ACTIVE",
        "opinion_triple": { "b": 0.70, "d": 0.08, "u": 0.22 },
        "posterior_probability": 0.7400,
        "last_updated_at": "2024-11-15T14:30:00Z",
        "cycle_id": "CYC-20241115-003"
      }
    ]
  },

  "data_quality": {
    "flag": "NORMAL",
    "operating_mode": "FULL",
    "missing_linkedin_profiles": 1,
    "sources_active": ["instagram_scraper", "linkedin_scraper", "cnpj_resolver"]
  }
}
```

---

### 4.3 Payload JSON de Poda Estruturada (pruned_reason_payload)

```json
{
  "pruning_event_id": "PRN-2024-00089",
  "generated_at": "2024-11-15T15:01:22Z",
  "cycle_id": "CYC-20241115-003",

  "target_entity": {
    "lead_id": "LE-2024-00199",
    "company_id": "CO-01044",
    "company_name": "TechParceiros Consultoria Ltda",
    "segment": "Consultoria"
  },

  "stopping_rules_evaluated": [
    {
      "rule_id": "SR-FINOPS-001",
      "rule_type": "EIG_MIC_THRESHOLD",
      "sensor_evaluated": "linkedin_deep_profile_enrichment",
      "eig_bits": 0.0210,
      "mic_brl": 0.0800,
      "eig_mic_ratio": 0.2625,
      "tau_finops": 0.1500,
      "condition_met": false,
      "note": "EIG/MIC = 0.2625 > τ = 0.15 — limiar NÃO atingido neste sensor"
    },
    {
      "rule_id": "SR-DSS-001",
      "rule_type": "DISCOVERY_SATURATION",
      "dss_window_size": 50,
      "dss_current_window": 0.0280,
      "dss_threshold": 0.0500,
      "consecutive_windows_below_threshold": 3,
      "consecutive_windows_required": 2,
      "condition_met": true,
      "note": "DSS = 0.028 < δ_DSS = 0.05 por 3 janelas consecutivas. Saturação de descoberta confirmada."
    }
  ],

  "primary_stopping_rule": "SR-DSS-001",

  "state_at_pruning": {
    "o_score_partial": 0.3800,
    "c_score_partial": 0.3100,
    "p_score_estimated": 0.2821,
    "active_hypotheses": ["H5"],
    "candidate_hypotheses": ["H3"],
    "committee_completeness": 0.2500,
    "committee_uncertainty": 0.7500,
    "evidence_counts": {
      "observed": 4,
      "inferences": 2,
      "evaluated_hypotheses": 2
    },
    "data_quality_flag": "LOW"
  },

  "mode_transition": {
    "from": "DEEP_INVESTIGATION",
    "to": "DELTA_SEARCH",
    "delta_search_config": {
      "monitoring_interval_days": 7,
      "triggers_for_reactivation": [
        "new_post_with_pain_keywords",
        "new_job_posting_detected",
        "anchor_profile_interaction",
        "linkedin_cargo_change"
      ],
      "scheduled_recheck_at": "2024-11-22T03:00:00Z"
    }
  },

  "audit_trail": {
    "total_sensors_invoked": 3,
    "total_api_calls": 12,
    "estimated_cost_brl": 0.3100,
    "data_freshness_avg": 0.6400,
    "reason_summary": "Saturação de descoberta confirmada (DSS < 0.05 por 3 janelas consecutivas = 150 entidades). Lead com valor parcial insuficiente (P_score < 0.40) e dados escassos. Transicionado para Delta Search com reativação por trigger automático.",
    "operator_note": null
  }
}
```

---

### 4.3.1 Conversation Blueprint Generator — Especificação Formal de Componente

O **Conversation Blueprint Generator (CBG)** é o sub-componente do `XAITranslator` (Módulo 5) responsável por produzir o payload `approach_blueprint` de forma estruturada, determinística e auditável. O CBG não é um módulo independente — opera como uma função pura dentro do `XAIPayloadBuilder`, consumindo outputs dos Módulos 3 e 4.

#### Entradas (Inputs Obrigatórios)

| Input | Tipo | Origem | Obrigatoriedade |
|---|---|---|---|
| `buying_motion_owner` | `CommitteeMember` JSON | Módulo 4 — `committee_members WHERE designation = 'BUYING_MOTION_OWNER'` | Obrigatório; se `UNKNOWN`, gera blueprint parcial com flag `bmo_unresolved: true` |
| `committee_profile` | `CommitteeMember[]` JSON | Módulo 4 — todos os membros do comitê com `role_probability > 0.40` | Obrigatório |
| `dominant_hypothesis` | `EvaluatedHypothesis` JSON | Módulo 3 — hipótese com maior `posterior_probability` em status `ACTIVE` | Obrigatório; se nenhuma ACTIVE, usa hipótese em `CANDIDATE` com maior posterior |
| `supporting_evidence` | `ObservedEvidence[]` JSON | Módulo 2 — evidências `classification = 'Supporting'` vinculadas à hipótese dominante | Obrigatório; mínimo 1 evidência |
| `pain_signals` | `GeneratedInference[]` JSON | Módulo 2 — inferências de tipo `*_centralization_signal`, `*_overload_signal`, `*_expansion_signal` | Opcional; enriquece narrativa quando presente |

#### Saídas (Outputs Estruturados)

O CBG produz um objeto `ConversationBlueprint` com os seguintes campos obrigatórios:

**1. Hook**

```json
{
  "hook": {
    "trigger": "string",          // Evento observável específico que justifica o contato agora
    "urgency_level": "ALTA|MEDIA|BAIXA",
    "trigger_evidence_ids": ["EV-xxx"],  // Evidências que sustentam a urgência
    "time_window_days": 21        // Janela de validade do hook (padrão: 21 dias)
  }
}
```

Lógica de geração: `urgency_level = ALTA` se qualquer trigger ativo (§4.5 Event Storming, linhas 1, 6, 14) detectado nos últimos 14 dias; `MEDIA` se 14-30 dias; `BAIXA` se > 30 dias.

**2. Context Trigger**

```json
{
  "context_trigger": {
    "observed_behavior": "string",     // Comportamento específico observado publicamente (ex: post, vaga)
    "source": "instagram|linkedin",
    "evidence_id": "EV-xxx",
    "days_ago": 5
  }
}
```

Derivado diretamente da evidência de maior `freshness_current × srs_at_collection` entre as Supporting evidences da hipótese dominante.

**3. Pain Narrative**

```json
{
  "pain_narrative": {
    "primary_pain": "string",      // Descrição da dor principal em linguagem orientada ao BMO
    "secondary_pain": "string",    // Dor secundária (hipótese com segundo maior posterior), se ≥ 0.40
    "pain_intensity": "CRITICA|ALTA|MODERADA|BAIXA",
    "narrative_anchors": ["string"] // 2-3 frases curtas que refletem a dor observada
  }
}
```

`pain_intensity` mapeado de `posterior_probability` da hipótese dominante: `≥ 0.75 → CRITICA`, `0.55-0.75 → ALTA`, `0.35-0.55 → MODERADA`, `< 0.35 → BAIXA`.

**4. Credibility Anchor**

```json
{
  "credibility_anchor": {
    "case_reference_segment": "string",   // Segmento de case de referência (não empresa específica)
    "outcome_type": "string",             // Tipo de resultado obtido pelo case
    "relevance_score": 0.85,              // Similaridade do case ao perfil do lead (calculada internamente)
    "use_if_gatekeeper_present": true     // Flag: usar anchor apenas se Gatekeeper no comitê
  }
}
```

O `case_reference_segment` é derivado do `segment` do lead + hipótese dominante, mapeado via tabela de lookup configurável no `icp_contract.case_library`.

**5. CTA Suggestion**

```json
{
  "cta_suggestion": {
    "primary_cta": "string",          // Ação de primeiro contato recomendada
    "channel": "instagram_comment|linkedin_comment|linkedin_dm|email",
    "timing_recommendation": "string", // Ex: "Aguardar 48-72h após comentário antes de DM"
    "contraindications": ["string"],  // O que NÃO fazer neste contexto específico
    "fallback_cta": "string"          // CTA alternativo se primary não obtiver resposta em 7 dias
  }
}
```

Lógica de seleção de canal: se BMO tem `last_post_iq_days_ago ≤ 3` → `instagram_comment` como primary; se BMO com LinkedIn ativo (`last_post_linkedin_days_ago ≤ 7`) → `linkedin_comment`; se SC = BMO e cargo C-level → `linkedin_dm` direto; caso contrário → `instagram_comment`.

#### Estrutura de Dados Completa do ConversationBlueprint

```json
{
  "conversation_blueprint": {
    "generated_at": "ISO8601",
    "generator_version": "CBG-1.0-MVP",
    "bmo_unresolved": false,
    "primary_pain_hypothesis": "H2 — label + descrição",
    "secondary_pain_hypothesis": "H1 — label + descrição | null",
    "hook": { ... },
    "context_trigger": { ... },
    "pain_narrative": { ... },
    "credibility_anchor": { ... },
    "cta_suggestion": { ... },
    "bmo_first_touch_strategy": "string",
    "recommended_first_action": "string",
    "champion_activation_path": "string",
    "key_message_anchors": ["string", "string", "string"],
    "contraindications": ["string"],
    "trigger_urgency": "ALTA|MEDIA|BAIXA"
  }
}
```

#### Payload de Saída — Integração com XAI Unified Payload

O `ConversationBlueprint` é serializado como o campo `approach_blueprint` dentro do `XAI Unified Payload` (§4.2). O `XAIPayloadBuilder` invoca o CBG como última etapa, após todos os scores e hipóteses estarem calculados. O CBG é stateless: dado o mesmo conjunto de inputs, produz sempre o mesmo output (determinismo total).

**Validações obrigatórias antes da emissão do blueprint:**
- `dominant_hypothesis.posterior_probability ≥ 0.25` (hipótese com evidência mínima)
- `bmo.bmo_momentum_score` calculado (mesmo que 0.0; indica BMO em estado inicial)
- Pelo menos 1 `supporting_evidence` com `freshness_current ≥ 0.30`

Se qualquer validação falhar, o CBG emite um blueprint com `"partial": true` e indica os campos não populados com `null` e razão de ausência.

---

```sql
-- ============================================================
-- SocialSelling MVP — DDL Completo v1.0
-- Paradigma: Graph-Ready Relacional
-- SGBD Target: PostgreSQL 16+
-- Extensões: pg_trgm, pgvector (NULL no MVP; V1-ready)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- CREATE EXTENSION IF NOT EXISTS vector; -- Ativar na V1

-- ────────────────────────────────────────────────────────────
-- LAYER 0: CONFIGURAÇÃO E CONTRATOS ICP
-- ────────────────────────────────────────────────────────────

CREATE TABLE icp_contract (
    contract_id         UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    version_hash        VARCHAR(64)     NOT NULL UNIQUE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    target_segments     TEXT[]          NOT NULL,
    weight_fit          DECIMAL(4,3)    NOT NULL CHECK (weight_fit BETWEEN 0 AND 1),
    weight_intent       DECIMAL(4,3)    NOT NULL CHECK (weight_intent BETWEEN 0 AND 1),
    weight_reachability DECIMAL(4,3)    NOT NULL CHECK (weight_reachability BETWEEN 0 AND 1),
    tau_finops          DECIMAL(6,4)    NOT NULL DEFAULT 0.1500,
    delta_dss           DECIMAL(4,3)    NOT NULL DEFAULT 0.0500,
    dss_window_size     INTEGER         NOT NULL DEFAULT 50,
    dss_consecutive_req INTEGER         NOT NULL DEFAULT 2,
    anchor_profiles     JSONB           NOT NULL DEFAULT '[]',
    keyword_taxonomy    JSONB           NOT NULL DEFAULT '{}',
    evidence_rules      JSONB           NOT NULL DEFAULT '{}',
    alpha_rank          DECIMAL(4,3)    NOT NULL DEFAULT 0.600,
    beta_rank           DECIMAL(4,3)    NOT NULL DEFAULT 4.000,
    CONSTRAINT weights_sum_1 CHECK (
        ABS(weight_fit + weight_intent + weight_reachability - 1.000) < 0.001
    )
);

CREATE TABLE hypothesis_catalog (
    hypothesis_id       CHAR(2)         PRIMARY KEY,
    contract_id         UUID            NOT NULL REFERENCES icp_contract(contract_id),
    label               VARCHAR(100)    NOT NULL,
    description         TEXT            NOT NULL,
    prior_probability   DECIMAL(6,5)    NOT NULL CHECK (prior_probability BETWEEN 0 AND 1),
    min_supporting_for_active INTEGER   NOT NULL DEFAULT 3,
    evidence_rules      JSONB           NOT NULL DEFAULT '{}'
);

-- ────────────────────────────────────────────────────────────
-- LAYER 1: CONFIABILIDADE DE FONTES
-- ────────────────────────────────────────────────────────────

CREATE TABLE source_reliability (
    source_id           UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key          VARCHAR(64)     NOT NULL UNIQUE,
    true_positives      BIGINT          NOT NULL DEFAULT 0 CHECK (true_positives >= 0),
    true_negatives      BIGINT          NOT NULL DEFAULT 0 CHECK (true_negatives >= 0),
    false_positives     BIGINT          NOT NULL DEFAULT 0 CHECK (false_positives >= 0),
    false_negatives     BIGINT          NOT NULL DEFAULT 0 CHECK (false_negatives >= 0),
    total_observations  BIGINT          NOT NULL DEFAULT 0 CHECK (total_observations >= 0),
    srs_current         DECIMAL(6,5)    NOT NULL DEFAULT 0.50000
                        CHECK (srs_current BETWEEN 0 AND 1),
    srs_gamma           DECIMAL(5,4)    NOT NULL DEFAULT 0.0500,
    last_recalculated   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

INSERT INTO source_reliability (source_key) VALUES
    ('instagram_scraper'),
    ('linkedin_scraper'),
    ('cnpj_resolver');

-- ────────────────────────────────────────────────────────────
-- LAYER 2: NÓS DO GRAFO (ENTIDADES)
-- ────────────────────────────────────────────────────────────

CREATE TABLE entity_nodes (
    entity_id           UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type         VARCHAR(20)     NOT NULL CHECK (entity_type IN ('COMPANY', 'PERSON')),
    canonical_name      VARCHAR(255)    NOT NULL,
    cnpj                VARCHAR(18),
    instagram_handle    VARCHAR(100),
    linkedin_url        VARCHAR(300),
    location_city       VARCHAR(100),
    location_state      CHAR(2),
    segment             VARCHAR(50),
    declared_team_size  VARCHAR(20)     CHECK (declared_team_size IN (
                            '1-10', '11-50', '51-200', '201-500', '500+'
                        )),
    -- Opinion Triple (Nó)
    belief              DECIMAL(5,4)    NOT NULL DEFAULT 0.5000,
    disbelief           DECIMAL(5,4)    NOT NULL DEFAULT 0.1000,
    uncertainty         DECIMAL(5,4)    NOT NULL DEFAULT 0.4000,
    -- Scores de Resolução
    rcs_score           DECIMAL(5,4),
    c_s_shannon         DECIMAL(5,4),
    -- Controle
    first_seen_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    last_updated_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    merge_parent_id     UUID            REFERENCES entity_nodes(entity_id),
    data_quality_flag   VARCHAR(20)     NOT NULL DEFAULT 'NORMAL'
                        CHECK (data_quality_flag IN ('NORMAL', 'LOW', 'DEGRADED')),
    CONSTRAINT opinion_triple_valid CHECK (
        ABS(belief + disbelief + uncertainty - 1.000) < 0.001
    )
);

CREATE INDEX idx_entity_nodes_type_segment
    ON entity_nodes (entity_type, segment);
CREATE INDEX idx_entity_nodes_cnpj
    ON entity_nodes (cnpj) WHERE cnpj IS NOT NULL;
CREATE INDEX idx_entity_nodes_name_trgm
    ON entity_nodes USING gin (canonical_name gin_trgm_ops);
CREATE INDEX idx_entity_nodes_active
    ON entity_nodes (is_active, entity_type) WHERE is_active = TRUE;

-- ────────────────────────────────────────────────────────────
-- LAYER 3: ARESTAS DO GRAFO (ARESTAS ATRIBUTADAS)
-- ────────────────────────────────────────────────────────────
-- NOTA DE CORREÇÃO DDL (v1.1): o token espúrio KEY_U foi removido da coluna
-- subjective_opinion_u da tabela tbl_edge_employed_at (referenciada em versões
-- anteriores do SDD). A coluna correta é:
--   subjective_opinion_u NUMERIC(4,3) NOT NULL, -- Uncertainty
-- sem qualquer prefixo de tipo composto. A tabela foi consolidada em entity_edges
-- abaixo, que adota a nomenclatura canônica do schema.

CREATE TABLE entity_edges (
    edge_id             UUID            NOT NULL DEFAULT gen_random_uuid(),
    source_entity_id    UUID            NOT NULL REFERENCES entity_nodes(entity_id),
    target_entity_id    UUID            NOT NULL REFERENCES entity_nodes(entity_id),
    edge_type           VARCHAR(50)     NOT NULL CHECK (edge_type IN (
                            'WORKS_AT', 'FORMER_EMPLOYEE', 'INTERACTED_WITH',
                            'MUTUAL_FOLLOWER', 'MENTIONED', 'COMMENTED_ON', 'LIKED'
                        )),
    weight              DECIMAL(5,4)    NOT NULL DEFAULT 1.0000
                        CHECK (weight BETWEEN 0 AND 1),
    -- Opinion Triple da Aresta
    belief              DECIMAL(5,4)    NOT NULL DEFAULT 0.5000,
    disbelief           DECIMAL(5,4)    NOT NULL DEFAULT 0.1000,
    uncertainty         DECIMAL(5,4)    NOT NULL DEFAULT 0.4000,
    -- Freshness
    evidence_collected_at TIMESTAMPTZ  NOT NULL,
    freshness_current   DECIMAL(5,4)   NOT NULL DEFAULT 1.0000,
    half_life_days      INTEGER         NOT NULL DEFAULT 14,
    -- Metadados
    source_key          VARCHAR(64)     NOT NULL,
    raw_evidence_ref    UUID,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    last_decay_applied  TIMESTAMPTZ,
    PRIMARY KEY (edge_id, source_entity_id, target_entity_id),
    CONSTRAINT no_self_edge CHECK (source_entity_id <> target_entity_id),
    CONSTRAINT opinion_triple_valid CHECK (
        ABS(belief + disbelief + uncertainty - 1.000) < 0.001
    )
);

CREATE INDEX idx_entity_edges_source
    ON entity_edges (source_entity_id, edge_type);
CREATE INDEX idx_entity_edges_target
    ON entity_edges (target_entity_id, edge_type);
CREATE INDEX idx_entity_edges_type_freshness
    ON entity_edges (edge_type, freshness_current DESC);
-- Multi-hop B-Tree (V1-ready para Dijkstra)
CREATE INDEX idx_entity_edges_multihop
    ON entity_edges (source_entity_id, target_entity_id, weight DESC, freshness_current DESC);

-- ────────────────────────────────────────────────────────────
-- LAYER 4: CAMADA 1 — EVIDÊNCIAS OBSERVADAS (IMUTÁVEIS)
-- ────────────────────────────────────────────────────────────

CREATE TABLE observed_evidence (
    evidence_id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id               UUID        NOT NULL REFERENCES entity_nodes(entity_id),
    source_key              VARCHAR(64) NOT NULL,
    evidence_type           VARCHAR(50) NOT NULL CHECK (evidence_type IN (
                                'post_caption', 'post_linkedin', 'bio', 'job_posting',
                                'comment_on_anchor', 'like_on_anchor', 'cargo_title',
                                'company_size', 'cnpj_cadastral', 'mutual_follower',
                                'story_presence', 'external_link'
                            )),
    raw_value               TEXT        NOT NULL,
    raw_url                 VARCHAR(500),
    collected_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    half_life_days          INTEGER     NOT NULL DEFAULT 14,
    freshness_at_collection DECIMAL(5,4) NOT NULL DEFAULT 1.0000,
    freshness_current       DECIMAL(5,4) NOT NULL DEFAULT 1.0000,
    srs_at_collection       DECIMAL(5,4) NOT NULL,
    immutable_hash          CHAR(64)    NOT NULL UNIQUE,  -- SHA-256(entity_id||source_key||raw_value||collected_at)
    cycle_id                VARCHAR(50) NOT NULL,
    classification          VARCHAR(20) CHECK (classification IN (
                                'Supporting', 'Contradicting', 'Missing', 'Unclassified'
                            )) DEFAULT 'Unclassified',
    hypothesis_linked       CHAR(2)     REFERENCES hypothesis_catalog(hypothesis_id)
                            -- RESTRIÇÃO DE INTEGRIDADE: o Charset e a Collation deste campo devem ser
                            -- obrigatoriamente idênticos aos de hypothesis_catalog(hypothesis_id)
                            -- para evitar falhas de indexação e busca binária em junções por chave estrangeira.
                            -- Em PostgreSQL, ambas as colunas devem compartilhar o mesmo Collation
                            -- (padrão: 'C' ou 'en_US.utf8'); divergências causam falhas silenciosas no planner.
    -- IMMUTABLE: nenhum UPDATE permitido após INSERT
);

CREATE INDEX idx_observed_evidence_entity_type
    ON observed_evidence (entity_id, evidence_type);
CREATE INDEX idx_observed_evidence_collected_desc
    ON observed_evidence (collected_at DESC);
CREATE INDEX idx_observed_evidence_cycle
    ON observed_evidence (cycle_id);
-- Multi-hop B-Tree: traversal grafo por entidade + tipo + frescor
CREATE INDEX idx_evidence_graph_traversal
    ON observed_evidence (entity_id, evidence_type, collected_at DESC);

-- ────────────────────────────────────────────────────────────
-- LAYER 5: CAMADA 2 — INFERÊNCIAS GERADAS
-- ────────────────────────────────────────────────────────────

CREATE TABLE generated_inferences (
    inference_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id           UUID            NOT NULL REFERENCES entity_nodes(entity_id),
    inference_type      VARCHAR(100)    NOT NULL,
    inferred_value      TEXT            NOT NULL,
    confidence          DECIMAL(5,4)    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    method              VARCHAR(100)    NOT NULL,
    source_evidence_ids UUID[]          NOT NULL DEFAULT '{}',
    cycle_id            VARCHAR(50)     NOT NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    superseded_by       UUID            REFERENCES generated_inferences(inference_id),
    is_current          BOOLEAN         NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_generated_inferences_entity_current
    ON generated_inferences (entity_id, is_current) WHERE is_current = TRUE;
CREATE INDEX idx_generated_inferences_type
    ON generated_inferences (inference_type, entity_id);
CREATE INDEX idx_generated_inferences_cycle
    ON generated_inferences (cycle_id);

-- ────────────────────────────────────────────────────────────
-- LAYER 6: CAMADA 3 — HIPÓTESES AVALIADAS
-- ────────────────────────────────────────────────────────────

CREATE TABLE evaluated_hypotheses (
    eval_id             UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id           UUID            NOT NULL REFERENCES entity_nodes(entity_id),
    hypothesis_id       CHAR(2)         NOT NULL REFERENCES hypothesis_catalog(hypothesis_id),
    cycle_id            VARCHAR(50)     NOT NULL,
    -- Estado Bayesiano
    prior_probability   DECIMAL(6,5)    NOT NULL CHECK (prior_probability BETWEEN 0 AND 1),
    posterior_probability DECIMAL(6,5)  NOT NULL CHECK (posterior_probability BETWEEN 0 AND 1),
    -- Opinion Triple
    belief              DECIMAL(5,4)    NOT NULL,
    disbelief           DECIMAL(5,4)    NOT NULL,
    uncertainty         DECIMAL(5,4)    NOT NULL,
    -- Contagens
    supporting_count    INTEGER         NOT NULL DEFAULT 0,
    contradicting_count INTEGER         NOT NULL DEFAULT 0,
    missing_count       INTEGER         NOT NULL DEFAULT 0,
    -- Freshness
    freshness_score     DECIMAL(5,4)    NOT NULL DEFAULT 1.0000,
    last_evidence_at    TIMESTAMPTZ,
    -- Status
    status              VARCHAR(20)     NOT NULL DEFAULT 'CANDIDATE'
                        CHECK (status IN ('CANDIDATE', 'ACTIVE', 'REJECTED', 'DORMANT')),
    evaluated_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT opinion_triple_valid CHECK (
        ABS(belief + disbelief + uncertainty - 1.000) < 0.001
    )
);

CREATE UNIQUE INDEX idx_evaluated_hypotheses_entity_hyp_cycle
    ON evaluated_hypotheses (entity_id, hypothesis_id, cycle_id);
CREATE INDEX idx_evaluated_hypotheses_entity_active
    ON evaluated_hypotheses (entity_id, status) WHERE status = 'ACTIVE';
-- Multi-hop B-Tree: entidade + posterior desc para hipótese dominante
CREATE INDEX idx_hypothesis_active_posterior
    ON evaluated_hypotheses (entity_id, posterior_probability DESC)
    WHERE status = 'ACTIVE';

-- ────────────────────────────────────────────────────────────
-- LAYER 7: COMITÊ DE COMPRAS
-- ────────────────────────────────────────────────────────────

CREATE TABLE committee_members (
    member_id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    company_entity_id       UUID        NOT NULL REFERENCES entity_nodes(entity_id),
    person_entity_id        UUID        NOT NULL REFERENCES entity_nodes(entity_id),
    role_declared           VARCHAR(200),
    role_inferred           VARCHAR(200),
    role_probability        DECIMAL(5,4) NOT NULL CHECK (role_probability BETWEEN 0 AND 1),
    seniority_score         DECIMAL(5,4) NOT NULL DEFAULT 0.5000,
    role_alignment_score    DECIMAL(5,4) NOT NULL DEFAULT 0.5000,
    engagement_frequency    DECIMAL(5,4) NOT NULL DEFAULT 0.0000,
    -- Opinion Triple do Membro
    belief                  DECIMAL(5,4) NOT NULL,
    disbelief               DECIMAL(5,4) NOT NULL,
    uncertainty             DECIMAL(5,4) NOT NULL,
    -- Designação
    designation             VARCHAR(30)  NOT NULL DEFAULT 'UNKNOWN'
                            CHECK (designation IN (
                                'STRUCTURAL_CHAMPION', 'BUYING_MOTION_OWNER',
                                'ECONOMIC_BUYER', 'GATEKEEPER', 'UNKNOWN'
                            )),
    bmo_momentum_score      DECIMAL(5,4) NOT NULL DEFAULT 0.0000,
    -- Controle
    first_identified_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_updated_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    cycle_id                VARCHAR(50)  NOT NULL,
    UNIQUE (company_entity_id, person_entity_id),
    CONSTRAINT opinion_triple_valid CHECK (
        ABS(belief + disbelief + uncertainty - 1.000) < 0.001
    )
);

-- Multi-hop B-Tree: empresa → papéis → probabilidade
CREATE INDEX idx_committee_company_designation
    ON committee_members (company_entity_id, designation, role_probability DESC);
CREATE INDEX idx_committee_bmo_momentum
    ON committee_members (company_entity_id, bmo_momentum_score DESC)
    WHERE designation = 'BUYING_MOTION_OWNER';

CREATE TABLE behavioral_momentum_log (
    log_id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    person_entity_id    UUID            NOT NULL REFERENCES entity_nodes(entity_id),
    event_type          VARCHAR(50)     NOT NULL CHECK (event_type IN (
                            'post_about_pain', 'anchor_comment', 'anchor_like',
                            'job_interaction', 'cargo_change', 'new_follow_anchor'
                        )),
    event_source        VARCHAR(64)     NOT NULL,
    evidence_id         UUID            REFERENCES observed_evidence(evidence_id),
    momentum_delta      DECIMAL(5,4)    NOT NULL DEFAULT 0.0000,
    recorded_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    cycle_id            VARCHAR(50)     NOT NULL
);

-- Multi-hop B-Tree: pessoa → tipo de evento → recência (BMO detection)
CREATE INDEX idx_behavioral_momentum_bmo_detection
    ON behavioral_momentum_log (person_entity_id, event_type, recorded_at DESC);

-- ────────────────────────────────────────────────────────────
-- LAYER 8: ANALYTICAL FEATURE STORE (DESNORMALIZADA)
-- Separação estrita: Opportunity Variables | Confidence Variables
-- ────────────────────────────────────────────────────────────

CREATE TABLE analytical_feature_store (
    feature_store_id    UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id           UUID            NOT NULL REFERENCES entity_nodes(entity_id),
    cycle_id            VARCHAR(50)     NOT NULL,
    computed_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- === OPPORTUNITY VARIABLES ===
    feat_fit_score              DECIMAL(5,4),
    feat_s_intent_score         DECIMAL(5,4),
    feat_reachability_hybrid    DECIMAL(5,4),
    feat_r_interactions         DECIMAL(5,4),
    feat_r_mutual_followers     DECIMAL(5,4),
    feat_r_org_proximity        DECIMAL(5,4),
    feat_committee_completeness DECIMAL(5,4),
    feat_e_fresh                DECIMAL(5,4),
    feat_o_score                DECIMAL(5,4),

    -- === CONFIDENCE VARIABLES ===
    feat_rcs_score              DECIMAL(5,4),
    feat_c_s_shannon            DECIMAL(5,4),
    feat_uncertainty_committee  DECIMAL(5,4),
    feat_hypothesis_confidence  DECIMAL(5,4),
    feat_srs_product            DECIMAL(5,4),
    feat_c_score                DECIMAL(5,4),

    -- === RANKING FINAL ===
    feat_p_score                DECIMAL(5,4),
    feat_rank_position          INTEGER,
    feat_rank_total             INTEGER,

    -- === FLAGS OPERACIONAIS ===
    data_quality_flag   VARCHAR(20)     NOT NULL DEFAULT 'NORMAL'
                        CHECK (data_quality_flag IN ('NORMAL', 'LOW', 'DEGRADED')),
    operating_mode      VARCHAR(30)     NOT NULL DEFAULT 'FULL'
                        CHECK (operating_mode IN (
                            'FULL', 'DEGRADED_LINKEDIN', 'DEGRADED_INSTAGRAM', 'CACHE_ONLY'
                        )),

    -- === V1/V2 READINESS (NULL NO MVP) ===
    -- ml_feature_vector      vector(128),        -- pgvector; ativar V1
    gradient_descent_target     DECIMAL(5,4),   -- NULL no MVP; V1
    meta_learning_weight        DECIMAL(5,4),   -- NULL no MVP; V1

    UNIQUE (entity_id, cycle_id)
);

-- Multi-hop B-Tree: ranking com filtro de qualidade
CREATE INDEX idx_feature_store_p_score_desc
    ON analytical_feature_store (feat_p_score DESC NULLS LAST)
    WHERE feat_p_score IS NOT NULL;
CREATE INDEX idx_feature_store_ranking_quality
    ON analytical_feature_store (feat_p_score DESC, data_quality_flag, operating_mode)
    WHERE feat_p_score IS NOT NULL;
-- Multi-hop: separação O/C para análise de quadrante
CREATE INDEX idx_feature_store_o_c_quadrant
    ON analytical_feature_store (feat_o_score DESC, feat_c_score DESC)
    WHERE feat_o_score IS NOT NULL AND feat_c_score IS NOT NULL;

-- ────────────────────────────────────────────────────────────
-- LAYER 9: LOGS OPERACIONAIS
-- ────────────────────────────────────────────────────────────

CREATE TABLE search_logs (
    log_id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_id            VARCHAR(50)     NOT NULL,
    execution_start     TIMESTAMPTZ     NOT NULL,
    execution_end       TIMESTAMPTZ,
    sensor_key          VARCHAR(64)     NOT NULL,
    query_dsl           JSONB           NOT NULL DEFAULT '{}',
    entities_processed  INTEGER         NOT NULL DEFAULT 0,
    entities_new        INTEGER         NOT NULL DEFAULT 0,
    dss_value           DECIMAL(6,5),
    dss_window_size     INTEGER         NOT NULL DEFAULT 50,
    operating_mode      VARCHAR(30)     NOT NULL DEFAULT 'FULL',
    api_calls_made      INTEGER         NOT NULL DEFAULT 0,
    estimated_cost_brl  DECIMAL(8,4)    NOT NULL DEFAULT 0.0000,
    eig_last            DECIMAL(8,6),
    mic_last            DECIMAL(8,6),
    eig_mic_ratio       DECIMAL(8,6),
    stopping_rule_triggered VARCHAR(50),
    http_status_final   INTEGER,
    error_detail        TEXT
);

CREATE INDEX idx_search_logs_cycle_sensor
    ON search_logs (cycle_id, sensor_key);
CREATE INDEX idx_search_logs_execution_start
    ON search_logs (execution_start DESC);

CREATE TABLE conflict_resolution_log (
    conflict_id         UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id           UUID            NOT NULL REFERENCES entity_nodes(entity_id),
    attribute_key       VARCHAR(100)    NOT NULL,
    source_a_key        VARCHAR(64)     NOT NULL,
    source_a_value      TEXT            NOT NULL,
    source_a_srs        DECIMAL(5,4)    NOT NULL,
    source_b_key        VARCHAR(64)     NOT NULL,
    source_b_value      TEXT            NOT NULL,
    source_b_srs        DECIMAL(5,4)    NOT NULL,
    divergence_delta    DECIMAL(7,5)    NOT NULL,
    resolution_method   VARCHAR(50)     NOT NULL DEFAULT 'SRS_HIERARCHY',
    authoritative_value TEXT            NOT NULL,
    residual_uncertainty_delta DECIMAL(5,4) NOT NULL DEFAULT 0.0000,
    conflict_severity   VARCHAR(20)     NOT NULL DEFAULT 'LOW'
                        CHECK (conflict_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    requires_manual_review BOOLEAN      NOT NULL DEFAULT FALSE,
    resolved_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    cycle_id            VARCHAR(50)     NOT NULL
);

CREATE INDEX idx_conflict_log_entity_cycle
    ON conflict_resolution_log (entity_id, cycle_id);
CREATE INDEX idx_conflict_log_severity
    ON conflict_resolution_log (conflict_severity, resolved_at DESC)
    WHERE conflict_severity IN ('HIGH', 'CRITICAL');

CREATE TABLE pruned_reason_log (
    pruning_id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_id            VARCHAR(50)     NOT NULL,
    entity_id           UUID            NOT NULL REFERENCES entity_nodes(entity_id),
    stopping_rule_id    VARCHAR(50)     NOT NULL,
    o_score_at_pruning  DECIMAL(5,4),
    c_score_at_pruning  DECIMAL(5,4),
    p_score_at_pruning  DECIMAL(5,4),
    dss_value           DECIMAL(6,5),
    eig_value           DECIMAL(8,6),
    mic_value           DECIMAL(8,6),
    eig_mic_ratio       DECIMAL(8,6),
    total_api_calls     INTEGER         NOT NULL DEFAULT 0,
    total_cost_brl      DECIMAL(8,4)    NOT NULL DEFAULT 0.0000,
    mode_transition_to  VARCHAR(30)     NOT NULL DEFAULT 'DELTA_SEARCH',
    delta_recheck_at    TIMESTAMPTZ,
    pruned_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    full_payload        JSONB
);

CREATE INDEX idx_pruned_log_entity_cycle
    ON pruned_reason_log (entity_id, cycle_id);
CREATE INDEX idx_pruned_log_recheck
    ON pruned_reason_log (delta_recheck_at ASC)
    WHERE mode_transition_to = 'DELTA_SEARCH';

-- ────────────────────────────────────────────────────────────
-- LAYER 10: CRM FEEDBACK LOOP (MIRROR TABLES — V1 READINESS)
-- ────────────────────────────────────────────────────────────

CREATE TABLE crm_outcome_log (
    outcome_id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id           UUID            NOT NULL REFERENCES entity_nodes(entity_id),
    crm_lead_id         VARCHAR(100)    NOT NULL,
    outcome_type        VARCHAR(30)     NOT NULL
                        CHECK (outcome_type IN (
                            'CLOSED_WON', 'CLOSED_LOST', 'NO_SHOW', 'DISQUALIFIED'
                        )),
    outcome_reason      TEXT,
    -- Snapshot de scores no momento do ranking
    p_score_at_ranking  DECIMAL(5,4),
    o_score_at_ranking  DECIMAL(5,4),
    c_score_at_ranking  DECIMAL(5,4),
    rank_position_at_ranking INTEGER,
    cycle_id_at_ranking VARCHAR(50),
    dominant_hypothesis_at_ranking CHAR(2),
    -- Campos para calibração V1 (NULL no MVP)
    bmo_designation_correct     BOOLEAN,    -- NULL até validação
    sc_designation_correct      BOOLEAN,    -- NULL até validação
    prior_calibration_delta     DECIMAL(5,4), -- NULL no MVP
    srs_feedback_source_key     VARCHAR(64),  -- fonte principal da evidência determinante
    -- Metadados de recepção
    webhook_received_at TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    source_system       VARCHAR(50)     NOT NULL DEFAULT 'MANUAL'
);

CREATE INDEX idx_crm_outcome_entity
    ON crm_outcome_log (entity_id, outcome_type);
CREATE INDEX idx_crm_outcome_cycle
    ON crm_outcome_log (cycle_id_at_ranking);
CREATE INDEX idx_crm_outcome_won
    ON crm_outcome_log (outcome_type, webhook_received_at DESC)
    WHERE outcome_type = 'CLOSED_WON';

-- ────────────────────────────────────────────────────────────
-- VIEW DE OBSERVABILIDADE COGNITIVA (§4.6)
-- ────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW v_cognitive_observability AS
SELECT
    DATE_TRUNC('day', sl.execution_start)                       AS operation_day,
    COUNT(DISTINCT afs.entity_id)                               AS leads_processed,
    COUNT(DISTINCT afs.entity_id)
        FILTER (WHERE afs.feat_p_score >= 0.50)                 AS leads_qualified,
    ROUND(AVG(afs.feat_p_score)::NUMERIC, 4)                    AS avg_p_score,
    ROUND(AVG(afs.feat_o_score)::NUMERIC, 4)                    AS avg_o_score,
    ROUND(AVG(afs.feat_c_score)::NUMERIC, 4)                    AS avg_c_score,
    ROUND(SUM(sl.estimated_cost_brl)::NUMERIC, 4)               AS total_cost_brl,
    ROUND((SUM(sl.estimated_cost_brl)
        / NULLIF(COUNT(DISTINCT afs.entity_id)
            FILTER (WHERE afs.feat_p_score >= 0.50), 0))::NUMERIC, 4)
                                                                 AS cost_per_qualified_lead,
    COUNT(prl.pruning_id)                                       AS pruning_events,
    ROUND((COUNT(prl.pruning_id)::FLOAT
        / NULLIF(COUNT(DISTINCT sl.cycle_id), 0))::NUMERIC, 4)  AS saturation_rate,
    ROUND(AVG(sl.dss_value)::NUMERIC, 5)                        AS avg_dss,
    COUNT(crl.conflict_id)                                      AS conflict_events,
    COUNT(crl.conflict_id)
        FILTER (WHERE crl.conflict_severity IN ('HIGH', 'CRITICAL'))
                                                                 AS critical_conflict_events,
    ROUND(AVG(afs.feat_e_fresh)::NUMERIC, 4)                    AS avg_freshness,
    COUNT(DISTINCT afs.entity_id)
        FILTER (WHERE afs.operating_mode <> 'FULL')             AS degraded_mode_leads
FROM search_logs sl
LEFT JOIN analytical_feature_store afs ON afs.cycle_id = sl.cycle_id
LEFT JOIN pruned_reason_log prl ON prl.cycle_id = sl.cycle_id
LEFT JOIN conflict_resolution_log crl ON crl.cycle_id = sl.cycle_id
GROUP BY DATE_TRUNC('day', sl.execution_start)
ORDER BY operation_day DESC;
```

---

### 4.5 Event Storming Operational Grid

| # | Comando | Evento de Domínio | Política de Negócio | Impacto DML |
|---|---|---|---|---|
| 1 | `EXECUTE_DISCOVERY_CYCLE(contract_id, seed_list)` | `DiscoveryCycleStarted` | Verificar `icp_contract.is_active = TRUE`; rejeitar se falso | `INSERT search_logs (cycle_id, execution_start, sensor_key, query_dsl)` |
| 2 | `COLLECT_EVIDENCE(entity_id, source_key, raw_payload)` | `EvidenceCollected` | Calcular `immutable_hash`; rejeitar duplicata (UNIQUE); se HTTP 429 → Degraded Mode | `INSERT observed_evidence`; `UPDATE entity_nodes.last_updated_at` |
| 3 | `DETECT_SCRAPER_FAILURE(source_key, error_type)` | `DegradedModeActivated` | Se LinkedIn → `u += 0.20`; se ambos → suspensão + alerta; atualizar `search_logs.operating_mode` | `UPDATE search_logs.operating_mode, http_status_final, error_detail` |
| 4 | `EVALUATE_DSS(cycle_id, window_size)` | `DSSCalculated` | Se `DSS < δ_DSS` por N janelas consecutivas → emitir `DiscoveryWindowSaturated` | `UPDATE search_logs.dss_value`; `INSERT pruned_reason_log` se condição de saturação |
| 5 | `CHECK_FINOPS_RULE(entity_id, sensor_key, eig, mic)` | `FinOpsRuleEvaluated` | Se `EIG/MIC < τ` → `InvestigationPruned`; sensor desativado para o lead; Delta Search | `INSERT pruned_reason_log`; `UPDATE search_logs.stopping_rule_triggered, eig_mic_ratio` |
| 6 | `RESOLVE_ENTITY(evidence_batch)` | `EntityResolved` ou `EntityMerged` | RCS ≥ 0.82 → auto-merge; 0.65–0.82 → `MERGE_CANDIDATE` + revisão; < 0.65 → nova entidade | `UPSERT entity_nodes`; `INSERT conflict_resolution_log` se divergência |
| 7 | `APPLY_CONFLICT_RESOLUTION(entity_id, attr, sources[])` | `ConflictResolved` | Ordenar por SRS; se `divergence_delta > δ_tolerance` → elevar `u` no nó | `INSERT conflict_resolution_log`; `UPDATE entity_nodes.(belief, disbelief, uncertainty)` |
| 8 | `APPLY_RRF_FUSION(candidate_list_by_source)` | `RRFFusionApplied` | Calcular posição RRF para cada candidato; selecionar top-1 como `authoritative` | Nenhum write direto; resultado alimenta `RESOLVE_ENTITY` |
| 9 | `DECAY_FRESHNESS(cycle_date)` | `FreshnessDecayed` | Executar diariamente; `E_fresh = e^(-ln(2)*Δt/t½)` para cada evidência e aresta ativa | `UPDATE observed_evidence.freshness_current`; `UPDATE entity_edges.freshness_current` |
| 10 | `UPDATE_SRS(source_key, tp_delta, tn_delta, fp_delta, fn_delta)` | `SRSRecalculated` | Incrementar contadores; recalcular `srs_current` via fórmula §2.10 | `UPDATE source_reliability.(true_positives, ..., srs_current, last_recalculated)` |
| 11 | `COMPUTE_INFERENCE(entity_id, evidence_ids[], method)` | `InferenceGenerated` | Mínimo 2 evidências observadas; marcar predecessor como `is_current = FALSE` | `INSERT generated_inferences`; `UPDATE generated_inferences.is_current = FALSE` (predecessores) |
| 12 | `EVALUATE_HYPOTHESIS(entity_id, hypothesis_id, cycle_id)` | `HypothesisUpdated` | Aplicar Bayes P(H\|E); se `supporting_count ≥ min_for_active` → status `ACTIVE`; preservar histórico | `INSERT evaluated_hypotheses` (nova versão por cycle_id); histórico nunca deletado |
| 13 | `MAP_COMMITTEE_MEMBER(company_id, person_id, evidence[])` | `CommitteeMemberMapped` | SC: cargo estático ≥ 6m + `role_alignment > 0.60`; BMO: `bmo_momentum_score > 0.55` + cluster ≥ 3 posts/21d | `UPSERT committee_members`; `INSERT behavioral_momentum_log` por event detectado |
| 14 | `IDENTIFY_BMO(company_id)` | `BMOIdentified` | Selecionar membro com `bmo_momentum_score` máximo E cluster ativo nos últimos 21 dias | `UPDATE committee_members.designation = 'BUYING_MOTION_OWNER'` para BMO eleito |
| 15 | `COMPUTE_SCORES(entity_id, cycle_id)` | `ScoresComputed` | Calcular O→C→P sequencialmente; escrita atômica no Feature Store | `INSERT analytical_feature_store` (UPSERT por `entity_id, cycle_id`) |
| 16 | `GENERATE_XAI_PAYLOAD(entity_id, cycle_id)` | `XAIPayloadGenerated` | `P_score` deve existir no Feature Store; incluir as 3 camadas de evidência | Nenhum write; leitura de `analytical_feature_store`, `evaluated_hypotheses`, `committee_members`, `observed_evidence` |
| 17 | `RECEIVE_CRM_WEBHOOK(crm_lead_id, outcome_type)` | `CRMOutcomeReceived` | Correlacionar `crm_lead_id → entity_id`; snapshot de scores do último ciclo | `INSERT crm_outcome_log` com snapshot de `analytical_feature_store` |
| 18 | `ACTIVATE_DELTA_SEARCH(entity_id, recheck_at)` | `DeltaSearchActivated` | Registrar data de próximo recheck; monitoramento passivo de 4 tipos de trigger | `UPDATE pruned_reason_log.delta_recheck_at`; scheduler externo configurado |

---

### 4.6 Plano de Observabilidade Cognitiva — SLOs

| SLO ID | Métrica | Fórmula SQL | Target | Janela | Alerta Crítico |
|---|---|---|---|---|---|
| SLO-01 | Custo por Lead Qualificado | `SUM(search_logs.estimated_cost_brl) / COUNT(afs.entity_id WHERE p_score ≥ 0.50)` | ≤ R$ 0.85 | Rolling 7d | > R$ 1.50 |
| SLO-02 | Taxa de Falsos Positivos em Fusão | `COUNT(conflict_log WHERE severity IN ('HIGH','CRITICAL')) / COUNT(entity_nodes WHERE merge_parent_id IS NOT NULL)` | ≤ 4% | Rolling 30d | > 10% |
| SLO-03 | Taxa de Saturação Vazia | `COUNT(pruned_reason_log WHERE rule = 'SR-DSS-001') / COUNT(DISTINCT search_logs.cycle_id)` | ≤ 15% | Rolling 7d | > 35% |
| SLO-04 | Cobertura de BMO Identificado | `COUNT(committee WHERE designation = 'BMO') / COUNT(afs WHERE p_score ≥ 0.50)` | ≥ 60% | Rolling 30d | < 30% |
| SLO-05 | Freshness Médio do Feature Store | `AVG(analytical_feature_store.feat_e_fresh WHERE p_score ≥ 0.50)` | ≥ 0.70 | Rolling 7d | < 0.45 |
| SLO-06 | Disponibilidade do Pipeline | `1 - (COUNT(search_logs WHERE http_status_final ≥ 500 OR error_detail IS NOT NULL) / COUNT(search_logs))` | ≥ 98.5% | Rolling 24h | < 95% |
| SLO-07 | Latência de Ciclo Completo | `AVG(execution_end - execution_start)` por lead completo | ≤ 180s | Rolling 24h | > 600s |
| SLO-08 | Taxa de Hipóteses Ativas por Lead Qualificado | `AVG(supporting_count + contradicting_count) WHERE status = 'ACTIVE' AND p_score ≥ 0.50` | ≥ 4 evidências por hipótese ativa | Rolling 30d | < 2 |

---

## SEÇÃO 5: ARQUITETURA DE INTEGRAÇÃO E CONTRATOS DE INTERFACE

### 5.1 Contratos de API Interna

**Input — Criação de Ciclo de Descoberta:**

```
POST /api/v1/cycles
Content-Type: application/json
Authorization: Bearer {token}

{
  "contract_id": "uuid",
  "execution_mode": "FULL | DELTA_SEARCH",
  "seed_targets": [
    {
      "instagram_handle": "@exemplo",
      "linkedin_url": "linkedin.com/company/exemplo",
      "source": "manual | crm_import | referral"
    }
  ]
}

Response 202 Accepted:
{
  "cycle_id": "CYC-YYYYMMDD-NNN",
  "estimated_completion_seconds": 180,
  "leads_in_queue": 45
}
```

**Output — Lista Ranqueada de Leads:**

```
GET /api/v1/leads?min_p_score=0.50&limit=20&cycle_id=CYC-xxx&data_quality=NORMAL,LOW
Authorization: Bearer {token}

Response 200:
{
  "cycle_id": "CYC-xxx",
  "total_qualified": 23,
  "leads": [ { ...XAI_Unified_Payload... } ]
}
```

**Webhook Receiver — CRM:**

```
POST /api/v1/webhooks/crm
Content-Type: application/json
X-Source-System: {crm_name}
X-Signature: {hmac_sha256_of_body}

{
  "crm_lead_id": "string",
  "outcome_type": "CLOSED_WON | CLOSED_LOST | NO_SHOW | DISQUALIFIED",
  "outcome_reason": "string | null",
  "occurred_at": "ISO8601"
}

Response 204 No Content
```

---

## SEÇÃO 6: STACK TÉCNICO E LIMITES DE ESCALA DO MVP

### 6.1 Stack Técnico

| Componente | Tecnologia | Justificativa |
|---|---|---|
| Banco de Dados Principal | PostgreSQL 16+ (`pg_trgm`, `pgvector` preparado) | Graph-Ready relacional; índices trigrama para JW; pgvector para V1 |
| Cache L1 | Redis 7+ | TTL-based para scrapers; pub/sub para eventos de domínio |
| Fila de Tarefas | Celery + RabbitMQ | Filas por prioridade de módulo; retry policy para falhas de scraper |
| Processamento | Python 3.11+ (asyncio) | Concorrência de I/O para scrapers paralelos |
| API Layer | FastAPI + Pydantic v2 | Validação contratual; OpenAPI auto-gerado; validação de assinatura webhook |
| Observabilidade | Prometheus + Grafana | Exportação direta de todos os SLOs §4.6 como métricas |
| Jaro-Winkler | `jellyfish` (Python) | Implementação C, alta performance |
| Scraping Instagram | Instaloader | Fallback para cache em rate-limit |
| Scraping LinkedIn | Playwright headless + cookie pool | Rotação de cookies; detecção de CAPTCHA com retry |

### 6.2 Limites Operacionais do MVP

| Parâmetro | Limite MVP | Justificativa |
|---|---|---|
| Leads qualificados por ciclo | ≤ 200 | Custo de scraping e latência controlados |
| Membros de comitê por empresa | ≤ 5 | Evidências públicas limitam granularidade |
| Fontes de dados ativas | 3 (Instagram, LinkedIn, CNPJ) | Complexidade de SRS controlada |
| Ciclos paralelos simultâneos | ≤ 3 | Rate-limit de scrapers |
| Hipóteses ativas por lead | ≤ 3 | Foco do MVP nos 5 hipóteses principais |
| Retenção de evidências | 365 dias | Cold storage após expiração |

---

## APÊNDICE A: GLOSSÁRIO TÉCNICO

| Termo | Definição |
|---|---|
| BMO | Buying Motion Owner: indivíduo com momentum comportamental ativo de transformação; pode diferir do SC |
| C_score | Confidence Score: mede a confiabilidade matemática e qualidade dos dados do lead |
| C_s | Data Confidence Score: derivado da Entropia de Shannon entre múltiplos provedores |
| CRP | Conflict Resolution Policy: política determinística de arbitragem de dados contraditórios |
| DSS | Discovery Saturation Score: razão de entidades inéditas sobre total processado em janela deslizante |
| E_fresh | Multiplicador de frescor; derivado da função de meia-vida exponencial configurável por tipo |
| EIG | Expected Information Gain: ganho esperado de informação de um sensor (divergência KL) |
| ICP | Ideal Customer Profile: contrato configurável de parâmetros do cliente-alvo |
| MIC | Marginal Information Cost: custo marginal monetário de acionamento de um sensor |
| O_score | Opportunity Score: mede o valor comercial intrínseco e o momentum do lead |
| P_score | Priority Score: função matricial não-linear de O_score e C_score para ranking final determinístico |
| RCS | Resolution Confidence Score: confiança de fusão de entidade via Jaro-Winkler com penalizadores |
| RRF | Reciprocal Rank Fusion: algoritmo de fusão de rankings de múltiplos scrapers |
| SC | Structural Champion: profissional com alto alinhamento funcional e cargo estático |
| SRS | Source Reliability Score: confiabilidade histórica de uma fonte de dados |
| ω (omega) | Tripla de opinião (b, d, u) da Lógica Subjetiva; `b + d + u = 1`; base de toda propagação de confiança |

---

## APÊNDICE B: RESPOSTAS FORMAIS ÀS TRÊS PERGUNTAS DO NEGÓCIO

| Pergunta | Módulo Responsável | Output Técnico |
|---|---|---|
| "Qual empresa/perfil devo abordar primeiro?" | Módulo 5 — MatrixRankFunction | `ranked_lead_list` ordenada por `P_score`; XAI payload com drivers de O_score e C_score |
| "Quem compõe o comitê e quem é o BMO?" | Módulo 4 — Buying Committee Analytics | `committee_members` com `designation = SC / BMO`; `CommitteeCompleteness`; ω-triple por membro |
| "Qual é a hipótese de dor e o blueprint de abordagem?" | Módulo 3 (hipótese dominante) + Módulo 5 (XAI) | `dominant_hypothesis` com posterior bayesiano; `approach_blueprint` no XAI payload |

---

**FIM DO DOCUMENTO**

*SocialSelling MVP SDD v1.1 — Emitido pelo Comitê de Engenharia de Elite*
*v1.1: 9 correções aplicadas (3 cirúrgicas + 6 arquiteturais) — ver Registro de Alterações no cabeçalho*
*Próxima revisão obrigatória: ao mutar o contrato ICP ou ao iniciar implementação de V1*
