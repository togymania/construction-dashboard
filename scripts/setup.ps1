# ==========================================
# Construction Dashboard - Initial Setup
# Windows PowerShell icin
# ==========================================

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Construction Dashboard - Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 1. .env dosyasini olustur
if (-Not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[OK] .env dosyasi olusturuldu" -ForegroundColor Green
} else {
    Write-Host "[SKIP] .env zaten mevcut" -ForegroundColor Yellow
}

# 2. Frontend - Next.js kurulumu
if (-Not (Test-Path "frontend\package.json")) {
    Write-Host ""
    Write-Host "[INFO] Next.js kuruluyor... (birkac dakika surebilir)" -ForegroundColor Cyan
    Write-Host ""

    # Mevcut frontend klasorunu yedekle
    Rename-Item -Path "frontend" -NewName "frontend_template_backup"

    # Next.js'i kur
    npx --yes create-next-app@latest frontend `
        --typescript `
        --tailwind `
        --eslint `
        --app `
        --src-dir `
        --import-alias "@/*" `
        --use-npm `
        --no-turbopack

    # Template dosyalarini geri tasi
    Copy-Item "frontend_template_backup\Dockerfile" "frontend\Dockerfile"
    Copy-Item "frontend_template_backup\.env.local.example" "frontend\.env.local.example"

    # Alt klasorleri olustur
    New-Item -ItemType Directory -Force -Path "frontend\src\app\(auth)" | Out-Null
    New-Item -ItemType Directory -Force -Path "frontend\src\app\(dashboard)\projects" | Out-Null
    New-Item -ItemType Directory -Force -Path "frontend\src\app\(dashboard)\budget" | Out-Null
    New-Item -ItemType Directory -Force -Path "frontend\src\app\(dashboard)\schedule" | Out-Null
    New-Item -ItemType Directory -Force -Path "frontend\src\app\(dashboard)\risks" | Out-Null
    New-Item -ItemType Directory -Force -Path "frontend\src\app\(dashboard)\reports" | Out-Null
    New-Item -ItemType Directory -Force -Path "frontend\src\components\ui" | Out-Null
    New-Item -ItemType Directory -Force -Path "frontend\src\components\charts" | Out-Null
    New-Item -ItemType Directory -Force -Path "frontend\src\components\layout" | Out-Null
    New-Item -ItemType Directory -Force -Path "frontend\src\components\shared" | Out-Null
    New-Item -ItemType Directory -Force -Path "frontend\src\lib\validators" | Out-Null
    New-Item -ItemType Directory -Force -Path "frontend\src\hooks" | Out-Null
    New-Item -ItemType Directory -Force -Path "frontend\src\store" | Out-Null
    New-Item -ItemType Directory -Force -Path "frontend\src\types" | Out-Null
    New-Item -ItemType Directory -Force -Path "frontend\src\config" | Out-Null

    # Backup'i temizle
    Remove-Item -Recurse -Force "frontend_template_backup"

    Write-Host "[OK] Next.js kuruldu ve klasor yapisi hazir" -ForegroundColor Green
} else {
    Write-Host "[SKIP] Frontend zaten kurulu" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Kurulum tamamlandi!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Simdi su komutu calistirabilirsin:" -ForegroundColor White
Write-Host ""
Write-Host "  docker compose up --build" -ForegroundColor Yellow
Write-Host ""
Write-Host "URL'ler:" -ForegroundColor White
Write-Host "  Frontend:  http://localhost:3000" -ForegroundColor Gray
Write-Host "  API Docs:  http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "  Health:    http://localhost:8000/health" -ForegroundColor Gray
Write-Host ""
