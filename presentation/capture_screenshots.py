"""Monotekstroy sayfalarının otomatik ekran görüntüsünü alır.

Playwright kullanarak headed (görünür) Chrome açar, ilk seferde login
yapman için bekler, sonra tüm sayfaları dolaşıp `screenshots/` klasörüne
PNG olarak kaydeder. İkinci çalıştırmada storage_state.json sayesinde
login adımını atlar.

Kullanım:
    python -m pip install playwright
    python -m playwright install chromium
    python capture_screenshots.py

Sonra:
    python build_presentation.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright yüklü değil. Kur:")
    print("  python -m pip install playwright")
    print("  python -m playwright install chromium")
    sys.exit(1)

BASE = "https://monotek-stroy-pm.vercel.app"
HERE = Path(__file__).parent
SHOTS = HERE / "screenshots"
SHOTS.mkdir(exist_ok=True)
STATE = HERE / "playwright-state.json"

PAGES = [
    ("01-panel.png",            "/"),
    ("02-projects.png",         "/projects"),
    ("03-project-overview.png", "/projects/1"),
    ("04-subcontractors.png",   "/projects/1/subcontractors"),
    ("05-workforce.png",        "/projects/1/workforce"),
    ("06-budget.png",           "/projects/1/budget"),
    ("07-expenses.png",         "/projects/1/expenses"),
    ("08-tenders-list.png",     "/projects/1/tenders"),
    ("09-tender-detail.png",    "/projects/1/tenders/6"),
    ("10-tender-ai.png",        "/projects/1/tenders/6/ai-analysis"),
    ("11-project-ai.png",       "/projects/1/ai-analysis"),
]


def capture():
    with sync_playwright() as pw:
        # Headed mode → ekran görünür, ilk seferde login yapabilirsin
        first_run = not STATE.exists()
        browser = pw.chromium.launch(headless=False)
        context_kwargs = {
            "viewport": {"width": 1568, "height": 800},
            "device_scale_factor": 1.0,
        }
        if not first_run:
            context_kwargs["storage_state"] = str(STATE)
        context = browser.new_context(**context_kwargs)
        page = context.new_page()

        if first_run:
            print("=" * 60)
            print("İLK ÇALIŞTIRMA")
            print("=" * 60)
            print("Tarayıcı açıldı. Lütfen siteye GİRİŞ YAP, ana sayfayı")
            print("gördüğünde bu terminale dön ve ENTER bas.")
            print(f"  → {BASE}/login")
            print()
            page.goto(f"{BASE}/login", wait_until="domcontentloaded")
            input("Login tamamlandığında ENTER bas... ")
            context.storage_state(path=str(STATE))
            print(f"✓ Oturum kaydedildi: {STATE.name}")
            print("  (sonraki çalıştırmalarda otomatik kullanılır)")
            print()

        print(f"{len(PAGES)} sayfa için ekran görüntüsü alınıyor...")
        for fname, route in PAGES:
            target = f"{BASE}{route}"
            print(f"  · {fname:30s}  {route}")
            try:
                page.goto(target, wait_until="networkidle", timeout=60_000)
            except Exception:
                # AI sayfaları uzun sürebilir, networkidle yerine domcontentloaded
                page.goto(target, wait_until="domcontentloaded", timeout=60_000)
                # AI çağrı sayfalarına ekstra bekleme
                time.sleep(15 if "ai-analysis" in route else 4)
            # Görsel olarak yerleştirilsin
            time.sleep(2)
            out = SHOTS / fname
            page.screenshot(path=str(out), full_page=False)
            print(f"    ✓ {out.name} ({out.stat().st_size // 1024} KB)")

        browser.close()
        print()
        print(f"✓ Tamamlandı. {len(PAGES)} ekran görüntüsü {SHOTS.name}/ altında.")
        print()
        print("Şimdi sunumu üret:")
        print("  python build_presentation.py")


if __name__ == "__main__":
    capture()
