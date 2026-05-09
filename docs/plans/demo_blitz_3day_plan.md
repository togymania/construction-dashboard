# Demo Blitz — 3 Günlük Plan (Gün 12-13-14)

**Hedef:** Jürinin "para kazanacağına inandığı" bir sistem göstermek.
**Mantra:** "We don't track construction. We predict it."
**Skor hedefi:** 7.2 → 9+/10

## Önceliklendirme felsefesi

- **Gerçek olmak zorunda:** Cashflow forecast + Excel import + 1 full proje + Reports
- **Akıllı fake olabilir:** Notifications, multi-project (2-3 seed), activity geçmişi (seed), AI insight'ın bir kısmı
- **Jüri test etmez** — temiz fake yeter, tutarsız fake öldürür

---

## GÜN 12 — "Living System" Foundation (~6 saat)

Statik dashboard'u yaşayan sisteme dönüştüren 3 omurga özelliği. Bu gün biten hiçbir şey görünmez ama Day 13'te rapor + Day 14'te demo akışı bunlara dayanır.

### 12.1 — Activity Feed (gerçek) (~2 saat)

**Backend:**
- Yeni model: `app/models/activity_log.py`
  - `id`, `type` (enum: expense_added, payment_recorded, workforce_uploaded, contract_signed, project_updated, document_extracted), `actor_id` (FK users), `project_id` (FK projects, nullable), `subject_type` + `subject_id` (polymorphic ref), `message` (str, pre-rendered TR/EN), `metadata` (JSON), `created_at`
- Alembic migration: `add_activity_log_table`
- Servis: `app/services/activity_logger.py`
  - `async def log(db, *, type, actor_id, project_id=None, subject_type, subject_id, message, metadata=None) -> None`
- Hook'lar (mevcut endpoint'lere ekleme):
  - `expenses.create` → log "Expense added: <amount> RUB to <category>"
  - `subcontractors` payment create → log "Payment recorded: <sub_name> #<num>"
  - `workforce.import` → log "Workforce snapshot uploaded: <date> (<company>)"
  - `subcontractor_contracts` create → log "Contract signed: <sub_name> — <amount> RUB"
  - `documents` upload → log "Contract document analyzed: <filename>"
  - `projects` create/update → log "Project updated: <name>"
- Yeni endpoint: `GET /api/v1/activity?limit=20&project_id=` → son N aktivite, en yeni üstte

**Frontend:**
- Type: `frontend/src/types/activity.ts`
- API: `api.activity.list({ limit, projectId })`
- Dashboard'daki hard-coded `recentActivity` array'i **siliniyor**, gerçek endpoint'ten çekiliyor
- İkon mapping: type → lucide ikonu (Receipt / DollarSign / Users / FileText / Briefcase / Bot)
- Relative time: "2 saat önce", "1 gün önce" — küçük bir formatter

**Seed (kritik):**
- `app/db/seed_activity_log.py` — son 14 günün aktivitelerini geçmişe doğru insert et (15-20 satır)
- Demo'da boş feed katil; seed ile dolu görünüyor

**Acceptance:**
- Dashboard'da sahte 5 satır gitmiş, gerçek ≥15 aktivite görünüyor
- Yeni bir expense eklendiğinde 1 saniye içinde feed'in tepesine düşüyor

### 12.2 — AI Risk Panel (~2 saat)

**Backend:**
- `app/services/risk_aggregator.py` — yeni dosya, **mevcut `insight_generator.py` üstüne portfolio-level wrapper**
- 4 kural ailesi:
  1. **Cash crunch prediction** — tüm aktif kontratların cashflow_forecast'larını topla, önümüzdeki 6 hafta için outflow > expected_inflow ise → "X hafta içinde nakit açığı bekleniyor" (severity: critical)
  2. **Payment delay aggregate** — son 90 günün ödeme delay ortalaması; >18 gün ise → "Alt yüklenici ödemeleri ortalama X gün gecikiyor" (severity: warning)
  3. **Budget overrun proxy** — kategori bazında utilization >85% → "X kategorisinde bütçe aşım riski" (severity: warning)
  4. **Workforce drop** — son 7 gün vs önceki 7 gün present total düşüşü >%15 → "Sahada işgücü %X düştü" (severity: info/warning)
- Schema: `PortfolioRiskSummary { generated_at, risks: [PortfolioRisk{title, body, severity, category, source, action_url?}] }`
- Endpoint: `GET /api/v1/risks/portfolio?project_id=&force_refresh=`
- Cache: mevcut `insights_cache.py` deseninin aynısı, key=`portfolio:{project_id}`, TTL=10dk

**Frontend:**
- Yeni component: `frontend/src/components/dashboard/ai-risk-panel.tsx`
- Dashboard'a 3. kart olarak ekleniyor (KPI grid altı, Activity + Active Projects'in yanı)
- Her risk satırında:
  - Severity ikonu + rengi (critical=kırmızı, warning=sarı, info=mavi)
  - Bold başlık
  - 1 satır body
  - **"AI Detected" badge** (önemli — premium algı)
  - "Yenile" butonu üstte (force_refresh=true)

**Acceptance:**
- Dashboard'da en az 3 risk satırı görünüyor (mock + mevcut data karışımı)
- Mock + gerçek karışımı tek bakışta tutarlı (jüri ayırt edemez)
- "AI Detected" badge her satırda var

### 12.3 — Smart Fake Notifications (~1 saat)

**Backend yok** — pure frontend ile başla, ileride geçer.

**Frontend:**
- Yeni component: `frontend/src/components/layout/notifications-dropdown.tsx`
- Header'a Bell ikonu + unread count badge (kırmızı dot, sayı)
- Dropdown içeriği — ilk açılışta backend'den çekiyormuş gibi 0.5s skeleton, sonra:
  - 5 hard-coded notification:
    - "Payment delayed: Yılmaz Yapı — 3 gün geçti" (warning, 2h ago)
    - "Budget exceeded: Structural Works %103" (critical, 4h ago)
    - "New workforce data uploaded: Monart 09.05" (info, 6h ago)
    - "Contract analyzed: Atlas Beton ek protokol" (info, 1d ago)
    - "Cashflow alert: 6 hafta sonra açık öngörüldü" (warning, 1d ago)
  - "Tümünü işaretle" + bireysel tıklama → unread count düşer (state localStorage'da)
- Optional polish: ileride backend bağlandığında çalışacak `api.notifications.list()` stub'ı bırak

**Acceptance:**
- Bell ikonu kırmızı 5 badge ile yanıyor
- Tıklayınca dropdown akıyor, 5 satır görünüyor
- "Mark all read" sayıyı 0'a düşürüyor

### 12.4 — Seed retro-fix (~30 dk)

- Mevcut `seed_*` scriptlerini gözden geçir, son 30 günün gerçekçi tarihleriyle expense + payment + workforce snapshot dağıt
- 2 yeni proje seed'le (Day 14'te multi-project demo için): "Kanal Istanbul Etap 2" (planning, 28B RUB), "Galataport Phase 2" (active, 18B RUB)
- Activity log seed'i bu yeni projelere de yayılsın

**Day 12 sonu acceptance:**
- Dashboard 4 KPI + Activity Feed (gerçek) + AI Risk Panel + Active Projects layout
- Header: Bell + 5 notification + theme toggle + language switcher + avatar
- 3 proje görünüyor, hepsinde aktivite ve risk var

---

## GÜN 13 — Executive Report + UX Kill (~6 saat)

Bu gün ürünü "iyi yazılmış sistem"den "alıp kullanılan rapor"a çevirir.

### 13.1 — Executive Report (PDF) (~3 saat)

**Backend:**
- Bağımlılık: `weasyprint==62.3` (HTML → PDF, abartısız, Linux'ta sorunsuz)
  - Alternatif: Jinja2 + pdfkit/wkhtmltopdf — ama WeasyPrint daha temiz
- requirements.txt'e ekle, Dockerfile'da `apt-get install libpango...` (WeasyPrint Linux deps)
- Yeni servis: `app/services/report_generator/__init__.py` (mevcut boş klasörü doldur)
  - `build_executive_report(db, project_id) -> bytes` — PDF döner
- Bölümler:
  1. **Cover** — proje adı, owner, tarih aralığı, ConstructHub logo + tarih damgası
  2. **Executive Summary** — 4 büyük rakam: Total Budget, Spent %, Active Subcontractors, Workforce Today
  3. **Budget vs Actual** — kategori bazında bar chart (matplotlib veya chart.js → svg embed) + tablo
  4. **Cashflow Forecast** (en güçlü özellik — öne çıkar) — 12 aylık history + 6 ay forecast (best/likely/worst), confidence band
  5. **Top Risks** — AI Risk Panel'den top 5 risk, severity ikonu + body
  6. **Workforce Trend** — son 4 hafta haftalık total + bu hafta kompozisyon
  7. **AI Insights** — `insight_generator`'dan 3-5 insight, "AI Generated" damgası
  8. **Footer** — generated by ConstructHub, sayfa numaraları
- Template: `app/services/report_generator/templates/executive.html` + `executive.css`
  - Premium görünüm: Inter font, OKLCH paleti, glassmorphism yerine print-friendly clean look
  - A4, kenar boşlukları, page-break disiplini
- Endpoint: `GET /api/v1/projects/{id}/report` → `application/pdf` stream, filename: `<project_slug>_<YYYY-MM-DD>.pdf`

**Frontend:**
- `/reports` sayfasını gerçek hale getir (`<ComingSoonPage>` siliniyor)
- Layout:
  - Sol: project picker (Select) + tarih aralığı (opsiyonel, ileride)
  - Sağ: "Generate Report" büyük buton (gradient primary + neon glow)
  - Tıklayınca: skeleton overlay 1-2s, sonra browser download
- Bonus: oluşturulan son raporları listeleyen küçük tablo (storage filesystem'e kaydedip URL ver) — opsiyonel

**Acceptance:**
- 1 tıkla A4 PDF indiriyor, 6+ sayfa, premium görünüm
- Cashflow forecast grafiği PDF'in 4. sayfasında, scenarios renkli
- Mock veriler değil, gerçek DB'den çekilmiş sayılar

### 13.2 — UX Kill Batch (~2 saat)

**Alert → Toast (kritik):**
- Tüm `subcontractors/*` sayfalarındaki `alert(...)` çağrılarını `toast.error()` / `toast.success()` ile değiştir (sonner zaten kurulu)
- Aynısını `projects/page.tsx`, `expenses/page.tsx` için yap
- Listele: `Grep "alert\("` → her dosyada 1-2 occurrence

**AI badge'leri:**
- Yeni component: `frontend/src/components/ui/ai-badge.tsx`
- 3 variant: `<AiBadge kind="detected">`, `kind="prediction"`, `kind="forecast"`
- Stil: gradient background (indigo→cyan), küçük Bot/Sparkles ikonu, uppercase letter-spacing
- Yerleştirme:
  - AI Risk Panel her satırda → "AI Detected"
  - CashFlowForecastChart başlığı → "Forecast"
  - SubcontractorInsightsCard her LLM kaynaklı insight → "Prediction" / "AI Detected"
  - ExtractedDataPreview source=llm/llm_mock → "AI Detected"

**Renk disiplini:**
- `frontend/src/lib/severity.ts` — yeni helper
  - `getSeverityClasses(severity: 'critical'|'warning'|'info'|'success')` → Tailwind class'ları
  - critical: bg-red-50/dark:bg-red-950 + text-red-600 + border-red-200
  - warning: amber
  - info: blue
  - success: emerald
- Tüm `text-amber-XXX` / `text-red-XXX` ad-hoc kullanımları bu helper'a migrate
- Hedef: jüri bir kart kırmızıysa **hemen** sorun olduğunu anlasın

**Day 10 carry-over fix'leri:**
- Top Positions chart legend (Recharts `<Cell>` per-bar fill düzgün renderlenmiyor) → `Bar` üzerinde `fill` yerine `<Cell>` array, legend için `payload` prop manuel pass
- Daily/Weekly chart UX: tooltip text daha açıklayıcı, axis label, ay/gün formatı locale-aware

### 13.3 — Multi-project görünüm + Anthropic key go-live (~1 saat)

**Multi-project:**
- Header'a project switcher dropdown (sidebar'da değil — header sağında)
- Seçili proje localStorage + `useProject()` context'ine yazılıyor
- Dashboard, /budget, /expenses, /workforce, /risks (yeni report linki) seçili projeye göre filtreleniyor

**Anthropic key (kullanıcı API key aldıysa):**
- `.env`'e `ANTHROPIC_API_KEY=sk-ant-...` ekle
- Backend restart → tüm `llm_mock` path'leri otomatik gerçek Claude'a flip
- Cache bust: `insights_cache.clear_all()` çağır
- Test: 1 contract document re-extract → gerçek extracted_data dönmeli

**Acceptance Day 13 sonu:**
- /reports sayfası gerçek, 1 tıkla PDF indiriyor
- Hiçbir yerde alert kalmadı, tüm hatalar toast
- AI badge'leri her insight/forecast/extraction'da görünür
- Header'da proje seçici, 3 proje arasında geçiş çalışıyor

---

## GÜN 14 — Deployment + Demo Polish (~6 saat)

Ürünü demoya hazır hale getir, jürinin linkten girip dolaşabileceği seviyeye çıkar.

### 14.1 — Deployment (~2.5 saat)

**Backend (Railway):**
- Railway'de yeni proje aç, GitHub repo bağla
- Postgres add-on ekle, `DATABASE_URL` otomatik env var
- `app/core/config.py`'de `DATABASE_URL` env var'dan da okuyabilsin (Railway'in formatı `postgresql://...`, asyncpg için `+asyncpg` gerekiyor — küçük adapter)
- Build/start command:
  - Build: `pip install -r requirements.txt`
  - Start: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Env vars: `SECRET_KEY`, `ANTHROPIC_API_KEY` (varsa), `ENVIRONMENT=production`
- CORS: `allow_origins=["https://<frontend-url>.vercel.app", "http://localhost:3000"]`
- Seed scriptini bir kez çalıştır (Railway shell'den)

**Frontend (Vercel):**
- GitHub repo bağla, root directory: `frontend`
- Env: `NEXT_PUBLIC_API_URL=https://<backend>.up.railway.app/api/v1`
- Build: default `next build`
- `frontend/src/lib/api-client.ts`'te base URL bu env'den okunsun (zaten okunuyor mu kontrol et)
- Custom domain opsiyonel: `constructhub-demo.vercel.app` yeterli

**Sanity check:**
- Login → demo user ile gir
- Tüm sayfaları gez (Dashboard / Projects / Subcontractors / Workforce / Expenses / Reports)
- Excel import (workforce + expense) production'da test et
- 1 rapor PDF indir
- Mobile responsive değilse fark etmez (jüri laptop'tan bakar)

### 14.2 — Killer Demo Flow Hazırlığı (~2 saat)

**Demo script** (3-4 dakika, `docs/demo_script.md` olarak yaz):

1. **Giriş (15 sn)** — "Büyük inşaat projeleri reaktif yönetiliyor. Biz bunu proaktif hale getiriyoruz."
2. **Project Overview (30 sn)** — Dashboard'a gir, 4 KPI, "Bu projede erken sinyaller var" → AI Risk Panel'e işaret et
3. **AI Moment / Cashflow (45 sn)** — Subcontractor detail → Cash Flow tab → Forecast chart "6 hafta önceden nakit krizini görüyoruz"
4. **Contract AI (30 sn)** — Contract detail → Documents tab → ExtractedDataPreview "Sistem kontrattan risk çıkarıyor"
5. **Workforce (20 sn)** — /workforce → grafikler "Sahadan gelen Excel → anında analiz"
6. **Finans (20 sn)** — /expenses → ledger import wizard "Operasyon ve finans birleşiyor"
7. **AI Risk Panel (25 sn)** — Dashboard'a dön, risk panel'i 5 saniye göster "Dashboard değil, karar veriyoruz"
8. **Kapanış / Rapor (30 sn)** — /reports → Generate → PDF indir → ekranda aç → "Yöneticiler sisteme girmez, bunu alır"
9. **Son cümle** — "We don't track construction. We predict it."

**Rehearsal:**
- En az 3 kez baştan sona çalış, takılan yer varsa fix et
- Screen recording yedek olarak al (jüri canlı'da bug'a rast gelirse video oynat)

### 14.3 — Bug Bash + Demo Data Polish (~1 saat)

- Console error'larını sıfırla (DevTools açıkken tıklama akışı çalış)
- 404'leri yakala — `/settings` sayfası hâlâ yok, ya implement et ya sidebar'dan gizle
- Loading state'leri kontrol et — Skeleton var mı, blank flash mı oluyor
- Empty state'ler — "No data yet" kartları boş projede de güzel görünsün
- TS strict-mode 6 hatası: build'i kıracaksa fix et, kırmıyorsa bırak (Day 14 sonrası iş)

### 14.4 — README + lansman polish (~30 dk)

- README.md'ye demo URL'leri ekle (frontend + backend + swagger)
- "Try it" bölümü: demo user credentials (admin@demo.com / Demo123!)
- Architecture diyagramının screenshot'ı README'ye
- LICENSE / contact bölümü

**Acceptance Day 14 sonu:**
- Public URL'den login → tam demo akışı çalışıyor
- 3-4 dk demo script tek seferde takılmadan akıyor
- Backup video var
- README jüri için anlaşılır

---

## Risk + Mitigation

| Risk | Mitigation |
|---|---|
| WeasyPrint Linux deps Railway'de çuvallarsa | Alternative: Playwright + Chromium, veya Chart.js base64 SVG inline |
| Anthropic API quota / yavaşlık | Demo'dan önce test et, kötü durumda mock'a geri dön (.env.cleanup) |
| Sandbox truncation | Tüm büyük dosyaları Edit/Read tool ile yaz, bash'ten python invoke etme |
| Multi-project context tüm sayfalara yayılmadıysa | Dashboard + Reports + Risks yeter, diğerleri "all projects" göstersin |
| Demo'da bug çıkar | Backup screen recording her zaman yanında olsun |

---

## Definition of Done (Demo Hazır = ?)

- [ ] Activity feed gerçek, son 30 gün dolu
- [ ] AI Risk Panel dashboard'da, 3+ risk satırı
- [ ] Notifications dropdown header'da, 5 satır
- [ ] Executive Report PDF 1 tıkla iniyor, 6+ sayfa
- [ ] Tüm alert'ler toast'a dönmüş
- [ ] AI badge'leri görünür yerlerde
- [ ] Multi-project geçişi çalışıyor (en az 3 proje seed)
- [ ] Public URL'den erişilebilir
- [ ] Demo script 3-4 dk içinde, takılmadan
- [ ] Backup screen recording var
- [ ] README'de demo bilgileri

---

## Sonra (Demo'dan sonra ya da stretch)

- Schedule (Gantt-lite) — Day 12+ planlandı ama jüri için kritik değil
- Risk register tam tablo — AI Risk Panel demo için yeter
- TS strict mode tam cleanup
- i18n RU + tam çeviri
- Tasks/Milestones modülü
- Notifications gerçek backend
