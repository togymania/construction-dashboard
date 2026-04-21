# ==========================================
# Construction Dashboard - Docker'siz Setup
# Windows PowerShell icin
# ==========================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Construction Dashboard - Yerel Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# --- Onkosullar ---
function Test-Command($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

if (-Not (Test-Command "python")) {
    Write-Host "[ERR] Python bulunamadi. Kur: https://python.org" -ForegroundColor Red
    exit 1
}
if (-Not (Test-Command "node")) {
    Write-Host "[ERR] Node.js bulunamadi. Kur: https://nodejs.org" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Python: $(python --version)" -ForegroundColor Green
Write-Host "[OK] Node:   $(node --version)" -ForegroundColor Green

if (Test-Command "psql") {
    Write-Host "[OK] psql:   $(psql --version)" -ForegroundColor Green
} else {
    Write-Host "[WARN] psql PATH'te degil. PostgreSQL kurdugundan emin ol." -ForegroundColor Yellow
}
Write-Host ""

# --- Kok .env ---
if (-Not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "[OK] Kok .env olusturuldu" -ForegroundColor Green
    }
}

# --- Backend Setup ---
Write-Host ""
Write-Host "=== Backend Setup ===" -ForegroundColor Cyan
Push-Location backend

if (-Not (Test-Path "venv")) {
    python -m venv venv
    Write-Host "[OK] venv olusturuldu" -ForegroundColor Green
}

# Activate venv
& .\venv\Scripts\Activate.ps1

python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
Write-Host "[OK] Python bagimliliklari kuruldu" -ForegroundColor Green

# Backend .env
if (-Not (Test-Path ".env")) {
    @"
PROJECT_NAME=Construction Management API
ENVIRONMENT=development
SECRET_KEY=dev_secret_key_change_in_production
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=construction_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
"@ | Out-File -Encoding utf8 .env
    Write-Host "[OK] backend/.env olusturuldu" -ForegroundColor Green
}

Pop-Location

# --- Veritabani ---
Write-Host ""
Write-Host "=== Veritabani Kontrol ===" -ForegroundColor Cyan
if (Test-Command "psql") {
    $env:PGPASSWORD = "postgres"
    $dbExists = psql -U postgres -h localhost -lqt 2>$null | Select-String "construction_db"
    if ($dbExists) {
        Write-Host "[OK] construction_db zaten mevcut" -ForegroundColor Green
    } else {
        Write-Host "[INFO] construction_db olusturuluyor..." -ForegroundColor Cyan
        try {
            createdb -U postgres -h localhost construction_db 2>$null
            Write-Host "[OK] construction_db olusturuldu" -ForegroundColor Green
        } catch {
            Write-Host "[WARN] DB olusturulamadi, elle yap: createdb -U postgres construction_db" -ForegroundColor Yellow
        }
    }
}

# --- Frontend Setup ---
Write-Host ""
Write-Host "=== Frontend Setup ===" -ForegroundColor Cyan

if (-Not (Test-Path "frontend\package.json")) {
    if (Test-Path "frontend") {
        Rename-Item -Path "frontend" -NewName "frontend_template_backup"
    }

    npx --yes create-next-app@latest frontend `
        --typescript --tailwind --eslint `
        --app --src-dir --import-alias "@/*" `
        --use-npm --no-turbopack

    if (Test-Path "frontend_template_backup\Dockerfile") {
        Copy-Item "frontend_template_backup\Dockerfile" "frontend\"
    }
    if (Test-Path "frontend_template_backup\.env.local.example") {
        Copy-Item "frontend_template_backup\.env.local.example" "frontend\"
    }

    # Alt klasorler
    $dirs = @(
        "frontend\src\app\(auth)",
        "frontend\src\app\(dashboard)\projects",
        "frontend\src\app\(dashboard)\budget",
        "frontend\src\app\(dashboard)\schedule",
        "frontend\src\app\(dashboard)\risks",
        "frontend\src\app\(dashboard)\reports",
        "frontend\src\components\ui",
        "frontend\src\components\charts",
        "frontend\src\components\layout",
        "frontend\src\components\shared",
        "frontend\src\lib\validators",
        "frontend\src\hooks",
        "frontend\src\store",
        "frontend\src\types",
        "frontend\src\config"
    )
    foreach ($dir in $dirs) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }

    Remove-Item -Recurse -Force "frontend_template_backup"
    Write-Host "[OK] Next.js kuruldu" -ForegroundColor Green
} else {
    Write-Host "[SKIP] Frontend zaten kurulu" -ForegroundColor Yellow
}

# Frontend .env.local
if (-Not (Test-Path "frontend\.env.local")) {
    "NEXT_PUBLIC_API_URL=http://localhost:8000" | Out-File -Encoding utf8 "frontend\.env.local"
    Write-Host "[OK] frontend/.env.local olusturuldu" -ForegroundColor Green
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Kurulum tamamlandi!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Simdi 2 terminal ac:" -ForegroundColor White
Write-Host ""
Write-Host "Terminal 1 (Backend):" -ForegroundColor White
Write-Host "  cd backend" -ForegroundColor Yellow
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host "  uvicorn app.main:app --reload --port 8000" -ForegroundColor Yellow
Write-Host ""
Write-Host "Terminal 2 (Frontend):" -ForegroundColor White
Write-Host "  cd frontend" -ForegroundColor Yellow
Write-Host "  npm run dev" -ForegroundColor Yellow
Write-Host ""
Write-Host "URL'ler:" -ForegroundColor White
Write-Host "  Frontend:  http://localhost:3000" -ForegroundColor Gray
Write-Host "  API Docs:  http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "  Health:    http://localhost:8000/health" -ForegroundColor Gray
Write-Host ""
