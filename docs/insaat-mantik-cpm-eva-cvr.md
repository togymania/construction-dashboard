# İnşaat Mühendisliği Mantığı: S-Curve / CPM / EVA / CVR

**Tarih:** 3 Haziran 2026
**Kapsam:** Üç prompt'un birebir uygulanması (zaman/kritik yol, kazanılmış değer, tahakkuk denetimi)

---

## Özet

Üç prompt da inşaat PM standartlarına uygun, **saf+test edilebilir mühendislik çekirdekleri** olarak yazıldı ve ardından iki AI servisine (Proje Direktörü + Yönetici Raporu) bağlandı. Çekirdekler izole doğrulandı (**42 yeni test, hepsi yeşil**). AI servis entegrasyonu yazıldı ve yapısal olarak teyit edildi; uçtan uca çalışması DB gerektirdiği için **lokalde doğrulanacak.**

---

## Prompt 1 — S-Curve Zaman + Kritik Yol (CPM)

**Yeni dosyalar:** `app/services/schedule_curve.py`, `app/services/critical_path.py` (+ test_schedule_curve, test_critical_path → 18 test ✅)

1. **Lineer → S-Eğrisi:** Planlanan ilerleme artık `geçen süre / toplam süre` değil, `S(t)=t^k/(t^k+(1-t)^k)` (k=2) S-eğrisi. Yavaş başlangıç / hızlı orta / yavaş bitiş. `k=1` eski lineer davranışı verir (geriye uyum).
2. **Kritik Yol yeniden tanımı:** “Bitişe 30 gün kala” yerine gerçek **CPM** — forward/backward pass ile ES/EF/LS/LF ve **Total Float**; kritik = TF≈0 zinciri. Bağımlılık modeli henüz yok (Takvim modülü “coming soon”), bu yüzden sözleşmelerden degenere bir ağ kuruluyor (en uzun sözleşme = TF 0). Gerçek aktivite ağı eklenince aynı motor çalışır.
3. **AI JSON context'ine eklendi:** `planned_s_curve_progress_pct`, `actual_earned_progress_pct`, `critical_path_delayed_days`.
4. **AI mantığı:** Hem rule verdict hem sistem prompt güncellendi — “fiili earned < planlanan S-eğrisi VE gecikme kritik yolda (TF=0) ise → AT_RISK/CRITICAL”.

## Prompt 2 — Earned Value (EVA)

**Yeni dosya:** `app/services/earned_value.py` (+ test → 11 test ✅)

1. **ACWP / BCWP / BCWS:** Actual Cost (ödenen+bekleyen), Earned Value (fiziksel % × BAC), Planned Value (S-eğrisi × BAC).
2. **CPI = BCWP/ACWP, SPI = BCWP/BCWS** hesaplanıyor.
3. **Maliyet kuralı:** CPI < 0,90 → bütçe aşımı (kırmızı); CPI > 1,0 → olumlu (yeşil); arası amber. AI Direktör'ün “Cost Consistency” KPI'sı eski sezgisel formülden bu CPI kuralına geçirildi.
4. **EAC projeksiyonu zorunlu:** Yönetici Raporu'nun **Mali Durum** bölümüne deterministik olarak şu cümle ekleniyor: “Mevcut performansa göre (CPI=X) projenin bitiş bütçesi Y ₽ tutarında aşabilir/altında kalabilir (EAC Z ₽).” (LLM atlasa bile garanti.)

## Prompt 3 — Tahakkuk (Accruals) / CVR

**Yeni dosya:** `app/services/accruals.py` + `data_reliability.apply_accrual_penalty` (+ test → 13 test ✅)

1. **`missing_accrual_flag`:** Fiziksel ilerlemesi olduğu halde son 30 günde maliyet (fatura/ACWP) kaydı düşülmeyen sözleşme.
2. **İlerleme-ödeme farkı:** saha % − ödeme % > 20 puan ise “Güvenilmez / Eksik Tahakkuk”.
3. **Data Trust Score'a negatif ağırlık:** `apply_accrual_penalty(score, flagged_ratio)` güven skorunu eksik-tahakkuk oranıyla düşürür (cap 40 puan). AI Direktör güvenilirlik KPI'sı ve Yönetici Raporu caveat'ı artık bu cezalı skoru kullanıyor.
4. **AI uyarısı:** Eksik tahakkuk yüksekse Yönetici Raporu özetine: “Sahada yapılan işlerin maliyet kayıtları (tahakkuklar) sisteme işlenmemiştir; mevcut kâr/zarar durumu yanıltıcı olabilir.”

---

## Bağlandığı Yerler (wiring)

| Dosya | Değişiklik |
|---|---|
| `project_ai_analysis.py` | facts'e S-curve/EVA/CPM/accrual; Cost KPI → CPI kuralı; takvim planı → S-curve; reliability → accrual cezası; rule verdict S-curve+kritik koşulu; sistem prompt (EN/TR) + JSON context güncellendi |
| `project_executive_report.py` | facts'e EVA+accrual; Mali Durum'a **zorunlu EAC cümlesi**; özete accrual uyarısı + tahakkuk-cezalı güven caveat'ı |
| `data_reliability.py` | `apply_accrual_penalty` |

---

## Doğrulama

| Modül | Test | Sonuç |
|---|---|---|
| schedule_curve | 10 | ✅ |
| critical_path | 8 | ✅ |
| earned_value | 11 | ✅ |
| accruals (+penalty) | 13 | ✅ |
| **Toplam (yeni saf çekirdek)** | **42** | **✅** |

**Dürüstlük notları:**
- AI servis **wiring'i** (facts/KPI/verdict/prompt) yazıldı, yapısal teyit edildi; **uçtan uca runtime testi** (DB + AI çağrısı) lokalde yapılmalı: `cd backend && pytest -q`.
- **Tahakkuk sinyali proje seviyesinde proxy** (saha % vs işlenen maliyet oranı). Gerçek per-sözleşme tahakkuk için sözleşme bazlı fiziksel ilerleme alanı gerekiyor (veri modelinde henüz yok) — CPM'in gerçek bağımlılık ağı gibi, bu da Takvim modülü gelince tam değer kazanır.
- Geriye uyum: S-curve `k=1`'de lineer; EAC/CPI veri yoksa “hesaplanamıyor” der; accrual cezası 0 oranında skoru değiştirmez.
