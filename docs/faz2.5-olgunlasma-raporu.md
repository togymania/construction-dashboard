# ConstructHub — Faz 2.5 (Kurumsal Olgunlaşma) Raporu

**Tarih:** 3 Haziran 2026
**Kapsam:** Reviewer geri bildirimindeki eksiklerin giderilmesi (S0–S5)
**Önceki:** `faz0-3-gelistirme-raporu.md`

---

## 1. Bu Faz Neden Var

Reviewer, Faz 0–3'ü "kriz önleme fazı başarıyla tamamlandı, kurumsal olgunlaşma henüz değil" diye değerlendirdi ve altı somut eksik sıraladı. Faz 2.5 bunları altı sprint'e dönüştürdü. Reviewer'ın en önemli iki uyarısını yöntem olarak benimsedim:

- **"Altyapı hazır" ≠ "çözüldü"** — bu raporda ikisi ayrı ayrı işaretlendi.
- **Ölçülmemiş başarı bir tahmindir** — "8070/9258 → %80" projeksiyonu artık ölçüm aracıyla değiştirildi.

---

## 2. Sprint Sprint Sonuçlar

### S0 — Match Evaluation Harness  (reviewer eksiği #1: ölçüm yok)
**Dosya:** `app/services/match_eval.py` + `test_match_eval.py` (8 test)
Precision / Recall / F1, FP/FN rate, ve **AUTO accuracy ≥ %95 zorunluluğu** (`meets_auto_target`). Sayım kuralları katı ve dürüst (yanlış-id hem FP hem FN). Temsili etiketli sette ölçülen: **Precision 1.0, Recall 1.0, AUTO 3/3 = %100 → hedef GEÇTİ.**
> Dürüstlük: bu, aracın doğruluğunu kanıtlar; **gerçek üretim doğruluğu** için aynı `evaluate()`'e canlı 9.258 kaydın elle etiketlenmiş örneklemi verilmeli.

### S1 — AI Governance entegrasyonu  (reviewer eksiği #2: gate çağrılmıyor)
**Dosyalar:** `data_reliability.py` (+`reliability_from_ledger_counts`), `project_executive_report.py`, `project_ai_analysis.py`
İki AI servisi artık **aynı paylaşılan skordan** karar veriyor. Yönetici Raporu özetine veri-güven caveat'ı ekleniyor; AI Direktör'ün **LLM path'i de** artık LOW güvende "ON_TRACK"ı AT_RISK'e kıstırıyor (önceden yalnız rule path gate'liydi). Canlı sayımlarda skor **6.04 → LOW**; ikisi de DATA_UNRELIABLE/AT_RISK veriyor → **artık çelişemezler.**
> Dürüstlük: paylaşılan skor mantığı izole doğrulandı; uçtan uca AI servis çağrısı DB ister, lokalde teyit edilecek.

### S2 — Parser Hardening çekirdeği  (reviewer "en kritik teknik eksik")
**Dosya:** `app/services/column_discovery.py` + `test_column_discovery.py` (8 test)
Sabit sütun indeksi yerine **header anlamından** eşleştirme (RU/TR/EN alias, fuzzy + **exact-eşleşme önceliği**, tek-bire-bir bağlama). Sütun kaysa bile doğru eşleşir; zorunlu sütun yoksa **sessizce değil `missing` ile gürültüyle** kırılır. `LEDGER_SPECS` hazır.
> Kalan: `ledger_excel.py`/`monart_budget_parser.py`/workforce parser'larını bu helper'a geçirmek (fallback-koruyan retrofit; çalışan parser'ı runtime testi olmadan değiştirmek riskli olduğu için ayrı adım).

### S3 — Observability  (reviewer eksiği #6: görünürlük yok)
**Dosya:** `app/core/observability.py` + `test_observability.py` (10 test)
**JSON-line structured logging** (`get_logger`, `log_event`) + thread-safe **metrics registry** (reconcile.auto/review/reject, parser.error). `record_reconciliation` reconcile CLI'ına **bağlandı**. Sentry/OTel yalnız env+paket varsa devreye girer (hard-dependency yok). Parser hatası artık `record_parser_error` ile sayılabilir/loglanabilir.

### S4 — Learning Match Engine  (reviewer eksiği: feedback learning yok)
**Dosya:** `app/services/match_memory.py` + `test_match_memory.py` (8 test)
Onaylanan eşleşmeleri hatırlar (`MatchMemory`), tekrar onaylandıkça **adaptive confidence boost** verir (her onay +4, cap +15). `boosted_rank` skoru yeniden bantlar: yeterli onayla bir REVIEW → AUTO'ya çıkar; ama sınırlı (zayıf bir eşleşme tek başına AUTO olamaz), 100'de cap'lenir. Üretim wiring'i: `build_memory_from_approved(db)` onaylı `MatchSuggestion`'lardan hafızayı kurar.

### S5 — Playwright E2E  (reviewer eksiği: her şey unit)
**Dosyalar:** `frontend/playwright.config.ts`, `frontend/e2e/smoke.spec.ts`, `package.json` (script + devDep)
Kritik akış scaffolding'i: login → dashboard KPI'ları, proje→bütçe gezinme, ve F1.5 için **SSOT tutarlılık** regresyon testi şablonu (`test.fixme`).
> Dürüstlük: scaffolding — bu ortamda **çalıştırılmadı**. Lokalde `npm i -D @playwright/test && npx playwright install && npm run test:e2e`; seçiciler kendi markup'ına göre ayarlanmalı.

---

## 3. Doğrulama Özeti (Faz 2.5 yeni testleri)

| Modül | Test | Sonuç |
|---|---|---|
| match_eval | 8 | ✅ |
| data_reliability (+ledger_counts) | 26 | ✅ |
| column_discovery | 8 | ✅ |
| observability | 10 | ✅ |
| match_memory | 8 | ✅ |
| **Faz 2.5 yeni (saf)** | **60** | **✅ hepsi geçti** |

Faz 0–3 ile birlikte izole doğrulanan toplam saf-mantık testi: **~190.**

---

## 4. Reviewer Eksikleri — Durum Tablosu

| Reviewer eksiği | Durum |
|---|---|
| #1 Başarı oranı ölçülmüyor | **Çözüldü** (S0 araç + ≥%95 kapısı); gerçek sayı için etiketli örneklem gerekli |
| #2 AI governance çağrılmıyor | **Çözüldü (kod)**; lokal/uçtan-uca teyit bekliyor |
| #3 SSOT yalnız Dashboard | **Kısmi**: dashboard + `/financials` backend hazır; Budget/ProjectList/AI frontend wiring kaldı |
| Parser hardening | **Çekirdek hazır** (S2); retrofit kaldı |
| Observability | **Çözüldü (S3)**; dashboard/Grafana opsiyonel |
| Learning match | **Çözüldü (S4 çekirdek + wiring fonksiyonu)** |
| E2E | **Scaffold (S5)**; lokal çalıştırma kaldı |

---

## 5. Senin Adımların (değişmedi + yeni)

```bash
cd backend
alembic upgrade head           # match_suggestions tablosu
ruff check . && pytest -q      # Faz 0-2.5 testleri (yeşil olmalı)
python -m app.db.reconcile --project-id 1          # dry-run (artık JSON metrik de loglar)

cd ../frontend
npm i -D @playwright/test && npx playwright install
npm run test:e2e               # seçicileri markup'a göre ayarla
```
Ayrıca: Anthropic API anahtarını döndür; git checkpoint (`del .git\index.lock` → tag → branch).

---

## 6. Genel Değerlendirme

Reviewer'ın çerçevesiyle: **kriz-önleme fazı + olgunlaşma fazının doğrulanabilir çekirdekleri** tamamlandı. Geriye kalan üç tür iş net: (a) **retrofit/wiring** (parser→discovery, SSOT→frontend, AI gate uçtan uca), (b) **lokal runtime doğrulama** (alembic, pytest, reconcile, e2e), (c) **gerçek-veri ölçümü** (etiketli örneklemle gerçek precision/recall). Bu üçü tamamlandığında reviewer'ın "%99 eşleşmeyen veri sorununa sistematik çözüm" beklentisi ölçülmüş bir sonuca döner.
