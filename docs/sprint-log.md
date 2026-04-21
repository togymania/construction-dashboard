# 📋 Sprint Log — 15 Gunluk Agile Sprint

## 🎯 Proje Hedefi

Milyar dolarlik buyuk olcekli insaat projelerinde yoneticilerin kullanacagi, web tabanli, SaaS mimarisinde bir **Enterprise Construction Management Dashboard** gelistirmek.

---

## ✅ Gun 1: Kurulum ve Temel Mimari

**Tarih:** _YYYY-MM-DD_
**Durum:** ✅ Tamamlandi

### Yapilanlar

- [x] Monorepo klasor yapisi olusturuldu (`frontend/`, `backend/`, `docs/`, `scripts/`)
- [x] FastAPI boilerplate (`app/main.py`, config, health check endpoint)
- [x] Next.js (App Router + TypeScript + Tailwind) hazirligi
- [x] PostgreSQL 16 Docker servisi
- [x] `docker-compose.yml` — tek komutla 3 servisi ayaga kaldirma
- [x] `.gitignore` (Node + Python + OS + Docker + AI artifacts)
- [x] Otomatik setup scriptleri (`setup.sh` + `setup.ps1`)
- [x] Olceklenebilir servis yapisi (`services/ai_parser`, `services/report_generator`, `services/notifications`)

### Mimari Kararlar (ADR)

1. **Monorepo** secildi — tip paylasimi ve CI/CD pratigi icin.
2. **FastAPI** (Django/Flask yerine) — async-first + ileride AI entegrasyonu icin.
3. **App Router** (Pages Router yerine) — server components ve modern Next.js paradigmasi.
4. **Shadcn UI** (MUI/Chakra yerine) — kod ownership + Tailwind entegrasyonu.
5. **PostgreSQL** (MongoDB yerine) — iliskisel veri modeli (projeler, butce kalemleri, WBS) icin.

### Onemli Notlar

- PostgreSQL host portu `5433` olarak ayarlandi (local PostgreSQL ile cakismamasi icin).
- Backend Docker image'inda `alembic`, `asyncpg`, `passlib` gibi bagimliliklar onceden yuklendi — ileriki gunlerde image rebuild gereksiz olsun diye.
- Frontend icin `--no-turbopack` secildi — Docker volume mount'larinda Turbopack bazi sorunlar yasayabiliyor.

---

## ⏳ Gun 2: Frontend Layout + Shadcn UI + API v1 Router

**Durum:** 🔜 Planlanan

### Planlanan cikti

- [ ] Shadcn component'lar eklenecek (Button, Card, Input, Table, Dialog, Sheet)
- [ ] Dashboard layout: Sidebar + Header + Breadcrumb
- [ ] Theme toggle (light/dark)
- [ ] Backend'de `/api/v1/` router yapisi
- [ ] Ornek mock endpoint: `/api/v1/projects`

---

## ⏳ Gun 3: Auth (JWT) + Kullanici Yonetimi

**Durum:** 🔜 Planlanan

### Planlanan cikti

- [ ] Database modelleri (User, Role)
- [ ] Alembic migration
- [ ] JWT tabanli auth (access + refresh token)
- [ ] Login/Register sayfalari
- [ ] Frontend'de auth context + protected routes

---

## ⏳ Gun 4-15

Detaylandirilacak modul planlari:

- **Gun 4:** Project CRUD (backend + frontend)
- **Gun 5:** Budget Tracking modulu
- **Gun 6:** Schedule / Gantt chart
- **Gun 7:** Risk Register
- **Gun 8:** Document Management (file upload)
- **Gun 9:** AI Parser (PDF/sozlesme analizi)
- **Gun 10:** Real-time notifications (WebSocket)
- **Gun 11:** Reporting & PDF/Excel export
- **Gun 12:** Role-based access control (RBAC)
- **Gun 13:** Dashboard analytics & KPI widget'lari
- **Gun 14:** Testing (unit + e2e with Playwright)
- **Gun 15:** Production deployment & CI/CD
