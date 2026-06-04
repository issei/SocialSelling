# ADR-007 — Aprendizado por feedback like/dislike (modelo treinado, auto-apply)

- **Status:** Proposto (aguardando ratificação do dono do produto) — 2026-06-04
- **Decisores:** Dono do produto + Claude Code
- **Emenda a:** M3 Score (pesos `[scoring]`) e à UI de operador (ADR-002). Complementa ADR-006
  (corpus acumulativo), que dá o universo de leads sobre o qual o feedback atua.

## Contexto
A PoC foi validada. Hoje os pesos da fórmula de score (`w_fit`, `w_intent`, …) são **fixos**
no `runtime.toml`, calibrados a mão. O dono quer que o sistema **aprenda com o uso**: marcar
leads já buscados com 👍/👎 e deixar o sistema **reajustar os pesos automaticamente**, para que
o ranking convirja ao que a operadora considera "bom lead".

Decisões explícitas do dono nesta sessão:
- **Modelo treinado** (regressão), não só heurística de comparação de médias.
- **Auto-aplicar** os pesos aprendidos (sem etapa manual de confirmação).
- **Dislike é só sinal de treino** — o lead permanece visível, com selo.

## Tensão com o guardrail §5
O CLAUDE.md §5 difere ML pesado/Bayesiano para V1+. Um **modelo treinado que altera os pesos
sozinho** tensiona esse guardrail. A decisão é **adotá-lo conscientemente**, mantendo-o dentro
do espírito do PoC (1 processo, JSON atômico, sem infra), com três salvaguardas:

1. **Python puro, sem dependências novas.** Regressão logística em ~40 linhas (`learning/model.py`),
   stdlib `math`. Sem numpy/sklearn.
2. **Determinismo (regra §3.2).** Treino full-batch, init em zeros, épocas fixas, amostras
   ordenadas por `company_id`, L2 — **sem aleatoriedade**. Mesmo log de feedback ⇒ mesmos pesos,
   bit a bit ⇒ ranking byte-idêntico.
3. **Travas de estabilidade do auto-apply.** (a) **gate de amostra mínima** (`min_likes` E
   `min_dislikes`): sem os dois lados, não treina nem aplica; (b) **L2**; (c) **shrinkage** rumo
   aos pesos atuais (mais votos ⇒ mais confiança no aprendido); (d) **clamp/normalização** que
   preserva a escala da fórmula. Resultado: o reajuste é gradual e reversível (basta editar a
   aba "Pesos"), nunca um salto brusco.

## Decisão
1. **Loop de feedback.** A operadora marca cada lead com 👍/👎 na tabela ou no drawer do cockpit.
   Cada voto é persistido (`data/feedback.json`, chave = `company_id`, escrita atômica) com os
   **componentes do score capturados no clique** (`fit`, `intent`, `confidence`, `persona_fit`)
   — sem recomputar o pipeline nem alterar `ProspectScore`.
2. **Modelo.** Regressão logística binária (like=1 / dislike=0) sobre as features `[fit, intent]`.
3. **Projeção → pesos.** Os coeficientes aprendidos são projetados sobre `w_fit`/`w_intent`
   (contribuição positiva, normalizada à escala atual), com shrinkage e clamp, e **gravados** no
   `runtime.toml` via o mesmo `save_scoring` da aba "Pesos".
4. **Camada.** Todo o aprendizado opera na **camada de apresentação** (componentes de
   `LeadCard.score`); jamais toca Observed Evidence ou Inferences (regra §3.1).
5. **Opt-in.** `[learning].enabled` (default `false` no código; `true` no `runtime.toml` ativado).
   Desligado ⇒ feedback é registrado mas nenhum peso muda (paridade).

## Consequências
- ✅ O ranking passa a refletir o julgamento da operadora, de forma **explicável** (a UI mostra o
  reajuste: `w_fit 0.60→0.63 …`) e **determinística**.
- ✅ Zero dependência/infra nova; cabe no PoC database-less.
- ⚠️ Só `w_fit`/`w_intent` são aprendidos neste corte. `confidence_exponent`, `w_fit_tech` e
  `w_fit_industry` exigiriam **persistir as sub-features** (`tech_match`/`industry_match`) por
  lead — **diferido** (guardrail "em dúvida, difira"). Caminho de extensão: adicionar essas
  features ao voto e treinar uma regressão por grupo de pesos.
- ⚠️ Feedback ruidoso/escasso pode oscilar os pesos — mitigado pelo gate + shrinkage + L2.
- ⚠️ `company_id` instável (ADR-006/ADR-008) faz votos se perderem entre runs; resolve junto com
  a entity resolution canônica.

## Alternativa considerada
**Heurística explicável** (comparar médias dos componentes de likes vs dislikes e nudgar pesos).
Mais simples e plenamente dentro do §5, mas o dono optou pelo **modelo treinado** por ser mais
fiel ao objetivo de "machine learning ajustando os parâmetros". Mantemos a heurística como
referência mental; o modelo treinado a subsume com as travas acima.
