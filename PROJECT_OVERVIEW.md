# Monartstroy PM AI — Proje Özeti

**Canlı sistem:** https://monart-stroy-pm.vercel.app
**Backend API:** https://monotek-stroy-pm-api.onrender.com
**Proje:** Central Moscow Hippodrome (Merkez Moskova Hipodrom Restorasyonu)

---

## 1. Genel Bakış

Tek bir web kabin uygulaması. Her departmanın elinde dağınık duran Excel'leri (finans, ÇMI bütçe, hakediş, puantaj, tender PDF/Excel) tek noktaya topluyor, kendi içlerinde bağlıyor ve yöneticiye karar (sayı değil) sunuyor.

Mimari:
- **Frontend:** Next.js 16 + React 19 + Tailwind 4 + Shadcn UI — Vercel'de host
- **Backend:** FastAPI 0.115 + SQLAlchemy 2.0 async + Alembic migrations — Render Frankfurt'ta host
- **DB:** PostgreSQL (Neon Frankfurt)
- **AI:** Anthropic Claude (claude-sonnet-4-5)
- **Dil:** TR / EN tam bilingual (database'deki ham Rusça metinler korunur)
- **Tarih formatı:** dd/mm/yyyy global (en-GB locale)
- **Para birimi:** RUB (₽) ile kompakt format (1.48B ₽, 245.3M ₽)

---

## 2. Kullanıcı Rolleri (RBAC)

5 farklı rol var:

| Rol | İzin |
|---|---|
| **ADMIN** | Her şey, ayarlar dahil |
| **PROJECT_MANAGER** | Tüm modüller, Excel import, atama |
| **ENGINEER** | Çoğunlukla okuma, ihale ekleme |
| **VIEWER** | Sadece okuma — edit butonları gizli |
| **WORKFORCE_EDITOR** | Sadece İşgücü sekmesi, ona da read+upload |

Demo hesaplar (canlı sistemde aktif):
- `admin@example.com` / `admin123` → VIEWER (read-only)
- `admin1@example.com` / `admin456` → WORKFORCE_EDITOR

WORKFORCE_EDITOR girişinde sidebar diğer sekmeleri göstermiyor, /projects/{id}/ ana sayfaya girse otomatik /workforce'a redirect ediyor, dashboard'da "Sınırlı erişim" kartı çıkıyor.

---

## 3. Sayfa Sayfa Özellikler

### 3.1 Dashboard (Panel)
- Proje sayısı, toplam bütçe, ilerleme özetleri
- Daily Briefing — Claude'un günlük 3-paragraf brifingi (her sabah AI tarafından üretiliyor)
- Data Quality kartı — kategorize edilmemiş ledger satırı sayısı + risk seviyesi

### 3.2 Projeler Listesi
- Projeler tablosu (durum, sağlık, bütçe, harcanan, ilerleme)
- Yeni proje oluşturma sihirbazı

### 3.3 Proje Genel Bakış
- Proje header card (lokasyon, durum, sağlık etiketi, açıklama)
- **EAC Forecast widget** — BAC (plan), AC (harcanan), EAC (tahmin), CPI, Variance, Progress
  - "Under budget / On track / Budget overrun / Insufficient data" rozet
  - Yeşil/Sarı/Kırmızı renkli durum
- **Modules grid** — 8 modül kartı (Taşeronlar, İşgücü, Bütçe, Harcamalar, İhaleler, Takvim, Riskler, Raporlar)

### 3.4 Taşeronlar
- Taşeron firma listesi (ad, vergi no, uzmanlık, durum, rating)
- Filtreleme: durum, uzmanlık, arama
- Her firmaya tıklayınca firma detay sayfası:
  - Tüm kontratlar (active/draft/completed)
  - Her kontratın altında ödemeler tablosu (manuel hakediş + Excel ledger payments birleşik)
  - Ödeme disiplin grafiği (zamanında / geç / çok geç oran)
  - Kontrat alarmları (end-date yaklaşıyor, fazla ödeme, vs.)
  - **AI Insights** — Claude'un firma profil özeti
  - **Profile Report (Firma Kartviziti)** — bir sayfalık executive özet
- **Aggregate Cash Flow Forecast** — 3 aylık nakit akışı tahmini (best/likely/worst senaryolar, mevsimsellik faktörü, güven skoru)

### 3.5 İşgücü (Workforce)
- 4 KPI kartı: Bugünün toplam mevcudu, ortalama 7 gün, Direct/Indirect/Subcont. dağılımı
- **Kümülatif adam-saat** (Civil / Electrical / Mechanical disiplinleri, günde 10 saat varsayım)
- Şirket bazlı kart (Monart Stroy + Monotek Stroy) — total, direct, indirect, subcont. rakamları
- Son 30 snapshot'ın tablosu (manuel + Excel'den yüklenmiş)
- Excel yükleme — birden fazla dosya aynı anda, şirket header'dan otomatik tespit edilir

### 3.6 Bütçe
- 4 KPI: Total Planned, Total Spent (OZET'ten), Utilization %, Remaining
- 2 grafik: Kategori bazlı planlanan, planlanan vs harcanan
- 3 sekme: Budget Items / Variance / Subcontractors
- **Budget Items** — kalem kalem planlanan tutar, kategori filtreleme
- **Variance Report** — her kalem için planned / actual / variance / utilization (Bina/Yollar gibi category-slug seviyesindeki ledger atamaları da kaleme oransal dağılır)
- **ÇMI Import** — Master ÇMI Excel'inden "Bütçe sorumlusu = Монарт" satırlarını filtreleyip 15 üst kategoriye otomatik kategorize ediyor (Bina, Yollar, Altyapı, Haberleşme, Isıtma, Elektrik, Peyzaj, Aydınlatma, Diğer İnşaat). Alt satırlar parent'ın `notes` alanına bullet olarak yazılır.

### 3.7 Harcamalar (Expenses / Ledger)
- **3 üst KPI**: Toplam Gelir, Toplam Gider, Net — değerler OZET sayfasından (Finansal Özet'teki yeşil = gelir, kırmızı = gider toplamı). Para birimi RUB ve kompakt format (15.45B ₽, 8.61B ₽, 6.84B ₽).
- **Finansal Özet (OZET) kartları** — iki yan yana kart:
  - **MONOTEKSTROY** — ISVEREN TAHSILATLARI, FIRMA ODEMELERI, UCRET GIDERLERI, VERGI ODEMELERI (Gelir Vergisi + KDV sub-item'lar), FAIZ GELIRLERI, BANKA GIDERLERI, DIGER GELIR-GIDERLER, TOPLAM
  - **MONARTSTROY** — aynı kalemler
  - Renk kodlu: pozitif yeşil, negatif kırmızı, sıfır gri
  - "Excel Yükle" butonuna basıp `Harcama Takip-HIPODROM-Monart.xlsx` veya `...-Monotek.xlsx` yüklediğinde:
    - Excel'in **Gelir-Gider** sayfasındaki tüm satırlar ledger_entries tablosuna eklenir (duplicate atlanır)
    - Excel'in **OZET** sayfasındaki rakamlar Finansal Özet kartlarına yazılır (dosya adından şirket otomatik tespit)
    - openpyxl `read_only=True` ile stream ediliyor → 10+ MB dosyalar OOM olmadan parse oluyor
- **Ledger import wizard** (2 adım):
  - Adım 1: Excel yükle, parse, preview (kaç satır, kaç duplicate, taşeron eşleştirme önerileri)
  - Adım 2: Eşleştirmeleri onayla, commit
- **Ledger tablosu** — 100 satır/sayfa, gelir/gider sekmeleri, taşeronsuz/bütçe-kodsuz filtreleri, arama, tarih aralığı
- Inline atama: her satıra budget_code ve subcontractor atanabiliyor (Toplu Ata da var)
- Atanan satırlar otomatik olarak:
  - Bütçe sekmesindeki "Actual" rakamlarına akıyor
  - Taşeronlar sekmesindeki "Paid" ve cash flow forecast'a akıyor

### 3.8 İhaleler (Tenders)
- Tender listesi (tablo: Başlık, Durum, Kalem sayısı, Teklif sayısı, En düşük, Oluşturulma)
- **Yeni tender oluşturma**:
  - Excel/PDF yükle → AI extraction (Claude PDF/Excel'i okuyup line items + bid'lere döker)
  - Manuel giriş
- **Tender detay sayfası**:
  - Karşılaştırma tablosu — line item × bidder grid
  - Detaylı mod (labor + material + total ayrımı) ve basit mod
  - Per-line variance göstergeleri (en ucuza göre %)
  - Variant detection (alternative versions of same item)
  - VAT toggle (KDV dahil/hariç)
  - Text-price detection (Claude metin tabanlı fiyatları da algılar)
  - Hierarchy desteği (üst kalem ve alt kalemler)
  - Quote date + revision history (yeni teklif eski versiyonu supersede eder)
  - "Add Bid (File)" — sadece tek firmanın teklifini yükle, AI mevcut line items'a göre eşleştirir
  - "Add Bid (Manual)" — sıfır dolu form, kullanıcı doldurur
  - Edit bid modal — AI yanlış okuduysa düzeltme
  - Delete bid + Delete tender
  - Award bid — kazanan teklifi işaretle (proje sonra ihale tamamlanmış gibi)
- **AI Bid Analysis** (Tender AI Analizi sayfası):
  - 6-bölümlü Claude raporu: Overview, Comparison, Analysis, Risks, Recommendation, Executive Summary
  - Confidence score
  - Bid spread metriği
- **Market Price Help** — Seviye 1 market fiyat referansı
- **TDF Excel Export** — gerçek KP Forma şablonu kullanarak 2-bidder formatında Excel çıktısı

### 3.9 AI Analysis (AI Project Director)
**En önemli modül.** Dashboard olmaktan çıkıp gerçek bir proje direktörüne dönüştü.

Üstte tek satır verdict (kırmızı/sarı/yeşil hero):
- **ON TRACK** / **AT RISK** / **CRITICAL** + tek cümle açıklama

3 sütun:
- **Key Drivers** — neden böyle (max 3 madde)
- **Critical Blocker** — en büyük tek tıkanıklık
- **Impact** — kaç gün gecikme + Time/Cost/Execution riski

2 sütun:
- **Data Confidence** — HIGH/MEDIUM/LOW + güvenilmeyen kısım açıklaması
- **Required Actions** — 3 net, anında yapılacak aksiyon

Altta **8 KPI tile** (4-per-row):
1. **Schedule Health** — plan vs actual delay (gün)
2. **Projected Delay** — bu hızla ne kadar geç biter
3. **Critical Path** — clear / at_risk / blocked
4. **Progress** — fiziksel ilerleme %
5. **Resource Efficiency** — progress / headcount
6. **Cost Consistency** — underreported / consistent / overrun_risk
7. **Data Reliability** — % kaç ledger satırı atanmış
8. **Contractor Risk** — kaç taşeron gecikmeli

**Arkadaki mantık (7 adım):**
1. Data validation — eksik veri %40+ → LOW confidence
2. Schedule check — actual vs planned linear interpolation
3. Critical path — proje bitişine 30 gün kala kontratlar
4. Resource efficiency
5. Cost logic — ac/bac vs progress %20 sapma
6. Momentum — son 7 gün headcount trendi
7. Final verdict — CRITICAL / AT_RISK / ON_TRACK

**Claude prompt davranış kuralları:**
- "Senior construction project director" rolü
- Tek cümle vardict
- Tek root cause
- "may / might / possibly" yok
- Asla aksiyonsuz bitmesin
- Veri kötüyse "Financials cannot be trusted" net ifadesi

API yoksa rule-based fallback aynı yapıyı üretiyor.

### 3.10 Raporlar
- Executive Summary kapak kartı
- 6 bölümlü AI raporu (proje yöneticisi için)
- Refresh + Print butonları

### 3.11 Riskler / Takvim
- Henüz "Coming Soon" placeholder — gelecek faz

### 3.12 Bütçe Kategorileri (Admin)
- 22 kategori yönetimi (6 default + 15 Monart-spesifik + Other)
- Reorder, edit, delete

### 3.13 Auth + Ayarlar
- Login / Register
- Token-based JWT
- User profile
- Tema (light/dark/system)
- Dil seçici (TR / EN)

---

## 4. Veri Akışı (Bir Günlük Tipik Kullanım)

1. **Sabah 09:00 — Muhasebe:**
   `Harcama Takip-HIPODROM-Monotek.xlsx` ve `...-Monart.xlsx` dosyalarını "Excel Yükle"den yükler. Sistem 5 saniyede:
   - 2,000+ yeni gelir-gider satırını ledger'a ekler (duplicate atlar)
   - OZET sayfasından iki şirketin finansal özetini Finansal Özet kartlarına yazar
   - Üst 3 KPI (Toplam Gelir 15.45B ₽, Gider 8.61B ₽, Net 6.84B ₽) güncellenir
   - EAC widget'ı AC değerini OZET'ten alıp CPI ve EAC'yi tekrar hesaplar

2. **Sabah 09:30 — Sahada İşgücü Sorumlusu:**
   `İşgücü > Excel Yükle`'den günün pankart dosyasını yükler. Sistem şirket header'dan otomatik tespit eder, snapshot olarak kaydeder, KPI'lar ve kümülatif adam-saat hesabı anında güncellenir.

3. **Öğleden sonra — Tender İnşaat Mühendisi:**
   Yeni teklif PDF'i geldi. `İhaleler > Add Bid (File)`'a yükler. Claude 10 saniyede PDF'i okur, mevcut line items'a eşleştirir. Mühendis yanlış eşleşmeleri düzelter, kaydeder. Karşılaştırma tablosunda yeni firma kolonu açılır.

4. **Akşam 17:00 — Proje Müdürü:**
   `AI Analysis > Refresh` butonuna basar. 8 saniyede Claude güncel veriyi okur ve:
   > VERDICT: AT RISK
   > Project is 12 days behind schedule due to delayed concrete deliveries; subcontractor cash flow tightens next month; 2 critical path activities at risk.
   > Required actions: 1) ... 2) ... 3) ...

   Müdür sayfayı kapatır, aksiyonları whatsapp'tan ekibe iletir.

---

## 5. Bugüne Kadar Çözülen Önemli Problemler

| Problem | Çözüm |
|---|---|
| Render free tier 50sn cold-start | UptimeRobot keep-alive ping (5dk'da bir) |
| Render Frankfurt'a taşıma | render.yaml region: frankfurt |
| CORS preflight 405 | FastAPI allow_origin_regex |
| bcrypt 4.x passlib crash | bcrypt<4 pin |
| Vercel zod transform TS error | Schema input/output type ayrımı |
| Vercel custom domain 404 | Manuel domain ekleme |
| WORKFORCE_EDITOR enum mismatch | İkinci migration ile UPPERCASE değer eklendi |
| Demo users startup seed | startCommand'a seed_demo_users dahil edildi |
| 10MB+ Monart Excel OOM | openpyxl `read_only=True` mode |
| Ledger budget_code = "bina" hiç eşleşmiyor | Category-slug fallback eşleştirme |
| Cashflow forecast 0 dönüyor | SubcontractorPayment + LedgerEntry birleşik history |
| Format compact negatif sayıda kırılma | sign + Math.abs ile düzeltildi |
| Tarih formatı mm/dd/yyyy | en-GB locale ile dd/mm/yyyy |
| EAC AC kaynağı yanlış (taşerondan) | OZET Toplam Gider'inden alınıyor |
| Vercel build syntax error (truncate) | Duplicate trailing block kaldırıldı |

---

## 6. Önemli Dosya Yapısı

```
backend/
├── app/
│   ├── api/v1/endpoints/    # FastAPI route'lar
│   │   ├── auth.py, projects.py, subcontractors.py
│   │   ├── budget_items.py, expenses.py, ledger.py
│   │   ├── tenders.py, workforce.py
│   │   ├── financial_summary.py (OZET endpoints)
│   │   └── dashboard.py (daily briefing, data quality)
│   ├── services/
│   │   ├── project_ai_analysis.py  (AI Project Director)
│   │   ├── tender_ai.py, subcontractor_profile.py
│   │   ├── ledger_excel.py (Gelir-Gider parser)
│   │   ├── financial_summary_parser.py (OZET parser)
│   │   ├── monart_budget_parser.py (ÇMI import)
│   │   ├── cashflow_forecast.py (3-aylık tahmin)
│   │   ├── tdf_export.py (KP Forma Excel export)
│   │   └── insights_cache.py (15dk cache)
│   ├── models/    # SQLAlchemy
│   ├── schemas/   # Pydantic
│   └── core/      # config, security
└── alembic/versions/  # ~15 migration

frontend/
├── src/
│   ├── app/(dashboard)/    # Next.js App Router
│   │   ├── projects/[id]/
│   │   │   ├── page.tsx (overview)
│   │   │   ├── subcontractors/  workforce/  budget/  expenses/
│   │   │   ├── tenders/  schedule/  risks/  reports/
│   │   │   └── ai-analysis/page.tsx (AI Project Director)
│   │   ├── settings/budget-categories/
│   │   └── page.tsx (dashboard)
│   ├── components/
│   │   ├── projects/eac-widget.tsx
│   │   ├── expenses/import-wizard.tsx, financial-summary-cards.tsx
│   │   ├── workforce/upload-dialog.tsx
│   │   ├── subcontractors/*  budget-items/variance-tab.tsx
│   │   └── layout/project-sidebar.tsx
│   ├── lib/
│   │   ├── api-client.ts (tüm API çağrıları)
│   │   ├── formatters.ts (formatRubCompact, formatDate, ...)
│   │   └── i18n/ (translations.ts — 1360 satır TR + EN)
│   └── types/
└── public/monotekstroy-logo.png
```

---

## 7. Demo Akış (Sunum İçin)

1. **Login** → admin / admin123 (VIEWER) ile gir, "edit butonları yok" — sonra logout
2. **Login** → admin1 / admin456 (WORKFORCE_EDITOR) ile gir, "sadece İşgücü görüyor" — logout
3. **Login** → admin gerçek hesabı
4. **Dashboard** → günün özetini göster
5. **Project Overview** → EAC widget'ı göster, modülleri tanıt
6. **Harcamalar** → 3 KPI (15.45B / 8.61B / 6.84B) + iki şirketin Finansal Özet kartı
   - "Excel Yükle" → Harcama Takip Excel'ini yükle → tüm rakamlar 5 saniyede güncellenir
7. **Bütçe** → ÇMI'den gelen 15 kategori, planned vs actual (Bina kategorisinde 250M / 5.86B)
8. **İhaleler** → Bir tender'ı aç, karşılaştırma tablosunu göster
9. **AI Analysis** → "Refresh" → Claude'un executive verdict'i

---

## 8. Şu An Beklenenler (Roadmap)

- **Schedule modülü** — Gantt chart + critical path proper tracking
- **Risks modülü** — manuel risk register + AI risk detection
- **TDF Excel export** — bidder count > 2 için template'i otomatik genişletme
- **Multi-project** — şu an tek proje (Central Moscow Hippodrome), çoklu proje desteği
- **Notification system** — kritik olaylar için email/Slack push
- **Mobile** — şu an responsive ama native mobile app yok

---

## 9. Erişim Bilgileri

- **Site:** https://monart-stroy-pm.vercel.app
- **Admin hesabı:** Kendi GitHub'ından kayıtlı (Tolga Topal)
- **Demo viewer:** admin@example.com / admin123
- **Demo workforce:** admin1@example.com / admin456
- **GitHub:** github.com/togymania/construction-dashboard
- **Render service:** monotek-stroy-pm-api (Frankfurt, Python 3, Free tier)
- **Vercel project:** monart-stroy-pm (Hobby, auto-deploy on main push)
- **DB:** Neon Postgres (Frankfurt)

---

*Son güncelleme: 14 Mayıs 2026*
