# Monotekstroy Yönetici Sunumu

16 slaytlık Türkçe PowerPoint sunumu — ekran görüntüleri **otomatik** çekilir.

## Tek-tıkla akış (önerilen)

```powershell
cd C:\Projects\construction-dashboard\presentation

# 1) Bağımlılıklar (tek seferlik)
python -m pip install playwright python-pptx Pillow
python -m playwright install chromium

# 2) Ekran görüntülerini otomatik al
#    İlk çalıştırmada Chrome açılır → login yap → ENTER bas → script gerisini halleder
python capture_screenshots.py

# 3) Sunumu üret
python build_presentation.py
```

Çıktı: `Monotekstroy-Sunum.pptx`

İkinci ve sonraki çalıştırmalarda `playwright-state.json` sayesinde otomatik
giriş yapılır, sadece adım 2 ve 3 saniyeler içinde çalışır.

---

## Manuel alternatif

Playwright kurmak istemiyorsan, ekran görüntülerini elle al ve
`screenshots/` klasörüne aşağıdaki adlarla koy:

| Dosya | Sayfa |
|---|---|
| `01-panel.png` | Panel (`/`) |
| `02-projects.png` | Projeler (`/projects`) |
| `03-project-overview.png` | Proje detayı (`/projects/1`) |
| `04-subcontractors.png` | Taşeronlar (`/projects/1/subcontractors`) |
| `05-workforce.png` | İşgücü (`/projects/1/workforce`) |
| `06-budget.png` | Bütçe (`/projects/1/budget`) |
| `07-expenses.png` | Harcamalar (`/projects/1/expenses`) |
| `08-tenders-list.png` | İhaleler (`/projects/1/tenders`) |
| `09-tender-detail.png` | İhale detay (`/projects/1/tenders/6`) |
| `10-tender-ai.png` | AI Tender Analizi (`/projects/1/tenders/6/ai-analysis`) |
| `11-project-ai.png` | AI Proje Analizi (`/projects/1/ai-analysis`) |

> **İpucu:** Chrome'da `F12` → `Ctrl+Shift+P` → "Capture screenshot" yaz →
> Enter. Sayfanın görünür kısmını PNG olarak indirir. 11 sayfa için
> yaklaşık 1 dakikalık iş.

Sonra:

```powershell
python build_presentation.py
```

Eksik görüntü varsa script ilgili kutuya gri "[ Ekran görüntüsü: ... ]"
placeholder'ı koyar — PowerPoint'i açıp manuel ekleyebilirsin.

---

## Slaytlar (16 adet)

1. **Kapak** — Monotekstroy: AI Destekli İnşaat Proje Yönetim Platformu
2. **Neden Monotekstroy** — 4 KPI fayda kartı
3. **Teknik Mimari** — Stack tablosu + AI yetenekleri kutusu
4. **Panel** — Yönetici paneli ana ekran
5. **Projeler** — Portföy görünümü
6. **Proje Detayı** — Genel Bakış + EAC Forecast
7. **Taşeronlar** — Sözleşme, ödeme, nakit akışı tahmini
8. **İşgücü** — Sahadaki personel analitiği + AI Insights
9. **Bütçe** — Plan vs Gerçekleşme
10. **Harcamalar** — Banka ekstresi + AI sınıflandırma
11. **İhaleler — Detay** — *Yıldız slayt: hiyerarşi + varyant + revize + renk*
12. **AI Tender Analizi** — 6 bölümlü karar raporu
13. **AI Proje Analizi** — 5 modüllü yönetici özeti
14. **Etki** — Beklenen operasyonel kazanımlar (koyu zemin)
15. **Yol Haritası** — Şu an / Faz 1 / Faz 2 / Faz 3
16. **Teşekkürler** — Kapanış + iletişim

## Marka

| Element | Değer |
|---|---|
| Primary | Indigo 600 `#4F46E5` |
| Secondary | Indigo 400 `#818CF8` |
| Accent | Amber 500 `#F59E0B` |
| Dark | Slate 900 `#0F172A` |
| Başlık fontu | Georgia |
| Gövde fontu | Calibri |

## Yeniden üret

`python build_presentation.py` her seferinde `.pptx` dosyasını sıfırdan
üretir — PowerPoint içinde elle yaptığın değişiklikler kaybolur. Kalıcı
değişiklikleri `build_presentation.py` içindeki `slide_*` fonksiyonlarına
yedir, script'i tekrar çalıştır.
