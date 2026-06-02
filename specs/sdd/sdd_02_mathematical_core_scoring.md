# SDD-02: Motores de Cálculo e Álgebra de Priorização
## SocialSelling — Solution Design Document
### Versão: 1.0-MVP | Classificação: CONFIDENCIAL — ENGENHARIA

---

**Escopo do Documento:** Definição formal de todas as funções de scoring do sistema — P_score (MatrixRankFunction), O_score (Opportunity), Fit Score vetorial, C_score (Confidence), C_s via entropia de Shannon, RCS via Jaro-Winkler, freshness decay exponencial e propriedades formais de domínio e monotonicidade. Todos os valores numéricos neste documento são calculados analiticamente; não existem placeholders.

**Documentos relacionados:**
- `sdd_01_product_vision_and_core_dag.md` — Arquitetura LangGraph, LeadState (denominado `LeadState` no SDD-01; padronizado como `LeadState` a partir do SDD-07), DAG de fases
- `sdd_04_sensory_search_and_finops_stopping.md` — DSS, EIG/MIC stopping rule, Delta Search
- `sdd_05_buying_committee_and_motion.md` — Buying Committee, Uncertainty_Committee, S_persona
- `sdd_06_database_schema_and_graph_ready_ddl.md` — DDL das tabelas `analytical_feature_store` (scores por ciclo), `source_reliability` (SRS e SQS por fonte), `observed_evidence` (evidências brutas)
- `sdd_07_event_storming_and_saga_orchestration.md` — EV-12 (score compute → `analytical_feature_store`), EV-15 (Delta Search trigger)
- `sdd_12_xai_and_pruning_json_contracts.md` — XAI Payload, auditabilidade de scoring

---

## Índice

1. [P_score — MatrixRankFunction](#1-pscore--matrixrankfunction)
2. [O_score — Opportunity Score](#2-oscore--opportunity-score)
3. [Fit Score Vetorial](#3-fit-score-vetorial)
4. [C_score — Confidence Score](#4-cscore--confidence-score)
5. [C_s via Entropia de Shannon](#5-cs-via-entropia-de-shannon)
6. [RCS via Jaro-Winkler](#6-rcs-via-jaro-winkler)
7. [Freshness Decay Exponencial](#7-freshness-decay-exponencial)
8. [Propriedades Formais](#8-propriedades-formais)

---

## 1. P_SCORE — MATRIXRANKFUNCTION

### 1.1 Fórmula e Justificativa dos Hiperparâmetros

O P_score é a função de ranqueamento final do sistema. Ele combina dois sinais ortogonais — oportunidade comercial (O_score) e confiança epistêmica nos dados (C_score) — por meio de uma função exponencial negativa que modula a confiança:

```
P_score = O_score × (1 - α × e^(-β × C_score))

α = 0.60
β = 4.0
```

**Interpretação algébrica:** O fator `(1 - α × e^(-β × C))` é uma função sigmóide assimétrica em C que opera como gate de confiança. Quando C=0, o gate vale `1 - α = 0.40`, o que impede que prospects com zero evidência coletada recebam P_score nulo — eles recebem 40% do seu O_score potencial. À medida que C cresce, o gate converge para 1.0, devolvendo integralmente o O_score.

**Justificativa de α = 0.60:**
O valor 0.60 é calibrado para que um prospect com O_score alto (≥ 0.70) e confiança zero ainda receba P_score ≥ 0.28, mantendo-o na banda DELTA SEARCH (≥ 0.25) e não em PRUNED. Isso preserva prospects de alto potencial cujos dados ainda não foram coletados. Se α fosse 1.0, qualquer C=0 produziria P_score=0, descartando imediatamente prospects sem histórico — comportamento indesejável no arranque do sistema.

**Justificativa de β = 4.0:**
O parâmetro β controla a velocidade de saturação. Com β=4.0, o gate atinge 91.9% do seu máximo com C=0.50 (meia confiança), sinalizando retorno marginal decrescente de coleta adicional de evidências acima de C≥0.70. Valores de β < 2.0 tornariam o gate excessivamente linear (sem incentivo a coletar até C alto); valores de β > 6.0 tornariam o sistema binário (C < 0.30 → descarte, C ≥ 0.30 → pleno ranqueamento).

### 1.2 Tabela f(C) = 1 - 0.60 × e^(-4.0 × C)

A coluna `f(C)` representa o gate de confiança. A coluna `P(1.0, C)` é o P_score máximo possível para cada nível de C (com O_score=1.0).

| C      | e^(-4C)    | f(C)       | P_score(O=1.0, C) |
|--------|------------|------------|-------------------|
| 0.00   | 1.000000   | 0.400000   | 0.400000          |
| 0.10   | 0.670320   | 0.597808   | 0.597808          |
| 0.20   | 0.449329   | 0.730403   | 0.730403          |
| 0.30   | 0.301194   | 0.819283   | 0.819283          |
| 0.40   | 0.201897   | 0.878862   | 0.878862          |
| 0.50   | 0.135335   | 0.918799   | 0.918799          |
| 0.60   | 0.090718   | 0.945569   | 0.945569          |
| 0.70   | 0.060810   | 0.963514   | 0.963514          |
| 0.80   | 0.040762   | 0.975543   | 0.975543          |
| 0.90   | 0.027324   | 0.983606   | 0.983606          |
| 1.00   | 0.018316   | 0.989011   | 0.989011          |

**Observação:** P_score nunca atinge 1.0 para nenhum C finito, pois `e^(-β×C) > 0` para todo C real. O limite superior teórico é O_score × 1.0, alcançado assintoticamente conforme C → ∞.

### 1.3 Quatro Quadrantes Operacionais

Os quadrantes são definidos pela combinação de O_score e C_score e determinam a ação operacional prescrita pelo sistema.

#### Quadrante I — Alto-O (≥ 0.70) / Alto-C (≥ 0.70): PRIORITY ACTION

```
P(0.70, 0.70) = 0.70 × (1 - 0.60 × e^(-4.0 × 0.70))
              = 0.70 × (1 - 0.60 × 0.060810)
              = 0.70 × (1 - 0.036486)
              = 0.70 × 0.963514
              = 0.674460

P(1.00, 1.00) = 1.00 × (1 - 0.60 × e^(-4.0 × 1.00))
              = 1.00 × (1 - 0.60 × 0.018316)
              = 1.00 × 0.989011
              = 0.989011
```

Prospects neste quadrante têm alta evidência de fit e alta confiança nas evidências coletadas. Ambos os P_scores estão acima do threshold 0.65 de PRIORITY ACTION. A ação prescrita é contato direto via rota de reachability identificada, sem investigação adicional obrigatória.

#### Quadrante II — Alto-O (≥ 0.70) / Baixo-C (< 0.35): INVESTIGAÇÃO URGENTE

```
P(0.70, 0.30) = 0.70 × (1 - 0.60 × e^(-4.0 × 0.30))
              = 0.70 × (1 - 0.60 × 0.301194)
              = 0.70 × (1 - 0.180717)
              = 0.70 × 0.819283
              = 0.573498

P(0.90, 0.20) = 0.90 × (1 - 0.60 × e^(-4.0 × 0.20))
              = 0.90 × (1 - 0.60 × 0.449329)
              = 0.90 × (1 - 0.269597)
              = 0.90 × 0.730403
              = 0.657362
```

O prospect sinaliza alto potencial mas as evidências são esparsas ou conflitantes (C baixo). O sistema emite um evento `InvestigationOpportunity` com prioridade máxima. O threshold de disparo desse evento é: **O ≥ 0.70 AND C < 0.35 AND P_score ≥ 0.30**. Ambos os exemplos satisfazem a condição (P=0.5735 e P=0.6574, ambos ≥ 0.30). A ação prescrita é Delta Search imediato com budget de 10 queries Tavily dedicadas.

#### Quadrante III — Baixo-O (< 0.40) / Alto-C (≥ 0.70): PODA / DELTA SEARCH

```
P(0.40, 0.70) = 0.40 × (1 - 0.60 × e^(-4.0 × 0.70))
              = 0.40 × (1 - 0.60 × 0.060810)
              = 0.40 × 0.963514
              = 0.385406
```

Alta confiança confirma que o prospect genuinamente não se encaixa no ICP — as evidências são sólidas e apontam para baixo fit. P_score = 0.3854 está na banda DELTA SEARCH (0.25–0.45). Se após um ciclo de Delta Search o P_score não ascender acima de 0.45, o prospect é movido para PRUNED via `PruningDecision` event.

#### Quadrante IV — Baixo-O / Baixo-C: PRUNED

```
P(0.30, 0.30) = 0.30 × (1 - 0.60 × e^(-4.0 × 0.30))
              = 0.30 × (1 - 0.60 × 0.301194)
              = 0.30 × 0.819283
              = 0.245785
```

P_score = 0.2458 está abaixo do threshold de 0.25, portanto o prospect é marcado como PRUNED imediatamente. O sistema registra `pruning_reason = 'LOW_O_LOW_C'` e cessa coleta de evidências para essa entidade no ciclo corrente.

### 1.4 Thresholds Operacionais — Quatro Bandas

| Banda            | Intervalo P_score | Ação Prescrita                                    | Evento Gerado              |
|------------------|-------------------|---------------------------------------------------|----------------------------|
| PRIORITY ACTION  | ≥ 0.65            | Rota de contato ativada, alerta para operador     | `ProspectPrioritized`      |
| MONITOR          | 0.45 – 0.6499     | Manter na fila, aguardar próximo ciclo de coleta  | `ProspectMonitored`        |
| DELTA SEARCH     | 0.25 – 0.4499     | Investigação adicional com budget reduzido (5q)   | `DeltaSearchTriggered`     |
| PRUNED           | < 0.25            | Coleta suspensa; arquivado com razão de poda      | `PruningDecision`          |

### 1.5 Regra de Desempate — Cinco Níveis

Quando dois ou mais prospects apresentam P_score idêntico (dentro de ε = 0.0001), a ordenação da `ranked_prospects` segue a hierarquia de critérios abaixo, aplicados sequencialmente até desambiguação completa:

| Nível | Critério           | Direção | Justificativa                                               |
|-------|--------------------|---------|-------------------------------------------------------------|
| 1     | `O_score`          | DESC    | Maior oportunidade intrínseca tem precedência               |
| 2     | `C_score`          | DESC    | Maior confiança nas evidências é preferível a menor         |
| 3     | `feat_e_fresh`     | DESC    | Evidências mais recentes indicam sinal mais atual           |
| 4     | `bmo_momentum`     | DESC    | Maior momentum do buying motion indica janela mais quente   |
| 5     | `entity_uuid`      | ASC     | Desempate determinístico por UUID para reprodutibilidade    |

O critério 5 (UUID ASC) garante que a ordenação seja totalmente determinística e auditável — dado o mesmo conjunto de scores, a ordem resultante é sempre idêntica, independentemente da ordem de inserção no banco de dados.

### 1.6 Tabela de Oito Exemplos Numéricos

Todos os valores calculados com α=0.60, β=4.0:

| O_score | C_score | e^(-4×C)   | f(C)       | P_score    | Banda           |
|---------|---------|------------|------------|------------|-----------------|
| 0.90    | 0.10    | 0.670320   | 0.597808   | 0.538027   | MONITOR         |
| 0.90    | 0.50    | 0.135335   | 0.918799   | 0.826919   | PRIORITY ACTION |
| 0.90    | 0.80    | 0.040762   | 0.975543   | 0.877988   | PRIORITY ACTION |
| 0.50    | 0.80    | 0.040762   | 0.975543   | 0.487771   | MONITOR         |
| 0.70    | 0.20    | 0.449329   | 0.730403   | 0.511282   | MONITOR         |
| 0.70    | 0.70    | 0.060810   | 0.963514   | 0.674460   | PRIORITY ACTION |
| 0.40    | 0.90    | 0.027324   | 0.983606   | 0.393442   | DELTA SEARCH    |
| 0.30    | 0.30    | 0.301194   | 0.819283   | 0.245785   | PRUNED          |

**Diagnóstico do caso O=0.90, C=0.10 → MONITOR:**
Este é o caso mais crítico de interpretação. O prospect tem altíssima oportunidade mas apenas 10% de confiança nas evidências. O sistema o coloca em MONITOR (P=0.538), não em PRIORITY ACTION, pois as evidências insuficientes tornam qualquer ação comercial prematura. O `InvestigationOpportunity` event é disparado (O≥0.70, C<0.35) para priorizar coleta.

### 1.7 Ausência de MMR — Diversidade via Filtro no icp_contract

O sistema não implementa Maximal Marginal Relevance (MMR) nem nenhuma outra função de reranqueamento por diversidade na camada de scoring. A diversidade de setor, região geográfica e porte das empresas prospectadas é controlada exclusivamente por **filtros declarativos no `icp_contract` ativo**, em particular nos campos:

- `sector_distribution_cap`: percentual máximo de prospects do mesmo setor no output
- `geo_concentration_limit`: limite de prospects da mesma cidade no ranque final
- `size_band_balance`: distribuição alvo entre faixas de tamanho (5-15, 16-30 colaboradores)

Esta escolha arquitetural mantém a `MatrixRankFunction` como função pura e determinística — seu output depende apenas de (O, C, α, β) — e delega decisões de portfólio para a camada de contrato. Isso garante que o score de um prospect nunca seja afetado pela presença de outros prospects no mesmo ciclo, preservando a independência de scores e a auditabilidade individual.

---

## 2. O_SCORE — OPPORTUNITY SCORE

### 2.1 Fórmula com Pesos

```
O_score = (w_F × Fit + w_I × S_intent + w_R × Reachability) × E_fresh

w_F = 0.45   (Fit)
w_I = 0.35   (S_intent)
w_R = 0.20   (Reachability)

w_F + w_I + w_R = 1.00
```

O O_score é uma combinação convexa de três componentes, escalada pelo fator de atualidade das evidências (E_fresh). O E_fresh aplicado aqui é o valor médio ponderado dos E_fresh individuais de todas as evidências que contribuíram para o cálculo dos três componentes naquele ciclo.

**Justificativa dos pesos:**

| Componente     | Peso | Razão                                                                                         |
|----------------|------|-----------------------------------------------------------------------------------------------|
| Fit            | 0.45 | Alinhamento estrutural com ICP é o preditor mais robusto de conversão para ticket R$18.000   |
| S_intent       | 0.35 | Sinais comportamentais de dor ativa são temporais mas de alta precisão quando presentes       |
| Reachability   | 0.20 | Acesso ao tomador de decisão é necessário mas não suficiente; peso menor para evitar viés geo |

### 2.2 S_intent — Três Sub-sinais

O S_intent é calculado como combinação ponderada de três sub-sinais observados nas plataformas coletadas:

```
S_intent = 0.50 × freq_posts_dor
         + 0.30 × vagas_sinalizadoras
         + 0.20 × engajamento_ancoras
```

**Definição de cada sub-sinal:**

| Sub-sinal              | Peso | Definição operacional                                                                 | Normalização               |
|------------------------|------|---------------------------------------------------------------------------------------|----------------------------|
| `freq_posts_dor`       | 0.50 | Frequência de posts contendo keywords de dor do ICP nas últimas 4 semanas            | min-max [0,1] com cap em 7 posts/semana |
| `vagas_sinalizadoras`  | 0.30 | Presença de vagas abertas para cargos que sinalizam expansão operacional e dor de escala | 0.0 (sem vagas) / 0.50 (1-2 vagas) / 1.0 (3+ vagas) |
| `engajamento_ancoras`  | 0.20 | Taxa de engajamento da fundadora com posts de âncoras conhecidas do ecossistema        | likes+comments / seguidores, cap em 0.05, normalizado para [0,1] |

Os três sub-sinais são independentes e podem ser observados em fontes distintas: `freq_posts_dor` e `engajamento_ancoras` provêm do Instagram/LinkedIn scraper; `vagas_sinalizadoras` provém do LinkedIn Jobs endpoint e da busca Tavily.

### 2.3 Justificativa Formal da Remoção de S_committee_Completeness do O_score

O `S_committee_Completeness` (proporção de papéis do buying committee identificados) foi considerado para inclusão no O_score como quarto componente. Sua remoção é justificada por três razões formais:

**Razão 1 — Separação de preocupações epistêmicas:**
O_score mede a atratividade da oportunidade comercial como uma propriedade da empresa (fit, intenção declarada, acesso). O `S_committee_Completeness` mede a qualidade da observação do sistema — quantos papéis internos conseguimos identificar. Esses são conceitos ortogonais: uma empresa pode ter comitê 100% mapeado e baixo fit, ou fit perfeito com comitê não mapeado. Misturar os dois sinaliza confusão entre a qualidade do prospect e a qualidade da coleta.

**Razão 2 — Dupla penalização indesejável:**
`S_committee_Completeness` já entra no C_score via `Uncertainty_Committee`, que penaliza a confiança quando papéis do comitê não estão mapeados. Se esse mesmo fator reduzisse o O_score, um prospect com comitê não mapeado seria penalizado duas vezes — uma vez na confiança e uma vez na oportunidade — o que causaria P_scores artificialmente baixos para empresas legítimas cujos perfis são difíceis de scrappear.

**Razão 3 — Preservação da interpretabilidade do O_score:**
O O_score deve ser interpretável como "quanto vale esta oportunidade se os dados forem perfeitos". Com essa semântica, o XAI Payload pode comparar O_score vs C_score e comunicar ao operador: "a oportunidade é alta, mas a confiança é baixa — investigue mais antes de agir". Se o O_score absorvesse penalidades de qualidade de dados, essa interpretação seria perdida.

**Conclusão:** `S_committee_Completeness` pertence ao C_score exclusivamente, via `Uncertainty_Committee`.

### 2.4 Reachability_Hybrid

A Reachability mede a facilidade de acesso à tomadora de decisão do prospect, combinando proximidade organizacional e presença digital:

```
Reachability = 0.60 × R_org_proximity
             + 0.40 × R_digital_presence
```

**Tabela R_org_proximity — Nível de Conexão:**

| Grau de Proximidade               | R_org_proximity | Descrição                                                    |
|-----------------------------------|-----------------|--------------------------------------------------------------|
| Conexão direta de 1º grau         | 1.00            | Fundadora segue ou é seguida pela âncora operacional        |
| Conexão de 2º grau via âncora     | 0.85            | Âncora compartilha seguidor/seguindo com a fundadora        |
| Mesmo ecossistema (eventos/grupo) | 0.70            | Co-presença em evento, grupo ou fórum identificado          |
| Sem conexão identificada          | 0.40            | Nenhuma rota de acesso mapeada nas fontes disponíveis        |

**R_digital_presence** é calculado como:

```
R_digital_presence = 0.50 × has_instagram_active
                   + 0.30 × has_linkedin_active
                   + 0.20 × has_email_public
```

Onde cada flag é binário (0 ou 1) baseado na observação de perfil ativo com posts nos últimos 60 dias.

**Nota V1 — Dijkstra:** Na versão V1 do sistema, `R_org_proximity` é calculado por busca de largura no grafo de relacionamentos armazenado em `entity_edges` (tabela do DDL SDD-06). Para escala V2, o cálculo migra para Dijkstra com peso de arestas definido por força de sinal (frequência de interação e recência). O campo `reachability_path` no `LeadState` preserva o caminho de conexão encontrado para auditoria.

### 2.5 Impacto das Hipóteses no O_score — 15 Hipóteses

Cada hipótese operacional do sistema, quando confirmada (status `ACTIVE` com `posterior ≥ threshold_confirm`), eleva um dos componentes do O_score dentro de um intervalo calibrado. Os valores abaixo representam o delta de adição ao componente afetado:

| Hipótese | Componente Afetado | Delta Mínimo | Delta Máximo | Interpretação                                             |
|----------|--------------------|--------------|--------------|-----------------------------------------------------------|
| H1       | S_intent           | +0.08        | +0.15        | Postagem de dor ativa sobre gestão de time                |
| H2       | Fit                | +0.10        | +0.18        | Porte declarado confirmado dentro da faixa ICP            |
| H3       | S_intent           | +0.06        | +0.12        | Engajamento com conteúdo de produtividade/ferramentas     |
| H4       | Fit                | +0.12        | +0.20        | Segmento de atuação confirmado por CNAE + bio             |
| H5       | S_intent           | +0.04        | +0.08        | Compartilhamento de post de concorrente                   |
| H6       | S_intent           | +0.15        | +0.25        | Vaga aberta para papel operacional estratégico            |
| H7       | S_intent           | +0.06        | +0.10        | Menção explícita de problema de escala em caption         |
| H8       | Fit                | +0.08        | +0.14        | Faturamento estimado dentro da faixa R$80k–R$500k         |
| H9       | S_intent           | +0.12        | +0.20        | Founder seguindo influenciadores de gestão e liderança    |
| H10      | S_intent           | +0.08        | +0.14        | Story com temática de planejamento estratégico            |
| H11      | Fit                | +0.06        | +0.12        | Localização geográfica confirmada em cidade-alvo          |
| H12      | S_intent           | +0.10        | +0.16        | Comentário em post de cliente atual do produto            |
| H13      | S_intent           | +0.15        | +0.22        | Publicação de reflexão sobre crescimento e desafios       |
| H14      | S_intent           | +0.08        | +0.14        | Interação com conteúdo de metodologia de consultoria      |
| H15      | Fit                | +0.06        | +0.10        | Anos de empresa no CNPJ dentro da faixa esperada (2–8a)  |

**Aplicação:** O delta efetivo dentro do intervalo é determinado pelo `posterior` da hipótese relativo ao threshold de confirmação: `delta = delta_min + (delta_max - delta_min) × (posterior - threshold_confirm) / (1.0 - threshold_confirm)`. O componente afetado é truncado em 1.0 após a adição.

---

## 3. FIT SCORE VETORIAL

### 3.1 Vetores ICP e Company — Seis Dimensões

O Fit Score é calculado por similaridade cosseno entre o vetor da empresa prospect (`company_vec`) e o vetor do ICP (`ICP_vec`), ambos em R^6:

```
Fit = cosine_sim(company_vec, ICP_vec) × prod_k(1 - u_k × delta)

delta = 0.15  (penalidade por dimensão incerta)
```

**Definição das seis dimensões:**

| Índice | Dimensão             | Tipo    | Derivação                                                                 | Exemplo ICP_vec |
|--------|----------------------|---------|---------------------------------------------------------------------------|-----------------|
| 0      | `sector_sim`         | Float   | Similaridade cosseno entre setor declarado e setor-alvo do ICP            | 1.00 (Advocacia)|
| 1      | `size_norm`          | Float   | Tabela `size_norm` baseada no número de colaboradores declarados ou inferidos | 0.35 (11-50) |
| 2      | `revenue_norm`       | Float   | Estimativa normalizada do faturamento mensal (R$80k→0.30; R$500k→0.80)   | 0.60            |
| 3      | `geo_sim`            | Float   | Tabela de proximidade geográfica (mesma cidade=1.0, mesmo estado=0.85)    | 1.00            |
| 4      | `tech_affinity`      | Float   | Score de adoção tecnológica inferido (SaaS tools declarados, CNPJ atividade) | 0.70         |
| 5      | `founding_recency`   | Float   | Normalização inversa da idade da empresa (2–8 anos = faixa ideal)         | 0.80            |

**ICP_vec de referência (produto R$18.000, fundadoras, Advocacia/Consultoria/SaaS/Engenharia, 5-30 colaboradores, R$80k–R$500k/mês):**

```
ICP_vec = [1.00, 0.35, 0.60, 1.00, 0.70, 0.80]
```

### 3.2 Similaridade Cosseno Ponderada com Penalidade de Incerteza

```
Fit = (company_vec · ICP_vec) / (norm(company_vec) × norm(ICP_vec))
      × prod_k(1 - u_k × 0.15)
```

A penalidade de incerteza é um produto de Hadamard — cada dimensão k contribui com o fator `(1 - u_k × 0.15)`, onde `u_k ∈ [0,1]` é a incerteza epistêmica associada àquela dimensão. O produto total penaliza progressivamente o Fit à medida que mais dimensões ficam incertas.

**Propriedade:** Se todas as incertezas forem zero (u_k = 0 para todo k), a penalidade é 1.0 e o Fit é igual ao cosseno puro. Se uma dimensão tiver u_k = 1.0 (sinal não observável), a penalidade daquela dimensão é `(1 - 1.0 × 0.15) = 0.85` — a dimensão não é excluída, mas contribui com 15% de penalidade.

### 3.3 Tabela size_norm — Cinco Faixas

| Faixa de Colaboradores | size_norm |
|------------------------|-----------|
| 1 – 10                 | 0.10      |
| 11 – 50                | 0.35      |
| 51 – 200               | 0.65      |
| 201 – 500              | 0.85      |
| 500+                   | 1.00      |

**Nota:** O ICP alvo (5–30 colaboradores) mapeia principalmente para a faixa 11–50 (size_norm=0.35). Empresas de 1–10 colaboradores (size_norm=0.10) ficam abaixo do mínimo de 5 e recebem penalidade implícita pela baixa similaridade com o ICP_vec[1]=0.35.

### 3.4 Atributos Mínimos Obrigatórios — MVP

Para que o Fit Score seja computado (não seja marcado como `NULL`), o sistema exige que ao menos as seguintes dimensões estejam observadas:

| Dimensão     | Fonte Primária          | Fallback                    | u_k se ausente |
|--------------|-------------------------|-----------------------------|----------------|
| `sector_sim` | CNAE principal do CNPJ  | Bio Instagram / título LinkedIn | 0.70        |
| `size_norm`  | CNPJ (QSA + funcionários declarados) | Bio Instagram     | 0.60           |
| `geo_sim`    | Endereço CNPJ           | Geolocalização bio Instagram | 0.30          |

Se nenhuma das três dimensões obrigatórias estiver disponível, o Fit Score é marcado como `INSUFFICIENT_DATA` e o O_score recebe `Fit = 0.0` com flag `fit_computable = false`. O prospect permanece no pipeline com C_score reduzido.

### 3.5 Tratamento de Alta Incerteza: u > 0.50 e u = 1.0

**Caso u_k > 0.50 (incerteza alta):** A dimensão é computada normalmente mas recebe penalidade substancial. Por exemplo, com u_k = 0.70, o fator de penalidade é `(1 - 0.70 × 0.15) = 0.895`. O sistema registra um flag `high_uncertainty_dimensions` no XAI Payload listando quais dimensões superam u=0.50.

**Caso u_k = 1.0 (sinal não observável):** Ocorre quando a fonte para aquela dimensão está completamente indisponível (ex.: CNPJ não encontrado → `size_norm` não derivável; Instagram em modo degradado → `tech_affinity` não calculável). O fator de penalidade é `(1 - 1.0 × 0.15) = 0.85`. A dimensão NÃO é removida do cosseno — ela recebe o valor médio da distribuição (0.50) como estimativa agnóstica para não distorcer o ângulo vetorial. O flag `imputed_dimensions` é registrado no XAI Payload.

**Limiar de colapso do Fit:** Se mais de 4 das 6 dimensões tiverem u_k ≥ 0.80, a penalidade acumulada aproximada é `(1-0.80×0.15)^4 = 0.88^4 = 0.5997`. Nesse caso, o Fit Score sinaliza `fit_reliability = LOW` mesmo que o valor calculado seja positivo.

### 3.6 Dois Exemplos Numéricos de Fit Score

**Exemplo 1: Prospect fortemente alinhado ao ICP**

```
ICP_vec     = [1.00, 0.35, 0.60, 1.00, 0.70, 0.80]
company_vec = [0.95, 0.35, 0.55, 1.00, 0.65, 0.75]
uncertainty  = [0.05, 0.10, 0.20, 0.05, 0.15, 0.10]

Contexto: Advogada fundadora, 18 colaboradores, R$200k/mês, Sao Paulo
          (mesma cidade), usa Asana e Slack (tech_affinity alto), empresa com 5 anos.

Produto interno (numerador):
  (0.95×1.00) + (0.35×0.35) + (0.55×0.60) + (1.00×1.00) + (0.65×0.70) + (0.75×0.80)
  = 0.9500 + 0.1225 + 0.3300 + 1.0000 + 0.4550 + 0.6000
  = 3.4575

norm(company_vec) = sqrt(0.9025 + 0.1225 + 0.3025 + 1.0000 + 0.4225 + 0.5625)
                  = sqrt(3.3125) = 1.8201

norm(ICP_vec) = sqrt(1.0000 + 0.1225 + 0.3600 + 1.0000 + 0.4900 + 0.6400)
              = sqrt(3.6125) = 1.9006

cosine_sim = 3.4575 / (1.8201 × 1.9006) = 3.4575 / 3.4583 = 0.999494

Penalidade de incerteza:
  dim[0]: (1 - 0.05 × 0.15) = 0.9925
  dim[1]: (1 - 0.10 × 0.15) = 0.9850
  dim[2]: (1 - 0.20 × 0.15) = 0.9700
  dim[3]: (1 - 0.05 × 0.15) = 0.9925
  dim[4]: (1 - 0.15 × 0.15) = 0.9775
  dim[5]: (1 - 0.10 × 0.15) = 0.9850
  produto = 0.9925 × 0.9850 × 0.9700 × 0.9925 × 0.9775 × 0.9850 = 0.906196

Fit = 0.999494 × 0.906196 = 0.905737
```

**Exemplo 2: Prospect parcialmente alinhado com alta incerteza**

```
ICP_vec     = [1.00, 0.35, 0.60, 1.00, 0.70, 0.80]
company_vec = [0.70, 0.10, 0.30, 0.70, 0.40, 0.50]
uncertainty  = [0.10, 0.40, 0.50, 0.15, 0.60, 0.30]

Contexto: Consultora em area adjacente, 8 colaboradores (faixa inferior ICP),
          faturamento estimado abaixo do minimo ICP, Curitiba (distancia geografica),
          pouca evidencia de tech, empresa recentemente fundada.

cosine_sim = 0.989203

Penalidade de incerteza:
  dim[0]: (1 - 0.10 × 0.15) = 0.9850
  dim[1]: (1 - 0.40 × 0.15) = 0.9400
  dim[2]: (1 - 0.50 × 0.15) = 0.9250
  dim[3]: (1 - 0.15 × 0.15) = 0.9775
  dim[4]: (1 - 0.60 × 0.15) = 0.9100
  dim[5]: (1 - 0.30 × 0.15) = 0.9550
  produto = 0.9850 × 0.9400 × 0.9250 × 0.9775 × 0.9100 × 0.9550 = 0.727558

Fit = 0.989203 × 0.727558 = 0.719702
```

**Interpretação comparativa:** A diferença entre os dois Fit Scores (0.9057 vs 0.7197) reflete não apenas o menor alinhamento vetorial do prospect 2, mas principalmente o efeito acumulado das incertezas elevadas — a penalidade do Exemplo 2 (0.7276) é 20% menor que a do Exemplo 1 (0.9062), contribuindo com um desconto adicional de 0.075 pontos no Fit.

---

## 4. C_SCORE — CONFIDENCE SCORE

### 4.1 Fórmula Multiplicativa Completa

```
C_score = RCS × C_s × (1 - Uncertainty_Committee) × Hypothesis_Confidence × prod_k(SRS_k)
```

O C_score é uma função **multiplicativa** de cinco fatores — cada fator em [0,1]. A escolha da multiplicação (em vez de soma ponderada) é deliberada: qualquer componente com valor próximo de zero colapsa o C_score, sinalizando que a confiança é fundamentalmente comprometida por aquela dimensão específica. Não existe compensação cruzada entre componentes.

**Semântica de cada fator:**

| Fator                     | O que mede                                               | Colapsa quando...                                  |
|---------------------------|----------------------------------------------------------|----------------------------------------------------|
| `RCS`                     | Certeza de que as fontes referem-se à mesma entidade     | Homônimos não resolvidos / CNPJ não encontrado     |
| `C_s`                     | Concentração do sinal em uma fonte dominante             | Fontes igualmente confiáveis → maxima entropia     |
| `1 - Uncertainty_Committee` | Completude do mapeamento do comite de compra           | Comite desconhecido / membros com alta incerteza   |
| `Hypothesis_Confidence`   | Força da hipótese dominante confirmada                   | Nenhuma hipótese ativa / hipótese fraca            |
| `prod_k(SRS_k)`           | Confiabilidade histórica cumulativa das fontes           | Fontes com histórico de erro / cold start          |

### 4.2 Uncertainty_Committee — Fórmula e Quatro Cenários

```
Uncertainty_Committee = min(u_bar_members + (1 - S_committee_Completeness) × 0.30, 1.0)

u_bar_members = media aritmética das incertezas individuais dos membros observados
S_committee_Completeness = papeis_observados / papeis_esperados_total
```

Os papéis esperados no buying committee padrão do ICP são três: Economic Buyer (fundadora), Operational Champion (gerente operacional), Influence Blocker (parceiro jurídico ou financeiro).

**Quatro cenários calculados:**

| Papéis Observados | S_committee_Completeness | u_bar_members | (1-Comp.)×0.30 | Uncertainty_Committee |
|-------------------|--------------------------|---------------|----------------|-----------------------|
| 0/3               | 0.0000                   | 0.50          | 0.3000         | min(0.8000, 1.0) = **0.8000** |
| 1/3               | 0.3333                   | 0.40          | 0.2000         | min(0.6000, 1.0) = **0.6000** |
| 2/3               | 0.6667                   | 0.25          | 0.1000         | min(0.3500, 1.0) = **0.3500** |
| 3/3               | 1.0000                   | 0.15          | 0.0000         | min(0.1500, 1.0) = **0.1500** |

**Interpretação:** Com comitê completamente não mapeado (0/3), `Uncertainty_Committee = 0.80`, portanto `(1 - 0.80) = 0.20`. Esse fator 0.20 é multiplicado no C_score, comprimindo qualquer outro valor positivo dos demais fatores para no máximo 20% de seu valor potencial. Com comitê totalmente mapeado e membros de alta certeza (3/3, u_bar=0.15), o fator é `(1 - 0.15) = 0.85`, indicando que mesmo com mapeamento completo sempre existe uma residual de incerteza de 15%.

### 4.3 Prova do Efeito Colapso — Três Cenários Numéricos

Os cenários abaixo demonstram como SRS baixos colapsam o C_score mesmo quando todos os outros fatores são favoráveis. Parâmetros base: RCS=0.90, C_s=0.85, Uncertainty_Committee=0.20 (comitê bem mapeado), Hypothesis_Confidence=0.80.

```
Parametros comuns:
  RCS                           = 0.90
  C_s                           = 0.85
  (1 - Uncertainty_Committee)   = 1 - 0.20 = 0.80
  Hypothesis_Confidence         = 0.80
  Produto base (sem SRS)        = 0.90 × 0.85 × 0.80 × 0.80 = 0.489600
```

**Cenário A — SRS único alto (k=1, SRS=0.85):**
```
C_score = 0.489600 × 0.85 = 0.416160
P_score (O=0.85) = 0.85 × (1 - 0.60 × e^(-4.0 × 0.416160))
                 = 0.85 × (1 - 0.60 × 0.188659)
                 = 0.85 × 0.886804 = 0.753783
→ Banda: PRIORITY ACTION
```

**Cenário B — SRS único baixo (k=1, SRS=0.30):**
```
C_score = 0.489600 × 0.30 = 0.146880
P_score (O=0.85) = 0.85 × (1 - 0.60 × e^(-4.0 × 0.146880))
                 = 0.85 × (1 - 0.60 × 0.556263)
                 = 0.85 × 0.666542 = 0.566561
→ Banda: MONITOR (caiu de PRIORITY ACTION para MONITOR)
→ Queda no P_score: 0.7538 → 0.5666 (reducao de 24.9%)
```

**Cenário C — SRS múltiplo, dois baixos (k=2, SRS=[0.30, 0.40]):**
```
prod_SRS = 0.30 × 0.40 = 0.120000
C_score = 0.489600 × 0.12 = 0.058752
P_score (O=0.85) = 0.85 × (1 - 0.60 × e^(-4.0 × 0.058752))
                 = 0.85 × (1 - 0.60 × 0.790123)
                 = 0.85 × 0.525926 = 0.447036
→ Banda: MONITOR (proximo ao limiar inferior — risco de cair em DELTA SEARCH)
→ Queda no P_score: 0.7538 → 0.4470 (reducao de 40.7%)
```

**Conclusão da prova:** Dois scrapers com SRS=0.30 e SRS=0.40 (ambos em early training, poucos ciclos de feedback) reduzem o P_score de um prospect de alta qualidade em 40.7%, potencialmente mantendo-o fora de PRIORITY ACTION indefinidamente até que o SRS_k convirja via `SRS_feedback_loop`. Isso demonstra que a qualidade das fontes não é preocupação secundária de infraestrutura — ela tem impacto direto e mensurável na priorização de prospects.

### 4.4 Hypothesis_Confidence

```
Hypothesis_Confidence = componente b da tripla omega da hipótese dominante ACTIVE

omega = (a, b, c)
  a = identificador da hipótese (H1..H15)
  b = posterior P(H|E) ∈ [0,1]
  c = threshold de confirmacao (tipicamente 0.70)

Hypothesis_Confidence = b da hipótese com maior b entre todas com status ACTIVE
```

**Caso sem hipótese ativa:** Se nenhuma hipótese tiver status `ACTIVE` (todas abaixo do threshold de confirmação), `Hypothesis_Confidence = 0.35` (valor de plausibilidade mínima — indica que o sistema sabe que existem hipóteses não resolvidas, mas não tem confirmação de nenhuma). Esse valor conservador evita que prospects sem hipótese confirmada recebam C_score inflado.

**Hipótese dominante:** Se múltiplas hipóteses estiverem `ACTIVE`, o sistema usa a hipótese com maior posterior `b`. A presença de múltiplas hipóteses confirmadas simultaneamente NÃO soma seus posteriors — cada prospect tem exatamente um `Hypothesis_Confidence` no ciclo corrente.

---

## 5. C_s VIA ENTROPIA DE SHANNON

### 5.1 Fórmulas Completas

```
H = -sum_i(p_i × log2(p_i))        (entropia de Shannon em bits)

H_max = log2(m)                     (entropia máxima para m fontes)

p_i = SQS_i / sum_j(SQS_j)         (probabilidade proporcional à qualidade da fonte)

C_s = 1 - H / H_max                (concentracao: 0 = max entropia; 1 = min entropia)

Convencao: quando m = 1, H = 0, H_max = 0 (indefinido), C_s = 1.0 por convencao.
```

**SQS_k (Source Quality Score):**
```
SQS_k = 0.35 × CRED_k + 0.25 × FRESH_k + 0.25 × COV_k + 0.15 × HACC_k

CRED_k   = credibilidade histórica da fonte (derivado de SRS_k)
FRESH_k  = atualidade das evidências da fonte (E_fresh medio ponderado)
COV_k    = cobertura de atributos ICP pela fonte (% de dimensoes com sinal)
HACC_k   = acuracia histórica de classificacao por hipótese
```

### 5.2 Quatro Cenários Calculados Numericamente

**Cenário 1: m=1, SQS=[0.80]**
```
m = 1, fonte única
p = [1.0]
H = -(1.0 × log2(1.0)) = -(1.0 × 0) = 0.000000
H_max = log2(1) = 0  →  convencao: C_s = 1.0 (fonte única = maxima concentracao)
C_s = 1.000000

Interpretacao: Todo o sinal vem de uma única fonte. Nao ha incerteza de qual
fonte acreditar. C_s = 1.0 contribui maximamente para o C_score.
```

**Cenário 2: m=2, SQS=[0.85, 0.10]**
```
m = 2, fontes: Instagram (SQS=0.85) e CNPJ (SQS=0.10)
total = 0.85 + 0.10 = 0.95

p[0] = 0.85 / 0.95 = 0.894737
p[1] = 0.10 / 0.95 = 0.105263

H = -(0.894737 × log2(0.894737)) - (0.105263 × log2(0.105263))
  = -(0.894737 × (-0.161645)) - (0.105263 × (-3.247927))
  =  0.144607 + 0.341854
  = 0.485461

H_max = log2(2) = 1.000000
C_s = 1 - 0.485461 / 1.000000 = 0.514539

Interpretacao: Fonte principal (Instagram) domina mas a fonte secundaria (CNPJ)
tem qualidade muito baixa. C_s = 0.51 indica concentracao moderada — ha um sinal
claro sobre qual fonte preferir, mas o sistema registra incerteza por ter duas
fontes com qualidades muito dispares.
```

**Cenário 3: m=2, SQS=[0.50, 0.50]**
```
m = 2, fontes com qualidade identica
p = [0.50, 0.50]

H = -(0.50 × log2(0.50)) - (0.50 × log2(0.50))
  = -(0.50 × (-1.0)) - (0.50 × (-1.0))
  = 0.500000 + 0.500000
  = 1.000000

H_max = log2(2) = 1.000000
C_s = 1 - 1.000000 / 1.000000 = 0.000000

Interpretacao: Entropia maxima para m=2. O sistema nao consegue determinar qual
fonte e mais confiavel — ambas tem a mesma qualidade. C_s = 0.0 colapsa o
C_score para zero independentemente dos outros fatores. Na pratica isso indica
um conflito de fontes irresolvido (ex.: Instagram declara 20 funcionarios,
CNPJ declara 3 — ambas as fontes com SQS identico).
```

**Cenário 4: m=3, SQS=[0.70, 0.20, 0.10]**
```
m = 3, fontes: Instagram (0.70), LinkedIn (0.20), CNPJ (0.10)
total = 0.70 + 0.20 + 0.10 = 1.00

p[0] = 0.70 / 1.00 = 0.700000
p[1] = 0.20 / 1.00 = 0.200000
p[2] = 0.10 / 1.00 = 0.100000

H = -(0.70 × log2(0.70)) - (0.20 × log2(0.20)) - (0.10 × log2(0.10))
  = -(0.70 × (-0.514573)) - (0.20 × (-2.321928)) - (0.10 × (-3.321928))
  = 0.360201 + 0.464386 + 0.332193
  = 1.156780

H_max = log2(3) = 1.584963
C_s = 1 - 1.156780 / 1.584963 = 1 - 0.729847 = 0.270153

Interpretacao: Tres fontes com qualidades decrescentes. Instagram domina (70%
do peso de qualidade) mas a distribuicao ainda e suficientemente espalhada para
resultar em C_s = 0.27 — baixo. O sistema sugere investigacao adicional para
elevar a qualidade das fontes secundarias ou consolidar o sinal na fonte principal.
```

---

## 6. RCS VIA JARO-WINKLER

### 6.1 Normalização de Strings

Antes de calcular o Jaro-Winkler, ambas as strings (nome da empresa encontrado na fonte vs. nome canônico no sistema) passam por normalização:

```python
import unicodedata
import re

def normalize_entity_name(s: str) -> str:
    # 1. Minusculas e strip
    s = s.lower().strip()
    # 2. Remocao de diacriticos (NFD decomposition + remocao de Mn)
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    # 3. Remocao de sufixos juridicos
    s = re.sub(
        r'\b(ltda|me|eireli|sa|s\.a\.|epp|mei|ss|sociedade simples|'
        r'sociedade anonima|s\/a|microempresa)\b',
        '', s
    )
    # 4. Remocao de pontuacao (exceto espacos)
    s = re.sub(r'[^a-z0-9\s]', '', s)
    # 5. Colapso de espacos multiplos
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# Exemplo:
# "Ferreira & Associados Advocacia Ltda." -> "ferreira associados advocacia"
# "FERREIRA Associados ADVOCACIA"          -> "ferreira associados advocacia"
```

### 6.2 Fórmula RCS com Tabelas de Modificadores

```
RCS = JaroWinkler(normalize(s1), normalize(s2)) × lambda_spatial × lambda_CNAE
```

**Tabela lambda_spatial — Proximidade Geográfica:**

| Relação Geográfica              | lambda_spatial | Lógica                                                     |
|---------------------------------|----------------|------------------------------------------------------------|
| Mesma cidade (município IBGE)   | 1.00           | Presença local confirma match                              |
| Mesmo estado (UF)               | 0.85           | Mesma UF reduz mas não elimina ambiguidade                 |
| Regiões geográficas distintas   | 0.70           | Risco de homônimo regional — penalidade moderada           |
| Localização não determinada (ND)| 0.70           | Ausência de dado geográfico tratada como caso conservador  |

**Tabela lambda_CNAE — Similaridade Setorial:**

| Nível de Coincidência CNAE            | lambda_CNAE | Critério                                          |
|---------------------------------------|-------------|---------------------------------------------------|
| CNAE idêntico (4 dígitos)             | 1.00        | Subclasse idêntica — forte confirmação de match   |
| Mesma divisão (2 dígitos)             | 0.85        | Mesmo setor amplo — match provável                |
| Mesma seção (letra identificadora)    | 0.70        | Mesma macro-seção econômica — match possível      |
| CNAEs incompatíveis (seções distintas)| 0.50        | Setores diferentes — forte indício de entidade distinta |
| CNPJ não disponível (ND)              | 1.00        | Sem penalidade por ausência — dado não coletável  |

### 6.3 Thresholds de Fusão — Quatro Categorias

| Faixa RCS        | Categoria               | Ação do Sistema                                                     |
|------------------|-------------------------|---------------------------------------------------------------------|
| RCS >= 0.90      | AUTO_MERGE (modo degradado) | Fusão automática sem revisão humana, flag `degraded_merge=true` |
| 0.82 <= RCS < 0.90 | AUTO_MERGE            | Fusão automática; entidade secundária marcada como `alias`          |
| 0.65 <= RCS < 0.82 | MANUAL_REVIEW         | Enfileirado para revisão do operador; score pausado até decisão     |
| RCS < 0.65       | DISTINCT                | Tratadas como entidades distintas; ambas mantidas no pipeline       |

**Nota sobre o threshold 0.90 em modo degradado:** Quando o sistema opera em `DEGRADED_INSTAGRAM` e o scraping retorna apenas nome parcial sem CNPJ, o threshold de AUTO_MERGE sobe de 0.82 para 0.90 para compensar a ausência dos modificadores lambda_CNAE e lambda_spatial (que ficam em seus valores de fallback). Isso reduz o risco de fusão incorreta quando os dados são incompletos.

### 6.4 Dois Exemplos Numéricos de RCS

**Exemplo 1: Mesmo escritório, grafia alternativa**

```
s1 = "Ferreira & Associados Advocacia Ltda"
s2 = "Ferreira e Associados Advocacia"

Após normalização:
  n1 = "ferreira associados advocacia"
  n2 = "ferreira e associados advocacia"

Jaro(n1, n2):
  len(n1) = 29, len(n2) = 32
  match_distance = max(29,32)//2 - 1 = 15
  matches = 29 (todas as letras de n1 encontram match em n2)
  transposições ≈ 0
  Jaro ≈ (29/29 + 29/32 + 29/29) / 3 ≈ 0.927

JaroWinkler(n1, n2):
  prefixo comum = "ferr" → prefix_length = 4 (cap)
  JW = 0.927 + 4 × 0.1 × (1 - 0.927) = 0.927 + 0.0292 = 0.952614

lambda_spatial = 1.00  (mesma cidade — Sao Paulo/SP identificado por CNPJ)
lambda_CNAE    = 1.00  (CNAE 6911-7/01 identico em ambos os registros)

RCS = 0.952614 × 1.00 × 1.00 = 0.952614
→ Categoria: AUTO_MERGE (RCS >= 0.82)
```

**Exemplo 2: Empresas distintas, mesmo setor**

```
s1 = "Lemos Consultoria Empresarial"
s2 = "Lima Consultoria Estrategica"

Após normalização:
  n1 = "lemos consultoria empresarial"
  n2 = "lima consultoria estrategica"

JaroWinkler(n1, n2) = 0.767846
  (strings compartilham "l" e "consultoria" mas divergem em
   "lemos"/"lima" e "empresarial"/"estrategica")

lambda_spatial = 0.85  (mesmo estado — RS, cidades distintas)
lambda_CNAE    = 0.85  (CNAE divisao 70 — mesma divisao, subclasses diferentes)

RCS = 0.767846 × 0.85 × 0.85 = 0.767846 × 0.7225 = 0.554769
→ Categoria: DISTINCT (RCS < 0.65)
→ Ambas as empresas mantidas como entidades separadas no pipeline.
```

---

## 7. FRESHNESS DECAY EXPONENCIAL

### 7.1 Fórmula e Propriedades Matemáticas

```
E_fresh(delta_t) = e^(-ln(2) × delta_t / t_half)

ln(2) = 0.693147

delta_t  = tempo decorrido desde a coleta da evidência (em dias)
t_half   = meia-vida do tipo de sinal (em dias)
```

**Propriedades verificáveis:**

| Propriedade                        | Verificação                                                    |
|------------------------------------|----------------------------------------------------------------|
| E_fresh(0) = 1.0                   | e^(-0.693147 × 0 / t_half) = e^0 = 1.0 verificado            |
| E_fresh(t_half) = 0.5              | e^(-0.693147 × t_half / t_half) = e^(-0.693147) = 0.5000 verificado |
| E_fresh(2 × t_half) = 0.25         | e^(-0.693147 × 2) = 0.2500 verificado                         |
| E_fresh estritamente decrescente   | dE/d(delta_t) = -(ln2/t_half) × e^(-ln2 × delta_t / t_half) < 0 para todo delta_t >= 0 |
| E_fresh pertence a (0, 1]          | Limite: delta_t → inf → E_fresh → 0+; nunca atinge zero       |

### 7.2 Tabela Exaustiva — Nove Tipos de Sinal

Todos os valores calculados com a fórmula `e^(-0.693147 × delta_t / t_half)`:

| Tipo de Sinal                 | t_half  | E_fresh(7d) | E_fresh(14d) | E_fresh(30d) | E_fresh(60d) |
|-------------------------------|---------|-------------|--------------|--------------|--------------|
| `comment_on_anchor`           |  7 dias | 0.5000      | 0.2500       | 0.0513       | 0.0026       |
| `post_caption_instagram`      | 14 dias | 0.7071      | 0.5000       | 0.2264       | 0.0513       |
| `post_linkedin`               | 21 dias | 0.7937      | 0.6300       | 0.3715       | 0.1380       |
| `job_posting_active`          | 30 dias | 0.8507      | 0.7236       | 0.5000       | 0.2500       |
| `mutual_follower_anchor`      | 45 dias | 0.8978      | 0.8060       | 0.6300       | 0.3969       |
| `cargo_title_linkedin`        | 90 dias | 0.9475      | 0.8978       | 0.7937       | 0.6300       |
| `bio_instagram`               | 90 dias | 0.9475      | 0.8978       | 0.7937       | 0.6300       |
| `company_size_declared`       |120 dias | 0.9604      | 0.9223       | 0.8409       | 0.7071       |
| `cnpj_cadastral_data`         |180 dias | 0.9734      | 0.9475       | 0.8909       | 0.7937       |

**Leitura da tabela:** Um `comment_on_anchor` coletado há 30 dias retém apenas 5.13% de seu valor original de frescor — para efeitos práticos, deve ser recapturado. Um registro `cnpj_cadastral_data` coletado há 60 dias ainda retém 79.37% do valor, justificando cache de 6 meses conforme DDL.

### 7.3 Modo Degradado Instagram — t_half = 12 horas

Quando o sistema detecta que o Instagram scraper está retornando dados inconsistentes (HTTP 429/403 frequentes, taxa de erro > 30%), entra em `DEGRADED_INSTAGRAM`. Nesse modo, todas as evidências coletadas via Instagram recebem t_half = 12h = 0.5 dias:

```
E_fresh(24h) = e^(-ln(2) × 1.0 / 0.5)
             = e^(-0.693147 × 2)
             = e^(-1.386294)
             = 0.250000
```

Em 24 horas, o sinal Instagram em modo degradado já perdeu 75% do seu valor. Isso garante que o sistema force recoleta assim que possível e não tome decisões de priorização baseadas em dados Instagram potencialmente corrompidos. O flag `operating_mode = 'DEGRADED_INSTAGRAM'` é registrado no `LeadState` e propagado para o XAI Payload de todos os prospects afetados no ciclo.

### 7.4 Source Quality Model — Dimensões, Fórmulas e Cold Starts

**SQS_k (Source Quality Score) — dimensões detalhadas:**

```
SQS_k = 0.35 × CRED_k + 0.25 × FRESH_k + 0.25 × COV_k + 0.15 × HACC_k
```

| Dimensão   | Peso | Definição                                               | Cálculo                                        | Cold Start |
|------------|------|---------------------------------------------------------|------------------------------------------------|------------|
| `CRED_k`   | 0.35 | Credibilidade histórica da fonte (derivada de SRS_k)    | CRED_k = SRS_k quando n_k >= 20; cold=0.50    | 0.50       |
| `FRESH_k`  | 0.25 | Atualidade média das evidências coletadas pela fonte    | Media ponderada de E_fresh sobre evidências ativas | E_fresh(t_source_half) |
| `COV_k`    | 0.25 | Cobertura: % de dimensões do ICP_vec observáveis pela fonte | dim_observadas_k / 6                       | 0.40       |
| `HACC_k`   | 0.15 | Acurácia histórica de hipóteses confirmadas via fonte   | H_correct_k / H_total_k (min 5 amostras)       | 0.50       |

**SRS_k (Source Reliability Score):**

```
SRS_k = (TP + TN) / (TP + TN + FP + FN) × (1 - e^(-0.05 × n_k))

Cold start: SRS_k = 0.50 quando n_k = 0
Ajuste pratico: SRS_k = max(0.50, formula) quando n_k < 15
```

**Tabela de convergência do SRS_k:**

| n_k (ciclos de feedback) | SRS_k (accuracy=0.80) | SRS_k (accuracy=0.60) |
|--------------------------|----------------------|-----------------------|
| 0   (cold start)         | 0.500000             | 0.500000              |
| 5                        | 0.176959 → ajust. 0.500 | 0.132719 → ajust. 0.500 |
| 10                       | 0.314775 → ajust. 0.500 | 0.236081 → ajust. 0.500 |
| 15                       | 0.422521             | 0.316891              |
| 20                       | 0.505696             | 0.379272              |
| 50                       | 0.734332             | 0.550749              |
| 100                      | 0.794610             | 0.595958              |
| 200                      | 0.799964             | 0.599973              |

**Nota sobre cold start n_k < 15:** A formula bruta cai abaixo de 0.50 nos primeiros ciclos porque `(1 - e^(-0.05×n_k))` cresce devagar para n pequeno. O ajuste `max(0.50, formula)` mantém o SRS no valor de cold start declarado até que a formula o supere organicamente em torno de n_k=15 (accuracy=0.80) ou n_k=20 (accuracy=0.60).

**t_half das fontes (para cálculo de FRESH_k):**

| Fonte                | t_half (frescor do dado coletado) |
|----------------------|-----------------------------------|
| `instagram_scraper`  |  3 dias                           |
| `linkedin_scraper`   |  7 dias                           |
| `cnpj_resolver`      | 30 dias                           |

### 7.5 Tabela de Atualização das Dimensões

| Dimensão do Score      | Trigger de Atualização                              | Frequência Máxima | Destino no BD (schema SDD-06)               |
|------------------------|-----------------------------------------------------|-------------------|---------------------------------------------|
| E_fresh por evidência  | Leitura de `collected_at` vs `NOW()`                | A cada query      | Campo `e_fresh` em `observed_evidence`      |
| SRS_k                  | Feedback loop via CRM webhook (EV-18)              | A cada ciclo      | Tabela `source_reliability` (campos `true_positives`, `false_positives`, `srs_current`) |
| SQS_k                  | Recálculo após atualização de SRS_k ou nova evidência| Diariamente      | Calculado em memória no MVP; V1: campo `historical_accuracy_weighted` em `source_reliability` |
| C_s                    | Recalculado a cada novo SQS_k                       | A cada ciclo      | Campo `feat_c_s_shannon` em `analytical_feature_store` |
| O_score                | Nova evidência coletada que afeta Fit, Intent ou Reach | Por coleta     | Campo `o_score` em `analytical_feature_store` |
| C_score                | Mudança em qualquer componente (RCS, C_s, SRS, Hyp) | Por coleta       | Campo `c_score` em `analytical_feature_store` |
| P_score                | Mudança em O_score ou C_score                       | Por coleta        | Campo `p_score` em `analytical_feature_store` |
| Ranking final          | Mudança em P_score de qualquer prospect no ciclo    | Fim de ciclo      | Campo `rank_position` em `analytical_feature_store`; view `v_cognitive_observability` |

---

## 8. PROPRIEDADES FORMAIS

### 8.1 Domínios — Prova de que Todos os Scores pertencem a [0,1]

**O_score pertence a [0,1]:**
```
Dados:
  Fit pertence a [0,1]          (cosseno normalizado × produto de penalidades em [0,1])
  S_intent pertence a [0,1]     (media ponderada de sub-sinais normalizados em [0,1])
  Reachability pertence a [0,1] (tabela discreta com valores em {0.40, 0.70, 0.85, 1.00})
  E_fresh pertence a (0,1]      (propriedade da função exponencial com argumento negativo)

Soma convexa: 0.45 × Fit + 0.35 × S_intent + 0.20 × Reachability
  Minimo: 0.45×0 + 0.35×0 + 0.20×0 = 0.0
  Maximo: 0.45×1 + 0.35×1 + 0.20×1 = 1.0

O_score = (soma convexa) × E_fresh pertence a [0,1] × (0,1] = [0,1]   QED
```

**C_score pertence a [0,1]:**
```
RCS = JW(·) × lambda_spatial × lambda_CNAE
  JW pertence a [0,1]       (propriedade da distância Jaro-Winkler)
  lambda_spatial pertence a {0.70, 0.85, 1.00} ⊂ [0,1]
  lambda_CNAE pertence a {0.50, 0.70, 0.85, 1.00} ⊂ [0,1]
  → RCS pertence a [0,1]

C_s pertence a [0,1]:
  H pertence a [0, H_max] → H/H_max pertence a [0,1]
  → C_s = 1 - H/H_max pertence a [0,1]

(1 - Uncertainty_Committee) pertence a [0,1]:
  Uncertainty_Committee = min(·, 1.0) pertence a [0,1]
  → (1 - Uncertainty_Committee) pertence a [0,1]

Hypothesis_Confidence pertence a [0,1]:
  posterior bayesiano, por definicao pertence a [0,1]

SRS_k pertence a [0,1]:
  (TP+TN)/(TP+TN+FP+FN) pertence a [0,1]   (acuracia <= 1)
  (1 - e^(-0.05×n_k)) pertence a [0,1)      (crescente de 0 a 1)
  → SRS_k pertence a [0,1)
  → prod_k(SRS_k) pertence a [0,1)

C_score = produto de 5 fatores em [0,1] → C_score pertence a [0,1]   QED
```

**P_score pertence a [0,1]:**
```
Dado O pertence a [0,1] e C pertence a [0,1], com alpha=0.60 e beta=4.0:

  e^(-beta × C) pertence a (e^(-beta), 1] para C pertence a [0,1]
  e^(-4.0 × 0) = 1.000000
  e^(-4.0 × 1) = 0.018316

  alpha × e^(-beta × C) pertence a (alpha × e^(-beta), alpha]
                        = (0.010990, 0.60]

  1 - alpha × e^(-beta × C) pertence a [1-0.60, 1-0.010990)
                             = [0.40, 0.989011)
                             ⊂ [0,1]

  P_score = O × (1 - alpha × e^(-beta × C))
  Limite inferior: O=0 → P_score = 0 para todo C
  Limite superior: O=1, C=1 → P_score = 0.989011 < 1.0

  P_score pertence a [0, 0.989011) ⊂ [0,1]   QED
```

### 8.2 Monotonicidade — P_score Cresce Monotonicamente com C_score

```
Teorema: Para O fixo e positivo (O > 0), P_score e estritamente crescente em C.

Prova:
  P(O, C) = O × (1 - alpha × e^(-beta × C))

  dP/dC = O × d/dC [1 - alpha × e^(-beta × C)]
        = O × alpha × beta × e^(-beta × C)
        = O × 0.60 × 4.0 × e^(-4C)
        = 2.4 × O × e^(-4C)

  Como O > 0, alpha > 0, beta > 0, e^(-4C) > 0 para todo C real finito:
    dP/dC = 2.4 × O × e^(-4C) > 0

  P_score e estritamente crescente em C para O > 0   QED

Prova de concavidade (retorno marginal decrescente):
  d²P/dC² = -O × alpha × beta² × e^(-beta × C)
           = -O × 0.60 × 16.0 × e^(-4C)
           = -9.6 × O × e^(-4C)
           < 0 para O > 0

  O benefício marginal de aumentar C diminui conforme C cresce.
  O maior ganho de P_score por unidade de esforco de coleta ocorre
  na transicao de C=0 para C=0.30 (onde dP/dC e maximo).

Valores de dP/dC para O=1.0:
  C=0.00:  dP/dC = 2.4 × e^0    = 2.400000  (maxima taxa de crescimento)
  C=0.10:  dP/dC = 2.4 × e^-0.4 = 1.608768
  C=0.30:  dP/dC = 2.4 × e^-1.2 = 0.722867
  C=0.50:  dP/dC = 2.4 × e^-2.0 = 0.324813
  C=0.70:  dP/dC = 2.4 × e^-2.8 = 0.145944
  C=1.00:  dP/dC = 2.4 × e^-4.0 = 0.043958  (taxa minima no dominio [0,1])
```

### 8.3 Reprodutibilidade — Auditabilidade Total a Partir de (O, C, α, β)

O sistema garante reprodutibilidade completa do P_score final a partir de um conjunto mínimo de parâmetros armazenados em banco de dados.

**Contrato de auditabilidade:** Dado o par `(entity_id, cycle_id)`, é possível reconstruir deterministicamente o P_score publicado a partir dos seguintes campos da tabela `analytical_feature_store` (schema SDD-06):

```
P_score reconstruido = O_score × (1 - alpha_rank × e^(-beta_rank × C_score))

Campos auditaveis no BD (tabela analytical_feature_store):
  o_score          → O_score do ciclo
  c_score          → C_score do ciclo
  p_score          → valor publicado (deve igualar a reconstrução)
  alpha_used       → alpha (0.60 — copiado de icp_contract.alpha_rank)
  beta_used        → beta  (4.0  — copiado de icp_contract.beta_rank)
```

**Decomposição auditável do O_score:**
```
O_score = (0.45 × Fit + 0.35 × S_intent + 0.20 × Reachability) × E_fresh

Campos auditaveis (tabela analytical_feature_store):
  feat_fit               → Fit
  feat_s_intent          → S_intent
  feat_reachability_hybrid → Reachability
  feat_e_fresh           → E_fresh médio ponderado
```

**Decomposição auditável do C_score:**
```
C_score = RCS × C_s × (1 - Uncertainty_Committee) × Hypothesis_Confidence × ∏SRS_k

Campos auditaveis:
  entity_nodes.rcs_score                → RCS (tabela entity_nodes, campo rcs_score)
  analytical_feature_store.feat_c_s_shannon       → C_s (entropia de Shannon normalizada)
  analytical_feature_store.feat_uncertainty_committee → Uncertainty_Committee
  analytical_feature_store.feat_hypothesis_confidence → Hypothesis_Confidence
  analytical_feature_store.feat_srs_product           → ∏SRS_k (produto pré-calculado)
  source_reliability.srs_current                      → SRS_k individual por fonte
```

**XAI Payload:** O documento `sdd_12_xai_and_pruning_json_contracts.md` define o contrato JSON completo do XAI Payload, que inclui a chain causal de cada evidência → hipótese → componente de score → P_score final. Toda mutação de score é registrada no LeadState (ver SDD-07 para definição canônica do TypedDict) com timestamp, nó do grafo de origem e delta aplicado, garantindo rastreabilidade fim-a-fim sem dependência de memória ou reprocessamento.

---

*Fim do SDD-02 — Versão 1.0-MVP*
*Documento gerado em: 2026-06-01*
*Próxima revisão: após ciclo piloto de coleta (30 dias de operação)*
