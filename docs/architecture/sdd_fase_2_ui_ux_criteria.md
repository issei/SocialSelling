# SDD — FASE 2: CRITÉRIOS DE DESIGN E ERGONOMIA DE UX (OPERATOR COCKPIT)
## Projeto: SocialSelling — Local Dashboard Edition
### Versão: 1.0-LOCAL | Status: APPROVED-FOR-IMPLEMENTATION

---

## 1. PRINCÍPIOS DE MITIGAÇÃO DE FADIGA COGNITIVA

O *Operator Cockpit* local é desenhado sob o princípio de eliminação total do esforço de análise exploratória secundária pelo operador humano. A interface traduz os payloads aninhados gerados pelo pipeline M1→M5 em respostas visuais imediatas.

### 1.1 Regra de Ouro dos Três Segundos
O operador deve ser capaz de abrir a tela do painel e determinar, em menos de 3 segundos por lead, a resposta exata de priorização. Isso é alcançado pela dissociação visual clara entre **Oportunidade** (o valor intrínseco do lead) e **Confiança** (a qualidade e integridade do sinal capturado).

### 1.2 Progressive Disclosure
Variáveis de controle analítico complexas (como fórmulas internas, exponenciais de confiança ou hashes de evidência) ficam ocultas por padrão sob elementos de interação colapsáveis ou tooltips nativas (`title` HTML), mantendo a tela limpa e focada em ações executáveis.

## 2. HIERARQUIA VISUAL ORIENTADA ÀS 3 PERGUNTAS CARDINAIS

A página única do Cockpit é estruturada em uma grade responsiva (*grid* Tailwind) dividida estritamente em **três blocos funcionais**.

### 2.1 Bloco I: "Onde Focar?" (Prioridade e Oportunidade)
Este componente traduz o contrato `ProspectScore` do lead.

* **Visualização do P_score:** Exibido através de uma barra de progresso horizontal em destaque, utilizando a escala dinâmica de cores do Tailwind baseada nos thresholds operacionais definidos:
  - `P_score >= 0.65` (Priority Action) → Barra de cor **Verde** (`bg-emerald-500`).
  - `0.45 <= P_score < 0.65` (Monitor/Acompanhamento) → Barra de cor **Amarela** (`bg-amber-500`).
  - `P_score < 0.45` (Early Pruning / Baixo Potencial) → Barra de cor **Cinza** (`bg-slate-400`).
* **Sinalizadores de Qualidade Separados:** Exibição lado a lado de dois medidores numéricos compactos com badges:
  - **Fit (Aderência Estrutural ao ICP):** Representa o alinhamento macro do segmento e technographics.
  - **Intent (Momentum/Sinais de Dor):** Representa a intensidade volumétrica das evidências observadas.
* **Identificação de Hard Filter:** Se o lead falhar no hard-filter (`hard_filter_passed == false`) devido à detecção de tecnologia desqualificadora (ex: wordpress), o card do lead recebe opacidade de 40%, borda vermelha e um badge com texto em bold: `REJEITADO POR FILTRO RÍGIDO`.

### 2.2 Bloco II: "Com Quem Falar?" (Mapeamento do Comitê)
Este componente extrai informações da camada de entidades e pessoas da resposta do pipeline.

* **Card do Decisor Primário:** Apresenta o nome do profissional identificado, cargo exato (`role_title`) e nível de senioridade inferido pelo motor cognitivo.
* **Indicador de Confiança do Membro:** Exibe um chip colorido pequeno ao lado do cargo contendo o valor de `confidence` da extração (ex: `Confiança: 90%`), mitigando o risco de o operador iniciar uma conversa com dados alucinados ou ambíguos.

### 2.3 Bloco III: "O que falar?" (Conversation Blueprint)
Este componente renderiza a tradução semântica gerada pelo contrato `XAIPayload`.

* **Drivers Positivos (Ganchos Reais):** Uma lista vertical verde (`text-emerald-700 bg-emerald-50`) exibindo os sinais que somaram pontos para a oportunidade, ligando-os ao impacto numérico obtido (ex: "+0.60" ou "+0.40").
* **Drivers Negativos / Barreiras:** Exibidos em lista vermelha/laranja para alertar sobre atritos detectados (ex: confiança baixa nas fontes).
* **Missing Evidence (Sinais Ausentes — Incerteza Explícita):** Apresentados em uma lista neutra cinza estruturada com o título *"Sinais Não Confirmados na Internet"*, listando de forma transparente os dados mapeados como ausentes (ex: indústria não identificada ou pessoas-chave não listadas nas fontes públicas).

## 3. GESTÃO VISUAL DE ESTADOS DE INCERTEZA E FALHA

O painel deve refletir o estado de degradação operacional da esteira de dados de forma nativa nas classes do Tailwind CSS.

### 3.1 Tratamento do Modo Degradado (`degraded_mode == true`)
Ao carregar um lote de leads cujo pipeline foi marcado como degradado por falha ou estouro de cota de algum sensor (ex: Tavily rate-limit):
* Um banner horizontal amarelo persistente (`bg-amber-100 border-amber-400 text-amber-800`) é renderizado no topo da página com o aviso: `⚠️ MODOD DEGRADADO ATIVO — SINAIS COLHIDOS VIA CACHE LOCAL OU FONTES SECUNDÁRIAS`.
* O valor numérico de confiança do lead recebe coloração laranja e um ícone de atenção ao lado, prevenindo abordagens agressivas baseadas em dados desatualizados.

## 4. DESIGN DOS TEMPLATES HTML (CLASSES UTILIÁRIAS TAILWIND)

### 4.1 Componente de Cabeçalho Geral (Ações Operacionais Locais)
```html
<div class="flex items-center justify-between border-b border-slate-200 pb-5 mb-8">
  <div>
    <h1 class="text-3xl font-bold tracking-tight text-slate-900">Operator Cockpit</h1>
    <p class="text-sm text-slate-500 mt-1">Gestão de prospecção baseada em inteligência de dados local</p>
  </div>
  <div class="flex gap-3">
    <a href="/config" class="rounded-md bg-white px-3.5 py-2.5 text-sm font-semibold text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 hover:bg-slate-50">Configurar ICP</a>
    <form action="/pipeline/run" method="POST">
      <button type="submit" class="rounded-md bg-emerald-600 px-3.5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-emerald-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-600 flex items-center gap-2">
        <svg class="h-4 w-4 animate-spin hidden" id="spinner" viewBox="0 0 24 24"></svg>
        Executar Prospecção
      </button>
    </form>
  </div>
</div>

```

### 4.2 Card de Prospect Estruturado (Mapeamento de Bloco Triplo)

```html
<div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm mb-6 hover:border-slate-300 transition-all">
  <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
    
    <div class="border-r border-slate-100 pr-6">
      <div class="flex items-start justify-between">
        <h3 class="text-lg font-bold text-slate-900">{{ prospect.explanation.company_id }}</h3>
        <span class="inline-flex items-center rounded-md px-2 py-1 text-xs font-medium text-emerald-700 bg-emerald-50 ring-1 ring-inset ring-emerald-600/20">{{ prospect.score.action_label }}</span>
      </div>
      <div class="mt-4">
        <div class="flex justify-between text-xs text-slate-500 mb-1">
          <span>Priority Score</span>
          <span class="font-semibold text-slate-900">{{ prospect.score.p_score }}</span>
        </div>
        <div class="w-full bg-slate-100 rounded-full h-2.5">
          <div class="bg-emerald-500 h-2.5 rounded-full" style="width: {{ prospect.score.p_score * 100 }}%"></div>
        </div>
      </div>
      <div class="mt-4 flex gap-4 text-xs text-slate-600">
        <div>Fit ICP: <span class="font-bold text-slate-900">{{ prospect.score.fit }}</span></div>
        <div>Intent Momentum: <span class="font-bold text-slate-900">{{ prospect.score.intent }}</span></div>
      </div>
    </div>

    <div class="border-r border-slate-100 px-6">
      <h4 class="text-sm font-semibold text-slate-500 tracking-wide uppercase">Comitê de Decisão</h4>
      <div class="mt-3 space-y-3">
        {% for person in prospect.explanation.people %}
        <div class="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-100">
          <div>
            <div class="text-sm font-medium text-slate-900">{{ person.normalized_name }}</div>
            <div class="text-xs text-slate-500">{{ person.role_title }} • {{ person.seniority }}</div>
          </div>
          <span class="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10">Confiança: {{ person.confidence * 100 }}%</span>
        </div>
        {% endfor %}
      </div>
    </div>

    <div class="pl-6">
      <h4 class="text-sm font-semibold text-slate-500 tracking-wide uppercase mb-3">Drivers de Abordagem (XAI)</h4>
      <div class="space-y-2 max-h-36 overflow-y-auto">
        {% for signal in prospect.explanation.positive_signals %}
        <div class="text-xs p-2 rounded bg-emerald-50 text-emerald-800 border border-emerald-100 flex gap-2">
          <span class="font-bold">{{ signal.impact }}</span>
          <span>{{ signal.text }}</span>
        </div>
        {% endfor %}
        
        {% for gap in prospect.explanation.missing_signals %}
        <div class="text-xs p-2 rounded bg-slate-50 text-slate-600 border border-slate-200 italic">
          ❓ Sinal ausente: {{ gap }}
        </div>
        {% endfor %}
      </div>
    </div>

  </div>
</div>

```
