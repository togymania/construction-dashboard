# ConstructHub — Master Plan v2 (Demo Hazırlık)

> **Update 2026-05-09:** All 5 phases shipped end-to-end. LLM paths gated
> on `ANTHROPIC_API_KEY`; rule-based fallback covers every endpoint so
> demos run today. See `docs/sprint-log.md` for what landed in each phase.



Bu plan, demo öncesi yapılacak tüm değişiklikleri 5 faza böler. Faz 1 bugün başlar; Faz 2-5 sırayla takip eder.

**Mantra:** "We don't track construction. We predict it."
**Hedef skor:** 7.2 → 9+/10
**API key:** Bugün verilecek → tüm `llm_mock` path'leri gerçek Claude'a flip.

---

## FAZ 1 — Bugün (~6-8 saat tahmini)

Üç ana değişiklik. Sidebar restructure'dan başlanır çünkü diğerlerinin routing'ini etkiler.

### 1.1 — Sidebar Restructure: Project-Scoped Navigation

**Sorun:** Subcontractors / Workforce / Expenses / Schedule / Risks / Reports şu an top-level menü. Aslında **her projenin alt başlıkları** olmalı.

**Çözüm:**
- Top-level sidebar'da sadece: **Dashboard**, **Projects** (+ Admin: Budget Categories, Settings).
- Kullanıcı bir projeye girdiğinde (`/projects/{id}`), proje-bağımlı sub-navigation görünecek: **Overview / Subcontractors / Workforce / Expenses / Schedule / Risks / Reports**.

**Routing değişiklikleri:**
- `/subcontractors` → `/projects/{id}/subcontractors`
- `/workforce` → `/projects/{id}/workforce`
- `/expenses` → `/projects/{id}/expenses`
- `/schedule` → `/projects/{id}/schedule`
- `/risks` → `/projects/{id}/risks`
- `/reports` → `/projects/{id}/reports`
- `/projects/{id}` (mevcut) → `/projects/{id}/overview` (rename + redirect)

**Frontend implementasyon:**
- `frontend/src/app/(dashboard)/projects/[id]/layout.tsx` — yeni layout, project context yükleyen + sub-sidebar render eden
- Sub-sidebar component: `frontend/src/components/layout/project-sidebar.tsx`
- Mevcut sidebar (`sidebar.tsx`) sadeleşiyor: Dashboard + Projects + Admin grubu
- Mevcut sayfalar `app/(dashboard)/subcontractors/page.tsx` → `app/(dashboard)/projects/[id]/subcontractors/page.tsx` taşınıyor
- Subcontractor detail sayfası: `/projects/{id}/subcontractors/{subId}` formatına geçiyor
- Project switcher header'da değil — sidebar üstünde proje adı + back-to-projects link
- Project context: `ProjectProvider` (param'dan id okuyup project objesini fetch eden), tüm child sayfalar bu context'i kullanır

**Backend etkisi:**
- Mevcut endpoint'ler zaten `?project_id=` filter alıyor, route değişikliği gerekmez
- Ancak global subcontractor listesi (`/subcontractors`) proje-spesifik kontrat listesi olarak kullanılacak — backend dokunmaya gerek yok, frontend filter ekler

**Acceptance:**
- Sidebar'da sadece Dashboard / Projects + Admin
- /projects/{id}'ye gidince sol panel proje adı + sub-nav görünüyor
- Tüm eski linkler yeni route'lara redirect ediyor

---

### 1.2 — Expenses: Sıralama + Bulk Atama

**Sorun:** Expenses tablosunda sıralama yok, "unassigned" budget code/subcontractor manuel atanamıyor, çoklu seçim yok.

**1.2.1 — Sıralama (sorting):**
- Tablo başlıklarına tıklanabilir sort eklenecek
- En azından: **Date** (asc/desc), **Amount** (büyük/küçük)
- Görsel ok ikonu (ChevronUp/ChevronDown)
- Bonus: Company (alfabetik), KOD, Account
- Frontend-side sort yeterli (sayfa zaten paginated görünmüyor — gerekirse server-side ekleriz)

**1.2.2 — Budget code atama:**
- Inline edit: "unassigned" badge'ine tıklayınca dropdown
- Combobox: BudgetCategory tablosundan kod listesi (search'lü)
- Tek satır anında PATCH ediliyor

**1.2.3 — Subcontractor atama (aynı pattern):**
- "—" hücresine tıklayınca subcontractor combobox
- Search + inline create-new optional
- Bonus: **AI Suggest** butonu — `subcontractor_matcher.py` company_name'e göre öneri yapar

**1.2.4 — Bulk assign (kritik):**
- Her satırın başına checkbox
- Header checkbox: "select all visible" / "select all filtered"
- Quick selectors: "select same company", "select same KOD"
- Sticky bulk action bar üstte:
  - "X seçili"
  - [Budget code dropdown] → Apply
  - [Subcontractor combobox] → Apply
  - [Clear selection]
- API: `PATCH /api/v1/ledger/bulk-assign` { entry_ids: [], budget_code?: str, subcontractor_id?: int }

**Acceptance:**
- Tablo sortable, görsel ok ikonu çalışıyor
- Tek tık inline atama yapılabiliyor
- Aynı firmanın 50+ satırı tek seferde atanabiliyor

---

### 1.3 — Subcontractor: Area Chart + Claude API + Firma Kartviziti

**1.3.1 — Cash Flow grafiği: Bar → Area chart**
- Mevcut Cash Flow tab'ındaki bar grafik `<AreaChart>`'a çevrilecek
- Gradient fill (indigo/cyan paletinden), smooth curve, opacity ~0.3-0.5
- Tooltip + legend korunacak
- `CashFlowForecastChart` zaten Composed (forecast) — ona stilistik tutarlı

**1.3.2 — Claude API go-live**
- API key bugün verilecek
- `.env`'e `ANTHROPIC_API_KEY=sk-ant-...` ekle
- `ANTHROPIC_MODEL` güncel model string'e çek (gerekirse)
- `insights_cache.clear_all()` mock cache temizle
- `parse_contract_with_llm()` zaten dual-mode — key varsa gerçek Anthropic
- Mock banner (`<ExtractedDataPreview>`'deki sarı uyarı) kaldırılıyor
- Tüm mevcut llm_mock dataları için re-extract çağrısı (opsiyonel, eski mock'ları gerçeğiyle değiştirmek için)

**1.3.3 — Firma "Kartviziti" (yeni özellik) — Subcontractor Profile Report**
- Her subcontractor için tüm dökümanların kombine analizi
- Subcontractor detail sayfasında **yeni tab: "Profil"** (en sol, Contracts tab'ından önce)
- İçerik:
  - **Şirket Özeti**: toplam kontrat değeri, aktif/tamamlanmış kontrat sayısı, ortalama rating
  - **Mali Profil**: ödenen vs bekleyen, ortalama ödeme gecikmesi, cashflow trend
  - **Risk Profili**: tüm risk_flags aggregate + Claude firma-seviyesi yorumu
  - **Kritik Tarihler Timeline**: tüm dökümanların key_dates'leri merge'lenmiş, takvime sıralı
  - **Ödeme Şartları**: tüm payment_terms_summary'ler distill edilmiş
  - **Penalty Patterns**: tüm penalty_clauses'tan ortak desenler (gecikme cezası ortalaması, kalite cezası varlığı vs.)
  - **AI Önerileri**: "Bu firma ile çalışırken dikkat edilmesi gerekenler" — executive bullets

**Backend:**
- Yeni servis: `app/services/subcontractor_profile.py`
  - `async build_profile_report(db, subcontractor_id) -> SubcontractorProfileReport`
  - Tüm ContractDocument.extracted_data + payment history + contracts birleşir
  - Tek Claude prompt → structured JSON dönüş
- Yeni schema: `SubcontractorProfileReport` (subcontractor.py'a eklenir)
- Yeni endpoint: `GET /api/v1/subcontractors/{id}/profile-report?force_refresh=`
- Cache: `insights_cache.py` desenıyle, TTL=1h (LLM çağrısı pahalı), key=`profile:{sub_id}`
- Cache invalidation: yeni doküman upload olunca invalidate

**Frontend:**
- Yeni type: `frontend/src/types/subcontractor.ts`'e `SubcontractorProfileReport` eklenir
- Yeni component: `frontend/src/components/subcontractors/profile-card.tsx`
- Subcontractor detail sayfasında yeni tab "Profil" (Contracts'tan önce)
- Premium görünüm: gradient header, "AI Generated" badge, kategorize bölümler, "Yenile" + "PDF olarak indir" butonları
- PDF indir butonu opsiyonel (Faz 5 reports pattern'iyle yapılabilir)

**Acceptance:**
- Cash Flow grafiği area olmuş, gradient güzel
- Bir kontrat döküman yüklendiğinde gerçek Claude yanıtı geliyor (mock değil)
- Subcontractor detay sayfasında "Profil" tab'ı var, açınca AI üretimli zengin özet
- Force refresh çalışıyor, cache 1 saat sonra otomatik refresh

---

## FAZ 2 — Budget Excel İşleme (Faz 1 sonrası)

Kullanıcı bütçeyi Excel formatında sağlayacak. Önce **Excel formatı anlaşılacak**, sonra parser yazılacak.

**Plan adımları:**
1. Kullanıcı örnek Excel(ler)i yükleyecek → format inceleme
2. Excel yapısı dokümante edilecek (`docs/budget_excel_format.md`)
3. Parser servisi: `app/services/budget_excel.py` (mevcut `workforce_excel.py` ve `ledger_excel.py` desenlerinde)
4. Endpoint: `POST /api/v1/projects/{id}/budget/import-excel`
5. Frontend: `BudgetImportDialog` (mevcut `expense-import-dialog` deseninde)
6. Idempotent import (dedup_hash benzeri mekanizma)

**Detay:** Format görüldükten sonra detaylanacak.

---

## FAZ 3 — Planned vs Actual Matching

Faz 2 bittikten sonra: yüklenmiş bütçenin **planned** kısmı ile expenses'teki **actual** harcamalar eşleştirilecek.

**Plan:**
1. Her budget item için "actual_spent" hesabı (matched expenses sum)
2. Matching mantığı:
   - Otomatik: budget_code + kategori + tarih aralığı
   - Manuel: kullanıcı bir expense'i bir budget item'a bağlayabilsin (FK)
   - Bulk match: Faz 1.2.4'teki bulk action bar'a "Bu satırları şu budget item'a bağla" eklenir
3. Frontend görünüm:
   - Budget items tablosunda "Planned / Actual / Variance" kolonları
   - Variance > %10 ise sarı, > %25 ise kırmızı
   - Her budget item satırı tıklanabilir → bağlı expense'leri açılır
4. Backend:
   - `Expense` veya `LedgerEntry` modeline `budget_item_id` FK eklenir (nullable)
   - Migration
   - Aggregate endpoint: `GET /api/v1/projects/{id}/budget/variance-report`

---

## FAZ 4 — Dashboard Daily AI Report (Claude API)

Faz 3 bittikten sonra: dashboard'un üst kısmında **günlük AI raporu** kart.

**Plan:**
1. Yeni servis: `app/services/daily_briefing.py`
   - Tüm projelerden son 24 saatlik veri toplar (yeni expenses, payments, workforce snapshots, document uploads, risk değişimleri)
   - Claude'a context yollar → executive briefing döner
   - Format: "Günaydın. Dün şunlar oldu / şunlara dikkat / bugün şu kararlar gerekiyor"
2. Endpoint: `GET /api/v1/dashboard/daily-briefing`
3. Cache: günlük (24h TTL), her gece otomatik regenerate (ileride scheduled task ile)
4. Frontend: dashboard'un en üstünde büyük kart (gradient bg, AI Generated badge, refresh butonu, "tüm raporu gör" linki Faz 5'e)

---

## FAZ 5 — Reports: Şantiye Özet Raporu (Claude API)

Reports sayfası — proje başına 1-2 sayfalık **yöneticinin görmesi gereken her şey** raporu.

**Bu rapor sadece veri değil, yorum içeriyor.** Yönetici sisteme girmeden bu raporu okuyup kararlarını verebilmeli.

**Plan:**
1. Yeni servis: `app/services/project_executive_report.py`
   - Proje contextini topla: budget vs actual, cashflow forecast, top subcontractor risks, workforce trend, recent activity, açık riskler, yaklaşan kritik tarihler
   - Tek Claude prompt → 6-8 paragraflık yorum + 5-10 kritik bullet
2. Endpoint: `GET /api/v1/projects/{id}/executive-report`
3. PDF render (Faz 1'deki report pattern'inde — WeasyPrint veya Playwright)
4. Frontend: `/projects/{id}/reports` sayfası
   - "Generate Executive Report" tek tık
   - Arkada AI çağırıyor, ekranda preview, sonra PDF indir
5. İçerik bölümleri:
   - **Executive Summary** (Claude yorum)
   - **Mali Durum** (rakam + AI yorum)
   - **Kritik Riskler** (AI öncelikli sıralı)
   - **Alt Yüklenici Performansı** (kart sıralaması + AI yorum)
   - **İşgücü Sağlığı** (trend + AI yorum)
   - **Önümüzdeki 30 Gün** (Claude'un öngörüsü)
   - **Tavsiye Edilen Aksiyonlar** (AI bullet)

---

## Faz öncelik sırası ve bağımlılıklar

```
FAZ 1 (sidebar + expenses + subcontractor)  ← BUGÜN
   ↓
FAZ 2 (budget excel parser)                 ← Excel görünce
   ↓
FAZ 3 (planned vs actual)                   ← FAZ 2 zorunlu prereq
   ↓
FAZ 4 (dashboard daily briefing)            ← FAZ 1 zorunlu (sidebar yeni route)
   ↓
FAZ 5 (project executive report)            ← FAZ 3 ideal, FAZ 4 ile pattern paylaşır
```

---

## Kritik teknik notlar (her fazda dikkat)

- **Sandbox mount truncation:** Büyük dosyaları Edit/Write tool ile yaz, bash'ten python invoke etme
- **API key güvenliği:** `.env` dosyası `.gitignore`'da, key commit edilmeyecek
- **Backwards-compat:** Yeni schema alanları optional, eski endpoint'ler korunacak
- **Migration disiplini:** Her DB değişikliği Alembic migration ile, downgrade test edilir
- **Cache temizliği:** Yeni veri girişlerinde ilgili cache key'leri invalidate
- **i18n:** Yeni UI string'leri `translations.ts`'e TR + EN olarak eklenecek
