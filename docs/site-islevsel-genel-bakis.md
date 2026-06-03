# ConstructHub — Site İşlevsel Genel Bakış Raporu

**Site:** monart-stroy-pm.vercel.app (marka: MOHAPT / Monartstroy)
**Tarih:** 3 Haziran 2026
**Kaynak:** Canlı site turu (Admin oturumu) + kod tabanı incelemesi
**Not:** Aşağıdaki somut sayılar, gezdiğim andaki **anlık görüntüdür**; canlı veri değişebilir.

---

## 1. Bu Site Ne Yapıyor?

ConstructHub, **milyar dolar ölçekli inşaat projelerini** yöneten kurumsal bir web panosudur (SaaS). Tek bir yöneticinin; bütçeyi, gerçek harcamaları, taşeronları, sözleşmeleri, sahadaki işgücünü, ihaleleri ve proje sağlığını **tek ekrandan** görüp karar almasını sağlar. Excel ve PDF'ten gelen dağınık finansal/operasyonel veriyi içeri alır, yapılandırır ve üstüne **yapay zekâ destekli yönetici özetleri** üretir.

Şu an canlıda **tek aktif gerçek proje** var: **“Central Moscow Hippodrome”** (Moskova hipodromu restorasyonu) — 16 milyar RUB bütçe, %74 tamamlanmış.

**Kimin için:** Proje müdürü / yönetici, finans ekibi, saha/işgücü sorumlusu, üst yönetim.

---

## 2. Hangi Parametrelerle Çalışıyor? (Çalışma Mantığı)

Site şu temel parametreler/eksenler üzerinde çalışır:

- **Kimlik & oturum:** JWT tabanlı giriş (e-posta + parola). Her istek bir access token taşır; korumalı sayfalar token olmadan açılmaz.
- **Rol bazlı erişim (RBAC) — 5 rol:** `ADMIN`, `PROJECT_MANAGER`, `ENGINEER`, `VIEWER`, `WORKFORCE_EDITOR`. Rol, kullanıcının hangi sayfaları görebileceğini ve hangi işlemleri (import, düzenleme, onay) yapabileceğini belirler. Örn. `VIEWER` salt-okunur; `WORKFORCE_EDITOR` yalnız İşgücü modülüne yönlenir.
- **Dil parametresi:** Her istek bir `X-User-Lang` (EN/TR) başlığı taşır; **AI çıktıları bu dile göre** üretilir (kaynak veri Rusça olsa bile arayüz diline çevrilir).
- **Proje bağlamı (project-scoped):** Neredeyse tüm veri bir `project_id` altında gruplanır. URL deseni `/projects/{id}/<modül>` şeklindedir; modüller seçili projeye göre veri gösterir.
- **Para birimi:** RUB (₽). Tutarlar büyük ölçekli (milyar) gösterilir.
- **AI anahtarı (opsiyonel):** `ANTHROPIC_API_KEY` varsa AI metinleri gerçek Claude ile üretilir; yoksa **kural tabanlı** aynı-şekilli çıktıya düşer (site AI'sız da çalışır).
- **Çok-şirketli yapı:** Veriler iki şirket etiketiyle ayrışır — **MONOTEKSTROY** ve **MONARTSTROY** (hem finansal özet hem işgücünde).

**Altyapı:** Frontend Vercel'de (Next.js 16), backend Render'da (FastAPI, Frankfurt), veritabanı Neon PostgreSQL (Frankfurt).

---

## 3. Veriler Siteye Nasıl Giriyor? (Veri Kaynakları)

Site çoğunlukla **Excel/PDF içe aktarımıyla** beslenir:

| Kaynak | Format | Beslediği modül |
|---|---|---|
| Bütçe cetveli (ÇMI / Monart) | Excel (.xlsx) | Bütçe kalemleri + kategoriler |
| Finansal defter (Ledger) | Excel (.xlsx) | Harcamalar / gelir-gider hareketleri |
| Finansal özet (OZET) | Excel (.xlsx) | Harcamalar üst KPI'ları (şirket bazlı) |
| Puantaj (işçi yoklama) | Excel (.xlsx) | İşgücü günlük sayıları |
| Taşeron sözleşmesi | PDF | Sözleşme detayları (LLM ile alan çıkarımı) |
| Teklif (KP formu) | Excel/Manuel | İhale teklif karşılaştırması |

İçe aktarım genelde **önizleme → doğrulama → onay (commit)** akışıyla çalışır; taşeron eşleştirmesi için isim-benzerliği önerileri sunulur.

---

## 4. Modül Modül: Ne Yapıyor, Hangi Veriyi Gösteriyor?

### Panel (Dashboard)
- **Ne:** Portföyün genel sağlığı + günlük AI brifingi.
- **Veri:** Aktif proje sayısı, toplam bütçe, “on-track” sayısı, açık risk sayısı; **Günlük Brifing** (son 24 saatte ne oldu); **Data Quality** kartı (kaç harcama bütçe-kodsuz, kaç ödeme taşeronsuz).
- **Parametre:** Aktif projeler, dil, son-24-saat penceresi.

### Projeler / Proje Detayı
- **Ne:** Proje listesi + tek proje genel bakışı.
- **Veri:** Ad, durum (Aktif), sağlık (On-track), konum, bütçe, ilerleme %, sahip; detayda **EAC Forecast** (BAC plan / AC harcanan / EAC tahmin, CPI), başlangıç-bitiş tarihleri, modül kısayolları.
- **Parametre:** `project_id`, status/health/search filtreleri.

### Bütçe
- **Ne:** Planlanan bütçe kırılımı ve planlanan-vs-gerçekleşen.
- **Veri:** Proje bütçesi (tavan), toplam planlanan, toplam harcanan, kullanım %; **8 kategori** (Bina, Yollar, Altyapı, Haberleşme, Isıtma, Elektrik, Peyzaj, Aydınlatma) ve **15 kalem** (detaylı Rusça pozisyonlar, alt-kalem dökümü); pasta + çubuk grafik; varyans (Planlanan vs Gerçekleşen) sekmesi.
- **Parametre:** `project_id`, bütçe kalemleri, OZET harcama.

### Harcamalar
- **Ne:** Excel’den içe aktarılan gelir-gider defteri + finansal özet.
- **Veri:** Toplam gelir / toplam gider / net; **Finansal Özet (OZET)** iki şirket için ayrı (MONOTEKSTROY & MONARTSTROY): işveren tahsilatları, firma ödemeleri, ücret giderleri, vergi (gelir/KDV), faiz, banka giderleri, toplam; kayıt sayısı + “bütçe kodsuz / taşeronsuz” sayaçları.
- **Parametre:** `project_id`, ledger satırları, OZET, tarih.

### Taşeronlar
- **Ne:** Firma, sözleşme ve ödeme yönetimi + nakit akışı tahmini.
- **Veri:** Toplam taşeron, aktif sözleşme, geciken sözleşme, toplam sözleşme değeri, ödeme ilerlemesi %; taşeron listesi (ad, vergi no, uzmanlık, aktif sözleşme, değer, rating); **ödeme durumu** (pasta), **değere göre ilk 5**, **aylık ödemeler (6 ay)**, **3 aylık nakit akışı tahmini** (güven yüzdesiyle, az-veri uyarısı dahil). Detayda sözleşme/ödeme/belge sekmeleri, AI firma kartı.
- **Parametre:** `project_id`, taşeron/sözleşme/ödeme kayıtları, EMA+mevsimsellik tahmin modeli.

### İşgücü (Puantaj)
- **Ne:** Sahadaki günlük personel analitiği.
- **Veri:** Toplam işgücü, direkt/taşeron kırılımı, haftalık değişim; **firma bazlı** (Monotek vs Monart) direkt/endirekt/taşeron; günlük trend (son 12 gün), haftalık ortalama; **disiplin dağılımı** (Civil/Electrical/Mechanical), **kümülatif adam-saat**, AI insights, son puantaj tablosu. Veri tarihi gösterilir.
- **Parametre:** `project_id`, puantaj snapshot’ları, pozisyonlar, şirket etiketi.

### İhaleler
- **Ne:** Her iş paketi için teklif karşılaştırması.
- **Veri:** İhale listesi (başlık, durum, kalem sayısı, teklif sayısı, en düşük teklif); detayda **yan yana teklif karşılaştırması**, kalem bazlı renk-kodlu birim fiyatlar, **teklif revizyon geçmişi (v1→v2→v3)**, teklif veren yorumları, “en düşük/en yüksek” işaretleri.
- **Parametre:** `project_id`, ihale, teklifler, revizyonlar.

### Takvim / Riskler / Raporlar
- **Takvim & Riskler:** Şu an “Coming soon” (placeholder) / yönlendirme.
- **Raporlar:** **Yönetici Raporu** — 6 bölümlü AI narratifi (Yönetici Özeti, Mali Durum, Kritik Riskler, Alt Yüklenici Performansı, İşgücü Sağlığı, Önümüzdeki 30 Gün) + Tavsiye Edilen Aksiyonlar + PDF/Yazdır.

### AI Analizi (Proje Direktörü)
- **Ne:** Kararlı, yönetici düzeyinde proje hükmü.
- **Veri:** Tek cümlelik **KARAR** (ON_TRACK / AT_RISK / KRİTİK), temel etkenler, kritik engel, öngörülen gecikme, veri güvenilirliği skoru, gerekli aksiyonlar, ve **8 KPI** (Takvim Sağlığı, Öngörülen Gecikme, Kritik Yol, İlerleme, Kaynak Verimliliği, Maliyet Tutarlılığı, Veri Güvenilirliği, Yüklenici Riski).

### Settings → Bütçe Kategorileri (Admin)
- Bütçe kategorilerinin yönetimi (admin).

---

## 5. Yapay Zekâ Yetenekleri

Site, Anthropic Claude üzerine kurulu (anahtar yoksa kural tabanlı fallback) birden çok AI özelliği sunar:

- **Günlük Brifing:** Son 24 saatin yönetici özeti.
- **Yönetici Raporu:** 6 bölümlük 1-2 sayfalık narratif digest.
- **AI Proje Direktörü:** Kararlı verdict + 8 KPI + aksiyonlar.
- **AI İhale Analizi:** Teklifleri karşılaştırır, **risk + öneri + yönetici özeti** üretir (ilginç biçimde en ucuzu değil, kalite/risk dengesini önerir).
- **Taşeron nakit akışı tahmini & firma kartı:** EMA + trend + mevsimsellik ile 3 aylık ödeme projeksiyonu, güven yüzdesiyle.
- **PDF sözleşme alan çıkarımı:** Yüklenen sözleşmeden alanları LLM ile çıkarır.

---

## 6. Siteye Baktığımda Ne Öğrenebiliyorum? (Gözlemlenebilir Bilgiler)

Admin oturumuyla gezdiğimde şu somut bilgilere ulaşabiliyorum (gezdiğim anki anlık görüntü):

**Proje:** Central Moscow Hippodrome — Moskova, RF · Aktif · Yolunda · 16,00B ₽ bütçe · %74 ilerleme · 01/02/2025 → 30/06/2026 · “Ana binanın restorasyonu ve projenin yeniden inşası.”
**Maliyet performansı:** BAC 11,94B ₽ · AC (harcanan) 7,33B ₽ · EAC 9,90B ₽ · CPI 1,21 (bütçenin altında).
**Bütçe:** 15 kalem, 8 kategori, kalem bazında detaylı Rusça pozisyonlar ve tutarlar.
**Finansal özet:** 14,16B ₽ gelir / 7,33B ₽ gider / 6,84B ₽ net; MONOTEKSTROY ve MONARTSTROY için ayrı OZET tabloları.
**Taşeronlar:** 3 firma (ООО МЦПИС, ООО ПАМП-ГРУПП, ООО Проектное бюро АрКо), 12 sözleşme (9 geciken), 661,3M ₽ toplam değer, %37,9 ödeme ilerlemesi, 3 aylık ~146,5M ₽ tahmini ödeme.
**İşgücü:** ~2.310 kişi (1.776 direkt, 399 taşeron); Monotek 2005 / Monart 305; disiplin: Civil %74, Electrical %18, Mechanical %8; ~187.600 kümülatif adam-saat; veri tarihi 2026-05-13.
**İhaleler:** 2 ihale (örn. “Резиновое напольное покрытие”), awarded, kalem bazlı karşılaştırma + teklif revizyonları + AI önerisi.
**AI hükmü:** Proje Direktörü “KRİTİK” verdiği bir değerlendirme; Yönetici Raporu 6 bölümlü narratif.
**Veri kalitesi:** Dashboard, ~9.258 finansal kayıttan ~9.188’inin bütçe-kodsuz, ~8.069’unun taşerona bağlanmamış olduğunu gösteriyor (HIGH uyarısı).

Özetle siteden; **bir projenin finansal sağlığı, taşeron ve sözleşme durumu, saha işgücü, ihale rekabeti ve AI’nın yönetici düzeyindeki kararını** uçtan uca okuyabiliyorum.

---

## 7. AI Analizlerinin Düşünme Mantığı ve Veri Kaynakları

Önemli ilke: **Sayılar koddan deterministik olarak hesaplanır; LLM yalnızca bu sayıların üstüne narratif/karar yazar.** Yani AI rakam uydurmaz — KPI’lar, varyans, gecikme günleri vb. her zaman kod tarafından üretilir, Claude sadece yorumlar. AI anahtarı yoksa aynı şekilli çıktı **kural motorundan** gelir.

### 7.1 AI Proje Direktörü (verdict + 8 KPI)
- **Veri kaynağı:** Sözleşmeler (taşeron + bitiş tarihleri), bütçe kalemleri (BAC = planlanan toplam; yoksa proje bütçesi), ledger harcamaları + proje harcamaları (AC), proje ilerleme %’si, ledger veri-kalitesi sayaçları (bütçe-kodsuz / taşeronsuz / toplam), ve son ~30 işgücü snapshot’ı.
- **Düşünme mantığı (7 adım, deterministik):**
  1. **Veri güveni:** kirli-oran (kodsuz+taşeronsuz)/toplam → eşikler %40/%20 ile LOW/MEDIUM/HIGH.
  2. **Takvim & gecikme:** planlanan ilerleme = geçen süre / toplam süre; fiili ilerlemeyle farktan gecikme günü; hıza (velocity) göre tahmini bitiş gecikmesi.
  3. **Kritik yol:** proje bitişine 30 gün kala biten sözleşmeler “kritik”; geciken kritik sözleşme → bloklu.
  4. **Kaynak verimliliği:** ilerleme / kişi sayısı × 1000 (çok kişi-az ilerleme sinyali).
  5. **Maliyet tutarlılığı:** (harcanan/BAC) − (ilerleme/100); +%20 üstü “bütçe aşımı”, −%20 altı “düşük raporlama”.
  6. **Veri güvenilirliği:** 1 − kirli-oran.
  7. **Yüklenici riski:** geciken taşeron sayısı.
- **Karar (verdict):** Kural motoru — bloklu→KRİTİK; tahmini gecikme >14→AT_RISK; maliyet aşımı/gecikme→AT_RISK; **veri güveni LOW ise “ON_TRACK” diyemez**. AI anahtarı varsa Claude “kıdemli proje direktörü” sistem promptuyla (kararlı, tereddütsüz, “veri güvenilmezse açıkça söyle”) aynı JSON kararı üretir; sayılar deterministik kalır.
- **Bizim eklediğimiz governance:** LLM “ON_TRACK” dese bile **paylaşılan güven skoru LOW ise AT_RISK’e kıstırılır** (artık LLM path’i de gate’li).

### 7.2 Yönetici Raporu (6 bölümlü narratif)
- **Veri kaynağı:** Bütçe varyans raporu (planlanan/taahhüt/gerçekleşen + bütçeyi aşan kalemler), taşeron toplamları (ödenen/bekleyen + ortalama ödeme gecikmesi — ödeme tarihleri ile vade farkından), değere göre ilk 5 taşeron, işgücü trendi (son 7 gün vs önceki 7 gün), ve veri-güvenilirliği skoru.
- **Düşünme mantığı:** Bölümler bu olgulardan türetilir — Mali Durum varyanstan, Kritik Riskler bütçe-aşımı kalemleri + ödeme gecikmesi + işgücü düşüşünden, vb. AI anahtarı varsa **tüm olgular JSON olarak Claude’a** gönderilir (“yönetici asistanı, olgusal, pazarlama dili yok, bölüm başına 1-3 cümle”); eksik bölümler kural çıktısıyla doldurulur.
- **Bizim eklediğimiz governance:** Güven HIGH değilse özet bölümünün başına **veri-güvenilirliği uyarısı** eklenir — bu rapor artık %99 bağlanmamış veride “yolunda/bütçe altında” diyemez.

### 7.3 Günlük Brifing
- **Veri kaynağı:** Son 24 saatteki finansal hareket, işgücü kaydı, yeni sözleşme; aktif proje/taşeron sayıları. 10 dk cache’li, dil-duyarlı.
- **Mantık:** “Son 24 saatte ne değişti, neye dikkat edilmeli, bugün ne yapılmalı” çerçevesi (AI veya kural).

### 7.4 AI İhale Analizi
- **Veri kaynağı:** O ihaledeki teklifler — kalem bazlı birim fiyatlar, toplamlar, teslim süreleri, KDV, teklif veren yorumları (dahil/hariç notları), revizyon geçmişi.
- **Mantık (gözlemlenen):** Teklifleri karşılaştırır, her teklif veren için **risk** çıkarır (eksik dokümantasyon, kalite belirsizliği, maliyet), bir **öneri + güven yüzdesi** ve yönetici özeti üretir. Dikkat çekici davranış: en ucuzu körü körüne önermez; teknik şartname/kalite riskini gerekçe göstererek dengeli seçeni önerebilir.

### 7.5 Taşeron Nakit Akışı Tahmini
- **Veri kaynağı:** Taşeronun geçmiş ödeme hareketleri.
- **Mantık:** EMA (üssel hareketli ortalama) + en-küçük-kareler trend + mevsimsellik faktörü ile 3 aylık ödeme projeksiyonu; **güven yüzdesi geçmiş uzunluğuna bağlı** (12 aydan az geçmişi olan firmalarda düşük güven + “mevsimsellik ortalandı” uyarısı).

### 7.6 PDF Sözleşme Alan Çıkarımı
- **Veri kaynağı:** Yüklenen sözleşme PDF’i.
- **Mantık:** LLM ile sözleşme alanlarını (taraf, tutar, süre vb.) çıkarır; sonuç kullanıcı onayına sunulur.

---

## 8. Kısıtlar / Dikkat Notları

- **Veri bütünlüğü:** Finansal kayıtların büyük kısmı bütçe koduna/taşerona bağlı değil; bu yüzden bazı KPI’lar (özellikle “harcanan %”) ekranlar arasında farklı görünebiliyor. (Bu, üzerinde çalıştığımız Faz 0–2.5 düzeltmelerinin ana konusu.)
- **Bazı modüller henüz aktif değil:** Takvim ve Riskler “coming soon”.
- **AI çıktıları** veri güvenilirliğine duyarlı olmalı; düşük güvende iyimser yorum yapılmamalı (governance düzeltmesi bu yönde yapıldı).
- **Tek aktif proje** var; çoklu-proje portföyü için tasarım hazır ama şu an tek proje besleniyor.
