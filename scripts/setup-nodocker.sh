#!/usr/bin/env bash
# ==========================================
# Construction Dashboard - Docker'siz Setup
# macOS / Linux icin
# ==========================================
set -e

echo ""
echo "=========================================="
echo "  Construction Dashboard - Yerel Setup"
echo "=========================================="
echo ""

# --- Onkosullar kontrol et ---
command -v python3 >/dev/null 2>&1 || { echo "[ERR] Python3 bulunamadi. Kur: https://python.org"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "[ERR] Node.js bulunamadi. Kur: https://nodejs.org"; exit 1; }
command -v psql >/dev/null 2>&1 || { echo "[WARN] psql bulunamadi. PostgreSQL'i kurdugundan emin ol."; }

echo "[OK] Python: $(python3 --version)"
echo "[OK] Node:   $(node --version)"
command -v psql >/dev/null 2>&1 && echo "[OK] psql:   $(psql --version)"
echo ""

# --- Kok .env ---
if [ ! -f .env ]; then
  cp .env.example .env 2>/dev/null || true
  echo "[OK] Kok .env olusturuldu"
fi

# --- Backend setup ---
echo ""
echo "=== Backend Setup ==="
cd backend

if [ ! -d venv ]; then
  python3 -m venv venv
  echo "[OK] venv olusturuldu"
fi

# shellcheck disable=SC1091
source venv/bin/activate

pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo "[OK] Python bagimliliklari kuruldu"

# Backend .env
if [ ! -f .env ]; then
  cat > .env <<'EOF'
PROJECT_NAME=Construction Management API
ENVIRONMENT=development
SECRET_KEY=dev_secret_key_change_in_production
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=construction_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
EOF
  echo "[OK] backend/.env olusturuldu"
fi

cd ..

# --- Veritabani kontrol ---
echo ""
echo "=== Veritabani Kontrol ==="
if command -v psql >/dev/null 2>&1; then
  if PGPASSWORD=postgres psql -U postgres -h localhost -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw construction_db; then
    echo "[OK] construction_db zaten mevcut"
  else
    echo "[INFO] construction_db olusturuluyor..."
    PGPASSWORD=postgres createdb -U postgres -h localhost construction_db 2>/dev/null \
      && echo "[OK] construction_db olusturuldu" \
      || echo "[WARN] DB olusturulamadi — elle yap: createdb -U postgres construction_db"
  fi
fi

# --- Frontend setup ---
echo ""
echo "=== Frontend Setup ==="

if [ ! -f frontend/package.json ]; then
  mv frontend frontend_template_backup 2>/dev/null || true

  npx --yes create-next-app@latest frontend \
    --typescript --tailwind --eslint \
    --app --src-dir --import-alias "@/*" \
    --use-npm --no-turbopack

  # Dockerfile ve env geri tasi (ileride Docker'a gecilebilsin)
  [ -f frontend_template_backup/Dockerfile ] && cp frontend_template_backup/Dockerfile frontend/
  [ -f frontend_template_backup/.env.local.example ] && cp frontend_template_backup/.env.local.example frontend/

  # Alt klasor yapisini yeniden olustur
  mkdir -p "frontend/src/app/(auth)"
  mkdir -p "frontend/src/app/(dashboard)/projects"
  mkdir -p "frontend/src/app/(dashboard)/budget"
  mkdir -p "frontend/src/app/(dashboard)/schedule"
  mkdir -p "frontend/src/app/(dashboard)/risks"
  mkdir -p "frontend/src/app/(dashboard)/reports"
  mkdir -p frontend/src/components/{ui,charts,layout,shared}
  mkdir -p frontend/src/lib/validators
  mkdir -p frontend/src/{hooks,store,types,config}

  rm -rf frontend_template_backup
  echo "[OK] Next.js kuruldu"
else
  echo "[SKIP] Frontend zaten kurulu"
fi

# Frontend .env.local
if [ ! -f frontend/.env.local ]; then
  echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > frontend/.env.local
  echo "[OK] frontend/.env.local olusturuldu"
fi

echo ""
echo "=========================================="
echo "  Kurulum tamamlandi!"
echo "=========================================="
echo ""
echo "Simdi 2 terminal ac:"
echo ""
echo "Terminal 1 (Backend):"
echo "  cd backend && source venv/bin/activate"
echo "  uvicorn app.main:app --reload --port 8000"
echo ""
echo "Terminal 2 (Frontend):"
echo "  cd frontend && npm run dev"
echo ""
echo "Ardindan:"
echo "  Frontend:  http://localhost:3000"
echo "  API Docs:  http://localhost:8000/docs"
echo "  Health:    http://localhost:8000/health"
echo ""
