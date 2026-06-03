# Prompt — gerar `icp_criteria.json`

Cole o bloco abaixo num LLM (Claude/Gemini), preencha a seção **CONTEXTO DO NEGÓCIO** e
salve a saída em `config/icp_criteria.<nome>.json`. Depois valide:

```bash
.venv/Scripts/python.exe -c "import json; from socialselling.contracts import ICPCriteria; ICPCriteria.model_validate(json.load(open('config/icp_criteria.SEU.json',encoding='utf-8'))); print('ICP valido')"
```

> O contrato usa `extra=\"forbid\"`: não adicione, renomeie nem remova campos. Os tokens
> de `industries`/`technographics` são comparados em **minúsculas** pelo M1/M3 — use os
> termos como aparecem em textos públicos da web.

---

```
Você é um especialista em GTM e definição de ICP (Ideal Customer Profile) B2B.
Gere um arquivo icp_criteria.json VÁLIDO para o sistema SocialSelling a partir do
contexto abaixo. O sistema responde "quem devo abordar primeiro?" buscando empresas
na web; este ICP guia a busca, o Fit e os filtros.

## CONTEXTO DO NEGÓCIO (preencha)
- O que vendemos:
- Problema/dor que resolvemos:
- Perfil de cliente ideal (porte, setor, região, modelo):
- Tecnologias que o cliente ideal costuma usar:
- Tecnologias que DESQUALIFICAM um cliente:
- Cargos que decidem ou influenciam a compra:
- Gatilhos de timing (eventos que indicam momento de compra):

## SCHEMA OBRIGATÓRIO (não adicione/renomeie campos — validação extra=forbid)
{
  "icp_id": "string curta em snake_case (ex: icp_enterprise_cloud_brazil)",
  "firmographics": {
    "industries": ["tokens minúsculos (ex: saas, fintech, e_commerce)"],
    "employee_range": { "min": "inteiro >= 0", "max": "inteiro >= min" },
    "geographies": { "country": "ISO-2 maiúsculo (ex: BR)", "regions": ["siglas (ex: SE, S)"] },
    "business_models": ["ex: B2B, B2C"]
  },
  "technographics": {
    "mandatory": ["techs OBRIGATÓRIAS, minúsculas (ex: aws, kubernetes)"],
    "preferred": ["techs desejáveis, minúsculas"],
    "excluded": ["techs que DESQUALIFICAM, minúsculas (ex: wordpress, wix)"]
  },
  "persona_matrix": {
    "target_roles": ["cargos em MAIUSCULAS_SNAKE (ex: CTO, VP_INFRASTRUCTURE, HEAD_DEVOPS)"],
    "min_seniority": "nivel minimo (ex: MANAGEMENT_LEVEL)"
  },
  "intent_triggers": ["eventos em MAIUSCULAS_SNAKE (ex: JOB_OPENING_TECH, FUNDING_ROUND, EXECUTIVE_TURNOVER)"]
}

## COMO O SISTEMA USA CADA CAMPO (siga para gerar bons valores)
- industries: correspondência por SUBSTRING em minúsculas. Use termos acháveis na web
  (ex: "fintech", não "serviços financeiros"). 3–6 itens.
- employee_range: faixa de porte alvo; min <= max.
- geographies.country: ISO-2 (BR, US...). regions: siglas/UFs relevantes.
- technographics.mandatory: DIRIGEM o Fit (interseção com techs detectadas). Use os nomes
  públicos/normalizados das ferramentas, minúsculos, 2–5 itens.
- technographics.excluded: acionam o HARD FILTER (zeram o lead). Só desqualificadores claros.
- persona_matrix: orientam a busca por decisores.
- intent_triggers: sinais de timing comercial.
- Mantenha listas enxutas e tokens de 1–2 palavras.

## SAÍDA
Responda APENAS com o JSON válido — sem markdown, sem comentários, sem texto antes/depois.
Garantias obrigatórias: employee_range.min <= max; country em ISO-2; NENHUM campo extra.

## EXEMPLO DE REFERÊNCIA (estrutura e estilo dos valores)
{
  "icp_id": "icp_enterprise_cloud_brazil",
  "firmographics": {
    "industries": ["saas", "fintech", "e_commerce"],
    "employee_range": { "min": 100, "max": 1000 },
    "geographies": { "country": "BR", "regions": ["SE", "S"] },
    "business_models": ["B2B"]
  },
  "technographics": {
    "mandatory": ["aws", "kubernetes"],
    "preferred": ["terraform", "datadog"],
    "excluded": ["cpanel", "wordpress"]
  },
  "persona_matrix": {
    "target_roles": ["CTO", "VP_INFRASTRUCTURE", "HEAD_DEVOPS"],
    "min_seniority": "MANAGEMENT_LEVEL"
  },
  "intent_triggers": ["JOB_OPENING_TECH", "FUNDING_ROUND", "EXECUTIVE_TURNOVER"]
}
```
