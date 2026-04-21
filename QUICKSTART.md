# 🚀 QUICKSTART

Bu projeyi ayaga kaldirmak icin 2 farkli yol var. **Onerilen: Yol 1.**

---

## 📋 Onkosullar

- **Docker Desktop** kurulu ve calisiyor olmali ([Indir](https://www.docker.com/products/docker-desktop/))
- **Node.js 20+** ([Indir](https://nodejs.org/)) — yalnizca setup scripti icin (Next.js'i indirmek icin)
- **Git** (opsiyonel)

---

## ✅ Yol 1: Otomatik Kurulum (Onerilen)

### macOS / Linux

```bash
cd construction-dashboard
chmod +x scripts/setup.sh
./scripts/setup.sh
docker compose up --build
```

### Windows (PowerShell)

```powershell
cd construction-dashboard

# PowerShell script policy'si kisitliysa once bunu calistir:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

.\scripts\setup.ps1
docker compose up --build
```

**Ne yapiyor bu script?**
1. `.env` dosyasini olusturuyor (`.env.example`'dan)
2. `frontend/` klasorune Next.js kuruyor (`create-next-app` ile)
3. Tum alt klasor yapilarini olusturuyor
4. Docker icin hazir hale getiriyor

---

## 🛠️ Yol 2: Manuel Kurulum

### 1. .env Olustur

```bash
cp .env.example .env
```

### 2. Frontend Kur

Root dizinden:

```bash
# Mevcut frontend/ klasorunu yedekle (Dockerfile gerekli cunku)
mv frontend frontend_backup

# Next.js'i kur
npx create-next-app@latest frontend \
  --typescript --tailwind --eslint \
  --app --src-dir --import-alias "@/*" \
  --use-npm --no-turbopack

# Dockerfile'i geri tasi
cp frontend_backup/Dockerfile frontend/
cp frontend_backup/.env.local.example frontend/

# Backup'i sil
rm -rf frontend_backup
```

### 3. Docker'i Baslat

```bash
docker compose up --build
```

---

## 🔍 Dogrulama

Basariyla calistiysa:

| URL | Ne goreceksin? |
|-----|----------------|
| http://localhost:3000 | Next.js varsayilan sayfasi |
| http://localhost:8000 | `{"message": "Construction Management API v0.1.0"}` |
| http://localhost:8000/docs | FastAPI Swagger UI |
| http://localhost:8000/health | `{"status": "ok", ...}` |

---

## 🛑 Servisleri Durdur

```bash
# Container'lari durdur
docker compose down

# Volume'leri de sil (DB datasi gider!)
docker compose down -v
```

---

## 🐛 Sorun Giderme

### "port is already allocated" hatasi

Baska bir servis 3000, 8000 veya 5433 portunu kullaniyor. `docker-compose.yml` icindeki port mapping'leri degistir (ornek: `"3001:3000"`).

### Frontend container'i surekli yeniden basliyor

`frontend/` klasorunde `package.json` yok demektir. Setup scriptini calistirmayi unutmus olabilirsin.

### "Cannot connect to Docker daemon"

Docker Desktop'i baslatmayi unuttun. Windows/macOS'ta uygulamayi ac, Linux'ta: `sudo systemctl start docker`.

### Python paketleri build sirasinda hata veriyor

Docker'a yeterli RAM ayirmamis olabilirsin (`psycopg2` icin 2GB+ onerilir). Docker Desktop > Settings > Resources bolumunden arttir.

### Windows'ta setup.ps1 "script cannot be loaded" diyor

Bir kereligine bu komutu calistir:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

---

## 📁 Sonraki Adim

Kurulum tamamsa **Gun 2** promptunu gonderebilirsin — frontend layout'una ve Shadcn UI component'larina geciyoruz.
