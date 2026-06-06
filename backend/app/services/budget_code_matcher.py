"""İş-tipi → bütçe kalemi (cost_code) eşleştirme motoru.

Cynteka faturasının "Вид работ" (iş tipi), satır içeriği ve firma bilgisinden
projenin bütçe kalemlerinden birine cost_code önerir. Saf (DB'siz, ağsız)
fonksiyonlardır; orchestrator/endpoint ayrıdır.

Karar mantığı (kullanıcı kuralı):
    * Tek kalemli kategoriye net düşüş    -> >=95 -> AUTO (otomatik yaz)
    * Çok kalemli kategori                -> <=94 -> REVIEW (öneri, insan seçer)
    * Kategori belirlenemiyor / saf gider  -> <80 -> REJECT (kodsuz kalır)
"""
from __future__ import annotations

from dataclasses import dataclass

try:  # rapidfuzz varsa kullan, yoksa basit oran
    from rapidfuzz import fuzz as _fuzz

    def _ratio(a: str, b: str) -> float:
        return float(_fuzz.token_set_ratio(a, b))
except Exception:  # pragma: no cover
    import difflib

    def _ratio(a: str, b: str) -> float:
        return difflib.SequenceMatcher(None, a, b).ratio() * 100.0


AUTO_MIN = 95.0
REVIEW_MIN = 80.0

# Kanonik kategori -> o kategoriye işaret eden RU/TR anahtar kelimeler.
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "bina": [
        "окн", "общестроитель", "реставрац", "отделочн", "здани",
        "фасад", "кровл", "bina",
    ],
    # NOT: "покрытие" (kaplama) çok genel — "ПВХ покрытие" gibi malzeme
    # faturalarını yanlış çeker; bilerek dışarıda bırakıldı.
    "yollar": ["дорог", "дорожк", "трасс", "асфальт", "беговая", "скачк", "yol"],
    "altyapi": [
        "канализ", "водоснаб", "водопровод", "ливнев", "дожд",
        "наружные сети", "altyap", "altyapı",
    ],
    "elektrik": [
        "электро", "электротехни", "кабель", "кабельн",
        "электроснаб", "elektrik",
    ],
    "haberlesme": ["связи", "слаботоч", "коммуникац", "haberle", "haberleşme"],
    "isitma": ["теплов", "отоплен", "тепловые сети", "isit", "ısıt"],
    "aydinlatma": ["освещен", "прожектор", "светильник", "aydinlat", "aydınlat"],
    "peyzaj": ["благоустройств", "озеленен", "ландшафт", "peyzaj"],
}

# Kategori slug/adından kanonik anahtarı çözmek için ipuçları.
_CANON_HINTS: dict[str, list[str]] = {
    "bina": ["bina", "здани", "building"],
    "yollar": ["yol", "дорог", "road"],
    "altyapi": ["altyap", "altyapı", "инфра", "altyapi"],
    "elektrik": ["elektrik", "электро", "power"],
    "haberlesme": ["haberle", "haberleşme", "связ", "comm"],
    "isitma": ["isit", "ısıt", "теплов", "heat"],
    "aydinlatma": ["aydinlat", "aydınlat", "освещ", "light"],
    "peyzaj": ["peyzaj", "благоустр", "ландшафт", "landscape"],
}


@dataclass(frozen=True)
class BudgetItemRef:
    """Eşleştirilebilir bir bütçe kalemi."""

    cost_code: str
    description: str
    category_slug: str = ""
    category_name: str = ""


@dataclass(frozen=True)
class InvoiceSignal:
    """Bir faturadan gelen eşleştirme sinyalleri."""

    work_type: str = ""      # Вид работ / proje adı son segmenti
    content: str = ""        # offerItems / nomenklatura birleşik
    company_name: str = ""
    inn: str = ""
    request_name: str = ""
    invoice_number: str = ""


@dataclass(frozen=True)
class CodeMatch:
    cost_code: str | None
    candidate_description: str | None
    category_slug: str | None
    confidence: float
    decision: str  # "auto" | "review" | "reject"
    rationale: str
    source: str    # "single_item" | "content_fuzzy" | "category_only" | "none"


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def canonical_category(item: BudgetItemRef) -> str | None:
    """Kalemin kategori slug/adından kanonik anahtarı çöz."""
    hay = f"{_norm(item.category_slug)} {_norm(item.category_name)}"
    for canon, hints in _CANON_HINTS.items():
        if any(h in hay for h in hints):
            return canon
    return None


def _score_categories(text: str) -> list[tuple[str, float]]:
    """Metindeki anahtar kelime isabetlerine göre kategorileri puanla."""
    scored: list[tuple[str, float]] = []
    for canon, kws in CATEGORY_KEYWORDS.items():
        hits = sum(1 for kw in kws if kw in text)
        if hits:
            scored.append((canon, float(hits)))
    scored.sort(key=lambda x: -x[1])
    return scored


def match_budget_code(signal: InvoiceSignal, items: list[BudgetItemRef]) -> CodeMatch:
    """Bir fatura sinyalini projenin bütçe kalemlerinden birine eşle."""
    wt = _norm(signal.work_type)
    body = _norm(f"{signal.content} {signal.request_name}")
    # İş tipi içerikten güçlü; iki katı ağırlık.
    weighted_text = f"{wt} {wt} {body}"

    by_canon: dict[str, list[BudgetItemRef]] = {}
    for it in items:
        if not it.cost_code:
            continue
        c = canonical_category(it)
        if c is None:
            continue
        by_canon.setdefault(c, []).append(it)

    if not by_canon:
        return CodeMatch(None, None, None, 0.0, "reject",
                         "Projede eşlenebilir bütçe kalemi yok.", "none")

    cat_scores = [(c, s) for c, s in _score_categories(weighted_text) if c in by_canon]
    if not cat_scores:
        return CodeMatch(None, None, None, 0.0, "reject",
                         "İş tipi/içerik bir bütçe kategorisine işaret etmiyor "
                         "(muhtemelen genel gider).", "none")

    top_canon, top_score = cat_scores[0]
    ambiguous_category = len(cat_scores) > 1 and cat_scores[1][1] >= top_score

    cat_items = by_canon[top_canon]
    cat_name = cat_items[0].category_name or top_canon

    # --- Tek kalemli kategori -> AUTO ---
    if len(cat_items) == 1:
        it = cat_items[0]
        if ambiguous_category:
            return CodeMatch(it.cost_code, it.description, it.category_slug, 86.0,
                             "review",
                             f"İş tipi '{cat_name}' kategorisine işaret ediyor ama "
                             f"başka kategori de benziyor; tek kalem olduğu için "
                             f"öneriliyor.", "single_item")
        return CodeMatch(it.cost_code, it.description, it.category_slug, 96.0,
                         "auto",
                         f"İş tipi açıkça '{cat_name}' = tek bütçe kalemi "
                         f"({it.cost_code}). Otomatik atandı.", "single_item")

    # --- Çok kalemli kategori -> en olası kalem, ASLA auto ---
    best_it = cat_items[0]
    best_sc = -1.0
    for it in cat_items:
        sc = _ratio(body, _norm(it.description)) if body else 0.0
        if sc > best_sc:
            best_sc, best_it = sc, it

    if best_sc >= 60:
        conf = min(92.0, 80.0 + (best_sc - 60) * 0.5)
        src = "content_fuzzy"
        why = (f"'{cat_name}' kategorisi; içerik en çok '{best_it.description}' "
               f"kalemiyle örtüşüyor (benzerlik {best_sc:.0f}). Çok kalemli "
               f"olduğu için onayına sunuldu.")
    else:
        conf = 80.0
        src = "category_only"
        why = (f"'{cat_name}' kategorisi belirlendi ama içerik hangi kaleme ait "
               f"olduğunu netleştirmiyor; en olası kalem öneriliyor.")

    return CodeMatch(best_it.cost_code, best_it.description, best_it.category_slug,
                     conf, "review", why, src)


def decision_for(confidence: float, item_count_in_category: int) -> str:
    """Eşik + kural: çok kalemli kategori asla auto olamaz."""
    if confidence >= AUTO_MIN and item_count_in_category == 1:
        return "auto"
    if confidence >= REVIEW_MIN:
        return "review"
    return "reject"
