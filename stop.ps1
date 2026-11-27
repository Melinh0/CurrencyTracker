Write-Host "=== Parando CurrencyTracker ===" -ForegroundColor Cyan
$stopped = @()

foreach ($port in @(9000, 4000)) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $procId = $conn.OwningProcess
        try { Stop-Process -Id $procId -Force -ErrorAction Stop; $stopped += "Porta $port (PID $procId)" } catch {}
    }
}

Get-Process python,node -ErrorAction SilentlyContinue | ForEach-Object {
    $cl = $_.CommandLine
}

Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

if ($stopped) { Write-Host ("Parado: " + ($stopped -join ", ")) -ForegroundColor Green }
else { Write-Host "Nenhum servico ativo." -ForegroundColor Yellow }
Write-Host "Pronto." -ForegroundColor Green