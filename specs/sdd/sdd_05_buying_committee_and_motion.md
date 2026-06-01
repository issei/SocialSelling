# SDD-05 — Buying Committee & Buying Motion

**Projeto:** SocialSelling — Intelligence Data System  
**Versão:** 1.0.0  
**Data:** 2026-06-01  
**Escopo:** Motor de scoring de comitê de compra, diferenciação SC vs BMO, e detecção de trigger events.

---

## Índice

1. [Persona Scoring Vector (S_persona)](#1-persona-scoring-vector-s_persona)
2. [Métricas Estatísticas do Comitê](#2-métricas-estatísticas-do-comitê)
3. [Motor de Diferenciação Cognitiva SC vs BMO](#3-motor-de-diferenciação-cognitiva-sc-vs-bmo)

---

## 1. Persona Scoring Vector (S_persona)

### 1.1 Definição Tridimensional Formal

O `S_persona` é um vetor tridimensional que quantifica a relevância de um indivíduo dentro do comitê de compra de um prospect. Cada dimensão captura um aspecto ortogonal da capacidade de influência e sinalização de dor desse indivíduo.

```
S_persona = (seniority_score, role_alignment_score, engagement_frequency)
```

**Score combinado ponderado (member_score):**

```
member_score = 0.40 × seniority_score
             + 0.35 × role_alignment_score
             + 0.25 × engagement_frequency
```

**Justificativa dos pesos:**

| Dimensão | Peso | Razão |
|---|---|---|
| `seniority_score` | 0.40 | Cargo define poder de decisão formal e orçamentário — dimensão de maior impacto para qualificação |
| `role_alignment_score` | 0.35 | Alinhamento funcional com os papéis esperados do ICP é o segundo sinal mais forte de relevância |
| `engagement_frequency` | 0.25 | Sinal de momentum comportamental relevante, mas volátil — peso menor para evitar falsos positivos |

O `member_score` é um escalar no intervalo `[0.0, 1.0]`. Não substitui o vetor original: o vetor completo `S_persona` é preservado na tabela `committee_members` para análise granular.

---

### 1.2 Seniority Level — Escala Discreta

O `seniority_score` é derivado do mapeamento do título declarado do indivíduo para um nível hierárquico discreto. O matching é feito por keyword lookup contra o título declarado (`role_declared`) e o título inferido (`role_inferred`).

**Tabela de mapeamento título → seniority_score:**

| Nível | Títulos Mapeados | seniority_score |
|---|---|---|
| C-Level / Fundador | CEO, COO, CTO, CFO, Founder, Sócia, Sócio, Sócia-Fundadora, Co-founder, Proprietária | **1.00** |
| Vice-President / Partner | VP, Vice-President, Vice-Presidente, Partner, Parceiro | **0.90** |
| Director | Director, Diretora, Diretor, Managing Director | **0.80** |
| Head / Senior Manager | Head of, Head de, Gerente Sênior, Senior Manager | **0.70** |
| Manager / Gerente | Manager, Gerente, Gerente de, Gestora | **0.60** |
| Supervisor / Coordinator | Supervisor, Supervisora, Coordinator, Coordenador, Coordenadora | **0.45** |
| Specialist / Senior Analyst | Specialist, Especialista, Analista Sênior, Senior Analyst, Consultor Sênior | **0.30** |
| Analyst / Assistant | Analyst, Analista, Assistente, Assistant | **0.20** |
| Trainee / Intern | Trainee, Estagiário, Estagiária, Intern | **0.05** |

**Tratamento de cargos ambíguos:**

1. **Primeira tentativa:** matching por keyword contra lista acima (case-insensitive, tokenização por espaço/hífen).
2. **Segunda tentativa:** se o título contiver múltiplas keywords de níveis diferentes (ex.: "Analista e Coordenadora"), priorizar o nível mais alto encontrado.
3. **Fallback:** se nenhuma keyword corresponder, atribuir `seniority_score = 0.30` (representa incerteza média — assume-se nível de especialista sem evidência).
4. **Flag de qualidade:** quando o fallback é acionado, registrar `data_quality_flag = 'LOW'` no nó correspondente em `entity_nodes`.

---

### 1.3 Role Alignment Score

O `role_alignment_score` mede a proximidade semântica entre o título declarado do indivíduo e os papéis funcionais esperados para o segmento do ICP. É calculado via **similaridade cosseno** entre embeddings semânticos.

**Formulação:**

```
role_alignment_score = cosine_similarity(
    embed(role_declared),
    embed(expected_role_for_segment)
)
```

Onde `embed(·)` representa a função de embedding do vocabulário de cargos.

**Implementação no MVP:**

- Utilizar **TF-IDF pré-computado** ou **word2vec** sobre corpus de títulos profissionais brasileiros e ingleses.
- Nenhuma chamada a LLM em tempo real no MVP — os vetores de papéis esperados são pré-computados e armazenados no campo `keyword_taxonomy` do `icp_contract` ativo.
- O resultado é um escalar no intervalo `[0.0, 1.0]`.

**Tabela de exemplos por segmento:**

| Segmento | Título Declarado | Papel Esperado ICP | role_alignment_score (exemplo) |
|---|---|---|---|
| Advocacia | "Sócia-Fundadora" | Economic Buyer | **0.92** |
| Advocacia | "Coordenadora Administrativa" | Operational Champion | **0.88** |
| Advocacia | "Advogado Associado" | *(nenhum papel esperado)* | **0.25** |
| Consultoria | "Sócio-Diretor" | Economic Buyer | **0.91** |
| Consultoria | "Coordenador de Projetos" | Delivery Champion | **0.85** |
| Software House | "CEO / Founder" | Economic Buyer | **0.95** |
| Software House | "CTO" | Product Champion | **0.87** |
| Software House | "Product Manager" | Product Champion | **0.83** |
| Engenharia | "Gerente de Projetos" | Operations Champion | **0.84** |
| Engenharia | "Assistente Financeiro" | *(nenhum papel esperado)* | **0.18** |

**Nota de implementação:** Títulos sem correspondência semântica próxima (similaridade cosseno < 0.30) são tratados como membros de comitê irrelevantes para o segmento — não são descartados, mas recebem baixo peso no `role_probability`.

---

### 1.4 Engagement Frequency

O `engagement_frequency` mede a frequência com que o indivíduo publica conteúdo relacionado às dores do ICP nas últimas **4 semanas corridas** a partir da data de coleta.

**Formulação:**

```
engagement_frequency = min(n_posts_dor / 5, 1.0)
```

- `n_posts_dor`: contagem de posts classificados como relacionados à dor do ICP nas últimas 4 semanas.
- Divisor 5: saturação — 5 ou mais posts equivalem à frequência máxima (1.0).
- Resultado truncado no intervalo `[0.0, 1.0]`.

**Classificação de posts — Dicionário de Dor:**

A classificação de um post como "relacionado à dor ICP" é feita via **keyword matching** contra o campo `keyword_taxonomy.pain_keywords[]` do `icp_contract` ativo.

Exemplos de categorias de dor por segmento:

| Segmento | Exemplos de pain_keywords |
|---|---|
| Advocacia | "gestão de equipe", "processos internos", "burnout", "clientes difíceis", "crescimento do escritório" |
| Consultoria | "escalabilidade", "entrega de projetos", "gestão de clientes", "margens", "time sobrecarregado" |
| Software House | "produto", "roadmap", "retenção", "churn", "processo de desenvolvimento", "dívida técnica" |
| Engenharia | "prazo de obra", "gestão de subcontratados", "orçamento", "compliance", "ERP" |

**Janela de tempo:** A janela de 4 semanas é recalculada a cada `cycle_id`. Posts mais antigos que 28 dias não contam, mesmo que ainda estejam disponíveis na fonte.

---

### 1.5 Score Final do Membro

**Fórmula:**

```
member_score = 0.40 × seniority_score
             + 0.35 × role_alignment_score
             + 0.25 × engagement_frequency
```

**Justificativa dos pesos:** O `seniority_score` recebe o maior peso porque cargo define poder de decisão formal — independente de quanto a pessoa posta ou de quanto seu título se alinha ao papel esperado, um CEO com pouco engajamento ainda é mais relevante para a qualificação do que um analista muito ativo. O `role_alignment_score` vem em segundo porque valida se a pessoa está no papel funcional certo. O `engagement_frequency` tem peso menor para evitar que indivíduos muito ativos em redes sociais inflem artificialmente o score de membros de baixo poder decisório.

**Exemplos numéricos:**

| Cenário | seniority | role_align | engag_freq | member_score |
|---|---|---|---|---|
| CEO altamente ativo | 1.00 | 0.95 | 1.00 | `0.40×1.00 + 0.35×0.95 + 0.25×1.00` = **0.983** |
| Coordenadora moderada | 0.45 | 0.88 | 0.60 | `0.40×0.45 + 0.35×0.88 + 0.25×0.60` = **0.638** |
| Analista irrelevante | 0.20 | 0.25 | 0.20 | `0.40×0.20 + 0.35×0.25 + 0.25×0.20` = **0.216** |
| Gerente inativo | 0.60 | 0.84 | 0.00 | `0.40×0.60 + 0.35×0.84 + 0.25×0.00` = **0.534** |

**Armazenamento:** O `member_score` é persistido em `committee_members.member_score`. O vetor completo (`seniority_score`, `role_alignment_score`, `engagement_frequency`) é preservado nos campos individuais para auditoria e recálculo futuro sem necessidade de reprocessar evidências brutas.

---

## 2. Métricas Estatísticas do Comitê

### 2.1 Committee Completeness

O `CommitteeCompleteness` (referenciado como `S_committee_Completeness`) mede a proporção de papéis funcionais esperados para o segmento que foram identificados no comitê do prospect.

**Formulação:**

```
S_committee_Completeness = |roles_identified| / |roles_expected_for_segment|
```

- `roles_identified`: conjunto de papéis distintos para os quais há ao menos um membro com `role_probability > 0.50`.
- `roles_expected_for_segment`: conjunto de papéis definidos no `icp_contract` para o segmento do prospect (sempre 3 no modelo atual).

**Tratamento de múltiplos membros para o mesmo papel:**

Quando há mais de um membro mapeado para o mesmo papel esperado (ex.: duas pessoas candidatas a "Economic Buyer"), apenas o membro com maior `role_probability` é considerado para o numerador de `|roles_identified|`. Os demais são mantidos na tabela `committee_members` com seu papel e probabilidade para fins de auditoria e eventual reconsideração.

**Papéis esperados por segmento:**

| Segmento | Papel 1 (Economic Buyer) | Papel 2 (Champion) | Papel 3 (Gatekeeper) |
|---|---|---|---|
| Advocacia Corporativa | Sócia-Fundadora | Coordenadora/Gerente Administrativa (Operational Champion) | Tech/Compliance Gatekeeper |
| Consultoria | Sócio-Diretor | Coordenador de Projetos (Delivery Champion) | Commercial Gatekeeper |
| Software House / SaaS | CEO / Founder | CTO / Product Manager (Product Champion) | Engineering Lead |
| Engenharia | Fundador / Diretor | Gerente de Projetos (Operations Champion) | Technical Lead |

**Como identificar cada papel via evidências:**

| Papel | Evidências Primárias | Evidências Secundárias |
|---|---|---|
| Economic Buyer | Cargo com "Sócia", "CEO", "Fundadora", "Diretora" + vínculo direto à empresa (CNPJ ou LinkedIn) | Menção em bio de Instagram como proprietária ou fundadora |
| Operational / Delivery Champion | Cargo com "Coordenadora", "Gerente", "Head de Operações" vinculado à empresa | Posts sobre gestão de equipe, processos, entregas, cronogramas |
| Tech / Product / Engineering Champion | Cargo com "CTO", "Product Manager", "Gerente de TI", "Engineering Lead" | Posts técnicos, comentários em repositórios, fóruns tech, eventos de produto |
| Gatekeeper / Compliance | Cargo com "Compliance", "Jurídico", "Financeiro", "Controller", "CFO" | Posts sobre regulamentação, auditoria, controle orçamentário |

**Impacto no C_score:**

`S_committee_Completeness < 1.0` aumenta o `Uncertainty_Committee`, que degrada diretamente o `C_score`. A relação é: cada papel não identificado adiciona penalidade estrutural de incerteza de `(1 - S_committee_Completeness) × 0.30`. Em termos práticos: um comitê incompleto sinaliza que o sistema não tem informação suficiente sobre quem decide — o ranking do prospect deve refletir essa limitação epistêmica sem penalizar o `O_score` (que representa o valor do lead, independente do conhecimento do comitê).

---

### 2.2 Committee Confidence

O `CommitteeConfidence` é a medida de confiança epistemológica sobre a composição identificada do comitê.

**Formulação:**

```
CommitteeConfidence = 1 - ū_committee
```

Onde `ū_committee` é a média ponderada das incertezas individuais dos membros identificados:

```
ū_committee = Σ(u_i × role_probability_i) / Σ(role_probability_i)
```

- `u_i`: componente de incerteza do triplet de Lógica Subjetiva do membro `i` em `committee_members` (campo `uncertainty`).
- `role_probability_i`: probabilidade de que o membro `i` ocupa o papel inferido (campo `role_probability` em `committee_members`).
- A ponderação por `role_probability` garante que membros com baixa confiança de papel contribuam menos para a média do que membros com alta certeza de papel.

**Interpretação:**

| CommitteeConfidence | Interpretação Operacional |
|---|---|
| ≥ 0.80 | Comitê bem identificado — alta confiança nas personas encontradas; abordagem autorizada |
| 0.60 – 0.79 | Comitê razoavelmente identificado — alguma incerteza nos membros; prosseguir com cautela |
| 0.40 – 0.59 | Comitê parcialmente identificado — inferências frágeis; coletar mais evidências antes de agir |
| < 0.40 | Comitê com alta incerteza — não confiar no BMO/SC identificado; bloquear abordagem |

---

### 2.3 Committee Uncertainty Score (ū_committee)

O `Uncertainty_Committee` é a medida de incerteza total do comitê que alimenta o cálculo do `C_score`. Combina dois efeitos ortogonais:

**Formulação:**

```
Uncertainty_Committee = min(ū_members + (1 - S_committee_Completeness) × 0.30, 1.0)
```

**Decomposição dos dois efeitos:**

**(a) Incerteza sobre membros identificados** (`ū_members`):
Captura a qualidade epistêmica das evidências sobre as pessoas já encontradas. Um membro identificado apenas por bio de Instagram com nomenclatura ambígua terá alta incerteza individual (`u_i` alto), elevando `ū_members`. Este efeito mede: "quão confiantes estamos sobre quem já encontramos?"

**(b) Incerteza estrutural de papéis não mapeados** (`(1 - S_committee_Completeness) × 0.30`):
Captura o risco de que papéis ainda não descobertos sejam decisivos para a compra. O coeficiente `0.30` calibra que a incompletude estrutural é menos grave do que a incerteza sobre membros conhecidos, mas ainda representa risco epistêmico relevante. Este efeito mede: "quão incertos estamos sobre quem ainda não encontramos?"

**Separabilidade semântica — propriedade crítica de design:**

O `Uncertainty_Committee` **não contamina o `O_score`**. Esta separação é intencional e deve ser preservada em todas as versões do sistema:

- **`O_score` (Opportunity Score):** hipótese de que o lead tem valor — baseado em fit, intent e reachability. Não depende de quem são os membros do comitê nem de quão bem eles foram mapeados.
- **`C_score` (Confidence Score):** confiança de que o sistema sabe o suficiente sobre o lead para agir com inteligência. Depende diretamente da qualidade das evidências coletadas, incluindo a composição do comitê.

Esta separação garante que um lead de alto valor (`O_score` alto) com comitê mal mapeado seja ranqueado com baixo `C_score` — sinalizando que o lead precisa de mais ciclos de coleta antes de ser abordado, sem incorretamente degradar sua avaliação de oportunidade.

**Exemplos numéricos:**

**Cenário 1 — 0 membros identificados:**
```
S_committee_Completeness = 0/3 = 0.000
ū_members = 0.000  (nenhum membro para médiar)
Uncertainty_Committee = 0.000 + (1 - 0.000) × 0.30 = 0.300

CommitteeConfidence = 1 - 0.300 = 0.700
feat_uncertainty_committee no C_score = 0.300  → degradação moderada
```

**Cenário 2 — 1 membro identificado (CommitteeCompleteness = 0.33), ū_m1 = 0.40:**
```
S_committee_Completeness = 1/3 = 0.333
ū_members = 0.400  (único membro tem incerteza 0.40)
Uncertainty_Committee = 0.400 + (1 - 0.333) × 0.30 = 0.400 + 0.200 = 0.600

CommitteeConfidence = 1 - 0.600 = 0.400
Impacto: degradação significativa — lead não está pronto para abordagem
```

**Cenário 3 — 3 membros identificados (CommitteeCompleteness = 1.00), ū_members ponderado = 0.20:**
```
S_committee_Completeness = 3/3 = 1.000
ū_members = 0.200
Uncertainty_Committee = 0.200 + (1 - 1.000) × 0.30 = 0.200 + 0.000 = 0.200

CommitteeConfidence = 1 - 0.200 = 0.800
Impacto: degradação mínima — comitê completo e bem evidenciado
```

**Cenário 4 — 3 membros identificados, mas evidências fracas (ū_members = 0.65):**
```
S_committee_Completeness = 1.000
Uncertainty_Committee = 0.650 + 0.000 = 0.650

CommitteeConfidence = 1 - 0.650 = 0.350
Impacto: degradação severa apesar de completude estrutural — qualidade de evidências insuficiente mesmo com todos os papéis mapeados
```

---

### 2.4 Tabela de Comportamento do Comitê por Nível de Completude

| Papéis Identificados | CommitteeCompleteness | Penalidade Estrutural `(1 - C) × 0.30` | Nota de Comportamento |
|---|---|---|---|
| 0 / 3 | 0.000 | **+0.30** | Nenhum papel mapeado — incerteza estrutural máxima permitida |
| 1 / 3 | 0.333 | **+0.20** | Um papel encontrado — dois papéis críticos ausentes |
| 2 / 3 | 0.667 | **+0.10** | Dois papéis mapeados — apenas um papel faltante |
| 3 / 3 | 1.000 | **+0.00** | Comitê completo — penalidade estrutural zerada |

**Observação:** A penalidade estrutural é adicionada ao `ū_members` para compor o `Uncertainty_Committee`. Mesmo com comitê completo (penalidade = 0.00), a incerteza dos membros individuais (`ū_members`) ainda pode degradar o `C_score` significativamente se as evidências coletadas forem de baixa qualidade (vide Cenário 4 acima).

---

## 3. Motor de Diferenciação Cognitiva SC vs BMO

### 3.1 Critérios Comportamentais Rigorosos

#### Structural Champion (SC) — Defensor Estrutural Estático

O SC é o indivíduo que representa o ponto de entrada hierárquico legítimo no comitê de compra. Sua posição é reconhecida internamente na organização, mas ele **não demonstra urgência ativa de mudança** no período de coleta.

**Critérios de classificação como SC:**

| Critério | Especificação |
|---|---|
| Estabilidade de cargo | Mesmo cargo há > 6 meses sem mudança registrada nas fontes (LinkedIn, CNPJ, Instagram bio) |
| Alinhamento funcional | `role_alignment_score > 0.60` com papel de influência ou decisão no segmento |
| Presença pública | Frequência moderada e consistente — tom profissional e operacional, sem urgência ou transformação |
| Momentum comportamental | `bmo_momentum_score < 0.55` |
| Padrão típico de conteúdo | Posts sobre resultados já alcançados, celebrações de equipe, conteúdo educativo sobre a área — sem posts sobre dor ativa ou busca por mudança |

**Exemplos de SC por segmento:**

- **Advocacia:** Sócia-fundadora com 10 anos de empresa, postando sobre jurisprudência e conquistas do escritório — sem posts sobre burnout de equipe, dificuldades de escala ou busca por ferramentas de gestão.
- **Consultoria:** Sócio-diretor com cargo estável há 3 anos, postando sobre cases de sucesso — sem urgência de transformação interna visível.
- **Software House:** CTO com cargo há 2 anos, postando sobre eventos tech e tendências — sem posts sobre dívida técnica, problemas de produto ou mudança de stack.
- **Engenharia:** Fundador postando sobre obras concluídas e equipe — sem menção a problemas de coordenação ou processos operacionais.

---

#### Buying Motion Owner (BMO) — Agente Dinâmico de Mudança

O BMO é o indivíduo que está **ativamente impulsionando** a busca por solução dentro da organização. Não precisa ser o decisor formal — pode ser um gerente, coordenador ou líder técnico que sente a dor com maior intensidade e está buscando saída.

**Critérios de classificação como BMO:**

| Critério | Especificação |
|---|---|
| Cluster de posts de dor | ≥ 3 posts sobre dor do ICP nos últimos 21 dias |
| Consumo ativo de soluções | Interage com conteúdo de ferramentas, metodologias ou fornecedores de solução |
| Momentum comportamental | `bmo_momentum_score ≥ 0.55` |
| Cargo | Irrelevante — BMO pode ser qualquer nível hierárquico |
| Engajamento em âncoras | Comenta ou reage em perfis âncora do ICP (G4, Endeavor, RD Summit, etc.) |

**Exemplos de BMO por segmento:**

- **Advocacia:** Coordenadora administrativa postando 4 vezes em 3 semanas sobre "processos manuais que travam a equipe" e interagindo com posts de automação jurídica.
- **Consultoria:** Gerente de projetos comentando em posts sobre metodologias de delivery e conectando-se com fornecedores de gestão de projetos.
- **Software House:** Product Manager postando sobre "roadmap caótico" e "falta de processo de priorização" — engajando ativamente com conteúdo de product ops e ferramentas de gestão de produto.
- **Engenharia:** Gerente de obras postando sobre dificuldades de coordenação de subcontratados e interagindo com fornecedores de ERP para construtoras.

---

### 3.2 bmo_momentum_score

O `bmo_momentum_score` é o score sintético que determina se um indivíduo está em modo de busca ativa de transformação.

**Formulação:**

```
bmo_momentum_score = 0.50 × post_cluster_score
                   + 0.30 × anchor_interaction_score
                   + 0.20 × trigger_event_score
```

**Detalhamento das componentes:**

```
post_cluster_score       = min(posts_dor_21_dias / 5, 1.0)
anchor_interaction_score = min(interações_em_âncoras_7_dias / 3, 1.0)
trigger_event_score      = min(0.5 × n_triggers_ativos, 1.0)
                           -- 0.5 por trigger ativo; máximo 1.0 com ≥ 2 triggers
```

**Componentes e pesos:**

| Componente | Peso | Janela | Saturação | Razão do Peso |
|---|---|---|---|---|
| `post_cluster_score` | 0.50 | 21 dias | 5 posts | Sinal mais direto de dor ativa — quem posta sobre dor está vivendo ela |
| `anchor_interaction_score` | 0.30 | 7 dias | 3 interações | Busca de solução via consumo de conteúdo especializado — sinal de intent |
| `trigger_event_score` | 0.20 | Variável por trigger | 2 triggers ativos | Eventos estruturais são menos frequentes mas altamente informativos |

**Thresholds de classificação:**

| bmo_momentum_score | Classificação resultante |
|---|---|
| ≥ 0.55 | **BUYING_MOTION_OWNER** — agente de mudança ativo |
| < 0.55 e `role_alignment_score > 0.60` | **STRUCTURAL_CHAMPION** — defensor estrutural |
| < 0.55 e `role_alignment_score ≤ 0.60` | **MEMBER** — membro relevante sem papel definido |
| Dados insuficientes para cálculo | **UNKNOWN** |

**Exemplos numéricos de bmo_momentum_score:**

| Cenário | post_cluster | anchor_int | trigger_event | bmo_momentum_score | Classificação |
|---|---|---|---|---|---|
| Coordenadora com 4 posts de dor, 2 interações em âncora, 1 trigger ativo | `min(4/5,1)=0.80` | `min(2/3,1)=0.67` | `min(0.5×1,1)=0.50` | `0.50×0.80 + 0.30×0.67 + 0.20×0.50` = **0.701** | BMO |
| CEO estável, 1 post de dor, 0 interações, 0 triggers | `min(1/5,1)=0.20` | `0.00` | `0.00` | `0.50×0.20` = **0.100** | SC (role_align=0.95 > 0.60) |
| Gerente altamente ativo, 5 posts, 3 interações, 2 triggers | `1.00` | `1.00` | `1.00` | `0.50 + 0.30 + 0.20` = **1.000** | BMO |
| Analista com alguma atividade, 2 posts, 1 interação, 0 triggers | `min(2/5,1)=0.40` | `min(1/3,1)=0.33` | `0.00` | `0.50×0.40 + 0.30×0.33` = **0.299** | MEMBER (role_align=0.22 ≤ 0.60) |

---

### 3.3 Podem SC e BMO Coincidir?

**Sim.** Quando o fundador ou decisor formal demonstra alto momentum comportamental, a mesma pessoa é simultaneamente o Structural Champion (poder formal de decisão) e o Buying Motion Owner (impulso ativo de mudança). Esta é a configuração mais favorável para a abordagem comercial.

**Condição de coincidência:**
```
bmo_momentum_score >= 0.55  AND  role_alignment_score > 0.60
```

**Regra de designação em caso de coincidência:**

```python
if bmo_momentum_score >= 0.55 and role_alignment_score > 0.60:
    designation = 'BUYING_MOTION_OWNER'
    # Registrar em rationale: "BMO coincide com SC — decisor formal com momentum ativo"
```

A designação `'BUYING_MOTION_OWNER'` tem **prioridade** sobre `'STRUCTURAL_CHAMPION'` quando os critérios de ambos são satisfeitos. O campo `rationale` em `committee_members` deve registrar explicitamente: `"BMO coincide com SC — decisor formal com momentum ativo"`.

**Impacto na estratégia de abordagem quando SC = BMO:**

- Eliminar intermediação desnecessária — não tentar construir rapport com champion intermediário antes de chegar ao decisor.
- Abordagem direta ao decisor com pitch focado em urgência e ROI imediato.
- Reduzir etapas de qualificação — o decisor já está no modo de busca; processos longos de rapport podem desperdiçar a janela de momentum.
- Risco de sobrecarga: evitar múltiplos contatos no mesmo período de 7 dias — o decisor ativo está sendo abordado por outros fornecedores simultâneamente.

---

### 3.4 Os 4 Tipos de Trigger Events — Janelas e Pesos

Os trigger events são sinais estruturais e comportamentais que indicam que a organização **entrou em janela de mudança ativa**. Cada trigger contribui para o `trigger_event_score` do `bmo_momentum_score`. São persistidos na tabela `behavioral_momentum_log`.

---

#### Trigger 1 — Contratação Sênior Recente (`SENIOR_HIRE`)

| Atributo | Especificação |
|---|---|
| **Sinal detectado** | Nova conexão LinkedIn de cargo ≥ Manager nos últimos 30 dias |
| **Fonte de dados** | LinkedIn — análise de novas conexões públicas ou anúncios de "bem-vindo ao time" |
| **Janela temporal** | 30 dias corridos a partir da data de coleta |
| **Peso no trigger_event_score** | **0.60** |
| **trigger_type no schema** | `'SENIOR_HIRE'` |
| **window_days** | 30 |

**Interpretação estratégica:**

A contratação de um líder sênior cria uma janela de mudança cultural. O novo colaborador chega com agenda própria, disposição para questionar processos existentes e necessidade de demonstrar valor rapidamente — fenômeno conhecido como "lua de mel do gestor". Esse estado representa uma oportunidade de entrada com soluções de reorganização e eficiência antes que o novo líder fixe sua agenda interna.

**Falsos positivos comuns:** Promoção interna anunciada como "nova posição" (não é contratação externa). Mitigação: verificar se o perfil aparece como conexão nova com histórico de empresa diferente, ou se o cargo mudou no mesmo perfil já existente na base.

---

#### Trigger 2 — Vaga Aberta Persistente (`PERSISTENT_JOB_POSTING`)

| Atributo | Especificação |
|---|---|
| **Sinal detectado** | Job posting ativo > 60 dias no LinkedIn Jobs ou plataformas de recrutamento |
| **Fonte de dados** | LinkedIn Jobs, Catho, Indeed, Gupy — via scraping ou API pública |
| **Janela temporal** | Posting ativo há mais de 60 dias corridos |
| **Peso no trigger_event_score** | **0.40** |
| **trigger_type no schema** | `'PERSISTENT_JOB_POSTING'` |
| **window_days** | 60 |

**Interpretação estratégica:**

Uma vaga que não é preenchida em 60 dias sinaliza um problema estrutural: posicionamento interno inadequado, salário abaixo do mercado, alta rotatividade na área, ou função que ninguém quer por causa da cultura ou do caos operacional. Todos esses sinais apontam para dor organizacional real — o tipo de dor que o Programa de Acompanhamento Estratégico resolve ao endereçar a raiz.

**Falsos positivos comuns:** Vaga repostada com nova data (reinicia a contagem artificialmente). Mitigação: usar hash do conteúdo da vaga para identificar repostagens e manter a data original de primeira publicação detectada.

---

#### Trigger 3 — Post de Transformação Ativo (`TRANSFORMATION_POST`)

| Atributo | Especificação |
|---|---|
| **Sinal detectado** | ≥ 2 posts sobre mudança de processo ou implementação de nova ferramenta em 14 dias |
| **Fonte de dados** | Instagram, LinkedIn — análise semântica de conteúdo de posts |
| **Janela temporal** | 14 dias corridos a partir da data de coleta |
| **Peso no trigger_event_score** | **0.80** |
| **trigger_type no schema** | `'TRANSFORMATION_POST'` |
| **window_days** | 14 |

**Interpretação estratégica:**

Este é o sinal mais forte dos quatro. Quando alguém posta sobre "estamos implementando X" ou "mudamos nosso processo de Y", está publicamente declarando que a organização está **no modo de solução**, não apenas no modo de dor. A janela de venda é extremamente curta — a pessoa pode já estar avaliando fornecedores ou pode ter acabado de fechar uma solução concorrente. Ação imediata recomendada quando este trigger está ativo.

**Palavras-chave de transformação para classificação:** `"implementando"`, `"migrando"`, `"adotamos"`, `"mudamos nosso processo"`, `"novo sistema"`, `"automatizamos"`, `"nova ferramenta"`, `"reestruturação"`, `"nova metodologia"`, `"estamos testando"`.

---

#### Trigger 4 — Novo Engajamento em Âncora (`ANCHOR_INTERACTION`)

| Atributo | Especificação |
|---|---|
| **Sinal detectado** | Comentário ou reação em perfil âncora do ICP nos últimos 7 dias |
| **Fonte de dados** | Instagram, LinkedIn — análise de atividade pública em perfis âncora |
| **Janela temporal** | 7 dias corridos a partir da data de coleta |
| **Peso no trigger_event_score** | **0.50** |
| **trigger_type no schema** | `'ANCHOR_INTERACTION'` |
| **window_days** | 7 |

**O que são perfis âncora:**

Perfis âncora são contas públicas que concentram audiências de decisores do ICP e publicam conteúdo de transformação empresarial. Exemplos: G4 Educação, Endeavor Brasil, RD Summit, Resultados Digitais, contas de consultores influentes no segmento. A lista é configurada no campo `anchor_profiles` do `icp_contract` ativo.

**Interpretação estratégica:**

Interagir com um perfil âncora em um período curto (7 dias) indica que o indivíduo está **ativamente consumindo conteúdo de transformação**. É um sinal de intent mais forte do que um simples follow — exige esforço deliberado de engajamento (comentar, reagir, compartilhar). A janela de 7 dias captura apenas interações muito recentes, tornando este trigger altamente sensível a mudanças de comportamento.

---

### 3.5 Estratégia de Abordagem Diferenciada SC vs BMO

A identificação correta do SC e do BMO define **quem abordar primeiro**, **com qual mensagem** e **em qual sequência**. Esta lógica deve ser exportada pelo sistema no campo `rationale` de `committee_members` e consumida pelo operador humano ou por agente de outreach.

#### Quando SC ≠ BMO (caso mais comum):

```
Sequência recomendada:
1. Engajar BMO primeiro
   → Reconhecimento técnico da dor específica que ele está expressando publicamente
   → Usar o conteúdo público dele como âncora de abertura de conversa

2. Construir rapport com BMO
   → Validar a dor sem propor solução ainda
   → Confirmar que o problema existe internamente e que ele é o agente de mudança

3. Qualificar o papel do BMO internamente
   → Verificar se o BMO tem acesso ao Economic Buyer (SC)
   → Entender o grau de influência do BMO sobre a decisão

4. Usar BMO como champion interno
   → Pedir que ele leve a conversa ao SC com framing correto
   → Fornecer materiais de habilitação (one-pager, case study do segmento)

5. Abordar SC com endorsement implícito do BMO
   → Chegar referenciado, não frio
   → Pitch de ROI e decisão, não de educação sobre o problema
```

**Por que não abordar o SC diretamente sem preparação:** O SC tem poder de decisão, mas sem urgência ativa. Uma abordagem fria resulta em "não é prioridade agora". O BMO já sente urgência — ele prepara o terreno, cria o contexto interno e valida que o problema é real para o tomador de decisão.

---

#### Quando SC = BMO (decisor com momentum ativo):

```
Sequência recomendada:
1. Abordagem direta ao decisor
   → Sem intermediação, sem rapport longo

2. Pitch focado em urgência e ROI imediato
   → Não educar sobre o problema — ele já sabe que tem o problema
   → Focar em: "como resolvemos isso para empresas iguais à sua em X semanas"

3. Reduzir etapas de qualificação
   → Não infantilizar o processo com perguntas de discovery óbvias
   → Ir direto para proposta de valor com números do segmento

4. Proposta no primeiro contato se momentum muito alto
   → Se bmo_momentum_score > 0.80 E pelo menos 2 trigger events ativos:
      considerar enviar proposta de descoberta já no primeiro contato
```

---

#### Quando BMO é desconhecido (`designation = 'UNKNOWN'`):

```
Sequência recomendada:
1. Abordagem ao SC com construção de rapport de longo prazo
   → Sem menção a pitch ou proposta nos primeiros 2-3 contatos

2. Usar conteúdo educativo como isca comportamental
   → Publicar conteúdo relevante ao segmento
   → Monitorar quem da empresa engaja com esse conteúdo — isso identifica o BMO

3. Monitorar engajamento do SC com o conteúdo publicado
   → Se o SC engajar ativamente (comentar, compartilhar, reagir), ele pode ser o próprio BMO

4. Retornar ao motor de detecção de trigger events após 14 dias
   → Re-executar coleta focada em behavioral_momentum_log para a empresa

5. Regra de segurança:
   → Nunca enviar proposta formal para prospect com designation = 'UNKNOWN'
   → O sistema deve bloquear essa ação até que pelo menos um membro do comitê
      tenha designation IN ('BUYING_MOTION_OWNER', 'STRUCTURAL_CHAMPION')
      com bmo_momentum_score calculado
```

---

*Fim do SDD-05 — Buying Committee & Buying Motion*
