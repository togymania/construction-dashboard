#!/usr/bin/env bash
# ==========================================
# Construction Dashboard - Initial Setup
# Linux/macOS icin
# ==========================================
set -e

echo ""
echo "=========================================="
echo "  Construction Dashboard - Setup"
echo "=========================================="
echo ""

# 1. .env dosyasini olustur
if [ ! -f .env ]; then
  cp .env.example .env
  echo "[OK] .env dosyasi olusturuldu"
else
  echo "[SKIP] .env zaten mevcut"
fi

# 2. Frontend - Next.js kurulumu
if [ ! -f frontend/package.json ]; then
  echo ""
  echo "[INFO] Next.js kuruluyor... (birkac dakika surebilir)"
  echo ""

  # Mevcut frontend klasorunu yedekle
  mv frontend frontend_template_backup

  # Next.js'i interaktif olmayan modda kur
  npx --yes create-next-app@latest frontend \
    --typescript \
    --tailwind \
    --eslint \
    --app \
    --src-dir \
    --import-alias "@/*" \
    --use-npm \
    --no-turbopack

  # Template'deki dosyalari (Dockerfile, .env.local.example, alt klasorler) geri tasi
  cp -r frontend_template_backup/Dockerfile frontend/Dockerfile
  cp -r frontend_template_backup/.env.local.example frontend/.env.local.example

  # Alt klasorleri olustur
  mkdir -p frontend/src/app/\(auth\)
  mkdir -p frontend/src/app/\(dashboard\)/{projects,budget,schedule,risks,reports}
  mkdir -p frontend/src/components/{ui,charts,layout,shared}
  mkdir -p frontend/src/lib/validators
  mkdir -p frontend/src/{hooks,store,types,config}

  # Backup'i temizle
  rm -rf frontend_template_backup

  echo "[OK] Next.js kuruldu ve klasor yapisi hazir"
else
  echo "[SKIP] Frontend zaten kurulu"
fi

echo ""
echo "=========================================="
echo "  Kurulum tamamlandi!"
echo "=========================================="
echo ""
echo "Simdi su komutu calistirabilirsin:"
echo ""
echo "  docker compose up --build"
echo ""
echo "URL'ler:"
echo "  Frontend:  http://localhost:3000"
echo "  API Docs:  http://localhost:8000/docs"
echo "  Health:    http://localhost:8000/health"
echo ""
