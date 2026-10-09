# Starts the CreateFlow backend and frontend together (Windows PowerShell).
# Run from the repository root:  .\scripts\start-dev.ps1

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root 'backend\.venv\Scripts\python.exe'

if (-not (Test-Path $py)) {
    Write-Host 'Backend virtualenv not found. Create it first:' -ForegroundColor Yellow
    Write-Host '  cd backend; py -3.12 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt'
    exit 1
}
if (-not (Test-Path (Join-Path $root 'frontend\node_modules'))) {
    Write-Host 'Frontend dependencies not found. Run: cd frontend; npm install' -ForegroundColor Yellow
    exit 1
}

$backend = Start-Process -FilePath $py `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--reload', '--port', '8000' `
    -WorkingDirectory (Join-Path $root 'backend') `
    -PassThru -NoNewWindow

Write-Host "Backend starting on http://127.0.0.1:8000 (pid $($backend.Id))" -ForegroundColor Cyan
Start-Sleep -Seconds 3

Set-Location (Join-Path $root 'frontend')
npm run dev

Write-Host 'Backend stopped.' -ForegroundColor Cyan