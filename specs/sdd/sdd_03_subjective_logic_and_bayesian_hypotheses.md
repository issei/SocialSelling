# SDD-03: Espaço Latente de Estados e Lógica Subjetiva
## SocialSelling — Solution Design Document
### Versão: 1.0-MVP | Classificação: CONFIDENCIAL — ENGENHARIA

---

**Escopo do Documento:** Framework formal de propagação de confiança baseado em Subjective Logic (Jøsang), motor de atualização recursiva Bayesiana, catálogo completo das 15 hipóteses de dor com supporting/contradicting evidence, critérios de transição de estado (CANDIDATE / ACTIVE / REJECTED) e exemplos numéricos calculados para cada operação do sistema.

**Documentos relacionados:**
- `sdd_01_product_vision_and_core_dag.md` — Arquitetura LangGraph, LeadState (denominado `AgentState` no SDD-01; padronizado como `LeadState` a partir do SDD-07), DAG de fases
- `sdd_02_mathematical_core_scoring.md` — Fórmulas P_score, O_score, C_score, SRS_k, freshness
- `sdd_04_sensory_search_and_finops_stopping.md` — Source Quality Vector, DSS, FinOps stopping
- `sdd_06_database_schema_and_graph_ready_ddl.md` — DDL das tabelas `evaluated_hypotheses` (hipóteses por ciclo com posteriores e triplas ω), `entity_nodes` (triplas ω de entidade nos campos `belief`, `disbelief`, `uncertainty`), `committee_members` (triplas ω individuais de membros), `hypothesis_catalog` (priors e regras de evidência)
- `sdd_12_xai_and_pruning_json_contracts.md` — XAI Payload e cadeia causal auditável

---

## Índice

1. [Framework de Propagação de Confiança](#1-framework-de-propagação-de-confiança)
2. [Catálogo Formal de Hipóteses H1–H15](#2-catálogo-formal-de-hipóteses-h1h15)
3. [Motor de Atualização Recursiva Bayesiana](#3-motor-de-atualização-recursiva-bayesiana)

---

## 1. FRAMEWORK DE PROPAGAÇÃO DE CONFIANÇA

### 1.1 A Opinião Subjetiva como Tripla

#### Definição Formal

A Subjective Logic formaliza o estado epistêmico de um agente sobre uma proposição binária por meio de uma tripla `ω = (b, d, u)` onde:

- **b (belief):** grau de crença afirmativa — fração do espaço de evidência que confirma a proposição.
- **d (disbelief):** grau de descrença — fração que refuta a proposição.
- **u (uncertainty):** grau de incerteza — fração atribuída à ausência ou ambiguidade de evidência.

A restrição estrutural é `b + d + u = 1` com `b, d, u ∈ [0, 1]`. A tripla habita o espaço simplex bidimensional `Δ²`.

#### Probabilidade Projetada

A probabilidade frequentista projetada a partir de uma tripla é:

```
P(ω) = b + a × u
```

onde `a` é a probabilidade a priori base da proposição (base rate). Quando `a = 0.5` (prior uniforme), `P(ω) = b + 0.5 × u`. Para o sistema SocialSelling, `a` é sempre o prior `P₀` da hipótese correspondente, garantindo que a probabilidade projetada seja consistente com a atualização Bayesiana.

#### Semântica dos Componentes

| Componente | Semântica | Exemplo de situação |
|---|---|---|
| `b` alto | Evidência forte afirmando a hipótese | Múltiplas vagas abertas confirmadas no LinkedIn |
| `d` alto | Evidência forte refutando a hipótese | Organograma publicado mostrando equipe completa e estável |
| `u` alto | Poucas ou nenhuma evidência relevante coletada | Perfil LinkedIn privado, zero posts públicos |
| `b≈d≈u≈0.33` | Evidências equilibradas e parcialmente contraditórias | Um post de crescimento e um post de corte de custos no mesmo período |

#### Três Exemplos de Triplas com Interpretação

**Exemplo A — Alta crença, baixa incerteza:**
`ω = (0.78, 0.12, 0.10)`
Interpretação: Evidência robusta confirma a hipótese (78%), refutação fraca (12%), pequena lacuna de informação (10%). Probabilidade projetada com `a=0.25`: `P = 0.78 + 0.25 × 0.10 = 0.803`. Hipótese candidata forte para ACTIVE.

**Exemplo B — Incerteza dominante:**
`ω = (0.15, 0.05, 0.80)`
Interpretação: Presença de algum sinal afirmativo leve (15%), ausência quase total de refutação (5%), informação majoritariamente ausente (80%). Ocorre quando a fonte principal estava indisponível (modo DEGRADED). Probabilidade projetada com `a=0.25`: `P = 0.15 + 0.25 × 0.80 = 0.350`. Estado CANDIDATE por posterior baixo.

**Exemplo C — Descrença dominante:**
`ω = (0.08, 0.72, 0.20)`
Interpretação: Evidências Contradicting preponderantes (72% do espaço de evidência refuta), sinal afirmativo residual (8%), incerteza moderada (20%). Probabilidade projetada com `a=0.25`: `P = 0.08 + 0.25 × 0.20 = 0.130`. Hipótese candidata a transição para REJECTED.

---

### 1.2 Operador de Desconto

#### Fórmula Completa

O operador de desconto aplica o fator de qualidade da fonte (`SRS_k`) a uma opinião observada `ω_B = (b_B, d_B, u_B)`, produzindo a opinião descontada `ω_disc`:

```
ω_disc = (SRS_k × b_B,  SRS_k × d_B,  1 - SRS_k × (b_B + d_B))
```

onde `SRS_k ∈ [0, 1]` é o Source Reliability Score da fonte `k`, calculado conforme `sdd_02_mathematical_core_scoring.md`.

#### Propriedades do Operador de Desconto

**Propriedade 1 — Preservação com SRS=1.0:**
`ω_disc = (1.0 × b_B, 1.0 × d_B, 1 - 1.0 × (b_B + d_B)) = (b_B, d_B, u_B)`
Fonte perfeita não altera a opinião original.

**Propriedade 2 — Vacuidade com SRS=0:**
`ω_disc = (0, 0, 1 - 0 × (b_B + d_B)) = (0, 0, 1)`
Fonte com zero confiabilidade produz vacuidade completa — a evidência é descartada integralmente e substituída por incerteza máxima.

**Propriedade 3 — Monotonia:**
`SRS_k₁ > SRS_k₂ → u_disc(k₁) < u_disc(k₂)` — fontes mais confiáveis transferem mais informação e geram menor incerteza residual.

#### Exemplo Numérico 1 — SRS alto

Fonte: LinkedIn Scraper, `SRS_k = 0.80`
Opinião bruta observada: `ω_B = (0.70, 0.10, 0.20)`

```
b_disc = 0.80 × 0.70 = 0.560
d_disc = 0.80 × 0.10 = 0.080
u_disc = 1 - 0.80 × (0.70 + 0.10)
       = 1 - 0.80 × 0.80
       = 1 - 0.640
       = 0.360

ω_disc = (0.560, 0.080, 0.360)
Verificação: 0.560 + 0.080 + 0.360 = 1.000 ✓
```

A confiabilidade 0.80 dilui b de 0.70 para 0.56 e transfere 0.16 para incerteza, refletindo que a fonte, embora boa, não é perfeita.

#### Exemplo Numérico 2 — SRS médio-baixo

Fonte: Instagram Scraper em modo DEGRADED, `SRS_k = 0.45`
Opinião bruta observada: `ω_B = (0.60, 0.20, 0.20)`

```
b_disc = 0.45 × 0.60 = 0.270
d_disc = 0.45 × 0.20 = 0.090
u_disc = 1 - 0.45 × (0.60 + 0.20)
       = 1 - 0.45 × 0.80
       = 1 - 0.360
       = 0.640

ω_disc = (0.270, 0.090, 0.640)
Verificação: 0.270 + 0.090 + 0.640 = 1.000 ✓
```

Com SRS=0.45, a incerteza salta de 0.20 para 0.64, indicando que o sinal colhido em modo degradado tem baixo poder informativo sobre a tripla consolidada da entidade.

---

### 1.3 Operador de Consenso

#### Fórmulas Completas

O operador de consenso (cumulative fusion) `ω_{A⊕B}` combina duas opiniões independentes `ω_A = (b_A, d_A, u_A)` e `ω_B = (b_B, d_B, u_B)` sobre a mesma proposição:

```
denominador  = u_A + u_B - u_A × u_B

b_{A⊕B} = (b_A × u_B + b_B × u_A) / denominador
d_{A⊕B} = (d_A × u_B + d_B × u_A) / denominador
u_{A⊕B} = (u_A × u_B) / denominador
```

**Intuição:** Opiniões com maior certeza (u pequeno) recebem mais peso na fusão. A incerteza fusionada decai geometricamente — duas fontes independentes com incerteza 0.50 produzem incerteza fusionada de `(0.50 × 0.50) / (0.50 + 0.50 - 0.25) = 0.25 / 0.75 = 0.333`, não 0.50.

#### Exemplo Numérico 1 — Consenso entre Instagram e CNPJ

`ω_A = (0.60, 0.20, 0.20)` — Instagram, evidência de crescimento de equipe
`ω_B = (0.50, 0.10, 0.40)` — CNPJ.ws, alteração societária recente

```
denominador = 0.20 + 0.40 - (0.20 × 0.40)
            = 0.60 - 0.08
            = 0.52

b_{A⊕B} = (0.60 × 0.40 + 0.50 × 0.20) / 0.52
         = (0.240 + 0.100) / 0.52
         = 0.340 / 0.52
         = 0.654

d_{A⊕B} = (0.20 × 0.40 + 0.10 × 0.20) / 0.52
         = (0.080 + 0.020) / 0.52
         = 0.100 / 0.52
         = 0.192

u_{A⊕B} = (0.20 × 0.40) / 0.52
         = 0.080 / 0.52
         = 0.154

ω_{A⊕B} = (0.654, 0.192, 0.154)
Verificação: 0.654 + 0.192 + 0.154 = 1.000 ✓
```

A fusão elevou a crença de 0.60/0.50 para 0.654 e reduziu a incerteza de 0.20/0.40 para 0.154.

#### Exemplo Numérico 2 — Consenso com opiniões divergentes

`ω_A = (0.70, 0.05, 0.25)` — LinkedIn Jobs, vaga sênior aberta confirmada
`ω_B = (0.30, 0.40, 0.30)` — Tavily News, notícia de reestruturação com cortes

```
denominador = 0.25 + 0.30 - (0.25 × 0.30)
            = 0.55 - 0.075
            = 0.475

b_{A⊕B} = (0.70 × 0.30 + 0.30 × 0.25) / 0.475
         = (0.210 + 0.075) / 0.475
         = 0.285 / 0.475
         = 0.600

d_{A⊕B} = (0.05 × 0.30 + 0.40 × 0.25) / 0.475
         = (0.015 + 0.100) / 0.475
         = 0.115 / 0.475
         = 0.242

u_{A⊕B} = (0.25 × 0.30) / 0.475
         = 0.075 / 0.475
         = 0.158

ω_{A⊕B} = (0.600, 0.242, 0.158)
Verificação: 0.600 + 0.242 + 0.158 = 1.000 ✓
```

A tensão entre a vaga aberta (b=0.70) e a notícia de reestruturação (d=0.40) produziu crença moderada (0.600) e descrença não negligenciável (0.242), refletindo corretamente o conflito de sinal.

---

### 1.4 GUARDA ZeroDivisionError — Implementação Obrigatória

#### Análise do Caso Degenerado

Quando ambas as fontes emitem opiniões dogmáticas — sem nenhuma incerteza residual — o denominador do operador de consenso colapsa:

```
u_A = 0  AND  u_B = 0
denominador = 0 + 0 - (0 × 0) = 0  →  ZeroDivisionError
```

Este caso ocorre na prática quando uma fonte de alta confiabilidade já saturou completamente sua opinião (`SRS_k ≈ 1.0` com evidência conclusiva) e uma segunda fonte igualmente dogmática entra em conflito. A fórmula padrão não tem solução analítica para este cenário — é uma singularidade do espaço simplex.

#### Pseudocódigo Python com Guarda Explícita

```python
def consensus_fusion(
    omega_a: tuple[float, float, float],
    omega_b: tuple[float, float, float],
    srs_a: float,
    srs_b: float,
) -> tuple[float, float, float]:
    """
    Operador de consenso (cumulative fusion) da Subjective Logic.
    Aplica guarda contra ZeroDivisionError quando u_A=0 AND u_B=0.

    Args:
        omega_a: tripla (b, d, u) da fonte A, já descontada por SRS_a
        omega_b: tripla (b, d, u) da fonte B, já descontada por SRS_b
        srs_a:   Source Reliability Score da fonte A
        srs_b:   Source Reliability Score da fonte B

    Returns:
        tripla fusionada (b_fused, d_fused, u_fused)
    """
    b_a, d_a, u_a = omega_a
    b_b, d_b, u_b = omega_b

    # --- GUARDA OBRIGATÓRIA ---
    # Denominador colapsa quando ambas as fontes são dogmáticas (u=0).
    # Vacuidade dogmática: adotar a opinião da fonte com maior SRS_k.
    if u_a == 0.0 and u_b == 0.0:
        if srs_a >= srs_b:
            return omega_a  # Fonte A tem maior autoridade epistêmica
        else:
            return omega_b  # Fonte B tem maior autoridade epistêmica

    denominador = u_a + u_b - (u_a * u_b)

    # Segurança adicional: denominador nunca deve ser <= 0 fora do caso u_a=u_b=0.
    # Se chegar aqui com denominador <= 0, é um erro de dados — levantar explicitamente.
    if denominador <= 0.0:
        raise ValueError(
            f"Denominador inválido no consensus_fusion: {denominador}. "
            f"omega_a={omega_a}, omega_b={omega_b}. "
            "Verifique se as triplas respeitam b+d+u=1 e todos os componentes em [0,1]."
        )

    b_fused = (b_a * u_b + b_b * u_a) / denominador
    d_fused = (d_a * u_b + d_b * u_a) / denominador
    u_fused = (u_a * u_b) / denominador

    # Normalização defensiva para erros de ponto flutuante
    total = b_fused + d_fused + u_fused
    if abs(total - 1.0) > 1e-9:
        b_fused /= total
        d_fused /= total
        u_fused /= total

    return (round(b_fused, 6), round(d_fused, 6), round(u_fused, 6))
```

#### Comportamento da Guarda

Quando `u_A = 0 AND u_B = 0`, o sistema adota a opinião da fonte com `SRS_k` superior. Esta escolha é semanticamente correta: a fonte com maior histórico de confiabilidade validada tem precedência epistêmica quando ambas estão certas de si mesmas mas divergem. A vacuidade dogmática não é fundida — é resolvida por autoridade.

A guarda deve ser invocada **antes** de qualquer divisão, nunca após captura de exceção, pois o custo computacional é O(1) e a ausência da guarda pode silenciosamente produzir `inf` ou `nan` em pipelines que não propagam exceções adequadamente.

---

### 1.5 Cadeia Causal de Propagação — 6 Camadas

#### Diagrama Textual

```
Camada 1: ω_SRS[fonte]
          └── Opinião de qualidade da própria fonte, calculada pelo SRS Feedback Loop
          └── Ex.: SRS_instagram = 0.82 → ω_SRS = (0.82, 0.00, 0.18)

Camada 2: ω_evidence
          └── Evidência bruta descontada: ω_disc = Desconto(ω_bruta, SRS_k)
          └── Ex.: ω_bruta=(0.70,0.10,0.20) + SRS=0.82 → ω_disc=(0.574,0.082,0.344)

Camada 3: ω_entity
          └── Fusão de múltiplas ω_evidence sobre o mesmo atributo da entidade
          └── Consenso iterativo: ω₁ ⊕ ω₂ ⊕ ... ⊕ ωₙ
          └── Ex.: ω_entity_followers = Consenso(ω_insta_disc, ω_tavily_disc)

Camada 4: ω_inference
          └── Inferência semântica aplicada sobre ω_entity
          └── Classificador semântico emite P(classe|texto) → mapeado para tripla
          └── Ex.: "post sobre burnout" → P(H10_dor)=0.75 → ω_inf=(0.75×0.80, 0.25×0.80, 0.20)

Camada 5: ω_hypothesis
          └── Fusão de todas ω_inference vinculadas à hipótese Hᵢ
          └── Consenso sobre o espaço de evidência relevante para Hᵢ
          └── Posterior Bayesiano P(Hᵢ|E) → mapeado em tripla via u_residual

Camada 6: ω_decision
          └── Entrada no cálculo de O_score e C_score
          └── b de ω_hypothesis → Hypothesis_Confidence → componente do C_score
          └── P(ω_hypothesis) → S_intent ou Fit → componente do O_score
```

#### Exemplo Numérico Completo — H2 percorrendo as 6 Camadas

**Contexto:** Prospect "Fernanda Alcantara Consultoria Ltda", coleta via Instagram. Hipótese H2 (Centralização Excessiva, P₀=0.30).

**Camada 1 — Qualidade da fonte Instagram:**
SRS Instagram calculado via feedback histórico: `SRS_instagram = 0.82`
`ω_SRS[instagram] = (0.82, 0.00, 0.18)` — a fonte tem crença 0.82 em sua própria confiabilidade.

**Camada 2 — Evidência bruta descontada:**
Evidência coletada: post "Hoje resolvi mais uma vez os três maiores problemas da empresa sozinha. Quem mais se identifica?" — classificado como `founder_solo_post`.
Opinião bruta do classificador: `ω_bruta = (0.80, 0.05, 0.15)`
Desconto:
```
b_disc = 0.82 × 0.80 = 0.656
d_disc = 0.82 × 0.05 = 0.041
u_disc = 1 - 0.82 × (0.80 + 0.05) = 1 - 0.82 × 0.85 = 1 - 0.697 = 0.303
ω_evidence = (0.656, 0.041, 0.303)
```

**Camada 3 — Atributo da entidade:**
Segunda evidência: ausência de colaboradores com menção nominal nos últimos 12 posts.
`ω_evidence_2 = (0.65, 0.05, 0.30)` — já descontada com SRS=0.82.
Consenso:
```
denominador = 0.303 + 0.300 - (0.303 × 0.300) = 0.603 - 0.091 = 0.512
b_entity = (0.656 × 0.300 + 0.650 × 0.303) / 0.512 = (0.1968 + 0.1970) / 0.512 = 0.3938 / 0.512 = 0.769
d_entity = (0.041 × 0.300 + 0.050 × 0.303) / 0.512 = (0.0123 + 0.0152) / 0.512 = 0.0275 / 0.512 = 0.054
u_entity = (0.303 × 0.300) / 0.512 = 0.0909 / 0.512 = 0.178
ω_entity = (0.769, 0.054, 0.178)  →  normalizado: (0.768, 0.054, 0.178)
```

**Camada 4 — Inferência semântica:**
O classificador semântico associa o padrão `founder_solo_post + ausência_colaboradores` à hipótese H2 com `P(H2_dor|padrão)=0.78`. `u_inf = 0.22` (incerteza de modelo).
```
b_inf = 0.78 × (1 - 0.22) = 0.78 × 0.78 = 0.608
d_inf = (1 - 0.78) × (1 - 0.22) = 0.22 × 0.78 = 0.172
u_inf = 0.22
ω_inference = (0.608, 0.172, 0.220)
```

**Camada 5 — Fusão na hipótese H2:**
Consenso entre `ω_entity` e `ω_inference`:
```
denominador = 0.178 + 0.220 - (0.178 × 0.220) = 0.398 - 0.039 = 0.359
b_hyp = (0.768 × 0.220 + 0.608 × 0.178) / 0.359 = (0.169 + 0.108) / 0.359 = 0.277 / 0.359 = 0.772
d_hyp = (0.054 × 0.220 + 0.172 × 0.178) / 0.359 = (0.012 + 0.031) / 0.359 = 0.043 / 0.359 = 0.120
u_hyp = (0.178 × 0.220) / 0.359 = 0.039 / 0.359 = 0.109
ω_hypothesis_H2 = (0.772, 0.120, 0.109)  →  normalizado após ponto flutuante
```
Posterior Bayesiano resultante (detalhado na Seção 3): `P(H2|E) ≈ 0.772 + 0.30 × 0.109 = 0.805`

**Camada 6 — Entrada no scoring:**
```
Hypothesis_Confidence(H2) = b_hyp = 0.772
Contribuição ao C_score: 0.772 × peso_H2_no_C
S_intent(H2) = P(ω_hypothesis_H2) = 0.805 → incremento O_score componente Fit (+0.10 a +0.18 conforme H2)
```

---

### 1.6 Conflict Resolution Policy — Impacto nas Triplas

#### Fórmulas de Penalização por Divergência

Quando duas fontes emitem sinais opostos com alta confiança, o sistema detecta conflito e aplica penalização na tripla consolidada. A `divergence_delta` é calculada como:

```
divergence_delta = |b_A - b_B| × (1 - u_A) × (1 - u_B)
```

A penalização ajusta a tripla da entidade para refletir a incerteza introduzida pelo conflito:

```
u_new = min(1.0,  u_current + divergence_delta × 0.40)
b_new = b_current × (1 - divergence_delta × 0.20)
d_new = 1 - b_new - u_new
```

Se `d_new < 0`, normalizar: `b_new = 1 - u_new`, `d_new = 0`.

#### Tabela de Severidade com Exemplos Numéricos

| Nível | Faixa divergence_delta | Exemplo divergence_delta | u_current | u_new | b_current | b_new | d_new | Ação do sistema |
|---|---|---|---|---|---|---|---|---|
| LOW | ≤ 0.30 | 0.20 | 0.15 | 0.15 + 0.20×0.40 = 0.230 | 0.72 | 0.72×(1−0.20×0.20) = 0.691 | 0.079 | Log, sem intervenção |
| MEDIUM | 0.30–0.60 | 0.45 | 0.20 | 0.20 + 0.45×0.40 = 0.380 | 0.65 | 0.65×(1−0.45×0.20) = 0.592 | 0.028 | Alert, flag para revisão |
| HIGH | 0.60–0.85 | 0.72 | 0.18 | 0.18 + 0.72×0.40 = 0.468 | 0.70 | 0.70×(1−0.72×0.20) = 0.599 | d<0 → d=0, b=0.532 | Suspensão da hipótese, re-query obrigatória |
| CRITICAL | > 0.85 | 0.91 | 0.10 | 0.10 + 0.91×0.40 = 0.464 | 0.80 | 0.80×(1−0.91×0.20) = 0.654 | d<0 → d=0, b=0.536 | Bloqueio da hipótese, escalonamento manual |

**Nota sobre casos negativos em d_new:** Em severidade HIGH e CRITICAL a penalização pode produzir `d_new < 0`, o que viola a restrição do simplex. O sistema corrige definindo `d_new = 0` e ajustando `b_new = 1 - u_new`. Esta correção reflete que o conflito de alta severidade elimina a descrença — a proposição fica genuinamente indeterminada.

---

## 2. CATÁLOGO FORMAL DE HIPÓTESES H1–H15

**Threshold de saturação para u_residual:** `threshold_saturation = 5` (5 evidências Supporting suficientes para saturar a janela de incerteza). Definido empiricamente sobre o ICP: fundadoras de Advocacia, Consultoria, SaaS e Engenharia com 5–30 colaboradores e faturamento R$80k–R$500k/mês.

---

#### H1 — Expansão Operacional | P₀ = 0.25

**Descrição Teórica da Dor**

Fundadoras em fase de escala experimentam um crescimento que, sem instrumentos adequados de gestão, torna-se fonte de estresse operacional. A expansão operacional manifesta-se como aumento simultâneo de demanda externa (novos clientes, novos contratos) e pressão interna (necessidade de contratar, onboarding, estruturação de processos) que excede a capacidade de absorção da liderança atual.

No ICP SocialSelling — empresas de 5 a 30 colaboradores — esse gap é particularmente agudo porque a founder ainda responde por decisões táticas enquanto tenta arquitetar o crescimento estratégico. A dor não é crescer; é crescer sem os instrumentos que tornam o crescimento sustentável.

Sinais públicos desta dor emergem primariamente via abertura de vagas (evidência de demanda por capacidade adicional) e via conteúdo que narra explicitamente a experiência de escala ("estamos crescendo muito e precisamos de reforço"). A co-ocorrência desses dois sinais é o padrão diagnóstico mais confiável do sistema para H1.

**Supporting Evidence**

| Sinal Observável | Fonte | P(E\|H) estimado |
|---|---|---|
| 2 ou mais vagas abertas simultaneamente no LinkedIn Jobs | LinkedIn Jobs | 0.80 |
| Posts com vocabulário de crescimento/escala (crescendo, expandindo, escalando, time crescendo) | Instagram / LinkedIn | 0.70 |
| Menção explícita a novo colaborador ou apresentação de integrante recente | Instagram / LinkedIn | 0.65 |
| Aumento de >20% de seguidores em 60 dias (proxy de tração) | Instagram | 0.55 |

**Contradicting Evidence**

| Sinal | Fonte | Impacto no Posterior |
|---|---|---|
| Equipe declarada estável há >12 meses sem novas vagas | LinkedIn | Reduz posterior em ~30% |
| Posts explicitando contenção de custos, cortes ou freeze de contratação | Instagram / LinkedIn | Reduz posterior em ~40% |
| Demissões declaradas publicamente | LinkedIn / Instagram | Reduz posterior em ~55% — forte evidência de anti-padrão |

**Missing Evidence (Entropia)**

| Dado Ausente | Impacto Shannon (bits) | Recomendação de Busca |
|---|---|---|
| Organograma formal ou lista de cargos atualizada | 0.18 bits | LinkedIn People tab + busca direta "empresa X" |
| Faturamento contábil dos últimos 12 meses | 0.25 bits | CNPJ.ws financeiro + Receita Federal |
| Declaração explícita de metas de crescimento | 0.15 bits | Posts de aniversário de empresa, entrevistas públicas |

**Impacto no O_score:** Componente S_intent incrementado em +0.08 a +0.15 quando cluster de vagas (≥2 simultâneas) é confirmado; condição: vaga ativa no LinkedIn Jobs com data de publicação ≤ 45 dias.

**Impacto no C_score:** Neutro — H1 por si só não altera a confiança de scoring, pois é uma hipótese de estado (crescimento), não de dor resolvível pelo produto.

**Interações:** Co-ocorrência com H2 (Centralização Excessiva) amplifica urgência — a founder que cresce e ainda centraliza tudo está em ponto de inflexão crítico. Co-ocorrência com H6 (Pré-Contratação Transformacional) indica janela de mudança transformacional com timing favorável para abordagem.

---

#### H2 — Centralização Excessiva | P₀ = 0.30

**Descrição Teórica da Dor**

A centralização excessiva é o padrão em que uma única pessoa — invariavelmente a founder — concentra decisões, comunicação externa, relacionamento com clientes e execução operacional. Este padrão é especialmente prevalente no ICP porque é a configuração natural de empresas nascidas do esforço individual da fundadora, que ainda não construiu processos ou confiança suficientes para delegar.

A dor se manifesta como incapacidade de crescer além do teto cognitivo da founder, gargalos de aprovação, cliente que só fala com a dono, e exaustão progressiva da liderança. É a hipótese de maior prevalência no ICP (P₀=0.30) porque é estruturalmente inerente a empresas nessa faixa de maturidade.

Evidências públicas são particularmente ricas para esta hipótese: o Instagram e o LinkedIn da empresa são administrados e protagonizados exclusivamente pela founder, sem posts de outros membros da equipe, sem menção a delegação ou a estrutura de liderança, com conteúdo que revela decisão unilateral de tudo.

**Supporting Evidence**

| Sinal Observável | Fonte | P(E\|H) estimado |
|---|---|---|
| Founder é o único rosto público da empresa em todos os canais | Instagram / LinkedIn | 0.75 |
| Ausência de qualquer colaborador com presença pública ou menção nominal em posts | Instagram / LinkedIn | 0.70 |
| Posts narrando sobrecarga solitária de decisão ("só eu", "mais um dia resolvendo tudo") | Instagram | 0.80 |
| Cargo de founder sem co-founder listado e tempo no cargo >18 meses | LinkedIn | 0.65 |

**Contradicting Evidence**

| Sinal | Fonte | Impacto no Posterior |
|---|---|---|
| Múltiplos colaboradores com presença pública e posts próprios na empresa | Instagram / LinkedIn | Reduz posterior em ~35% |
| Delegação declarada explicitamente ("minha equipe cuida de X") | Instagram / LinkedIn | Reduz posterior em ~25% |
| Organograma compartilhado com estrutura de lideranças intermediárias | LinkedIn | Reduz posterior em ~40% |

**Missing Evidence (Entropia)**

| Dado Ausente | Impacto Shannon (bits) | Recomendação de Busca |
|---|---|---|
| Número real de decisores com autonomia operacional | 0.20 bits | LinkedIn People + análise de quem posta pela empresa |
| Nível real de delegação operacional documentado | 0.22 bits | Entrevistas públicas, podcasts, lives da founder |

**Impacto no O_score:** Componente Fit incrementado em +0.10 a +0.18 quando `icp_centralization_score > 0.60`; a centralização é o driver mais forte de encaixe com o produto.

**Impacto no C_score:** Incrementa o C_score quando posterior > 0.65 — hipótese com alta confiança de centralização indica que a evidência de dor é densa e consistente.

**Interações:** Co-ocorrência com H10 (Sobrecarga do Fundador) amplifica S_intent — as duas hipóteses ativas simultaneamente sinalizam founder em estado crítico de esgotamento decisório. Mutuamente excludente com co-fundadores declarados com papéis operacionais distintos e visíveis.

---

#### H3 — Gargalo de Liderança Intermediária | P₀ = 0.20

**Descrição Teórica da Dor**

Quando a empresa cresce além de 10 colaboradores e a founder ainda não instituiu lideranças intermediárias (coordenadoras, gerentes, supervisoras), emerge um gargalo estrutural: toda demanda de decisão tática sobe diretamente para a founder, enquanto as colaboradoras de linha executam sem autonomia real. Esta configuração é insustentável além de certo volume.

A dor se manifesta como filas de aprovação, projetos atrasados por falta de decisão local, colaboradoras desmotivadas pela ausência de crescimento de carreira, e a founder operando como aprovadora de tudo. No contexto do ICP, esta hipótese é frequentemente precursora de crises de qualidade (H11) e de retenção (H7).

Evidências de gargalo de liderança intermediária são mais ricas no LinkedIn (vagas abertas para cargos de coordenação há mais de 45 dias indicam dificuldade de preencher a posição, não apenas a dor) e no Instagram (posts de líderes intermediárias relatando sobrecarga são sinal direto).

**Supporting Evidence**

| Sinal Observável | Fonte | P(E\|H) estimado |
|---|---|---|
| Coordenadora ou líder postando sobre sobrecarga operacional em primeira pessoa | Instagram / LinkedIn | 0.65 |
| Vaga para cargo de liderança (coordenação, gerência) aberta há >45 dias sem fechamento | LinkedIn Jobs | 0.70 |
| Posts sobre burnout de equipe ou dificuldade de gestão de pessoas | Instagram / LinkedIn | 0.60 |
| Vaga de Analista Sênior sem equivalente de liderança listado | LinkedIn Jobs | 0.55 |

**Contradicting Evidence**

| Sinal | Fonte | Impacto no Posterior |
|---|---|---|
| Estrutura hierárquica clara com múltiplos líderes visíveis e postando | LinkedIn / Instagram | Reduz posterior em ~40% |
| Equipe de liderança intermediária com titles de Manager/Coordenadora visíveis | LinkedIn | Reduz posterior em ~35% |

**Missing Evidence (Entropia)**

| Dado Ausente | Impacto Shannon (bits) | Recomendação de Busca |
|---|---|---|
| Organograma com linhas de reporte intermediárias | 0.18 bits | LinkedIn People + site institucional |
| Cargos de coordenação/gestão não listados no LinkedIn da empresa | 0.15 bits | LinkedIn People tab, filtrando por título |

**Impacto no O_score:** S_intent incrementado em +0.06 a +0.12 quando vaga de liderança aberta >45 dias é confirmada.

**Impacto no C_score:** Reduz quando a coleta é feita apenas via Instagram (modo somente-Instagram ativo) — sem LinkedIn, `u = 0.80` para esta hipótese, pois evidências de estrutura de liderança são primariamente oriundas do LinkedIn. O C_score reflete a baixa confiança na ausência de confirmação via LinkedIn.

**Interações:** Co-ocorrência com H7 (Crise de Retenção) amplifica urgência — gargalo de liderança acelera turnover. Co-ocorrência com H1 (Expansão Operacional) sugere empresa crescendo sem estrutura de liderança adequada para suportar o crescimento.

---

#### H4 — Necessidade de Automação | P₀ = 0.15

**Descrição Teórica da Dor**

Empresas no ICP — especialmente Consultoria e Advocacia — operam frequentemente com processos manuais intensivos: planilhas para gestão de casos, Google Forms para coleta de dados de clientes, WhatsApp para comunicação interna, e-mail para aprovações. Esta configuração funciona até aproximadamente 8–12 colaboradores, momento em que o volume de retrabalho e os erros por processo manual tornam-se economicamente inaceitáveis.

A dor é concreta: horas-pessoa gastas em tarefas repetitivas de consolidação de dados, erros por digitação manual, incapacidade de ter visão gerencial em tempo real sem montar planilhas manualmente. A founder que experimenta esta dor frequentemente exterioriza frustração com ferramentas básicas ou celebra pequenas automações como conquistas significativas.

A hipótese tem prior baixo (0.15) porque nem toda empresa do ICP é candidata — aquelas com stack tecnológico avançado (ERP, CRM enterprise, BPM) já superaram esta fase e não são receptivas à oferta.

**Supporting Evidence**

| Sinal Observável | Fonte | P(E\|H) estimado |
|---|---|---|
| Posts mencionando planilhas como ferramenta central de gestão | Instagram / LinkedIn | 0.70 |
| Menção a ferramentas básicas (Google Sheets, WhatsApp Business como CRM) | Instagram / LinkedIn | 0.65 |
| Posts expressando frustração com retrabalho, "fazer a mesma coisa várias vezes" | Instagram | 0.75 |
| Vaga de Analista de Processos ou Automação aberta | LinkedIn Jobs | 0.60 |

**Contradicting Evidence**

| Sinal | Fonte | Impacto no Posterior |
|---|---|---|
| Stack avançado declarado (ERP como SAP/Totvs, CRM enterprise como Salesforce/HubSpot) | Instagram / LinkedIn / Site | Reduz posterior em ~50% — forte contra-indicação |
| Consultor de processos ou Analista de BPM contratado nos últimos 6 meses | LinkedIn | Reduz posterior em ~45% — problema provavelmente em resolução |

**Missing Evidence (Entropia)**

| Dado Ausente | Impacto Shannon (bits) | Recomendação de Busca |
|---|---|---|
| Stack tecnológico real em uso (ferramentas listadas no site ou em perfis da equipe) | 0.25 bits | LinkedIn de colaboradores (seções de skills), site institucional, Glassdoor |

**Impacto no O_score:** Componente Fit incrementado em +0.12 a +0.20 quando `icp_maturity_score < 0.40` — empresas em estágio inicial de maturidade operacional são as maiores beneficiárias de automação.

**Impacto no C_score:** Reduz quando Contradicting forte (stack avançado) está presente — a confiança de que a hipótese é real cai, e o C_score reflete corretamente que a evidência disponível não sustenta H4.

**Interações:** Co-ocorrência com H5 (Busca por Eficiência) sugere empresa em transição de mentalidade operacional. Co-ocorrência com H10 (Sobrecarga do Fundador) indica que a founder está pessoalmente impactada pelo retrabalho manual.

---

#### H5 — Busca por Eficiência | P₀ = 0.10

**Descrição Teórica da Dor**

Diferente de H4 (automação de processo específico), H5 representa uma mentalidade de busca por eficiência sistêmica — a founder que já superou a crise de crescimento acelerado e agora busca otimizar margens, reduzir desperdício e operar com menos esforço para o mesmo resultado. É uma hipótese de estágio mais maduro dentro do ICP.

A dor aqui é sutil: não é uma crise urgente, mas uma insatisfação persistente com a relação esforço/resultado. A founder consegue crescer, mas sente que está deixando dinheiro na mesa por ineficiências que poderia corrigir. Posts sobre produtividade, sistemas e otimização são o principal indicador público desta mentalidade.

O prior baixo (0.10) reflete que este estado de maturidade é menos frequente no ICP definido — empresas menores tipicamente estão ainda em crise de crescimento ou de processo, não em otimização fina.

**Supporting Evidence**

| Sinal Observável | Fonte | P(E\|H) estimado |
|---|---|---|
| Alto engajamento em posts sobre produtividade e gestão de tempo | Instagram / LinkedIn | 0.55 |
| Posts narrando estabilização do crescimento após período de expansão | Instagram / LinkedIn | 0.60 |
| Conteúdo sobre otimização de processos, metodologias ágeis, OKRs | Instagram / LinkedIn | 0.50 |
| Seguindo ou referenciando conteúdo de eficiência operacional | Instagram | 0.45 |

**Contradicting Evidence**

| Sinal | Fonte | Impacto no Posterior |
|---|---|---|
| Crescimento acelerado recente com múltiplas novas contratações (>3 em 90 dias) | LinkedIn | Reduz posterior em ~30% — foco está em crescimento, não otimização |
| Posts sobre expansão e novos projetos (mentalidade de escala, não de eficiência) | Instagram / LinkedIn | Reduz posterior em ~20% |

**Missing Evidence (Entropia)**

| Dado Ausente | Impacto Shannon (bits) | Recomendação de Busca |
|---|---|---|
| Dados de margem operacional ou custo por cliente | 0.20 bits | Relatórios públicos, entrevistas, menção em podcasts |

**Impacto no O_score:** S_intent incrementado em +0.04 a +0.08 — sinal de baixa urgência comparado a outras hipóteses, mas relevante quando combinado com outras evidências de maturidade.

**Impacto no C_score:** Neutro — H5 não afeta diretamente a confiança de scoring por ser uma hipótese de mentalidade difícil de observar externamente com alta certeza.

**Interações:** Co-ocorrência com H4 (Automação) indica empresa em transição de maturidade operacional. Hipóteses H5 e H1 são tipicamente excludentes em timing — empresa em busca de eficiência já passou pelo pico de expansão acelerada.

---

#### H6 — Pré-Contratação Transformacional | P₀ = 0.12

**Descrição Teórica da Dor**

A pré-contratação transformacional é o momento de maior receptividade a mudanças em uma empresa: uma nova liderança sênior (C-level, Diretora, Head) acaba de entrar ou está prestes a entrar, trazendo mandato explícito para transformar área ou processo. Esta entrada cria uma janela de oportunidade porque o novo líder precisa demonstrar impacto rapidamente e está ativamente buscando soluções.

No ICP SocialSelling, este sinal é o de maior valor preditivo para urgência de compra (maior incremento unitário de S_intent do sistema). A founder que recém contratou uma Diretora Comercial, por exemplo, está sinalizando que estruturou budget e mandato para transformar vendas — momento ideal para abordagem.

A dificuldade desta hipótese é o timing: a janela dura tipicamente 60–90 dias após a contratação. Depois deste período, o novo líder já tomou suas decisões iniciais e a receptividade cai.

**Supporting Evidence**

| Sinal Observável | Fonte | P(E\|H) estimado |
|---|---|---|
| Nova conexão de 1º grau no LinkedIn com cargo ≥ Director / Head / VP nos últimos 60 dias | LinkedIn | 0.85 |
| Post de boas-vindas a novo colaborador sênior (CEO/Founder apresentando novo líder) | Instagram / LinkedIn | 0.80 |
| Vaga de liderança sênior publicada e depois removida (proxy de fechamento) nos últimos 90 dias | LinkedIn Jobs | 0.75 |
| Bio atualizada da empresa mencionando novo membro da liderança | LinkedIn | 0.65 |

**Contradicting Evidence**

| Sinal | Fonte | Impacto no Posterior |
|---|---|---|
| Liderança sênior declaradamente estável há >18 meses sem mudanças | LinkedIn | Reduz posterior em ~45% |
| Cultura de continuidade explícita ("nosso time de liderança está conosco desde o início") | Instagram / LinkedIn | Reduz posterior em ~30% |

**Missing Evidence (Entropia)**

| Dado Ausente | Impacto Shannon (bits) | Recomendação de Busca |
|---|---|---|
| Briefing ou mandato declarado do novo líder | 0.20 bits | Posts do próprio novo líder no LinkedIn sobre seus objetivos no cargo |
| Escopo real do mandato transformacional | 0.18 bits | Entrevistas, posts de 30/60/90 dias do novo líder |

**Impacto no O_score:** S_intent incrementado em +0.15 a +0.25 — maior incremento unitário do sistema para um único sinal de hipótese, refletindo a altíssima urgência associada à janela transformacional.

**Impacto no C_score:** Incrementa quando LinkedIn Jobs confirma fechamento da vaga de liderança (evidência de que a contratação realmente ocorreu, não apenas que estava planejada).

**Interações:** Co-ocorrência com H1 (Expansão Operacional) indica empresa crescendo E estruturando liderança simultaneamente — máxima janela de oportunidade. Co-ocorrência com H9 (Transição de Modelo) sugere mudança organizacional profunda em curso.

---

#### H7 — Crise de Retenção | P₀ = 0.10

**Descrição Teórica da Dor**

A crise de retenção ocorre quando a empresa perde colaboradores em ritmo superior à capacidade de substituição, criando um ciclo destrutivo: a saída de pessoas gera sobrecarga nos que ficam, que por sua vez aumenta a probabilidade de novas saídas. Para fundadoras do ICP, este ciclo é particularmente danoso porque cada colaboradora leva consigo conhecimento não documentado e relacionamentos com clientes.

A dor manifesta-se como vagas recorrentes para o mesmo cargo (o sinal mais confiável do sistema para esta hipótese — vaga que fecha e reabre indica que a substituição anterior não funcionou), posts sobre cultura e valores (frequentemente reação à saída de pessoas), e ausência de posts de longevidade ("fulana completa 2 anos conosco").

O prior baixo (0.10) reflete que nem toda empresa do ICP vive crise de retenção — é um estado patológico, não a condição basal.

**Supporting Evidence**

| Sinal Observável | Fonte | P(E\|H) estimado |
|---|---|---|
| Múltiplas vagas para o mesmo cargo nos últimos 6 meses (proxy de turnover) | LinkedIn Jobs | 0.80 |
| Posts sobre cultura, valores e retenção de talentos com tom de esforço/preocupação | Instagram / LinkedIn | 0.65 |
| Ausência de posts de aniversário de colaboradoras (nenhum "X anos conosco") | Instagram | 0.55 |
| Menção direta a dificuldades de manter equipe | Instagram / LinkedIn | 0.70 |

**Contradicting Evidence**

| Sinal | Fonte | Impacto no Posterior |
|---|---|---|
| Time estável há >18 meses com posts de longevidade recorrentes | LinkedIn / Instagram | Reduz posterior em ~40% |
| Posts celebrando aniversários de colaboradoras com frequência | Instagram | Reduz posterior em ~35% |

**Missing Evidence (Entropia)**

| Dado Ausente | Impacto Shannon (bits) | Recomendação de Busca |
|---|---|---|
| Taxa de turnover real (número de saídas / headcount médio) | 0.22 bits | Glassdoor reviews, LinkedIn (ex-funcionárias que atualizaram cargo) |
| Causas declaradas de saída | 0.18 bits | Glassdoor, posts de ex-colaboradoras no LinkedIn |

**Impacto no O_score:** S_intent incrementado em +0.06 a +0.10 — sinal de urgência moderado, mais relevante quando padrão recorrente (≥2 ciclos de mesma vaga) é detectado.

**Impacto no C_score:** Incrementa quando padrão recorrente de mesma vaga é detectado — a evidência de ciclo de reposição é mais robusta e aumenta a confiança no diagnóstico.

**Interações:** Co-ocorrência com H3 (Gargalo de Liderança Intermediária) amplifica urgência — a ausência de lideranças intermediárias é frequentemente causa estrutural da crise de retenção. Co-ocorrência com H11 (Dor de Qualidade) sugere degradação sistêmica: a equipe que sai leva o conhecimento que garantia a qualidade.

---

#### H8 — Pressão de Vendas | P₀ = 0.18

**Descrição Teórica da Dor**

A pressão de vendas emerge quando a founder ancora o processo comercial em si mesma — ela é a principal (ou única) vendedora, responsável por prospectar, qualificar, apresentar e fechar. Esta configuração tem um teto natural: o tempo da founder. Quando o pipeline de oportunidades ultrapassa este teto, a empresa enfrenta perda de receita potencial simplesmente por incapacidade de atender à demanda.

No ICP, este padrão é especialmente prevalente em Consultoria e Advocacia, onde a reputação pessoal da founder é o principal ativo comercial e a venda é intrinsecamente relacional. A dor é dupla: a founder sente o peso de ser o único motor de crescimento de receita, e a empresa fica vulnerável a ciclos de feast-or-famine conforme o bandwidth da founder flutua.

**Supporting Evidence**

| Sinal Observável | Fonte | P(E\|H) estimado |
|---|---|---|
| Posts sobre meta de vendas, novos clientes como conquista pessoal da founder | Instagram / LinkedIn | 0.70 |
| Vaga para SDR, BDR, Inside Sales ou Executiva Comercial aberta | LinkedIn Jobs | 0.75 |
| Founder com título de "Sócia Fundadora + Diretora Comercial" ou similar | LinkedIn | 0.65 |
| Ausência de qualquer colaboradora com cargo comercial visível | LinkedIn | 0.60 |

**Contradicting Evidence**

| Sinal | Fonte | Impacto no Posterior |
|---|---|---|
| Equipe de vendas estruturada com ≥2 profissionais comerciais listados | LinkedIn | Reduz posterior em ~45% |
| CRM declarado em uso com equipe de SDRs mencionada | LinkedIn / Instagram | Reduz posterior em ~40% |
| Posts sobre pipeline e funil gerenciados por equipe (não pela founder) | Instagram / LinkedIn | Reduz posterior em ~30% |

**Missing Evidence (Entropia)**

| Dado Ausente | Impacto Shannon (bits) | Recomendação de Busca |
|---|---|---|
| Processo comercial interno (quem faz o quê no ciclo de vendas) | 0.18 bits | LinkedIn de colaboradoras + posts sobre vendas da empresa |

**Impacto no O_score:** Componente Fit incrementado em +0.08 a +0.14 — encaixe direto de produto quando a pressão de vendas está no teto da founder.

**Impacto no C_score:** Neutro — a hipótese de pressão de vendas não afeta diretamente a confiança de scoring, pois a evidência é observável mas o mecanismo interno é difícil de validar externamente.

**Interações:** Co-ocorrência com H2 (Centralização Excessiva) amplifica Fit — a founder centraliza inclusive o comercial. Co-ocorrência com H10 (Sobrecarga do Fundador) é quase certa quando H8 está ACTIVE — a founder que vende, entrega e gerencia está em sobrecarga estrutural.

---

#### H9 — Transição de Modelo | P₀ = 0.08

**Descrição Teórica da Dor**

A transição de modelo de negócio é um evento de alta magnitude e alta incerteza: a empresa está mudando fundamentalmente como gera valor (ex.: de consultoria por projeto para SaaS, de serviço avulso para retainer, de produto físico para digital). Esta mudança requer novos processos, novas competências, nova forma de comunicar o valor, e frequentemente, novas pessoas.

A dor desta hipótese é a inadequação sistêmica — as pessoas, processos e ferramentas que funcionaram para o modelo antigo não necessariamente funcionam para o novo. A founder navega uma transição com risco alto de execução enquanto mantém o negócio original funcionando.

O prior baixo (0.08) reflete que transição de modelo é um evento discreto e raro — a maioria das empresas do ICP não está em transição em um dado momento.

**Supporting Evidence**

| Sinal Observável | Fonte | P(E\|H) estimado |
|---|---|---|
| Posts anunciando novo produto, serviço ou linha de negócio incompatível com o modelo atual | Instagram / LinkedIn | 0.80 |
| Mudança de messaging no bio do Instagram ou LinkedIn nos últimos 90 dias | Instagram / LinkedIn | 0.75 |
| Vaga com escopo incompatível com o modelo declarado de negócio | LinkedIn Jobs | 0.70 |
| Mudança de CNPJ em atividade econômica principal (CNAE) | CNPJ.ws | 0.65 |

**Contradicting Evidence**

| Sinal | Fonte | Impacto no Posterior |
|---|---|---|
| Posicionamento declarado estável há >24 meses sem mudança de messaging | Instagram / LinkedIn | Reduz posterior em ~50% |
| Zero posts sobre novos produtos ou serviços nos últimos 12 meses | Instagram / LinkedIn | Reduz posterior em ~35% |

**Missing Evidence (Entropia)**

| Dado Ausente | Impacto Shannon (bits) | Recomendação de Busca |
|---|---|---|
| Roadmap de produto/serviço futuro | 0.22 bits | Posts de planejamento, entrevistas, apresentações públicas |
| Decisão interna sobre abandono do modelo anterior | 0.20 bits | Entrevistas, podcasts, lives com a founder |

**Impacto no O_score:** S_intent incrementado em +0.12 a +0.20 — transição de modelo cria necessidade aguda de instrumentos novos, mas timing é incerto.

**Impacto no C_score:** Reduz — alta incerteza sobre o timing da transição (quando exatamente o novo modelo estará operacional) diminui a confiança no diagnóstico e na receptividade a soluções externas.

**Interações:** Co-ocorrência com H6 (Pré-Contratação Transformacional) é o padrão de maior urgência combinada — nova liderança + novo modelo = janela máxima. Co-ocorrência com H4 (Automação) indica que o novo modelo provavelmente exige instrumentos que o modelo antigo não precisava.

---

#### H10 — Sobrecarga do Fundador | P₀ = 0.22

**Descrição Teórica da Dor**

A sobrecarga do fundador é o estado em que a founder opera consistentemente acima de sua capacidade sustentável, executando trabalho operacional que não deveria ser responsabilidade de quem lidera estrategicamente. É uma das hipóteses mais prevalentes no ICP (P₀=0.22) porque é estruturalmente inerente ao estágio de empresa de 5–30 colaboradores onde a founder ainda não completou a transição de operadora para líder.

A dor é existencial: a founder sabe que deveria estar pensando estratégia, mas passa a maior parte do tempo apagando incêndios operacionais. A externalização desta dor nas redes sociais é rica e frequente — posts de madrugada, relatos de finais de semana trabalhando, posts sobre "quando será que vou conseguir sair da operação" são evidências de alta especificidade.

Esta hipótese é especialmente relevante para o produto SocialSelling porque a sobrecarga do fundador frequentemente motiva a busca por inteligência automatizada — qualquer ferramenta que economize tempo de pesquisa manual é receptiva.

**Supporting Evidence**

| Sinal Observável | Fonte | P(E\|H) estimado |
|---|---|---|
| Posts explícitos sobre falta de tempo para pensar estratégia ("quero sair da operação") | Instagram / LinkedIn | 0.75 |
| Posts de madrugada (22h–6h) ou finais de semana com conteúdo operacional | Instagram | 0.65 |
| Founder executando trabalho claramente operacional (respondendo clientes, fazendo entregas) | Instagram | 0.70 |
| Bio com múltiplos chapéus ("founder + comercial + atendimento + financeiro") | LinkedIn | 0.60 |

**Contradicting Evidence**

| Sinal | Fonte | Impacto no Posterior |
|---|---|---|
| COO ou Diretora de Operações declarada com presença pública ativa | LinkedIn / Instagram | Reduz posterior em ~50% — há alguém estruturalmente responsável pela operação |
| Equipe de operações visível e com autonomia pública ("meu time resolve X") | Instagram / LinkedIn | Reduz posterior em ~35% |

**Missing Evidence (Entropia)**

| Dado Ausente | Impacto Shannon (bits) | Recomendação de Busca |
|---|---|---|
| Estrutura de governança interna (quem toma quais decisões) | 0.18 bits | Entrevistas, podcasts, organograma |

**Impacto no O_score:** S_intent incrementado em +0.08 a +0.14; quando H2 (Centralização) está co-ocorrendo, o incremento combinado pode atingir +0.20 a +0.25.

**Impacto no C_score:** Incrementa quando padrão comportamental no Instagram é consistente (≥3 posts nos últimos 30 dias com vocabulário de sobrecarga) — consistência temporal é forte indicador de estado estrutural, não de momento isolado.

**Interações:** Co-ocorrência com H2 (Centralização Excessiva) é o par mais frequente e mais amplificador do sistema — a founder que centraliza inevitavelmente sobrecarrega. Co-ocorrência com H8 (Pressão de Vendas) indica que a sobrecarga tem componente comercial significativo.

---

#### H11 — Dor de Qualidade de Entrega | P₀ = 0.12

**Descrição Teórica da Dor**

A dor de qualidade de entrega emerge quando a empresa cresce em volume de clientes ou projetos mas não consegue manter o padrão de qualidade que caracterizou seus primeiros anos. O crescimento sem processos estruturados de qualidade gera inconsistência de entrega — alguns clientes recebem o produto excelente, outros recebem algo abaixo do prometido.

No ICP, esta hipótese é especialmente relevante em Advocacia (onde erros de processo têm consequências jurídicas para o cliente) e em Consultoria (onde a reputação é o único ativo). A founder que experimenta esta dor frequentemente a expressa como "dificuldade de escalar sem perder a essência" ou "qualidade que só eu garanto".

A observação desta dor é difícil — comentários negativos são raros em redes sociais gerenciadas ativamente, e a ausência de depoimentos não é prova de insatisfação. Por isso, vagas de QA são o sinal mais objetivo disponível, pois representam ação concreta da empresa em resposta à dor percebida.

**Supporting Evidence**

| Sinal Observável | Fonte | P(E\|H) estimado |
|---|---|---|
| Posts sobre padrão de qualidade como desafio ou compromisso explícito | Instagram / LinkedIn | 0.65 |
| Vaga de QA, Analista de Qualidade ou Supervisora de Entregas | LinkedIn Jobs | 0.70 |
| Comentário de cliente insatisfeito em post público (ou resposta defensiva da founder a comentário) | Instagram | 0.75 |
| Menções veladas a reclamações ("aprendemos muito com esse caso e melhoramos") | Instagram / LinkedIn | 0.60 |

**Contradicting Evidence**

| Sinal | Fonte | Impacto no Posterior |
|---|---|---|
| Depoimentos de clientes satisfeitos recentes e frequentes (≥3 nos últimos 60 dias) | Instagram / LinkedIn | Reduz posterior em ~30% |
| NPS alto declarado publicamente ou certificação de qualidade obtida | LinkedIn / Site | Reduz posterior em ~40% |

**Missing Evidence (Entropia)**

| Dado Ausente | Impacto Shannon (bits) | Recomendação de Busca |
|---|---|---|
| Satisfação de cliente (NPS ou equivalente) | 0.25 bits | Glassdoor, Google Reviews, ReclameAqui |
| Taxa de churn de clientes | 0.22 bits | Posts sobre longevidade de clientes, estudos de caso |

**Impacto no O_score:** Componente Fit incrementado em +0.06 a +0.12 quando evidência de dor de qualidade é confirmada.

**Impacto no C_score:** Reduz — a dor de qualidade é difícil de observar publicamente com alta certeza. Comentários negativos são raros em redes sociais gerenciadas ativamente, e a ausência de evidência não é evidência de ausência. A incerteza residual permanece alta.

**Interações:** Co-ocorrência com H3 (Gargalo de Liderança Intermediária) é causalmente consistente — a ausência de lideranças intermediárias gera inconsistência de entrega. Co-ocorrência com H7 (Crise de Retenção) sugere ciclo vicioso: queda de qualidade gera insatisfação de clientes, pressão sobre equipe e novas saídas.

---

#### H12 — Expansão Geográfica | P₀ = 0.10

**Descrição Teórica da Dor**

A expansão geográfica representa a decisão de operar em mercado(s) além do local de origem — seja abrindo escritório em outra cidade, seja contratando equipe em outra região, seja atendendo clientes em localização diferente. Esta expansão cria necessidades operacionais novas: gestão de equipe remota ou distribuída, processos que funcionem sem presença física da founder, e instrumentos de coordenação que transcendam a proximidade geográfica.

No ICP, expansão geográfica é um sinal de maturidade e ambição — indica que o modelo de negócio provou-se suficientemente robusto para justificar a complexidade adicional de operar em múltiplas localidades.

O prior moderado-baixo (0.10) reflete que expansão geográfica é um evento relativamente raro no recorte de empresas de 5–30 colaboradores, embora existente e plenamente observável via sinais públicos.

**Supporting Evidence**

| Sinal Observável | Fonte | P(E\|H) estimado |
|---|---|---|
| Post anunciando nova filial, escritório ou operação em outra cidade/estado | Instagram / LinkedIn | 0.85 |
| Vaga publicada com localização diferente da sede declarada da empresa | LinkedIn Jobs | 0.80 |
| Engajamento consistente em eventos ou conteúdo de outra região | Instagram | 0.65 |
| Menção a clientes ou projetos em outra localidade como padrão, não exceção | Instagram / LinkedIn | 0.60 |

**Contradicting Evidence**

| Sinal | Fonte | Impacto no Posterior |
|---|---|---|
| Declaração explícita de operação local ou regional sem planos de expansão | Instagram / LinkedIn | Reduz posterior em ~45% |
| Equipe 100% remota declarada sem âncora geográfica nova (empresa nativa remota) | LinkedIn | Reduz posterior em ~30% — expansão geográfica não é o padrão, é o modelo base |

**Missing Evidence (Entropia)**

| Dado Ausente | Impacto Shannon (bits) | Recomendação de Busca |
|---|---|---|
| Plano formal de expansão geográfica | 0.18 bits | Entrevistas, posts de planejamento anual, pitch decks públicos |
| Timing de abertura da nova unidade | 0.15 bits | Posts de construção/reforma, vagas com data de início |

**Impacto no O_score:** S_intent incrementado em +0.10 a +0.16 quando confirmada nova localização ativa.

**Impacto no C_score:** Incrementa quando LinkedIn Jobs confirma vaga em nova localização — evidência de que a expansão é real e não apenas planejada.

**Interações:** Co-ocorrência com H1 (Expansão Operacional) é o padrão mais comum — crescimento orgânico que eventualmente justifica presença física em outro mercado. Co-ocorrência com H3 (Gargalo de Liderança) é problemático — expansão sem liderança intermediária multiplica os gargalos existentes.

---

#### H13 — Pressão Regulatória | P₀ = 0.08

**Descrição Teórica da Dor**

A pressão regulatória emerge quando uma mudança normativa externa impõe à empresa a obrigação de adequar processos, contratar competências específicas (DPO, Compliance Officer), ou demonstrar conformidade até um prazo. Para o ICP, esta pressão é especialmente relevante em três cenários: LGPD (todas as empresas com dados pessoais de clientes), regulações setoriais de Advocacia (OAB), e certificações técnicas em Engenharia (ISO, ABNT).

A urgência desta hipótese é a mais concreta do sistema — é a única onde há um prazo externo inapelável. Uma empresa que precisa ser LGPD-compliant até certa data não tem a opção de procrastinar indefinidamente. Este elemento de prazo é o que torna H13 o trigger de urgência mais imediata e concreto do catálogo.

O prior baixo (0.08) reflete que nem sempre há uma pressão regulatória ativa — é um estado que depende do calendário normativo externo e do estágio de maturidade atual da empresa em relação à regulação aplicável.

**Supporting Evidence**

| Sinal Observável | Fonte | P(E\|H) estimado |
|---|---|---|
| Posts sobre conformidade, auditoria, certificação ou adequação regulatória | Instagram / LinkedIn | 0.80 |
| Vaga para Compliance Officer, DPO, Analista de Regulação ou Qualidade Regulatória | LinkedIn Jobs | 0.85 |
| Menção explícita a prazo regulatório ou data de auditoria | Instagram / LinkedIn | 0.90 |
| Segmento de atuação correlacionado com regulação conhecida e ativa (LGPD, CVM, ANVISA, CREA) | CNPJ.ws (CNAE) | 0.70 |

**Contradicting Evidence**

| Sinal | Fonte | Impacto no Posterior |
|---|---|---|
| Certificações já obtidas e publicadas recentemente (ISO, certificado de conformidade) | LinkedIn / Site | Reduz posterior em ~50% — adequação já concluída |
| Declaração explícita de auditoria concluída com êxito | LinkedIn / Instagram | Reduz posterior em ~55% |

**Missing Evidence (Entropia)**

| Dado Ausente | Impacto Shannon (bits) | Recomendação de Busca |
|---|---|---|
| Escopo da regulação aplicável ao negócio específico | 0.20 bits | CNAE + mapeamento de regulação setorial |
| Maturidade atual de conformidade da empresa | 0.18 bits | Entrevistas, posts técnicos, certificações listadas no LinkedIn |

**Impacto no O_score:** S_intent incrementado em +0.15 a +0.22 — trigger de urgência mais concreta e imediata do sistema, superando até H6 quando prazo regulatório é confirmado.

**Impacto no C_score:** Incrementa quando segmento do ICP correlaciona diretamente com regulação conhecida — a correlação entre CNAE e regulação aplicável é determinística para os setores do ICP, elevando a confiança no diagnóstico sem necessidade de evidência adicional.

**Interações:** Co-ocorrência com H4 (Automação) é frequente — adequação regulatória frequentemente exige automação de registros e trilhas de auditoria. H13 é praticamente independente das demais hipóteses em termos de causalidade — a pressão regulatória é exógena ao estado operacional interno da empresa.

---

#### H14 — Sócio Novo / Reestruturação Societária | P₀ = 0.07

**Descrição Teórica da Dor**

A entrada de um novo sócio ou uma reestruturação societária significativa representa uma das maiores janelas de transformação organizacional. O novo sócio traz capital, mas também traz mandato para mudanças — novas prioridades, novos processos, frequentemente uma nova visão de como a empresa deve operar. A founder que recebe este capital se compromete implicitamente com uma agenda de profissionalização.

No ICP, esta hipótese é mais rara (P₀=0.07) mas de alto valor quando confirmada. A reestruturação societária é detectável via dados de CNPJ — alterações no quadro societário são registradas na Junta Comercial e refletidas nos dados públicos do CNPJ.ws com latência de 15–30 dias.

**Supporting Evidence**

| Sinal Observável | Fonte | P(E\|H) estimado |
|---|---|---|
| Anúncio explícito de novo sócio ou sócia em post da founder | Instagram / LinkedIn | 0.85 |
| Alteração cadastral no CNPJ (quadro societário) detectada via CNPJ.ws | CNPJ.ws | 0.90 |
| Novo perfil LinkedIn com cargo de Partner/Sócio conectado à empresa | LinkedIn | 0.75 |
| Post de boas-vindas a novo sócio ou anúncio de aporte | Instagram / LinkedIn | 0.80 |

**Contradicting Evidence**

| Sinal | Fonte | Impacto no Posterior |
|---|---|---|
| Estrutura societária declarada como estável há >24 meses sem mudanças | CNPJ.ws + LinkedIn | Reduz posterior em ~50% |
| Declaração explícita de não aceitar sócios ("bootstrapped por escolha") | Instagram / LinkedIn | Reduz posterior em ~40% |

**Missing Evidence (Entropia)**

| Dado Ausente | Impacto Shannon (bits) | Recomendação de Busca |
|---|---|---|
| Quadro societário formal atualizado (nome e participação dos sócios) | 0.15 bits | CNPJ.ws quadro societário |
| Termos do acordo societário (o que o novo sócio exige em troca do capital) | 0.12 bits | Entrevistas, posts sobre a parceria |

**Impacto no O_score:** S_intent incrementado em +0.08 a +0.14 — sinal de que há capital novo e mandato para mudança.

**Impacto no C_score:** Incrementa quando CNPJ.ws confirma a alteração societária — evidência objetiva e não ambígua que eleva significativamente a confiança no diagnóstico.

**Interações:** Co-ocorrência com H9 (Transição de Modelo) é frequente — novo sócio frequentemente é o catalisador de mudança de modelo. Co-ocorrência com H6 (Pré-Contratação Transformacional) sugere empresa em fase de profissionalização acelerada com múltiplos vetores de mudança simultâneos.

---

#### H15 — Dor de Visibilidade / Marca | P₀ = 0.15

**Descrição Teórica da Dor**

A dor de visibilidade é a incapacidade de gerar novos clientes por canais que não dependam da rede de indicações pessoais da founder. A empresa existe, entrega bem, tem clientes satisfeitos — mas o pipeline de novos clientes é 100% dependente de "alguém que indicou", o que cria volatilidade e teto de crescimento definido pelo tamanho da rede pessoal da founder.

No ICP, esta hipótese é especialmente relevante porque fundadoras de serviços profissionais (Advocacia, Consultoria) têm uma cultura de crescimento por indicação que funcionou no início mas se torna limitante na faixa de R$150k–R$400k/mês de faturamento, quando a empresa precisa de canais escaláveis.

A observação desta hipótese é paradoxalmente possível via Instagram — baixo engajamento orgânico no próprio perfil da empresa é evidência direta de invisibilidade. O censor que monitora o engajamento pode calcular benchmarks do setor e identificar desvios com alta objetividade.

**Supporting Evidence**

| Sinal Observável | Fonte | P(E\|H) estimado |
|---|---|---|
| Posts explícitos sobre dificuldade de atrair novos clientes por canais orgânicos | Instagram / LinkedIn | 0.70 |
| Baixo engajamento orgânico consistente (taxa abaixo de 2% por post nos últimos 30 dias) | Instagram | 0.65 |
| Menção explícita à dependência de indicações como único canal de aquisição | Instagram / LinkedIn | 0.75 |
| Vaga para Marketing, Growth, Social Media ou Conteúdo | LinkedIn Jobs | 0.70 |

**Contradicting Evidence**

| Sinal | Fonte | Impacto no Posterior |
|---|---|---|
| Alto engajamento orgânico consistente (>5% por post) e presença em múltiplos canais | Instagram | Reduz posterior em ~40% |
| Declaração de budget de mídia paga ou campanha de aquisição ativa | LinkedIn / Instagram | Reduz posterior em ~35% |
| Presença regular em veículos de mídia especializados (entrevistas, artigos publicados) | Tavily | Reduz posterior em ~30% |

**Missing Evidence (Entropia)**

| Dado Ausente | Impacto Shannon (bits) | Recomendação de Busca |
|---|---|---|
| Estratégia de marketing atual (orgânico, pago, misto) | 0.18 bits | Posts sobre marketing, entrevistas, vagas de marketing da empresa |
| Budget alocado para aquisição de clientes | 0.15 bits | Vagas de marketing com faixa salarial, posts sobre investimento em marketing |

**Impacto no O_score:** Componente Fit incrementado em +0.06 a +0.10 quando dor de visibilidade é confirmada por baixo engajamento diretamente observável.

**Impacto no C_score:** Incrementa quando baixo engajamento é diretamente observável no perfil — o C_score reflete que a evidência é objetiva e calculada, não inferida de declarações ambíguas.

**Interações:** Co-ocorrência com H8 (Pressão de Vendas) amplifica urgência — a founder que é a única vendedora E não tem canal de geração de leads está em máxima pressão comercial. H15 e H1 (Expansão Operacional) são frequentemente excludentes em timing — empresa crescendo rapidamente geralmente não tem problema de visibilidade naquele momento.

---

## 3. MOTOR DE ATUALIZAÇÃO RECURSIVA BAYESIANA

### 3.1 Formulação Matemática Completa

#### Regra de Bayes com Normalização sobre Hipóteses Ativas

O motor de atualização processa evidências sequencialmente sobre o conjunto de hipóteses ativas `H = {H₁, H₂, ..., H₁₅}`. Para cada nova evidência `Eₜ`, o posterior é calculado por:

```
P(Hᵢ | E₁, ..., Eₜ) =      P(Eₜ | Hᵢ) × P(Hᵢ | E₁, ..., Eₜ₋₁)
                        ──────────────────────────────────────────────────────
                        Σⱼ P(Eₜ | Hⱼ) × P(Hⱼ | E₁, ..., Eₜ₋₁)
```

onde o denominador é o normalizador `Z`, calculado sobre **todas as hipóteses ativas** (hipóteses rejeitadas são excluídas do denominador para evitar que evidência indireta as reanime sem gatilho explícito).

O complemento `¬Hᵢ` é tratado como hipótese agregada com:
```
P(Eₜ | ¬Hᵢ) = [Σⱼ≠ᵢ P(Eₜ | Hⱼ) × P(Hⱼ)] / [Σⱼ≠ᵢ P(Hⱼ)]
```

Para simplificação computacional, o sistema usa a aproximação de dois termos:
```
P(Hᵢ | Eₜ) =          P(Eₜ | Hᵢ) × P(Hᵢ)
              ────────────────────────────────────────────────────────────
              P(Eₜ | Hᵢ) × P(Hᵢ)  +  P(Eₜ | ¬Hᵢ) × (1 - P(Hᵢ))
```

onde `P(Eₜ | ¬Hᵢ)` é configurado por hipótese baseado no conjunto Contradicting — tipicamente entre 0.12 e 0.25 para evidências Supporting (a evidência pode ocorrer mesmo quando a hipótese é falsa, mas com menor probabilidade).

#### Pseudocódigo do Motor de Atualização

```python
def bayesian_update(
    prior: float,
    p_e_given_h: float,
    p_e_given_not_h: float,
) -> float:
    """
    Atualização bayesiana sequencial para uma única hipótese.
    Retorna o posterior P(H|E).
    """
    numerator = p_e_given_h * prior
    denominator = numerator + p_e_given_not_h * (1.0 - prior)

    if denominator == 0.0:
        # Impossível: evidência não pode ocorrer sob nenhuma hipótese.
        # Retorna prior inalterado com flag de anomalia.
        return prior

    return numerator / denominator


def process_evidence_batch(
    hypothesis_id: str,
    prior: float,
    evidence_list: list[dict],
    # cada item: {type: "supporting"|"contradicting", p_e_given_h: float, p_e_given_not_h: float}
    threshold_saturation: int = 5,
) -> dict:
    """
    Processa sequencialmente todas as evidências de uma hipótese.
    Retorna posterior final, tripla omega e estado.
    """
    posterior = prior
    n_supporting = 0
    n_total = 0

    for evidence in evidence_list:
        if evidence["type"] == "supporting":
            p_e_given_h = evidence["p_e_given_h"]
            p_e_given_not_h = evidence.get("p_e_given_not_h", 0.20)
            posterior = bayesian_update(posterior, p_e_given_h, p_e_given_not_h)
            n_supporting += 1
        elif evidence["type"] == "contradicting":
            # Para Contradicting: P(E|H) é baixo, P(E|¬H) é alto
            p_e_given_h = evidence.get("p_e_given_h", 0.15)
            p_e_given_not_h = evidence["p_e_given_not_h"]
            posterior = bayesian_update(posterior, p_e_given_h, p_e_given_not_h)
        n_total += 1

    # Mapeamento para tripla omega
    u_residual = max(0.0, 1.0 - n_supporting / threshold_saturation)
    b = posterior * (1.0 - u_residual)
    d = (1.0 - posterior) * (1.0 - u_residual)
    u = u_residual

    # Determinação de estado
    if posterior < 0.15:
        state = "REJECTED"
    elif posterior >= 0.45 and n_supporting >= 3:
        state = "ACTIVE"
    else:
        state = "CANDIDATE"

    return {
        "hypothesis_id": hypothesis_id,
        "posterior": round(posterior, 6),
        "omega": (round(b, 6), round(d, 6), round(u, 6)),
        "state": state,
        "n_supporting": n_supporting,
        "n_total": n_total,
        "u_residual": round(u_residual, 6),
    }
```

---

### 3.2 Mapeamento Posterior → Tripla ω com u_residual

O mapeamento converte o posterior escalar `P(Hᵢ|E)` em tripla subjetiva, preservando a incerteza residual proporcional à escassez de evidências:

```
u_residual = max(0,  1 - n_evidências_Supporting / threshold_saturation)

b = P(Hᵢ|E) × (1 - u_residual)
d = (1 - P(Hᵢ|E)) × (1 - u_residual)
u = u_residual

threshold_saturation = 5  (evidências Supporting para saturação completa)
```

**Propriedades do mapeamento:**
- Com 0 evidências Supporting: `u_residual = 1.0` → `b = 0`, `d = 0`, `u = 1.0` — hipótese em vacuidade total independente do posterior.
- Com 3 evidências Supporting: `u_residual = 0.40` → `b = posterior × 0.60`, `d = (1-posterior) × 0.60`, `u = 0.40`.
- Com 5 ou mais evidências Supporting: `u_residual = 0.0` → `b = posterior`, `d = 1 - posterior`, `u = 0` — saturação completa.

**Tabela de u_residual por quantidade de evidências Supporting:**

| n_supporting | u_residual | Fator de escala (1 − u) | Interpretação |
|---|---|---|---|
| 0 | 1.000 | 0.000 | Vacuidade total — prior apenas |
| 1 | 0.800 | 0.200 | Sinal fraco, altíssima incerteza |
| 2 | 0.600 | 0.400 | Dois sinais, incerteza moderada-alta |
| 3 | 0.400 | 0.600 | Threshold ACTIVE (posterior condição) |
| 4 | 0.200 | 0.800 | Evidência robusta, incerteza residual baixa |
| 5 | 0.000 | 1.000 | Saturação completa |

---

### 3.3 Critérios de Transição de Estado

| Estado | Condição de Entrada | Condição de Saída | Efeitos no Sistema |
|---|---|---|---|
| **CANDIDATE** | `posterior < 0.45` OU `n_supporting < 3` | `posterior ≥ 0.45 AND n_supporting ≥ 3` → ACTIVE; `posterior < 0.15 com Contradicting suficientes` → REJECTED | Hipótese monitorada, contribui parcialmente ao O_score e C_score |
| **ACTIVE** | `posterior ≥ 0.45 AND n_supporting ≥ 3` | `posterior < 0.35` (deslocamento >0.10 por Contradicting) → CANDIDATE; `posterior < 0.15` → REJECTED | Hipótese contribui plenamente ao O_score (S_intent ou Fit) e Hypothesis_Confidence ao C_score |
| **REJECTED** | `posterior < 0.15` com pelo menos 2 evidências Contradicting presentes | Re-avaliação forçada por nova evidência Supporting forte (`P(E\|H) > 0.85`) → CANDIDATE | Hipótese excluída do denominador Bayesiano, excluída do O_score e C_score |

**Regra adicional — ACTIVE para CANDIDATE por estagnação de evidências:** Se uma hipótese ACTIVE não recebe nenhuma nova evidência Supporting em 30 dias e o `e_fresh` das evidências existentes decai abaixo de 0.40, ela transita para CANDIDATE independente do posterior — o sistema não mantém hipóteses ACTIVE com base em evidências estagnadas.

---

### 3.4 Re-avaliação Forçada

A re-avaliação forçada é disparada quando o posterior desloca mais de 0.15 em qualquer direção em um único ciclo de evidências:

```
|P(Hᵢ|Eₙ) - P(Hᵢ|Eₙ₋₁)| > 0.15  →  force_reevaluation = True
```

Quando `force_reevaluation = True`, o sistema executa:
1. Recalcula `u_residual` com a contagem atualizada de evidências Supporting.
2. Aplica Conflict Resolution Policy se `divergence_delta > 0.30`.
3. Reavalia o estado (CANDIDATE / ACTIVE / REJECTED) com os novos parâmetros.
4. Registra o evento no `v_cognitive_log` com timestamp, magnitude do deslocamento e evidência causadora.
5. Se o deslocamento for negativo (queda de posterior > 0.15), verifica se alguma hipótese ACTIVE deve transitar para CANDIDATE — proteção contra degradação silenciosa.

---

### 3.5 Exemplo Numérico Completo para H2 — 3 Ciclos Calculados

**Contexto:** Prospect "Carla Bittencourt Advocacia Empresarial", coleta via Instagram + LinkedIn. Hipótese H2 (Centralização Excessiva). `P₀ = 0.30`, `threshold_saturation = 5`.

---

#### Ciclo 1 — Duas Evidências Supporting

**Prior:** `P(H2) = 0.30`

**Evidência E1:** Founder é o único rosto público em todos os posts das últimas 12 semanas.
`P(E1|H2) = 0.75`, `P(E1|¬H2) = 0.20`

```
P(H2|E1) = (0.75 × 0.30) / (0.75 × 0.30 + 0.20 × 0.70)
          = 0.2250 / (0.2250 + 0.1400)
          = 0.2250 / 0.3650
          = 0.6164
```

**Evidência E2:** Post "Hoje mais uma vez fui eu que resolvi tudo. Fundadora é isso: você é o negócio."
`P(E2|H2) = 0.80`, `P(E2|¬H2) = 0.15`

```
P(H2|E1,E2) = (0.80 × 0.6164) / (0.80 × 0.6164 + 0.15 × 0.3836)
             = 0.4931 / (0.4931 + 0.0575)
             = 0.4931 / 0.5506
             = 0.8957
```

**Mapeamento para tripla ω após Ciclo 1:**
```
n_supporting = 2
u_residual   = max(0, 1 - 2/5) = 0.600

b = 0.8957 × (1 - 0.600) = 0.8957 × 0.400 = 0.358
d = (1 - 0.8957) × (1 - 0.600) = 0.1043 × 0.400 = 0.042
u = 0.600

ω_H2_ciclo1 = (0.358, 0.042, 0.600)
Verificação: 0.358 + 0.042 + 0.600 = 1.000 ✓
```

**Estado após Ciclo 1:** CANDIDATE
- `posterior = 0.8957 ≥ 0.45` ✓ mas `n_supporting = 2 < 3` — condição AND não satisfeita.
- Deslocamento: `|0.8957 - 0.30| = 0.5957 > 0.15` → `force_reevaluation = True`, evento registrado no `v_cognitive_log`.

---

#### Ciclo 2 — Uma Evidência Contradicting

**Prior do Ciclo 2:** `P(H2) = 0.8957`

**Evidência E3 (Contradicting):** LinkedIn mostra 3 colaboradoras com títulos de Coordenadora e Gerente de Projetos.
`P(E3|H2) = 0.10` (centralização é improvável se há coordenadoras formais), `P(E3|¬H2) = 0.75`

```
P(H2|E1,E2,E3) = (0.10 × 0.8957) / (0.10 × 0.8957 + 0.75 × 0.1043)
                = 0.0896 / (0.0896 + 0.0782)
                = 0.0896 / 0.1678
                = 0.5340
```

**Mapeamento para tripla ω após Ciclo 2:**
```
n_supporting = 2  (E3 é Contradicting, não incrementa n_supporting)
u_residual   = max(0, 1 - 2/5) = 0.600

b = 0.5340 × 0.400 = 0.214
d = (1 - 0.5340) × 0.400 = 0.4660 × 0.400 = 0.186
u = 0.600

ω_H2_ciclo2 = (0.214, 0.186, 0.600)
Verificação: 0.214 + 0.186 + 0.600 = 1.000 ✓
```

**Estado após Ciclo 2:** CANDIDATE
- `posterior = 0.5340 ≥ 0.45` ✓ mas `n_supporting = 2 < 3` — condição AND não satisfeita.
- Deslocamento negativo: `|0.5340 - 0.8957| = 0.3617 > 0.15` → `force_reevaluation = True`.
- Sistema verifica se hipótese deve transitar para REJECTED: `posterior = 0.5340 > 0.15` — permanece CANDIDATE.

---

#### Ciclo 3 — Duas Evidências Supporting Adicionais

**Prior do Ciclo 3:** `P(H2) = 0.5340`

**Evidência E4:** Cargo único "Sócia-Fundadora" no LinkedIn por 22 meses, sem co-founder listado.
`P(E4|H2) = 0.65`, `P(E4|¬H2) = 0.25`

```
P(H2|E1..E4) = (0.65 × 0.5340) / (0.65 × 0.5340 + 0.25 × 0.4660)
              = 0.3471 / (0.3471 + 0.1165)
              = 0.3471 / 0.4636
              = 0.7487
```

**Evidência E5:** Post às 23h47 de uma sexta-feira: "Aprovando proposta para cliente porque ninguém mais aprova aqui."
`P(E5|H2) = 0.80`, `P(E5|¬H2) = 0.12`

```
P(H2|E1..E5) = (0.80 × 0.7487) / (0.80 × 0.7487 + 0.12 × 0.2513)
              = 0.5990 / (0.5990 + 0.0302)
              = 0.5990 / 0.6292
              = 0.9520
```

**Mapeamento para tripla ω após Ciclo 3:**
```
n_supporting = 4  (E1, E2, E4, E5 são Supporting; E3 é Contradicting)
u_residual   = max(0, 1 - 4/5) = 0.200

b = 0.9520 × (1 - 0.200) = 0.9520 × 0.800 = 0.762
d = (1 - 0.9520) × (1 - 0.200) = 0.0480 × 0.800 = 0.038
u = 0.200

ω_H2_ciclo3 = (0.762, 0.038, 0.200)
Verificação: 0.762 + 0.038 + 0.200 = 1.000 ✓
```

**Estado após Ciclo 3:** ACTIVE
- `posterior = 0.9520 ≥ 0.45` ✓ E `n_supporting = 4 ≥ 3` ✓ — ambas as condições satisfeitas.
- Deslocamento: `|0.9520 - 0.5340| = 0.4180 > 0.15` → `force_reevaluation = True`, evento registrado.

**Resultados finais após Ciclo 3:**
```
Hypothesis_Confidence(H2) = b = 0.762   → componente do C_score
P(ω_H2) = b + P₀ × u = 0.762 + 0.30 × 0.200 = 0.762 + 0.060 = 0.822
S_intent(H2) = 0.822  →  incremento O_score componente Fit no teto da faixa (+0.18)
Estado final: ACTIVE | n_supporting=4 | u_residual=0.200
```

**Resumo dos 3 Ciclos:**

| Ciclo | Evidências processadas | n_supporting | Posterior | u_residual | b | d | u | Estado |
|---|---|---|---|---|---|---|---|---|
| 0 — prior | — | 0 | 0.300 | 1.000 | 0.000 | 0.000 | 1.000 | CANDIDATE |
| 1 | E1 + E2 Supporting | 2 | 0.896 | 0.600 | 0.358 | 0.042 | 0.600 | CANDIDATE |
| 2 | E3 Contradicting | 2 | 0.534 | 0.600 | 0.214 | 0.186 | 0.600 | CANDIDATE |
| 3 | E4 + E5 Supporting | 4 | 0.952 | 0.200 | 0.762 | 0.038 | 0.200 | **ACTIVE** |

---

*Fim do SDD-03. Documento gerado em 2026-06-01 para o projeto SocialSelling.*
*Documento anterior: `sdd_01_product_vision_and_core_dag.md` — Arquitetura LangGraph e DAG de fases.*
*Próximo documento relacionado: `sdd_04_sensory_search_and_finops_stopping.md` — Arquitetura de coleta e mecanismo de parada FinOps.*
