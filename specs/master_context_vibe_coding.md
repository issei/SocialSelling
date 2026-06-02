# MASTER CONTEXT — VIBE CODING LOCAL
## SocialSelling — Sistema de Inteligência de Prospecção B2B
### Versão: 1.0-LOCAL | Ambiente: Database-less, In-Memory, Gemini + Tavily

---

> **INSTRUÇÃO GERAL À IA GERADORA DE CÓDIGO**
> Este documento é o contexto operacional completo para geração de um SDD e código local do sistema SocialSelling. O sistema NÃO é um CRM, NÃO gerencia sequências de e-mail e NÃO persiste dados em banco de dados. Toda a inteligência roda em memória (Python TypedDict), usa Gemini como motor cognitivo e Tavily como motor de busca. O objetivo de cada ciclo é responder três perguntas: "Qual empresa abordar primeiro?", "Quem dentro dela é o verdadeiro agente de mudança?" e "O que falar para iniciar uma conversa personalizada?".

---

## DIFERENÇAS FUNDAMENTAIS: LOCAL vs. ENTERPRISE SDD

| Dimensão | Enterprise SDD (sdd_*.md) | Local — Vibe Coding |
|---|---|---|
| Persistência | PostgreSQL 16 + Aurora Serverless | Zero banco — estado em Python dict (RAM) |
| LLM Engine | OpenAI GPT-4 | Google Gemini Flash / Pro |
| Busca Web | Scrapers Instagram/LinkedIn + CNPJ.ws | Tavily Search API |
| Infraestrutura | AWS Lambda + API Gateway | Script Python local (CLI) |
| Orquestração | LangGraph com nós assíncronos | LangGraph simplificado ou pipeline síncrono |
| Output | REST API + XAI Payload JSON | Arquivo Markdown + JSON no terminal |
| Deploy | GitHub Actions + Terraform | `python main.py --seed leads.csv` |
| Custo por lead | Configurável via icp_contract | τ_FinOps = R$0,30 / lead (hard limit) |
| Autenticação | AWS Secrets Manager | Variáveis de ambiente (.env) |

---

## PILLAR 1: DOMAIN KNOWLEDGE & TARGET ICP TAXONOMY

### 1.1 Verticais de Negócio Estritas (4 setores-alvo)

O sistema deve identificar e filtrar leads exclusivamente nestas quatro verticais. Qualquer empresa fora delas recebe `disqualified=true` imediatamente, sem gastar tokens de análise.

#### Vertical 1 — Escritórios de Advocacia Corporativa

**Keywords de identificação no Tavily:** `advocacia corporativa`, `direito empresarial`, `escritório de advocacia`, `OAB`, `direito tributário`, `M&A`, `compliance`, `direito trabalhista corporativo`, `direito migratório`

**Como falam do negócio (vocabulário natural para o Gemini reconhecer):**
- Nunca dizem "empresa" — dizem **"escritório"**
- Nunca dizem "vender" — dizem **"fechar serviço"** ou **"contratação"**
- "Processo" = caso do cliente (não processo interno)
- "Prazo" é palavra crítica — aparece em toda conversa
- "Protocolar", "peticionar", "diligência", "duplo cheque" = vocabulário operacional
- "Reunião de alinhamento", "supervisor", "meta mínima/desejável/extra"

**Sinais de ICP válido no Tavily/perfil público:**
- CNPJ com CNAE 6911-7/00 (Atividades Jurídicas)
- Bio com "Sócia", "Advogada", "Escritório", "OAB/XX nº"
- Equipe visível em posts (fotos com colaboradores, anúncio de vagas)
- Menção a múltiplos clientes ou casos simultâneos

**NÃO usar com este público:** "empresa", "vender", "produto", "escalar", "funil de vendas", "cliente ideal"

---

#### Vertical 2 — Consultorias Empresariais e Financeiras

**Keywords de identificação:** `consultoria empresarial`, `consultoria financeira`, `controladoria`, `planejamento estratégico`, `CFO as a service`, `BPO financeiro`, `gestão financeira`, `consultoria de gestão`

**Como falam do negócio:**
- "Projeto" = unidade de trabalho (cada cliente é um projeto)
- "Entregável", "escopo", "proposta", "kick-off", "status"
- "Horas faturáveis" como métrica central
- "Metodologia", "framework", "governança" — não ter metodologia é constrangedor
- "Pipeline" para carteira em negociação
- "Ocupação" ou "alocação" para capacidade do time
- "ROI", "KPI", "OKR", "benchmark", "due diligence" são termos naturais

**Sinais de ICP válido:**
- CNAE 7020-4/00 (Consultoria em Gestão Empresarial)
- Posts sobre projetos com múltiplos clientes simultâneos
- Menção a "entrega" de diagnóstico ou plano estratégico

---

#### Vertical 3 — Software Houses e SaaS B2B

**Keywords de identificação:** `software house`, `SaaS`, `desenvolvimento de software`, `produto digital`, `fintech`, `plataforma B2B`, `tech startup`

**Como falam do negócio:**
- "Squad", "sprint", "backlog", "deploy", "roadmap", "feature"
- "Founder" ou "CEO", "CTO" para co-fundador técnico
- "MRR" como métrica central, "churn", "CAC", "LTV", "ARR"
- "Onboarding", "CS" (Customer Success), "SLA"
- "Daily", "retrospectiva", "OKR"
- "Agile", "Scrum", "Kanban" como vocabulário natural

**Sinais de ICP válido:**
- CNAE 6201-5/01 (Desenvolvimento de Programas de Computador)
- Posts sobre produto, funcionalidades, releases
- Menção a time técnico (devs, designers, PMs)
- Posts sobre IA/automação como gatilho de timing de ALTA conversão

---

#### Vertical 4 — Empresas de Engenharia

**Keywords de identificação:** `engenharia civil`, `construtora`, `consultoria de obras`, `gestão de projetos de engenharia`, `engenharia ambiental`, `ART`, `CREA`

**Como falam do negócio:**
- "Obra", "projeto", "laudo", "ART", "CREA/CAU"
- "Prazo de entrega", "medição", "aditivo", "cronograma físico-financeiro"
- "Fiscalização", "vistoria", "memorial descritivo"
- Centralização em torno do engenheiro sênior como único rosto técnico confiável

**Sinais de ICP válido:**
- CNAE 7112-0/00 (Serviços de Engenharia) ou similar
- Posts sobre obras, projetos, equipes em campo
- Menção a múltiplos projetos simultâneos

---

### 1.2 Dicionário Semântico de Linguagem de Dor

O Gemini deve classificar evidências de dor mapeando o que a fundadora **diz publicamente** para o que **realmente significa operacionalmente**. Este dicionário é injetado diretamente no prompt do motor de hipóteses.

#### Tabela de Tradução Semântica

| O que ela diz | Tradução operacional | Hipótese ativada | Peso de Atualização Bayesiana |
|---|---|---|---|
| "Estamos em fase de estruturação" | A empresa está em caos interno — processos inexistentes | H2 Centralização / H4 Automação | 0.75 |
| "Estou muito envolvida nos projetos" | Não consegue delegar; está presa na operação | H2 Centralização / H10 Sobrecarga | 0.80 |
| "Prefiro acompanhar de perto cada entrega" | Não confia na equipe para executar sem ela | H2 Centralização | 0.70 |
| "Estamos crescendo muito rápido" | A estrutura não acompanhou o crescimento | H1 Expansão / H2 Centralização | 0.75 |
| "Montando um time incrível" | Acabou de contratar sem processo de integração | H1 Expansão / H3 Liderança | 0.65 |
| "Foco total no negócio esse semestre" | Sobrecarregada; sente que está atrasada | H10 Sobrecarga | 0.70 |
| "Quero implementar IA no meu negócio" | Quer modernizar mas a base operacional não está pronta | H4 Automação (timing ALTA) | 0.85 |
| "Preciso organizar melhor meu tempo" | No operacional quando deveria estar no estratégico | H10 Sobrecarga / H2 Centralização | 0.72 |
| "Agenda lotada" | Gargalo de liderança; decisora única | H2 Centralização / H10 Sobrecarga | 0.68 |
| "Sem mim trava" | Centralização aguda; empresa depende 1-to-1 da fundadora | H2 Centralização | 0.90 |
| "Preciso reorganizar a casa" | Estrutura inexistente ou insuficiente para o tamanho atual | H2 Centralização / H4 Automação | 0.78 |
| "Não consigo sair da operação" | Presa no dia a dia; impossibilidade de delegar | H2 Centralização / H10 Sobrecarga | 0.88 |
| "Cresci mas me perdi" | Empresa superou a capacidade de gestão da fundadora | H1 Expansão / H2 Centralização | 0.82 |
| "Minha equipe não toca sem me acionar" | Ausência de processos e alçadas de decisão claras | H2 Centralização / H3 Liderança | 0.85 |
| "Sem mim perde qualidade" | Crença limitante — o processo pode capturar o padrão | H2 Centralização | 0.75 |
| "Estamos estruturando nossa equipe de vendas" | Sem processo comercial; crescimento por indicação | H8 Pressão de Vendas | 0.72 |
| "Precisa de aprovação da sócia" | Risco de ciclo longo — múltiplas decisoras | ⚠️ FLAG: ciclo de venda longo | N/A |

#### Denominador Comum de Dor (Cross-Vertical)

Independente do setor, quando a dor de gestão está presente, todas falam de forma parecida. O Gemini deve priorizar estas frases como sinais de timing **ALTA**:

```
"Tudo passa por mim."
"Sem mim trava."
"Não consigo sair da operação."
"Cresci mas me perdi."
"Preciso organizar a casa antes de crescer."
"Quero implementar IA mas sei que preciso organizar antes."
```

---

### 1.3 Parâmetros de Filtro do ICP (Confirmados)

```python
ICP_FILTERS = {
    "headcount_min": 5,
    "headcount_max": 30,
    "revenue_min_brl_monthly": 80_000,
    "revenue_max_brl_monthly": 500_000,
    "business_age_min_years": 3,
    "business_age_max_years": 10,
    "decision_maker_profile": "FOUNDER_SOLO",  # sem sócias com poder de veto visível
    "target_gender": "female_founder_preferred",
    "target_segments": [
        "Advocacia Corporativa",
        "Consultorias Empresariais e Financeiras",
        "Software Houses e SaaS B2B",
        "Empresas de Engenharia"
    ]
}
```

**Critérios de desqualificação automática (zero tokens gastos):**
- Operação solo sem sinal de equipe → `disqualified=true, reason="solo_operator"`
- Menos de 2 anos de negócio → `disqualified=true, reason="too_early_stage"`
- Perfil 100% pessoal sem empresa estruturada → `disqualified=true, reason="no_company"`
- Sinais de retração/corte de custos → `disqualified=true, reason="retracting"`
- Mais de 2 sócias sem decisora clara → `disqualified=true, reason="multi_founder_risk"`
- Setor fora das 4 verticais → `disqualified=true, reason="wrong_vertical"`

**Proxy de faturamento (inferência — sem acesso a dados contábeis):**
O Gemini deve inferir a faixa de faturamento usando estes proxies visuais:
- Equipe de 5-10 pessoas em setor de serviços B2B → R$80k-150k/mês estimado
- Equipe de 10-20 pessoas + escritório/sede visível → R$150k-300k/mês estimado
- Equipe de 20-30 pessoas + múltiplos clientes simultâneos + branding profissional → R$300k-500k/mês estimado
- Uncertainty padrão: `u=0.45` em todas as inferências de faturamento (não observável diretamente)

---

## PILLAR 2: HIGH-TICKET SOLUTION MECHANICS

### 2.1 Proposta de Valor Central (Para o CBG)

**Produto:** Programa de Acompanhamento Estratégico — R$18.000
**Duração:** 6 meses (3 meses ativos + 3 meses de suporte via WhatsApp)
**Framing oficial:** A especialista atua como **Diretora Estratégica Temporária** — entra no negócio, desenha o plano, supervisiona a execução, valida cada entrega e **sai deixando uma equipe autônoma** que funciona sem a presença constante da fundadora.

**Transformação central (estado de entrada → estado de saída):**

```
ESTADO DE ENTRADA:
  - Empresária presa na operação
  - Sendo o gargalo do próprio negócio
  - Decisões centralizadas — equipe sem autonomia
  - Crescimento travado por falta de estrutura

ESTADO DE SAÍDA (operacional):
  - Processos documentados
  - Equipe autônoma com responsabilidades claras
  - Rituais de gestão implementados
  - Estrutura pronta para escalar

ESTADO DE SAÍDA (emocional):
  - Sensação de controle sobre o próprio negócio
  - Clareza sobre o papel de líder
  - "Nunca me senti tanto no controle do escritório. Me fez evoluir profundamente
     como líder e principalmente humanamente." (depoimento real de cliente)
```

**Entregáveis concretos do programa (o CBG pode referenciar estes):**
1. Organograma com responsabilidades e alçadas de decisão
2. Processos do core business mapeados e documentados
3. Ferramentas de gestão configuradas e em uso pela equipe
4. Rituais de reunião e acompanhamento de metas implementados
5. Plano estratégico para os meses seguintes ao encerramento

**Diferenciais percebidos pelas clientes (para credibility anchors):**
- Personalização real — não é template
- Validação de cada passo — não fica sozinha na execução
- Clareza e direcionamento — sai de cada reunião sabendo exatamente o que fazer
- A especialista é quem atende — não uma equipe ou time de suporte

**O que o programa NÃO resolve (para o Gemini não prometer):**
- Problemas de falta de demanda ou marketing
- Gestão financeira contábil
- Treinamento direto da equipe operacional

---

### 2.2 Crenças Limitantes Dominantes (Dissolução pelo CBG)

O CBG deve ancorar o blueprint na dissolução preventiva das crenças antes que elas apareçam como objeções. O Gemini conhece o seguinte mapa:

| Crença Limitante | Como Aparece Verbalmente | Ângulo de Dissolução no Blueprint |
|---|---|---|
| "Não tenho tempo agora" | "Tô muito corrida, quando tiver mais tranquila" | A falta de tempo É causada pela ausência de estrutura — não o contrário |
| "Meu negócio é muito específico" | "Meu caso é diferente, não acho que se aplica" | Especificidade técnica ≠ especificidade operacional. Os problemas de gestão são os mesmos |
| "Ninguém faz tão bem quanto eu" | Silêncio após qualquer menção a delegar | O processo captura o SEU jeito de fazer — não substitui, cristaliza |
| "Processos tiram a criatividade" | Comum em agências, SaaS e consultorias criativas | Processo libera criatividade. O operacional sem processo é que ocupa o espaço criativo |
| "Vou fazer quando crescer mais" | "Quando estabilizar, aí a gente conversa" | O crescimento está travado exatamente pela ausência dessa estrutura |
| "Não vejo valor em estruturar processos" | "Acho muito burocrático isso" | Processo não é burocracia. É o que permite que você apareça APENAS quando necessário |
| "Não é prioridade" | "Tenho outras coisas mais urgentes agora" | O gargalo está na operação, não no marketing. Organizar já aumenta resultado sem mais clientes |
| "Já fiz mentoria e não funcionou" | Resistência após experiências anteriores | Diferença fundamental: aprender o que fazer vs. ter alguém validando CADA PASSO dentro do SEU negócio |

---

### 2.3 Estrutura de Ofertas e Isca

**Isca (porta de entrada):** Call de Diagnóstico Gratuito — 1 hora
- Objetivo declarado ao lead: mapear gargalos operacionais sem compromisso
- Objetivo real: qualificar, gerar confiança e **fechar no mesmo dia**
- Dado histórico: todas as clientes que fecharam tomaram a decisão **no mesmo dia da call**

**Oferta principal:** Programa de Acompanhamento Estratégico — **R$18.000**
- Foco de toda a prospecção do sistema

**Oferta de entrada paga (para leads que precisam de segurança):**
- Diagnóstico 360º: R$4.000 (até 5 colaboradores) ou R$7.000 (até 15)
- O valor é **abatido** se contratar o programa principal

**Upsell natural:** Consultoria de Implementação — R$20.000 a R$38.000+
- Para quem precisa de mão na massa além da orientação

**Instrução crítica para o CBG:**
```
NUNCA mencionar o programa, preço ou qualquer elemento de venda no primeiro contato.
NUNCA usar linguagem de oportunidade, urgência artificial ou escassez falsa.
O blueprint deve soar como uma mensagem que a especialista escreveria PESSOALMENTE.
```

---

## PILLAR 3: COMPONENTES OPERACIONAIS DE AGENTES LOCAIS

### 3.1 Stack Técnico Local

```python
# Dependências do projeto local
TECH_STACK = {
    "runtime": "Python 3.12",
    "llm_primary": "google-generativeai",  # Gemini Flash 1.5 / 2.0
    "llm_fallback": "gemini-1.5-pro",      # Para scoring complexo quando Flash falha
    "search_api": "tavily-python",
    "orchestration": "langgraph",          # Grafo local simplificado
    "env_management": "python-dotenv",
    "output_serialization": ["json", "markdown"],
    "cli": "argparse",
    "type_hints": "typing + TypedDict"
}

# Arquivo .env necessário
ENV_VARS = {
    "GEMINI_API_KEY": "<sua_chave_google_ai_studio>",
    "TAVILY_API_KEY": "<sua_chave_tavily>",
    "MIC_BUDGET_BRL": "0.30",      # Custo máximo por lead
    "TAU_FINOPS": "0.15",           # Threshold EIG/MIC em bits/R$0.01
    "DSS_WINDOW": "50",             # Janela do Discovery Saturation Score
    "DSS_THRESHOLD": "0.05"         # 5% de novidade mínima
}
```

### 3.2 Configuração de Custo Marginal (MIC) — FinOps Local

**Budget confirmado: R$0,30 por lead (ciclo completo)**

```python
MIC_CONFIG = {
    "total_budget_per_lead_brl": 0.30,
    "tau_finops": 0.15,  # bits de informação por R$0.01
    "sensors": {
        "tavily_search_query": {
            "mic_brl": 0.005,    # ~R$0,005 por query Tavily
            "max_queries_per_lead": 8  # Hard limit: 8 queries × R$0,005 = R$0,04
        },
        "gemini_flash_inference": {
            "mic_brl": 0.002,    # ~R$0,002 por inferência Flash
            "max_inferences_per_lead": 12  # 12 × R$0,002 = R$0,024
        },
        "gemini_pro_inference": {
            "mic_brl": 0.020,    # ~R$0,020 por inferência Pro (10× mais caro)
            "max_inferences_per_lead": 3   # Usar Pro apenas para scoring final
        }
    }
}

# Stopping Rule: se EIG(sensor) / MIC(sensor) < τ_FinOps → desativar sensor
# EIG calculado via variação esperada do posterior da hipótese dominante
# Exemplo: Tavily query adicional com EIG = 0.001 bits e MIC = 0.005
# EIG/MIC = 0.001/0.005 = 0.2 bits/R$0.01 → ACIMA de τ=0.15 → GO
# Exemplo: 4ª query sem hipótese nova com EIG = 0.0005 bits e MIC = 0.005
# EIG/MIC = 0.0005/0.005 = 0.1 bits/R$0.01 → ABAIXO de τ=0.15 → NO-GO → Delta Search
```

**Registro de auditoria de custo (em memória):**
```python
class CostAudit(TypedDict):
    lead_id: str
    tavily_queries_executed: int
    gemini_flash_calls: int
    gemini_pro_calls: int
    total_cost_brl: float
    budget_remaining_brl: float
    finops_triggered: bool
    finops_reason: Optional[str]
```

---

### 3.3 Distinção Comportamental BMO vs. Structural Champion

O sistema local deve classificar cada membro identificado do comitê em uma das designações:

#### Structural Champion (SC) — Fundadora Estática
Representa o poder de decisão econômico formal. Cargo estável, presença pública consistente mas sem cluster de momentum de transformação ativo.

**Critérios locais de identificação:**
- Cargo estático há > 6 meses (Sócia-Fundadora, CEO, Diretora)
- `role_alignment_score` > 0.60 com papel de Economic Buyer
- `bmo_momentum_score` < 0.55 — posts sobre dor mas sem cluster ativo
- Exemplo real: fundadora que posta "mais um mês correndo atrás de tudo sozinha" mas sem posts sobre busca ativa de solução

#### Buying Motion Owner (BMO) — Agente Dinâmico de Mudança
Não precisa ser o decisor formal. É quem está BUSCANDO ativamente a transformação — consumindo conteúdo de dor e interagindo com ferramentas de solução.

**Sinais comportamentais explícitos para o Gemini identificar como BMO:**

```python
BMO_SIGNALS = {
    "post_cluster": {
        "threshold": 3,           # ≥3 posts em 21 dias
        "window_days": 21,
        "topics": [
            "automação de tarefas manuais",
            "dificuldade de padronizar processos",
            "sobrecarga operacional com busca de saída",
            "implementação de ferramenta de gestão",
            "delegação sendo construída ativamente",
            "nova metodologia sendo testada",
            "ferramentas: Notion, ClickUp, Asana, Monday, Pipedrive, etc.",
        ],
        "weight_in_momentum_score": 0.50
    },
    "anchor_interaction": {
        "threshold": 1,           # ≥1 interação em perfil âncora
        "window_days": 7,
        "anchor_profiles": ["@g4educacao", "@endeavorbrasil", "@sebrae"],
        "weight_in_momentum_score": 0.30
    },
    "trigger_events": {
        "window_days": 30,
        "events": [
            "Contratação recente de cargo ≥ Manager/Coordenador",
            "Vaga de 'Analista de Processos' ou 'Coordenador' aberta há >45 dias",
            "Post explícito sobre busca de solução de gestão",
            "Compartilhou case de empresa que resolveu problema semelhante"
        ],
        "weight_in_momentum_score": 0.20
    }
}

# bmo_momentum_score = 0.50×post_cluster_score + 0.30×anchor_interaction_score + 0.20×trigger_event_score
# Threshold de BMO: bmo_momentum_score >= 0.55
# Threshold de SC: bmo_momentum_score < 0.55 AND role_alignment_score > 0.60
```

**Regra de abordagem baseada na designação:**
```python
APPROACH_RULES = {
    "BMO_DISTINCT_FROM_SC": {
        "first_touch": "Engajar BMO com reconhecimento técnico via Instagram/LinkedIn",
        "timing": "48-72h após comentário → avaliar → DM se engajamento",
        "avoid": "Não abordar SC diretamente antes de validar dor com BMO"
    },
    "SC_IS_BMO": {
        "first_touch": "Abordagem direta à decisora com pitch mais direto",
        "timing": "DM após 2-3 posts de engajamento orgânico",
        "avoid": "Não intermediar desnecessariamente"
    },
    "BMO_UNKNOWN": {
        "first_touch": "Abordar SC com cautela, construir rapport antes de qualquer pitch",
        "timing": "Mais ciclos de aquecimento necessários",
        "avoid": "Não mencionar programa antes de rapport estabelecido"
    }
}
```

---

### 3.4 LeadState — Estrutura de Dados In-Memory

O estado completo de um lead roda em memória como um TypedDict Python. **Zero banco de dados.**

```python
from typing import TypedDict, Optional, Literal
from dataclasses import dataclass, field

class OpinionTriple(TypedDict):
    b: float  # belief [0,1]
    d: float  # disbelief [0,1]
    u: float  # uncertainty [0,1]
    # invariante: b + d + u = 1.0

class ScoreVector(TypedDict):
    o_score: float
    c_score: float
    p_score: float
    fit: float
    s_intent: float
    reachability: float
    e_fresh: float
    rcs: float
    c_s_shannon: float
    uncertainty_committee: float
    hypothesis_confidence: float
    srs_product: float
    threshold_band: Literal["PRIORITY_ACTION", "MONITOR", "DELTA_SEARCH", "PRUNED"]

class EvidenceItem(TypedDict):
    evidence_id: str
    source: Literal["tavily", "gemini_inference"]
    raw_value: str
    evidence_type: str
    classification: Literal["Supporting", "Contradicting", "Missing", "Neutral"]
    hypothesis_linked: Optional[str]
    freshness: float
    collected_at: str  # ISO8601

class HypothesisState(TypedDict):
    hypothesis_id: str  # H1-H15
    label: str
    status: Literal["CANDIDATE", "ACTIVE", "REJECTED"]
    prior: float
    posterior: float
    omega: OpinionTriple
    supporting_count: int
    contradicting_count: int

class CommitteeMember(TypedDict):
    name: str
    role_declared: str
    role_inferred: str
    seniority_score: float
    role_alignment_score: float
    engagement_frequency: float
    member_score: float
    designation: Literal["STRUCTURAL_CHAMPION", "BUYING_MOTION_OWNER", "MEMBER", "UNKNOWN"]
    bmo_momentum_score: float
    omega: OpinionTriple

class ConversationBlueprint(TypedDict):
    hook: str
    urgency_level: Literal["ALTA", "MEDIA", "BAIXA"]
    context_trigger: str
    primary_pain: str
    pain_intensity: Literal["CRITICA", "ALTA", "MODERADA", "BAIXA"]
    narrative_anchors: list[str]
    credibility_anchor: str
    primary_cta: str
    channel: Literal["instagram_comment", "linkedin_comment", "linkedin_dm", "email"]
    timing_recommendation: str
    contraindications: list[str]
    fallback_cta: str

class LeadState(TypedDict):
    # Identidade
    lead_id: str
    company_name: str
    instagram_handle: Optional[str]
    linkedin_url: Optional[str]
    segment: str
    
    # Controle de ciclo
    operating_mode: Literal["FULL", "DEGRADED_TAVILY", "DEGRADED_GEMINI", "CACHE_ONLY"]
    stopping_triggered: bool
    stopping_reason: Optional[str]
    disqualified: bool
    disqualification_reason: Optional[str]
    
    # Evidências
    evidence_batch: list[EvidenceItem]
    
    # Hipóteses
    hypotheses: dict[str, HypothesisState]  # key = "H1"-"H15"
    dominant_hypothesis_id: Optional[str]
    
    # Comitê
    committee_members: list[CommitteeMember]
    committee_completeness: float
    committee_uncertainty: float
    bmo_identified: bool
    
    # Scores
    scores: Optional[ScoreVector]
    
    # Blueprint
    blueprint: Optional[ConversationBlueprint]
    
    # FinOps
    cost_audit: dict  # CostAudit
    
    # Qualidade
    data_quality_flag: Literal["NORMAL", "LOW", "DEGRADED"]
    errors: list[str]
```

---

### 3.5 Configuração de Saída (Output Local)

**Formato dual confirmado: JSON estruturado + Markdown legível**

```python
OUTPUT_CONFIG = {
    "formats": ["json", "markdown"],
    "json_file": "output/leads_{timestamp}.json",
    "markdown_file": "output/blueprint_{lead_id}_{timestamp}.md",
    "terminal_summary": True,  # Exibe resumo no terminal após cada lead
    "include_fields": {
        "json": "all_fields",  # XAI payload completo
        "markdown": [
            "company_name",
            "segment",
            "scores.p_score",
            "scores.threshold_band",
            "dominant_hypothesis",
            "committee_members",  # apenas SC e BMO
            "blueprint",           # todos os 5 componentes
            "data_quality_flag",
            "cost_audit.total_cost_brl"
        ]
    }
}
```

---

## PILLAR 4: MATRIZ DE CENÁRIOS BDD

### 4.1 Cenário 1 — Fluxo de Sucesso (Happy Path)

**História de usuário:**
```
Como operadora do sistema SocialSelling local,
Quando executo `python main.py --seed leads.csv --limit 1`,
E o Tavily retorna posts públicos com sinais explícitos de centralização,
E o Gemini classifica a hipótese H2 como ACTIVE com posterior ≥ 0.65,
Então quero receber um blueprint completo com Hook de urgência ALTA,
E a Pain Narrative ancorada em expressões reais coletadas do perfil,
E a CTA direcionada ao BMO (não à fundadora diretamente),
E o custo total abaixo de R$0,30,
E o arquivo Markdown gerado em output/.
```

**Gherkin:**
```gherkin
# language: pt
Funcionalidade: Qualificação e Blueprint para lead com H2 ativa

  Cenário: Advocacia com centralização explícita → blueprint de urgência ALTA
    Dado que o sistema recebe uma seed com handle "@lexassociados"
    E que o Tavily retorna posts com "sem mim trava" e "correndo atrás de tudo sozinha"
    E que o Gemini identifica a hipótese H2 como ACTIVE com posterior > 0.65
    E que o bmo_momentum_score de Marcos Teixeira (Coordenador) é > 0.55
    Quando o pipeline completo é executado
    Então o LeadState.scores.p_score deve ser ≥ 0.45
    E o LeadState.scores.threshold_band deve ser "PRIORITY_ACTION" ou "MONITOR"
    E o LeadState.blueprint.urgency_level deve ser "ALTA" ou "MEDIA"
    E o LeadState.blueprint.channel deve ser "instagram_comment"
    E o LeadState.blueprint.contraindications deve ter pelo menos 1 item
    E o LeadState.cost_audit.total_cost_brl deve ser ≤ 0.30
    E o arquivo output/blueprint_<lead_id>_<timestamp>.md deve ser gerado
    E o LeadState.data_quality_flag deve ser "NORMAL"
```

---

### 4.2 Cenário 2 — Fluxo de Poda FinOps

**História de usuário:**
```
Como sistema de controle de custos,
Quando o lead analisado é um profissional solo sem equipe visível,
Ou quando o EIG de novas queries Tavily cai abaixo de τ_FinOps=0.15,
Então quero que o sistema descarte o lead imediatamente sem gastar mais tokens,
E registre o motivo estruturado em pruned_reason dentro do LeadState,
E não gere blueprint.
```

**Gherkin:**
```gherkin
  Cenário: Lead solo desqualificado sem custo de análise
    Dado que o sistema recebe uma seed com handle "@profissional_solo"
    E que o Tavily retorna bio "Consultora independente | Especialista em finanças"
    E que não há menção a equipe, colaboradores ou escritório nos posts
    Quando o módulo de qualificação executa
    Então o LeadState.disqualified deve ser True
    E o LeadState.disqualification_reason deve ser "solo_operator"
    E o LeadState.cost_audit.total_cost_brl deve ser ≤ 0.01
    E nenhuma chamada ao Gemini para scoring deve ser feita
    E o LeadState.blueprint deve ser None

  Cenário: EIG/MIC abaixo do threshold → Delta Search Mode
    Dado que o sistema está processando o lead "TechParceiros Consultoria"
    E que 5 queries Tavily já foram executadas sem hipótese nova
    E que o EIG da próxima query é estimado em 0.0005 bits
    E que o MIC da query Tavily é R$0.005
    Quando a FinOps Stopping Rule é avaliada (EIG/MIC = 0.1 < τ=0.15)
    Então o LeadState.stopping_triggered deve ser True
    E o LeadState.stopping_reason deve ser "finops_eig_mic_below_threshold"
    E o pipeline deve gerar blueprint parcial com dados disponíveis
    E o LeadState.data_quality_flag deve ser "LOW"
```

---

### 4.3 Cenário 3 — Fluxo de Operação Degradada

**História de usuário:**
```
Como sistema resiliente,
Quando a API Tavily retorna timeout ou erro HTTP 429,
Então quero que o sistema continue operando com o Gemini sobre dados parciais,
E sinalize o modo degradado no LeadState,
E aumente a incerteza em todos os atributos derivados de busca web,
E não quebre a execução.
```

**Gherkin:**
```gherkin
  Cenário: Tavily indisponível → sistema opera em modo DEGRADED_TAVILY
    Dado que o sistema iniciou processamento do lead "TechAlpha Software House"
    E que a API Tavily retorna HTTP 429 em 3 tentativas com backoff exponencial
    E que o sistema detectou a falha após a 3ª tentativa (5s, 10s, 20s)
    Quando o pipeline continua com os dados parciais do Gemini
    Então o LeadState.operating_mode deve ser "DEGRADED_TAVILY"
    E o LeadState.evidence_batch deve conter apenas evidências do Gemini (inferidas)
    E a incerteza de todos os atributos derivados de busca web deve ser += 0.20
    E as hipóteses H1, H3, H12 devem ter uncertainty_residual = 0.80
    E os scores devem ser calculados com dados parciais disponíveis
    E o LeadState.data_quality_flag deve ser "DEGRADED"
    E o sistema NÃO deve lançar exceção Python não tratada
    E o LeadState.blueprint deve incluir aviso "dados_parciais_tavily: true"
    E o custo total deve refletir apenas as chamadas Gemini realizadas

  Cenário: Gemini com timeout → retry com backoff e fallback para resposta mínima
    Dado que o Gemini Flash retorna timeout na chamada de scoring
    Quando o sistema executa retry com backoff (3 tentativas)
    E todas as tentativas falham
    Então o LeadState.operating_mode deve ser "DEGRADED_GEMINI"
    E o LeadState.scores deve conter scores parciais calculados heuristicamente
    E o LeadState.blueprint deve ser None (sem blueprint sem Gemini)
    E o LeadState.errors deve conter "gemini_scoring_timeout"
    E o output JSON deve incluir estado parcial para reprocessamento futuro
    E o sistema deve salvar LeadState em output/partial_<lead_id>.json
```

---

### 4.4 Thresholds Operacionais Locais

```python
THRESHOLDS = {
    # P_score bands
    "priority_action": 0.65,   # P ≥ 0.65 → abordar imediatamente
    "monitor": 0.45,            # 0.45 ≤ P < 0.65 → aguardar trigger
    "delta_search": 0.25,       # 0.25 ≤ P < 0.45 → monitorar passivamente
    "pruned": 0.0,              # P < 0.25 → descartar

    # MatrixRankFunction
    "alpha": 0.60,
    "beta": 4.0,

    # Hipóteses
    "hypothesis_active_posterior": 0.45,
    "hypothesis_active_min_supporting": 3,
    "hypothesis_rejected_posterior": 0.15,

    # BMO
    "bmo_momentum_threshold": 0.55,
    "seniority_minimum_for_champion": 0.45,  # Coordinator+

    # FinOps
    "tau_finops_bits_per_cent": 0.15,
    "max_budget_per_lead_brl": 0.30,
    "max_tavily_queries_per_lead": 8,
    "max_gemini_flash_calls_per_lead": 12,
    "max_gemini_pro_calls_per_lead": 3,

    # DSS (Discovery Saturation Score)
    "dss_window_size": 50,
    "dss_saturation_threshold": 0.05,
    "dss_consecutive_windows": 2,

    # Retry
    "api_max_retries": 3,
    "api_backoff_seconds": [5, 10, 20],  # backoff exponencial
}
```

---

## PILLAR 5: ARQUITETURA LOCAL DO PIPELINE

### 5.1 Fluxo de Execução (10 Fases — Versão Local)

```
Fase 0: SEED INGESTION
  Input: leads.csv | handle Instagram | URL LinkedIn
  Processo: normalizar, deduplicar, validar formato
  Output: lista de leads_to_process

Fase 1: QUICK QUALIFICATION (FILTRO BARATO)
  Input: lead básico
  Processo: Tavily query rápida → verificar setor/equipe/tamanho
  Custo: 1 query Tavily (R$0.005)
  Output: qualified=True/False; se False → disqualified + motivo + STOP

Fase 2: EVIDENCE COLLECTION
  Input: lead qualificado
  Processo: Tavily multi-query (até 5 queries) sobre empresa, fundadora, vagas, posts
  Custo: até 5 × R$0.005 = R$0.025
  Output: evidence_batch (textos brutos coletados)

Fase 3: GEMINI EVIDENCE CLASSIFICATION
  Input: evidence_batch
  Processo: Gemini Flash classifica cada evidência → Supporting/Contradicting/Missing
             por hipótese H1-H15; extrai opinion triples
  Custo: 2-3 × R$0.002 = R$0.006
  Output: classified_evidence por hipótese

Fase 4: BAYESIAN HYPOTHESIS UPDATE
  Input: classified_evidence + priors H1-H15
  Processo: atualização P(H_i|E) para cada hipótese;
            identificar hipótese dominante (maior posterior ACTIVE)
  Custo: calculado em Python puro — zero API calls
  Output: hypotheses dict com posteriores atualizados

Fase 5: COMMITTEE MAPPING
  Input: evidence_batch (menções de pessoas/cargos)
  Processo: Gemini Flash identifica membros, atribui S_persona;
            calcula bmo_momentum_score para cada membro
  Custo: 1-2 × R$0.002 = R$0.004
  Output: committee_members com designação SC/BMO

Fase 6: SCORE COMPUTATION
  Input: hypotheses + committee + evidence_batch
  Processo: calcular Fit, S_intent, Reachability, E_fresh → O_score
            calcular RCS (heurístico sem Jaro-Winkler completo no MVP local),
            C_s (Shannon com 2-3 fontes), Uncertainty_Committee, Hypothesis_Confidence → C_score
            MatrixRankFunction → P_score
  Custo: calculado em Python puro
  Output: ScoreVector completo

Fase 7: FINOPS CHECK
  Input: ScoreVector + cost_audit
  Processo: verificar se EIG/MIC < τ para cada sensor restante;
            verificar budget remaining
  Output: continuar ou → stopping_triggered + Delta Search

Fase 8: BLUEPRINT GENERATION (CBG Local)
  Input: dominant_hypothesis + committee + pain_signals + segment
  Processo: Gemini Pro gera ConversationBlueprint adaptado ao setor
            com vocabulário do dicionário semântico desta vertical
  Custo: 1 × R$0.020 (Pro para qualidade máxima)
  Output: ConversationBlueprint completo

Fase 9: OUTPUT SERIALIZATION
  Input: LeadState completo
  Processo: serializar JSON XAI-style + Markdown legível
  Output: output/leads_{ts}.json + output/blueprint_{lead_id}_{ts}.md
          + resumo no terminal
```

### 5.2 Prompt do Gemini — Template de Scoring (Fase 5-6)

O Gemini receberá este template injetado com dados reais do LeadState:

```python
GEMINI_SCORING_PROMPT = """
Você é um especialista em inteligência comercial B2B para o mercado brasileiro.
Analise as evidências coletadas sobre a empresa abaixo e responda em JSON estruturado.

## EMPRESA
Nome: {company_name}
Setor: {segment}
Handle: {instagram_handle}

## EVIDÊNCIAS COLETADAS
{evidence_batch_formatted}

## CONTEXTO DO ICP
Alvo: Mulheres fundadoras de {segment} com 5-30 colaboradores.
Dor central: centralização operacional, incapacidade de delegar, crescimento sem estrutura.
Produto sendo vendido: Programa de Acompanhamento Estratégico R$18.000
(Especialista como Diretora Estratégica Temporária por 6 meses)

## DICIONÁRIO DE DOR (use para classificar evidências)
{pain_dictionary_injected}

## TAREFA
1. Para cada hipótese ativa ({active_hypotheses}), atribua:
   - posterior_probability (0.0 a 1.0)
   - classification das evidências: Supporting / Contradicting / Missing
   - opinion_triple: {{ "b": float, "d": float, "u": float }} (soma = 1.0)

2. Identifique membros do comitê mencionados nas evidências:
   - Nome, cargo, designation (STRUCTURAL_CHAMPION / BUYING_MOTION_OWNER / MEMBER)
   - bmo_momentum_score (0.0 a 1.0) baseado nos sinais comportamentais descritos

3. Calcule os scores finais:
   - fit: similaridade entre o perfil da empresa e o ICP
   - s_intent: intensidade de sinal de busca ativa por solução
   - data_quality_flag: NORMAL / LOW / DEGRADED

Responda EXCLUSIVAMENTE em JSON válido com a estrutura:
{expected_output_schema}
"""
```

### 5.3 Prompt do CBG (Fase 8) — Geração de Blueprint

```python
CBG_PROMPT = """
Você é um SDR de elite especializado em Social Selling B2B no mercado brasileiro.
Gere um Conversation Blueprint preciso e personalizado para a abordagem comercial.

## EMPRESA ALVO
{company_summary}

## HIPÓTESE DOMINANTE DE DOR
{dominant_hypothesis_with_posterior}

## COMPRADOR MOTION OWNER (BMO)
{bmo_profile}

## VOCABULÁRIO DO SETOR ({segment})
{sector_vocabulary_injected}

## CRENÇAS LIMITANTES A DISSOLVER PREVENTIVAMENTE
{limiting_beliefs_for_segment}

## REGRAS ABSOLUTAS DE GERAÇÃO
- NUNCA mencionar o programa, preço ou qualquer elemento de venda no primeiro contato
- NUNCA usar linguagem de urgência artificial ou escassez
- A mensagem deve soar como escrita PESSOALMENTE pela especialista
- Adaptar TOTALMENTE ao vocabulário natural do setor {segment}
- Ancorar nas evidências reais coletadas (não inventar)

## OUTPUT ESPERADO (JSON)
{{
  "hook": "string — evento real específico que justifica o contato AGORA",
  "urgency_level": "ALTA|MEDIA|BAIXA",
  "context_trigger": "string — comportamento público específico observado",
  "primary_pain": "string — dor em primeira pessoa da empresa",
  "pain_intensity": "CRITICA|ALTA|MODERADA|BAIXA",
  "narrative_anchors": ["frase 1 real", "frase 2 real", "frase 3 real"],
  "credibility_anchor": "string — referência a case análogo sem mencionar empresa",
  "primary_cta": "string — ação exata de primeiro contato recomendada",
  "channel": "instagram_comment|linkedin_comment|linkedin_dm|email",
  "timing_recommendation": "string — timing específico",
  "contraindications": ["string — o que NÃO fazer 1", "string 2", "string 3"],
  "fallback_cta": "string — ação alternativa se sem resposta em 7 dias"
}}
"""
```

---

## APÊNDICE A: MODO DE FALHA E COMPORTAMENTO DE RETRY

```python
FAILURE_MODES = {
    "tavily_rate_limit": {
        "trigger": "HTTP 429 em 3 tentativas",
        "response": "DEGRADED_TAVILY",
        "u_increment": 0.20,
        "frozen_hypotheses": ["H3", "H4", "H12"],  # dependem de dados de busca
        "frozen_u": 0.80,
        "continue_pipeline": True
    },
    "tavily_timeout": {
        "trigger": "timeout > 30s em 3 tentativas",
        "response": "DEGRADED_TAVILY",
        "u_increment": 0.20,
        "continue_pipeline": True
    },
    "gemini_timeout": {
        "trigger": "timeout > 60s em 3 tentativas",
        "response": "DEGRADED_GEMINI",
        "blueprint_generation": False,
        "save_partial_state": True,
        "continue_pipeline": False  # sem Gemini não há scoring confiável
    },
    "dual_failure": {
        "trigger": "Tavily + Gemini ambos indisponíveis",
        "response": "CACHE_ONLY",
        "save_partial_state": True,
        "terminal_alert": True,
        "continue_pipeline": False
    },
    "budget_exhausted": {
        "trigger": "cost_audit.total_cost_brl >= max_budget_per_lead_brl",
        "response": "FINOPS_STOP",
        "generate_partial_blueprint": True,
        "data_quality_flag": "LOW"
    }
}

RETRY_CONFIG = {
    "max_retries": 3,
    "backoff_seconds": [5, 10, 20],
    "jitter": True  # adicionar 0-2s aleatório para evitar thundering herd
}
```

---

## APÊNDICE B: ESTRUTURA DE ARQUIVOS DO PROJETO LOCAL

```
socialselling-local/
├── .env                          # GEMINI_API_KEY, TAVILY_API_KEY, etc.
├── .env.example                  # template público (sem valores reais)
├── main.py                       # CLI entry point
├── requirements.txt              # dependências Python
├── README.md                     # instrução de execução
│
├── config/
│   ├── icp_contract.json         # parâmetros ICP configuráveis
│   ├── pain_dictionary.json      # dicionário semântico de dor
│   └── sector_vocabulary.json    # vocabulário por vertical
│
├── core/
│   ├── lead_state.py             # TypedDict LeadState e subtipos
│   ├── pipeline.py               # orquestração das 10 fases
│   ├── qualification.py          # Fase 0-1: filtro rápido
│   ├── evidence_collector.py     # Fase 2: Tavily multi-query
│   ├── hypothesis_engine.py      # Fase 3-4: Gemini + Bayes
│   ├── committee_analyzer.py     # Fase 5: BMO vs SC
│   ├── scoring.py                # Fase 6: scores matemáticos
│   ├── finops.py                 # Fase 7: FinOps stopping rule
│   └── blueprint_generator.py   # Fase 8: CBG via Gemini Pro
│
├── adapters/
│   ├── tavily_adapter.py         # wrapper Tavily com retry + degraded mode
│   └── gemini_adapter.py         # wrapper Gemini Flash/Pro com retry + fallback
│
├── output/
│   ├── leads_<timestamp>.json    # XAI payload completo por ciclo
│   └── blueprint_<id>_<ts>.md   # Markdown legível por lead
│
└── tests/
    ├── test_scoring.py           # testes unitários das fórmulas matemáticas
    ├── test_hypothesis.py        # testes do motor bayesiano
    ├── test_finops.py            # testes da stopping rule
    └── fixtures/                 # mocks de respostas Tavily e Gemini
        ├── mock_tavily_advocacia.json
        ├── mock_tavily_software.json
        └── mock_gemini_scoring.json
```

---

## APÊNDICE C: EXEMPLO DE EXECUÇÃO CLI

```bash
# Processar uma seed list de 10 leads, budget de R$0,30/lead
python main.py \
  --seed data/leads_advocacia.csv \
  --limit 10 \
  --budget 0.30 \
  --segment "Advocacia Corporativa" \
  --output-format dual \
  --verbose

# Processar um único handle para teste
python main.py \
  --handle "@lexassociados" \
  --segment auto-detect \
  --output-format json

# Modo dry-run (sem chamadas reais de API, usa fixtures)
python main.py \
  --seed data/test.csv \
  --dry-run \
  --fixture-mode
```

**Output no terminal (resumo por lead):**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Lex & Associados Advocacia Empresarial
   Segmento: Advocacia Corporativa
   P_score: 0.703 → PRIORITY ACTION

📊 Scores: O=0.741 | C=0.614 | P=0.703
   Hipótese dominante: H2 (Centralização) — posterior=0.74
   Comitê: SC=Dra. Fernanda Melo | BMO=Marcos Teixeira (momentum=0.87)

💡 Blueprint gerado — urgência: ALTA
   Canal: instagram_comment
   Hook: "Vaga de Analista de Processos aberta há 67 dias + 4 posts de sobrecarga"

💰 Custo: R$ 0.028 / budget R$ 0.30 (9.3%)
📁 Salvo: output/blueprint_LE-001_20241115.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

*master_context_vibe_coding.md | SocialSelling Local v1.0*
*Parâmetros confirmados: headcount 5-30 | faturamento R$80k-R$500k/mês | MIC R$0,30/lead*
*Engine: Gemini Flash + Pro | Search: Tavily | Persistência: in-memory only*
