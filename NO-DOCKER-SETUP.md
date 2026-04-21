# 🚀 Docker'siz Kurulum Rehberi

Bu rehber, Docker kullanmadan projeyi yerel makinende calistirmak icindir. 3 servisi ayri ayri kuracagiz:

1. **PostgreSQL** — native installer ile
2. **Backend (FastAPI)** — Python venv ile
3. **Frontend (Next.js)** — npm ile

---

## 📋 Genel Gereksinimler

Uc aracı sisteme kurman lazim:

- **Python 3.12+** — [python.org/downloads](https://www.python.org/downloads/)
- **Node.js 20+** — [nodejs.org](https://nodejs.org/)
- **PostgreSQL 16** — (asagida isletim sistemine gore kurulum)

---

## 🗄️ 1. PostgreSQL Kurulumu

### Windows

1. [EnterpriseDB PostgreSQL installer](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads) indir
2. Kurulumda **sifre** olarak `postgres` gir (veya kendi sifren — sonra `.env`'e yazacagiz)
3. Port: `5432` (varsayilan)
4. Kurulum bittiginde **pgAdmin** ile veya komut satirindan test:

```powershell
# Start Menu > "SQL Shell (psql)" ac
# Varsayilanlari kabul et, sifreni gir
# Icerideyken:
CREATE DATABASE construction_db;
\q
```

### macOS

**Secenek A: Postgres.app (en kolay)**

1. [postgresapp.com](https://postgresapp.com/) → indir ve Applications'a surukle
2. Baslat, "Initialize" butonuna tikla
3. Terminal'de database olustur:

```bash
/Applications/Postgres.app/Contents/Versions/latest/bin/createdb construction_db
```

**Secenek B: Homebrew**

```bash
brew install postgresql@16
brew services start postgresql@16
createdb construction_db
```

### Linux (Ubuntu/Debian)

```bash
# Repository ekle
sudo sh -c 'echo "deb https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -

# Kur
sudo apt update
sudo apt install -y postgresql-16

# Servisi baslat
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Sifre ayarla ve DB olustur
sudo -u postgres psql
```

psql icindeyken:
```sql
ALTER USER postgres WITH PASSWORD 'postgres';
CREATE DATABASE construction_db;
\q
```

### ✅ PostgreSQL Dogrulama

Herhangi bir isletim sisteminde:

```bash
psql -U postgres -d construction_db -c "SELECT version();"
```

PostgreSQL versiyonu yaziyorsa basarili. 🎉

---

## 🐍 2. Backend Kurulumu (FastAPI)

### Adim 1: Klasore Gir ve venv Olustur

```bash
cd construction-dashboard/backend
python -m venv venv
```

### Adim 2: venv Aktive Et

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
# Eger hata verirse bir kereligine:
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

**Windows (CMD):**
```cmd
venv\Scripts\activate.bat
```

**macOS / Linux:**
```bash
source venv/bin/activate
```

Terminal satirinin basinda `(venv)` yazmasi lazim — aktif oldugunu boyle anlariz.

### Adim 3: Bagimliliklari Kur

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Adim 4: .env Dosyasini Olustur

`backend/.env` dosyasi olustur (YOKSA):

```env
PROJECT_NAME=Construction Management API
ENVIRONMENT=development
SECRET_KEY=dev_secret_key_change_in_production

POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=construction_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

> ⚠️ **Onemli:** `POSTGRES_HOST` artik `db` degil, **`localhost`**. Ve `POSTGRES_PORT` artik 5433 degil, **5432** (native kurulumun varsayilan portu).

### Adim 5: Backend'i Baslat

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Test: Tarayicida http://localhost:8000/health ac → `{"status": "ok", ...}` gormen lazim. ✅

---

## ⚛️ 3. Frontend Kurulumu (Next.js)

### Adim 1: Next.js Init (ilk kez)

Yeni bir terminal ac (backend'inki calismaya devam etsin).

Proje kokunde:

```bash
cd construction-dashboard

# Mevcut frontend klasoru sadece Dockerfile ve alt klasorler iceriyor
# Nextjs'i yuklemek icin gecici olarak yedekle:
mv frontend frontend_backup

npx create-next-app@latest frontend \
  --typescript --tailwind --eslint \
  --app --src-dir --import-alias "@/*" \
  --use-npm --no-turbopack

# Dockerfile ve env'i geri tasi (ileride Docker'a gecersen diye)
cp frontend_backup/Dockerfile frontend/ 2>/dev/null || true
cp frontend_backup/.env.local.example frontend/ 2>/dev/null || true

# Backup'i sil
rm -rf frontend_backup     # Linux/macOS
# Windows: Remove-Item -Recurse -Force frontend_backup
```

### Adim 2: .env.local Olustur

`frontend/.env.local` dosyasi:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Adim 3: Frontend'i Baslat

```bash
cd frontend
npm run dev
```

Test: http://localhost:3000 → Next.js karsilama sayfasi. ✅

---

## 🎯 Tum Servisler Ayagi Kalktiginda

Uc farkli terminal acik olacak:

| Terminal | Ne Calisiyor | Port |
|----------|--------------|------|
| 1 | PostgreSQL (arka planda, servis) | 5432 |
| 2 | `uvicorn app.main:app --reload` | 8000 |
| 3 | `npm run dev` | 3000 |

URL'ler:
- http://localhost:3000 — Frontend
- http://localhost:8000/docs — API Swagger
- http://localhost:8000/health — Health check

---

## 🛑 Servisleri Durdur

- **Frontend/Backend:** Terminalde `Ctrl+C`
- **PostgreSQL:**
  - Windows: Services.msc > postgresql > Stop
  - macOS (Postgres.app): uygulamanin menusunden Stop
  - macOS (Homebrew): `brew services stop postgresql@16`
  - Linux: `sudo systemctl stop postgresql`

---

## 🐛 Sorun Giderme

### "psql: command not found"

PostgreSQL'in `bin` klasoru PATH'e eklenmemis.

- **Windows:** `C:\Program Files\PostgreSQL\16\bin` — System Environment Variables > PATH'e ekle
- **macOS (Postgres.app):** `echo 'export PATH="/Applications/Postgres.app/Contents/Versions/latest/bin:$PATH"' >> ~/.zshrc`

### "connection refused" (Backend DB'ye baglanamiyor)

PostgreSQL calismiyor veya yanlis portta. Kontrol et:
```bash
# Calisip calismadigini gor:
# Windows: services.msc
# macOS: brew services list  (veya Postgres.app acik mi?)
# Linux: sudo systemctl status postgresql
```

### "password authentication failed for user postgres"

Kurulumda girdigin sifre `.env`'deki sifre ile uyusmuyor. `.env`'i duzelt veya postgres sifresini sifirla:

```bash
sudo -u postgres psql
ALTER USER postgres WITH PASSWORD 'postgres';
\q
```

### "Port 5432 is already in use"

Zaten calisan bir PostgreSQL var. Ya onu kullan ya da yeni kurulumu baska bir port'ta baslat.

### Python 'pip install psycopg2-binary' hata veriyor

Windows'ta bazen wheel eksik oluyor. Bu durumda:

```bash
pip install psycopg2-binary --only-binary :all:
```

### "Error: Cannot find module 'next'" (frontend)

`npm install` calistirmadiysan:
```bash
cd frontend
npm install
npm run dev
```

---

## 🔄 Docker'a Gecerseniz

Docker'i sonradan kurmak istersen, hicbir kod degisikligi gerekmez. Sadece:

1. `.env` icindeki `POSTGRES_HOST` degerini `localhost` → `db` yap
2. `POSTGRES_PORT` degerini `5432` → `5432` (ayni) birak
3. `docker compose up --build`

Zip icinde hem Docker'li hem Docker'siz konfig var, ikisi de hazir.

---

## 📝 Ozet Komut Listesi (Quick Reference)

Her seferinde bastan baslatmak icin:

```bash
# Terminal 1 (PostgreSQL zaten arka planda calisiyor)

# Terminal 2 (Backend)
cd construction-dashboard/backend
source venv/bin/activate       # Linux/macOS
# .\venv\Scripts\Activate.ps1  # Windows
uvicorn app.main:app --reload --port 8000

# Terminal 3 (Frontend)
cd construction-dashboard/frontend
npm run dev
```

Bu kadar! 🎉
