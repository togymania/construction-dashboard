"""Tests for the work-type -> budget item matching engine."""
from __future__ import annotations

from app.services.budget_code_matcher import (
    AUTO_MIN,
    REVIEW_MIN,
    BudgetItemRef,
    InvoiceSignal,
    canonical_category,
    match_budget_code,
)

# Gerçek projeyi yansıtan kalemler (cost_code, açıklama, kategori)
ITEMS = [
    BudgetItemRef("3", "Главное здание (ОКН)", "bina", "Bina"),
    BudgetItemRef("29", "Призовые дороги (скачка)", "yollar", "Yollar"),
    BudgetItemRef("30", "Призовые дороги (беговая)", "yollar", "Yollar"),
    BudgetItemRef("31", "Рабочая дорожка тренинга (мягкое)", "yollar", "Yollar"),
    BudgetItemRef("35", "Канализация", "altyapi", "Altyapı"),
    BudgetItemRef("36", "Водоснабжение", "altyapi", "Altyapı"),
    BudgetItemRef("37", "Дождевая канализация", "altyapi", "Altyapı"),
    BudgetItemRef("38", "Наружные сети связи", "haberlesme", "Haberleşme"),
    BudgetItemRef("39", "Тепловые сети", "isitma", "Isıtma"),
    BudgetItemRef("40", "Электроснабжение (кабельные линии 0,4 кВ)", "elektrik", "Elektrik"),
    BudgetItemRef("41", "Территориальное наружное освещение", "elektrik", "Elektrik"),
    BudgetItemRef("44", "Благоустройство", "peyzaj", "Peyzaj"),
    BudgetItemRef("45", "Спортивное освещение", "aydinlatma", "Aydınlatma"),
]


class TestCanonicalCategory:
    def test_slug_resolves(self):
        assert canonical_category(BudgetItemRef("3", "x", "bina", "Bina")) == "bina"
        assert canonical_category(BudgetItemRef("40", "x", "elektrik", "Elektrik")) == "elektrik"

    def test_name_fallback(self):
        # slug boş, ad Rusça
        assert canonical_category(BudgetItemRef("39", "x", "", "Тепловые / Isıtma")) == "isitma"

    def test_unknown(self):
        assert canonical_category(BudgetItemRef("99", "x", "ofis", "Ofis Gideri")) is None


class TestSingleItemAuto:
    def test_okn_general_construction_auto_bina(self):
        sig = InvoiceSignal(work_type="Общестроительные работы")
        m = match_budget_code(sig, ITEMS)
        assert m.cost_code == "3"
        assert m.decision == "auto"
        assert m.confidence >= AUTO_MIN

    def test_restoration_okn_auto_bina(self):
        sig = InvoiceSignal(
            work_type="Реставрационные работы объекта культурного наследия (ОКН)"
        )
        m = match_budget_code(sig, ITEMS)
        assert m.cost_code == "3"
        assert m.decision == "auto"

    def test_heating_single_item_auto(self):
        sig = InvoiceSignal(work_type="Инженерно-технические работы",
                            content="Тепловые сети отопление монтаж")
        m = match_budget_code(sig, ITEMS)
        assert m.cost_code == "39"  # Тепловые сети (tek isıtma kalemi)
        assert m.decision == "auto"

    def test_haberlesme_single_item_auto(self):
        sig = InvoiceSignal(work_type="Слаботочные сети связи")
        m = match_budget_code(sig, ITEMS)
        assert m.cost_code == "38"
        assert m.decision == "auto"


class TestMultiItemReview:
    def test_electrical_multi_item_review_not_auto(self):
        # Elektrik'te 2 kalem var (40, 41) -> asla auto
        sig = InvoiceSignal(work_type="Электротехнические работы", content="Кабель")
        m = match_budget_code(sig, ITEMS)
        assert m.category_slug == "elektrik"
        assert m.decision == "review"
        assert m.confidence < AUTO_MIN
        assert m.confidence >= REVIEW_MIN

    def test_electrical_cable_prefers_cable_item(self):
        sig = InvoiceSignal(work_type="Электротехнические работы",
                            content="Кабельные линии 0,4 кВ электроснабжение")
        m = match_budget_code(sig, ITEMS)
        assert m.cost_code == "40"  # kablo kalemi
        assert m.decision == "review"

    def test_roads_multi_item_review(self):
        sig = InvoiceSignal(work_type="Дорожные работы", content="асфальт покрытие")
        m = match_budget_code(sig, ITEMS)
        assert m.category_slug == "yollar"
        assert m.decision == "review"
        assert m.confidence < AUTO_MIN

    def test_water_sewer_multi_item_review(self):
        sig = InvoiceSignal(work_type="Инженерные сети", content="Канализация трубы")
        m = match_budget_code(sig, ITEMS)
        assert m.category_slug == "altyapi"
        assert m.decision == "review"


class TestReject:
    def test_office_supplies_reject(self):
        sig = InvoiceSignal(work_type="Без договора",
                            content="Перчатки х/б, ПВХ покрытие 300 шт")
        m = match_budget_code(sig, ITEMS)
        # eldiven hangi inşaat kalemine ait değil
        assert m.decision == "reject"
        assert m.cost_code is None

    def test_subcontract_services_no_signal_reject(self):
        sig = InvoiceSignal(work_type="Субподряд и услуги",
                            content="Консультационные услуги по лицензии")
        m = match_budget_code(sig, ITEMS)
        assert m.decision == "reject"

    def test_empty_signal_reject(self):
        m = match_budget_code(InvoiceSignal(), ITEMS)
        assert m.decision == "reject"

    def test_no_items_reject(self):
        m = match_budget_code(InvoiceSignal(work_type="Общестроительные"), [])
        assert m.decision == "reject"
        assert "kalem yok" in m.rationale.lower() or "yok" in m.rationale.lower()


class TestRobustness:
    def test_router_electrical_keyword_but_office(self):
        # "Электротехнические" iş tipi -> elektrik kategorisi (router faturası).
        # Çok kalemli -> review; auto YAZMAZ (kullanıcı seçer).
        sig = InvoiceSignal(work_type="Электротехнические работы",
                            content="Роутер MIKROTIK RB4011")
        m = match_budget_code(sig, ITEMS)
        assert m.decision == "review"

    def test_content_only_no_worktype(self):
        sig = InvoiceSignal(content="Кабельные линии электроснабжение")
        m = match_budget_code(sig, ITEMS)
        assert m.category_slug == "elektrik"
        assert m.decision == "review"
