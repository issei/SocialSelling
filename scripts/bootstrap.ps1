# Bootstrap do ambiente local (IaC local) — recria tudo do zero.
# Uso:  ./scripts/bootstrap.ps1
# Nota: usa 'py' (no Windows 'python' pode cair no stub da Microsoft Store).
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
  Write-Host "Criando venv..." -ForegroundColor Cyan
  py -m venv .venv
}

Write-Host "Instalando dependencias (deps + dev)..." -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"

if (-not (Test-Path ".env")) {
  Write-Host "Criando .env a partir do exemplo (preencha as chaves)..." -ForegroundColor Yellow
  Copy-Item ".env.example" ".env"
}

Write-Host "Rodando quality gate..." -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m ruff check .
& .\.venv\Scripts\python.exe -m mypy
& .\.venv\Scripts\python.exe -m pytest -q

Write-Host "BOOTSTRAP OK — ambiente pronto." -ForegroundColor Green
