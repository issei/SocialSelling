# SDD — UX da lista de leads: tabela + drawer de detalhes enriquecidos

> **Status:** **PROPOSTA (v1.0)**. Escopo dentro do **ADR-002** (UI de operador local) — é
> evolução da superfície existente, sem novo backend. Complementa o
> `operator-cockpit-ui-sdd.md` (data grid de alta densidade), aterrissando a parte
> imediatamente útil: a **lista de resultados vira tabela** com ações rápidas e um
> **painel de detalhes** (slide-over) para os dados enriquecidos.
>
> **Princípio reitor (design):** *scan-then-focus*. A tabela é para **varrer e comparar**
> dezenas de leads num relance (densa, ordenável, com sinais visuais de score e canais);
> o **drawer** é para **focar num lead** e ver tudo que foi enriquecido, de forma amigável.
>
> **Sem mudança de backend/contrato:** consome o JSON já retornado por `POST /api/run`
> (`list[LeadCard]`). Só muda o *rendering* no `static/index.html`. As seções
> `#parametros`/`#assistente`/`#resultados` e todos os IDs do JS de config são preservados.

---

## 1. Problema & diagnóstico da UI atual

Hoje os resultados são **cards** num grid de 2 colunas (`card(l)` em `static/index.html`).
Limitações de UX para o trabalho real ("quem abordar primeiro?"):

| Problema | Efeito |
|---|---|
| Cards não alinham colunas | difícil **comparar** score/persona/setor entre leads |
| Sem ordenação | o operador não re-prioriza (ex.: por score, por canal disponível) |
| Densidade baixa | poucos leads por tela; rolagem longa em lotes |
| Detalhes espremidos no card | contato/sinais/fontes competindo por espaço; nada "respira" |
| Links como texto solto | ação de abrir Instagram/LinkedIn pouco evidente |

**Decisão:** lista densa **tabular** + **drawer de detalhe** sob demanda.

---

## 2. Contrato de dados (já existente — `LeadCard`)

A tabela e o drawer leem **apenas** o que o `LeadCard` expõe (camada de apresentação):

```
rank, display_name, company, role, sector, location,
links{ instagram, linkedin, website },
contact{ email, phone },
score{ fit, intent, confidence, persona_fit, p_score, hard_filter_passed },
why_now[], gaps[], sources[]
```

> **Campos "enriquecidos" exibíveis hoje:** `contact.email/phone` (degrau 3 Apollo),
> `sector`/`location` (firmografia), `links` (Instagram/LinkedIn/site). Aprofundar com
> `employee_count`/`domain`/`confidence` exigiria estender o contrato `LeadCard` — fica
> como **melhoria futura** (§7), fora desta WU.

---

## 3. A tabela de leads (scan)

### 3.1 Colunas

| Coluna | Conteúdo | Tratamento visual |
|---|---|---|
| **#** | `rank` | número discreto, largura fixa |
| **Lead** | `display_name` + `role` (linha 2, menor) + **badge de persona** | nome em destaque |
| **Empresa** | `company` | texto secundário |
| **Setor · Local** | `sector` · `location` | muted; oculta em telas estreitas |
| **Score** | barra horizontal proporcional ao `p_score` + valor | cor por faixa (alto=esmeralda, médio=âmbar, baixo=cinza) |
| **Canais** | ícones-ação Instagram / LinkedIn / Site (só os presentes) | clicáveis, abrem em nova aba |
| **›** | abre o drawer | área de clique da linha inteira |

### 3.2 Interações

- **Linha clicável** → abre o drawer do lead. Os **ícones de canal** usam
  `stopPropagation` (abrir o link **não** abre o drawer).
- **Ordenação:** clique nos cabeçalhos **Score**, **Lead** e **Empresa** alterna asc/desc;
  default = ordem do ranking (M4). Indicador de seta no header ativo.
- **Badge de persona:** `fundadora` (rosa), `fundador` (azul), `empresa` (âmbar),
  `indefinido` (cinza) — derivado do XAI/score quando disponível; senão omitido.
- **Estado vazio:** ilustração textual amigável ("Nenhum lead qualificado neste ciclo")
  em vez de tabela vazia.
- **Indicador "enriquecido":** um ponto/ícone discreto na linha quando há `contact.email`
  ou `contact.phone` (lead acionável com contato revelado).

### 3.3 Responsivo

- ≥ md: tabela completa.
- < md: colunas **Setor·Local** e **Empresa** colapsam para dentro do nome (stack); a
  tabela vira lista de linhas compactas, mantendo Score + Canais + abrir-drawer.

---

## 4. O drawer de detalhes (focus)

Painel **slide-over** da direita (overlay escurece o fundo). Largura ~ 28rem; rolável.

### 4.1 Anatomia (de cima para baixo)

1. **Cabeçalho:** badge `#rank` · `display_name` · `company` · badge de persona · botão ✕.
2. **Score em destaque:** `P` grande + **4 barras** rotuladas (Fit, Intent, Confiança,
   Persona), cada uma 0–1 com cor por intensidade. Carimbo "reprovado no hard filter" se
   `hard_filter_passed=false`.
3. **Contato (enriquecido):** `email` e `phone` com botão **copiar**; ausência mostrada
   como "não revelado" (muted) — fiel ao Open-World (lacuna explícita, nunca inventado).
4. **Canais:** botões grandes Instagram / LinkedIn / Site (os presentes), com o domínio
   visível.
5. **Por que agora:** lista `why_now` (drivers positivos), com marcador esmeralda.
6. **Lacunas / sinais ausentes:** lista `gaps` (âmbar) — inclui `contato_nao_revelado`,
   `sem_email_no_apollo`, etc. (rastros honestos do enriquecimento).
7. **Fontes:** contagem + lista de `sources` (URLs clicáveis, truncadas).

### 4.2 Comportamento

- Abre com transição (translate-x). Fecha por: ✕, clique no overlay, **tecla Esc**.
- Acessível: `role="dialog"`, `aria-modal`, foco movido ao painel; `aria-label` nos ícones.
- Determinístico/местном: puro front-end sobre o JSON do run; sem nova chamada.

---

## 5. Sistema visual (amigável & bonito)

- **Paleta:** base slate clara; primária índigo (já usada); acentos por canal (Instagram
  rosa, LinkedIn azul) e por score (esmeralda/âmbar/cinza).
- **Tipografia:** Inter; números do score com `tabular-nums` (alinham na coluna).
- **Componentes:** cantos arredondados (`rounded-xl`), sombras suaves, hover sutil nas
  linhas, foco visível (acessibilidade). Ícones inline (SVG/emoji) sem dependência nova.
- **Tailwind via CDN** (já em uso) — zero build, mantém o guardrail de simplicidade.

---

## 6. Plano de testes (gate inalterado)

Front-end servido como HTML estático + render client-side; os testes validam a **presença
da estrutura** e a **preservação dos contratos** (FastAPI TestClient, sem rede):

| Suite | Asserção |
|---|---|
| `web/test_pages.py` (existente) | `#parametros`/`#assistente`/`#resultados` continuam presentes (não regredir) |
| `web/test_results_ui.py` (novo) | o HTML contém a **tabela** (`id="leadsTable"`), o corpo `id="leadsBody"`, o **drawer** (`id="leadDrawer"`) e o estado-vazio (`id="leadsEmpty"`) |
| `web/test_e2e.py` (existente) | fluxo assistente→salvar→executar inalterado; `/api/run` ainda devolve `leads[]` com `links.instagram` |

> **Invariante de não-regressão:** o **contrato** de `/api/run` e os IDs do JS de
> config/assistente são preservados; a mudança é **estritamente de apresentação**.

---

## 7. Implementação (1 PR verde) e melhorias futuras

- **WU-UX1** *(esta)* — reescrever a seção de resultados do `static/index.html`: tabela
  (`renderTable`), ações de canal, **drawer** (`openDrawer`/`closeDrawer`), ordenação,
  estado-vazio, badges. Preservar todo o JS de config/assistente. + `test_results_ui.py`.
- **Melhoria futura — contrato `LeadCard`:** expor `employee_count`, `domain` e
  `company.confidence` para um drawer ainda mais rico ("firmografia enriquecida"). Toca
  `contracts.py` + `orchestrator._to_lead_card` → WU própria (com testes de contrato).
- **Melhoria futura — exportar:** botão "copiar tabela / CSV" do lote (operação local).
- **Melhoria futura — filtros:** por canal disponível (tem Instagram? tem contato?),
  alinhado ao Cockpit SDD.
