# ==========================================
# Tek komutla backend + frontend baslat
# Windows PowerShell
# ==========================================
# Kullanim: .\scripts\start-all.ps1

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Servisler baslatiliyor..." -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Backend'i yeni bir PowerShell penceresinde baslat
$backendCmd = @"
cd '$PSScriptRoot\..\backend';
.\venv\Scripts\Activate.ps1;
uvicorn app.main:app --reload --port 8000
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

Start-Sleep -Seconds 2

# Frontend'i yeni bir PowerShell penceresinde baslat
$frontendCmd = @"
cd '$PSScriptRoot\..\frontend';
npm run dev
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

Write-Host ""
Write-Host "[OK] Iki yeni PowerShell penceresi acildi" -ForegroundColor Green
Write-Host ""
Write-Host "URL'ler:" -ForegroundColor White
Write-Host "  Frontend:  http://localhost:3000" -ForegroundColor Gray
Write-Host "  API Docs:  http://localhost:8000/docs" -ForegroundColor Gray
Write-Host ""
Write-Host "Durdurmak icin: Her pencerede Ctrl+C" -ForegroundColor Yellow
Write-Host ""
