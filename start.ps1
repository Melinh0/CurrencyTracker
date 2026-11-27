$ErrorActionPreference = "Stop"
$root = "C:\Users\yagom\Documents\GitHub\CurrencyTracker"

Write-Host "=== CurrencyTracker - Inicializando ===" -ForegroundColor Cyan

function Test-Port($port) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
}

if (-not (Test-Port 9000)) {
    Write-Host "Iniciando Backend (porta 9000)..." -ForegroundColor Yellow
    $env:TF_CPP_MIN_LOG_LEVEL = "3"
    $env:PYTHONUNBUFFERED = "1"
    Start-Process -FilePath "python" -ArgumentList "-m","uvicorn","currency_tracker.api.main:app","--host","127.0.0.1","--port","9000" -WorkingDirectory $root -WindowStyle Hidden
} else {
    Write-Host "Backend ja esta rodando." -ForegroundColor Green
}

if (-not (Test-Port 4000)) {
    Write-Host "Iniciando Frontend (porta 4000)..." -ForegroundColor Yellow
    $env:BROWSER = "none"
    Start-Process -FilePath "cmd" -ArgumentList "/c","npm run dev" -WorkingDirectory "$root\frontend" -WindowStyle Hidden
} else {
    Write-Host "Frontend ja esta rodando." -ForegroundColor Green
}

Write-Host "`nAguardando inicializacao..." -ForegroundColor Yellow
$ok = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 3
    if ((Test-Port 9000) -and (Test-Port 4000)) { $ok = $true; break }
}

if ($ok) {
    Write-Host "`n=== PRONTO ===" -ForegroundColor Green
    Write-Host "Frontend : http://localhost:4000" -ForegroundColor Cyan
    Write-Host "Backend  : http://localhost:9000" -ForegroundColor Cyan
    Write-Host "`nAbra http://localhost:4000 no navegador." -ForegroundColor White
} else {
    Write-Host "`nTimeout aguardando servicos. Verifique manualmente." -ForegroundColor Red
}