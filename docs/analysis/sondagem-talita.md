# Sondagem empírica — aderência da busca ao público Talita (2026-06-03)

Rodada real (Tavily + Gemini) com `scripts/probe_talita.py` e o ICP da Talita.

## Resultado principal (inverte a pessimista L-024)
A busca **é viável** para founders de serviços — desde que: queries em PT-BR
orientadas à persona ("fundadora") + `include_domains=[instagram.com, linkedin.com]`.
Apareceram pessoas reais (ex.: "Amanda Smith Martins, sócia fundadora", "Mateus
Costa-Ribeiro, Co-founder/CEO").

## Cobertura de campos (extração de 14 leads na sondagem)
| Campo | Cobertura |
|---|---|
| instagram_url | 10/14 (71%) — o campo prioritário é o mais disponível |
| linkedin_url | 2/14 |
| website | 1/14 |
| email | 1/14 |
| telefone | 0/14 |
| localização | 1/14 |

Run real do pipeline (Lead Card) com o ICP Talita: **29 leads, ~todos com Instagram**.

## Implicações já implementadas (v0.8.1 / v0.9.0)
- `generate_queries` PT-BR + persona; `include_domains` no M1 (config-driven).
- `CompanyEntity` com contato/social; M2 extrai e **valida domínio** das URLs.
- `LeadCard` acionável (Instagram first) como saída do pipeline.

## Dívida / calibração (backlog, NÃO bloqueia)
- **Precisão de gênero/perfil:** ainda entram homens e contas de empresa (ex.: o run
  trouxe "Silvio Meira"). "fundadora" na query ajuda mas não filtra — V1 pode usar
  desqualificador `perfil_nao_fundadora`/`homem` ou re-rank por persona.
- **Pessoa vs empresa:** vários leads são a conta da firma, sem nome da decisora.
- **Contato (email/telefone):** raríssimo no SERP; só com enriquecimento (fora do
  guardrail atual). Para abordar, o link do Instagram basta (decisão do dono).
- **Priors e pesos:** calibrar com feedback real de conversão.
