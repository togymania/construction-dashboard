# ConstructHub — Faz 0–3 Geliştirme Raporu

**Tarih:** 3 Haziran 2026
**Kapsam:** Denetim bulgularına dayalı kurumsallaşma yol haritasının uygulanması (Faz 0 → Faz 3)
**Hazırlayan:** Claude (Cowork)

---

## 1. Yönetici Özeti

Bugün, daha önce çıkardığımız denetim raporundaki kritik bulguları ele alan dört fazlık yol haritasının **kod tarafını** uyguladık. Çalışma yöntemi tutarlıydı: her fazın çekirdek iş mantığı **saf, izole, bağımlılıksız ve birim-testli** modüller olarak yazıldı; veritabanı/endpoint/migration gibi entegrasyon parçaları mevcut proje konvansiyonlarına birebir uyduruldu.

Önemli kısıt: bu oturumdaki çalışma ortamında **canlı veritabanı, asyncpg ve git yazımı yoktu**; ayrıca dosya sistemi mount'u bash okumalarını zaman zaman kestiği için doğrulamayı **izole bir sandbox'ta** yaptım. Bu yüzden:

- **Saf mantık modülleri** (cost_code, matching, reconciliation planner, metrics, data_reliability, risk_scoring) → **birim testleriyle doğrulandı, hepsi yeşil.**
- **Entegrasyon kodu** (yeni model, migration, endpoint'ler, dashboard düzenlemesi) → **konvansiyona uygun yazıldı ama bu oturumda çalıştırılamadı.** Lokalde `alembic upgrade head` + `pytest` + `ruff` ile teyit edilmeli.

Toplam: **19 yeni dosya, 6 değişen dosya, 1 CI pipeline, 1 fiziksel checkpoint.**

---

## 2. Faz 0 — Temel & Güven

**Amaç:** Güvenli zemin, sır güvenliği, normalize motoru, SSOT çekirdeği, test/CI iskeleti.

| Dosya | Tür | Ne yapar |
|---|---|---|
| `app/services/cost_code.py` | yeni | **Cost Code Normalization Engine.** `"03" / "3.0" / " 3 " / "３" / "29,00"` hepsini tek canonical forma indirir. WBS kodlarını (`3.10`) bozmaz. |
| `app/services/metrics.py` | yeni | **SSOT Metrics Service çekirdeği.** Tek "harcanan %" tanımı (`spent/planned`). |
| `app/services/budget_variance.py` | değişti | Eşleştirmenin 3 noktası `.strip().lower()` yerine canonical normalize kullanıyor; **çakışmada toplama** yapıyor (yoksa "03" ve "3" birbirini eziyordu). |
| `app/core/config.py` | değişti | Prod'da varsayılan `SECRET_KEY` ile **açılışı reddeder** (fail-fast). |
| `.github/workflows/ci.yml` | yeni | Her push/PR'da backend ruff+pytest, frontend tsc. |
| `app/tests/test_cost_code.py`, `test_metrics.py` | yeni | 70+ test senaryosu. |

**Düzeltilen denetim bulgusu:** Eşleştirmenin kırılgan string-join'i + tutarsız metrik tanımının kökü.
**Doğrulama:** cost_code 62 senaryo, metrics math (61.39% = bütçe sayfasıyla birebir) → **geçti.**

---

## 3. Faz 1 — Veri Bütünlüğü Kurtarma

**Amaç:** Canlıdaki %99 eşleşmeyen finansal veriyi (9.188 kodsuz harcama, 8.069 bağlanmamış ödeme) düzeltecek altyapı.

| Dosya | Tür | Ne yapar |
|---|---|---|
| `app/services/matching.py` | yeni | **Generic Matching Pipeline.** exact (normalize) → fuzzy (rapidfuzz token_set_ratio) → confidence bant (AUTO ≥90 / REVIEW ≥75 / REJECT). **Belirsizlik kapısı:** en iyi aday ikinciyi 5 puan geçemezse AUTO'ya değil REVIEW'a düşer. |
| `app/services/reconciliation.py` | yeni | **Reconciliation planner** (saf) + DB yükleyici. Unmatched satırlara aday üretir, istatistik + projeksiyon çıkarır. Salt-okunur (dry-run). |
| `app/db/reconcile.py` | yeni | **Auto-Reconciliation Engine** (çalıştırılabilir). `--apply` yalnız AUTO-tier'ı ve yalnız NULL alanları değiştirir, **JSON audit** yazar, `--undo` ile birebir geri alınır. |
| `app/models/match_suggestion.py` | yeni | **Human Review** kalıcı öneri tablosu (PENDING/APPROVED/REJECTED + audit). |
| `alembic/versions/j0e1f2a3b4c5_*.py` | yeni | `match_suggestions` tablosu migration'ı (head `i9d0e1f2g3h4`'e bağlı). |
| `app/api/v1/endpoints/reconciliation.py` | yeni | `generate` / `list` / `approve` / `reject` / `bulk-approve` / `bulk-reject` endpoint'leri. Approve değeri **yalnız NULL ise** yazar. |
| `app/schemas/match_suggestion.py`, `app/schemas/financials.py` | yeni | Pydantic şemalar. |
| `app/api/v1/router.py`, `alembic/env.py` | değişti | Router + model kaydı. |
| `app/tests/test_matching.py`, `test_reconciliation.py` | yeni | 29 test. |

### Faz 1.5 — SSOT Wiring
- `app/schemas/financials.py` + yeni `GET /projects/{id}/financials` → tüm yüzeylerin okuyacağı **canonical** metrik kaynağı.
- **Dashboard düzeltildi:** "Total Budget %0 used" hatasının kök nedeni dashboard'ın harcamayı **boş `Expense` tablosundan** toplamasıydı. Artık Metrics Service'ten (OZET-tabanlı gerçek harcama) okuyor → bütçe sayfasıyla tutarlı.

**Düzeltilen denetim bulguları:** #2 (veri eşleştirme), #3 (4 farklı "harcanan %"), kısmen #1 (test).
**Doğrulama:** matching 21, reconciliation planner 8 (projeksiyon: 8070/9258 → %80+) → **geçti.** Migration/endpoint **lokalde çalıştırılacak.**

---

## 4. Faz 2 — AI Governance

**Amaç:** İki AI özelliğinin (Yönetici Raporu "yolunda" vs AI Direktör "KRİTİK") aynı veride çelişmesini engellemek.

| Dosya | Tür | Ne yapar |
|---|---|---|
| `app/services/data_reliability.py` | yeni | **Data Reliability Score + Verdict Gate.** Objektif sinyallerden (eşleşme kapsamı, tazelik) 0–100 güven skoru üretir. **Kapı:** güven düşükse iyimser karar (on_track/watch) → `DATA_UNRELIABLE`'a düşürülür; kötümser kararlar (at_risk/critical) asla yumuşatılmaz. Her iki AI özelliği bunu çağırırsa bir daha çelişemez. |
| `app/tests/test_data_reliability.py` | yeni | 22 test. |

**Düzeltilen denetim bulgusu:** #4 (iki AI çelişkisi). Canlı senaryo (70/9258 eşleşme, ~20 gün eski veri) → güven skoru LOW → "on_track" otomatik `DATA_UNRELIABLE` olur. Tam da audit'teki yanlış "proje yolunda" mesajını engeller.
**Doğrulama:** 22 test → **geçti.**

> **Not:** Bu modül governance'ın *çekirdeği*. İki AI servisine (executive report, project director) bağlanması — yani gerçekten çağırmaları — risksiz bir sonraki dokunuş olarak bırakıldı (AI servislerini runtime testi olmadan değiştirmek riskli).

---

## 5. Faz 3 — Construction Intelligence (predictive çekirdekler)

**Amaç:** Prompt'taki "AI-Powered Construction Intelligence" vizyonunun ölçülebilir, deterministik çekirdekleri.

| Dosya | Tür | Ne yapar |
|---|---|---|
| `app/services/risk_scoring.py` | yeni | **Subcontractor Risk Scoring** (0–100; ağırlıklı: geciken sözleşme oranı, ödeme ilerlemesi, geçmiş uzunluğu, rating) + **Cost Overrun Forecast** (Earned Value: EV/CPI/EAC/VAC + overrun bandı). |
| `app/tests/test_risk_scoring.py` | yeni | 10 test. |

**Doğrulama:** EAC çekirdeği canlı Hippodrome kartıyla birebir (BAC 11.94B, AC 7.33B, %74 → CPI ~1.21, EAC ~9.90B, bütçe altında). 10 test → **geçti.**

> Bu çekirdekler aynı arayüzün arkasında ileride eğitimli ML modelleriyle değiştirilebilir.

---

## 6. Bilinçli Olarak YAPILMAYANLAR (dürüst durum)

Aşağıdakiler çok-haftalık / altyapı işleri veya runtime/DB/git gerektirdiği için bu oturumda **yapılmadı** ve öyle iddia edilmiyor:

- **Faz 1 frontend review UI** — backend hazır; öneri kuyruğu için React sayfası ve proje-listesi/AI yüzeylerinin `/financials`'a bağlanması frontend dokunuşu + runtime testi ister.
- **Faz 2 AI servis entegrasyonu** — reliability gate modülü hazır ama executive_report/project_director servisleri henüz onu *çağırmıyor*.
- **Faz 2 parser sağlamlaştırma** (sabit sütun → header'dan dinamik), **auth token refresh**, **observability (Sentry/OTel)** — tasarlandı, kodlanmadı.
- **Faz 3 altyapı:** Redis, event sistemi, Executive Copilot, Playwright E2E + contract + AI regression testleri, eğitimli predictive ML — kapsamlı ve bu ortamda doğrulanamaz.

---

## 7. Senin Yapman Gereken Adımlar

Bu oturumdan **git'e yazamadım** (kilit) ve **DB'ye dokunamadım**. Lokalde:

```bash
# 1) Güvenlik
#    Anthropic API anahtarını döndür (yeni anahtar üret, Render env'ine koy).

# 2) Git checkpoint (bir kez)
del .git\index.lock
git tag checkpoint-pre-fixes
git checkout -b fixes-2026-06

# 3) Backend
cd backend
alembic upgrade head            # yeni match_suggestions tablosu
ruff check .                    # lint
pytest -q                       # Faz 0-3 testleri (yeşil olmalı)

# 4) Veri kurtarma (önce dry-run, hiçbir şey yazmaz)
python -m app.db.reconcile --project-id 1
python -m app.db.reconcile --project-id 1 --apply        # AUTO'yu uygula
# REVIEW kuyruğu (API):
#   POST /api/v1/projects/1/reconciliation/generate
#   GET  /api/v1/reconciliation/suggestions
```

---

## 8. Riskler / Nelere Dikkat

1. **Entegrasyon kodu runtime'da denenmedi.** Migration ve endpoint'ler konvansiyona uygun ama ilk `pytest`/`alembic` çalıştırmasında ufak düzeltmeler gerekebilir.
2. **`budget_code` AUTO eşleşmesi düşük çıkabilir** — bu *doğru* davranış: maaş/vergi/banka satırları gerçekten bir inşaat bütçe kalemine karşılık gelmez; zorla eşlemek yanlış olurdu. Asıl kazanç taşeron eşleştirmede.
3. **Dashboard "harcanan %" artık ~%45.8 (spent/budget) gösterecek**, bütçe sayfası ~%61.4 (spent/planned). İkisi **aynı harcama rakamından** türüyor ama farklı paydadan — bu tasarımsal ve etiketli; "0/72/61.4/2" kaosu bitti.
4. **Mount truncation** sadece benim bash doğrulamamı etkiledi; senin dosyaların (Edit/Write köprüsü) eksiksiz.

---

## 9. Test Özeti (izole doğrulama)

| Modül | Test | Sonuç |
|---|---|---|
| cost_code | 62 senaryo | ✅ |
| matching | 21 | ✅ |
| reconciliation planner | 8 | ✅ |
| metrics | 8 | ✅ |
| data_reliability | 22 | ✅ |
| risk_scoring | 10 | ✅ |
| **Toplam (saf mantık)** | **~131** | **✅ hepsi geçti** |

Entegrasyon (model/migration/endpoint/dashboard): yazıldı, **lokalde çalıştırılacak.**
