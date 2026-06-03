# ADR-001 — Camada de intenção: hipóteses e desqualificadores no scoring

- **Status:** Aceito (2026-06-03)
- **Contexto:** ADR-000 (escopo canônico). Complementa, não substitui.

## Problema
O scoring original (v0.7.0) calculava `Intent` como uma proxy por contagem de
evidências (`|derived_from| / norma`). Os campos de maior valor de negócio —
`intent_triggers` do ICP e todo o `hypotheses_catalog.json` — não eram consumidos.
Para o público real (founders de serviços; ver `icp_criteria.talita.json`), o que
decide a abordagem é **timing + dor + autonomia de decisão**, não estrutura.

## Decisão
1. **Sinais na camada 2.** `Inference` ganha `intent_signals[]` e `disqualifiers[]`,
   extraídos pelo M2 a partir de um **vocabulário controlado** (intenção = união dos
   `surface_signals` das hipóteses; desqualificadores = lista fixa em `signals.py`).
   O M2 nunca inventa: filtra para tokens conhecidos.
2. **Intent dirigido por hipóteses (M3).** `Intent = min(1, Σ priors das hipóteses que
   disparam)`, onde uma hipótese dispara se suas `surface_signals` intersectam os
   `intent_signals` detectados. Ausência de sinal ⇒ `Intent = 0` (Open-World: não
   inventa momentum).
3. **Hard filter por desqualificador (M3).** Qualquer `disqualifier` detectado (founder
   solo, negócio imaturo, retração, sem decisora, fora de setor) zera o lead
   (`p_score = 0`), além do filtro de tecnologia proibida.
4. **Explicação (M5).** Drivers `INTENT_TIMING` (lista os sinais) e `DISQUALIFIER`
   tornam o ranking auditável.

## Consequências
- O ranking passa a refletir a estratégia (ver BDD `objetivo_ranking.feature`:
  Mayara lidera, solo desqualificada zera, fora-de-setor abaixo).
- Determinismo preservado (regras puras; sem rede no M3/M5).
- **Dívida conhecida (fora desta fatia):** a camada de BUSCA (M1/Tavily) e a query
  generation ainda são afinadas para empresas de tecnologia em inglês. Achar founders
  individuais com sinais sociais é trabalho seguinte (provável sondagem empírica antes
  de codar). Os priors das hipóteses são chutes iniciais — calibrar com dados reais.
