# 🏗️ Enterprise Construction Management Dashboard

Milyar dolarlık buyuk olcekli insaat projelerinde yoneticilerin kullanacagi, web tabanli, SaaS mimarisinde bir Enterprise Construction Management Dashboard.

## 📦 Tech Stack

- **Frontend:** Next.js 14+ (App Router, TypeScript), TailwindCSS, Shadcn UI
- **Backend:** FastAPI (Python 3.12, async)
- **Database:** PostgreSQL 16
- **Containerization:** Docker + Docker Compose

## 🚀 Hizli Baslangic

**Iki kurulum secenegin var:**

### Secenek A: Docker'siz (Yerel Kurulum) — Onerilen eger Docker yoksa

Detayli rehber: [`NO-DOCKER-SETUP.md`](NO-DOCKER-SETUP.md)

Kisa ozet:

```bash
# Onkosul: Python 3.12+, Node.js 20+, PostgreSQL 16 kurulu olmali

# Otomatik setup
./scripts/setup-nodocker.sh       # macOS/Linux
# .\scripts\setup-nodocker.ps1    # Windows

# Servisleri baslat
./scripts/start-all.sh            # macOS/Linux
# .\scripts\start-all.ps1         # Windows
```

### Secenek B: Docker ile

### Gereksinimler

- Docker Desktop (veya Docker Engine + Docker Compose)
- Git
- (Opsiyonel - local development icin) Node.js 20+, Python 3.12+

### Kurulum

```bash
# 1. Env dosyasini kopyala
cp .env.example .env

# 2. Tum servisleri ayaga kaldir
docker compose up --build

# Arka planda calistirmak icin:
# docker compose up -d --build
```

### Kontrol

Tarayicida su URL'leri ac:

- **Frontend:** http://localhost:3000
- **Backend Swagger UI:** http://localhost:8000/docs
- **Backend ReDoc:** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/health

### Servisleri Durdurma

```bash
docker compose down

# Volume'leri de temizlemek icin (DB datasi silinir):
# docker compose down -v
```

## 📁 Klasor Yapisi

```
construction-dashboard/
├── frontend/          # Next.js uygulamasi
├── backend/           # FastAPI uygulamasi
├── docs/              # Mimari dokumantasyon
├── scripts/           # Yardimci scriptler
├── docker-compose.yml
├── .env.example
└── README.md
```

## 🗓️ Sprint Plani

15 gunluk agile sprint icin gunluk cikti log'u `docs/sprint-log.md` icinde.

- [x] **Gun 1:** Kurulum ve temel mimari
- [ ] **Gun 2:** Frontend layout + Shadcn UI + API v1 router
- [ ] **Gun 3:** Auth (JWT) + kullanici yonetimi
- [ ] **Gun 4-15:** Modul bazli gelistirme

## 🛠️ Local Development (Docker olmadan)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
# Ilk kez: Next.js kurulumu (bos frontend klasoru varsayiyor - asagida init komutu)
npm install
npm run dev
```

> **Not:** `frontend/` klasoru ilk acilista Next.js init komutu ile doldurulmalidir. Detaylar `docs/SETUP.md` icinde.

## 📝 Lisans

Proprietary. Tum haklari sakli.
