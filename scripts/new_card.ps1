# new_card.ps1 - cria um card no GitHub Project #1 ja com o template DoR e o
# bloco checavel, em Backlog (autoria de dia; ver docs/governance/modo-operacional.md).
#
# Uso:
#   pwsh scripts/new_card.ps1 -Title "M2: extrair sinal de contratacao"
#   pwsh scripts/new_card.ps1 -Title "..." -Priority Alta
#
# Cria SEMPRE em Backlog (o DoR ainda nao esta completo no scaffold). Depois de
# preencher o corpo e marcar os [x] do DoR, mova para Todo (aprovacao do dono).

param(
  [Parameter(Mandatory = $true)] [string] $Title,
  [ValidateSet("Alta", "Media", "Baixa")] [string] $Priority = "Media"
)

$ErrorActionPreference = "Stop"
$owner     = "issei"
$number    = 1
$projectId = "PVT_kwHOAAi2gM4BZ3J3"
$statusFid = "PVTSSF_lAHOAAi2gM4BZ3J3zhUy5Jg"   # Status
$backlog   = "6cf82daa"
$prioFid   = "PVTSSF_lAHOAAi2gM4BZ3J3zhUzDd8"   # Priority
$prioOpt   = @{ Alta = "da3cda2e"; Media = "dd378f56"; Baixa = "8ffead41" }

# Checa escopo de Projects
if ((gh auth status 2>&1 | Select-String "Token scopes") -notmatch "project") {
  Write-Error "Token sem escopo 'project'. Rode: gh auth refresh -s project,read:project"; exit 1
}

$body = @'
## Objetivo
<1 frase: o porque + resultado observavel>

## Contrato (entrada -> saida)
<refs a contracts.py / docs/contratos/; ADR se cruza fronteira de modulo>

## Criterios de aceitacao (Gherkin)
- Feliz:      Dado <...> Quando <...> Entao <...>
- Degradado:  Dado <429/timeout> Quando <...> Entao <degrada, nao quebra>
- Open-World: Dado <sinal ausente> Quando <...> Entao <incerteza sobe, missing evidence>

## Fixtures necessarias
<endpoints/arquivos em tests/fixtures/ -- ou: nenhuma (modulo puro)>

## Fora de escopo
<o que NAO fazer nesta card>

## Dependencias / bloqueios
<ADRs, WUs anteriores, plano pago, fixtures -- ou: nenhum>

## DoD especifico
<como saber que ESTA card terminou, alem do DoD generico>

## Tamanho
<1-2 passos? cabe numa janela? se nao, quebrar>

## DoR (checklist -- marque [x]; so vai para Todo com TODOS [x])
- [ ] Objetivo observavel em 1 frase
- [ ] Cabe em 1 WU (1-2 passos / uma janela)
- [ ] Contrato entrada->saida definido (ADR se cruza fronteira de modulo)
- [ ] Gherkin: feliz + degradado + Open-World
- [ ] Fixtures identificadas (ou modulo puro); sem bloqueio de rede-paga
- [ ] Sem decisao de fronteira em aberto
- [ ] Dentro do escopo (CLAUDE.md 3/5, ADR-000) e deterministico (1e-9, APIs mockadas)
- [ ] DoD especifico declarado acima
'@

Write-Host "Criando card '$Title' (Priority=$Priority) em Backlog..."
$item = gh project item-create $number --owner $owner --title $Title --body $body --format json | ConvertFrom-Json
gh project item-edit --id $item.id --project-id $projectId --field-id $statusFid --single-select-option-id $backlog | Out-Null
gh project item-edit --id $item.id --project-id $projectId --field-id $prioFid  --single-select-option-id $prioOpt[$Priority] | Out-Null

Write-Host ""
Write-Host "Card criado (id=$($item.id)) em https://github.com/users/$owner/projects/$number"
Write-Host "Proximo: preencha o corpo, marque os [x] do DoR e mova para Todo (aprovacao)."
