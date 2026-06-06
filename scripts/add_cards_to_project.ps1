# add_cards_to_project.ps1
# Adiciona as issues #70-#73 (Proveniência GTM) ao GitHub Project #1 como cards em Backlog.
# Rodar na máquina local onde o gh CLI está autenticado.
#
# Uso: pwsh scripts/add_cards_to_project.ps1

$ErrorActionPreference = "Stop"
$owner     = "issei"
$number    = 1
$projectId = "PVT_kwHOAAi2gM4BZ3J3"
$statusFid = "PVTSSF_lAHOAAi2gM4BZ3J3zhUy5Jg"
$backlog   = "6cf82daa"
$prioFid   = "PVTSSF_lAHOAAi2gM4BZ3J3zhUzDd8"
$prioAlta  = "da3cda2e"
$prioMedia = "dd378f56"

$cards = @(
    @{ issue = 70; priority = $prioAlta;  label = "WU-A: DataProvenance + metadados de hipóteses" },
    @{ issue = 71; priority = $prioAlta;  label = "WU-B: M5 evidence_index → Driver.references" },
    @{ issue = 72; priority = $prioAlta;  label = "WU-C: ICP Profile CRUD + CLI --profile" },
    @{ issue = 73; priority = $prioMedia; label = "WU-D: UI wizard + gestor de perfis + badges" }
)

foreach ($card in $cards) {
    $url = "https://github.com/$owner/SocialSelling/issues/$($card.issue)"
    Write-Host "Adicionando #$($card.issue) — $($card.label)..."

    $item = gh project item-add $number --owner $owner --url $url --format json | ConvertFrom-Json

    gh project item-edit --id $item.id --project-id $projectId `
        --field-id $statusFid --single-select-option-id $backlog | Out-Null

    gh project item-edit --id $item.id --project-id $projectId `
        --field-id $prioFid --single-select-option-id $card.priority | Out-Null

    Write-Host "  ✓ id=$($item.id) → Backlog, Priority=$(if ($card.priority -eq $prioAlta) { 'Alta' } else { 'Media' })"
}

Write-Host ""
Write-Host "Concluído. Acesse: https://github.com/users/$owner/projects/$number"
