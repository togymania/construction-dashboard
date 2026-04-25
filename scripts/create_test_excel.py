"""Create a sample Excel file for testing the expense import feature."""
import openpyxl
from datetime import date

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Expenses"

# Header row
headers = ["Vendor", "Invoice No", "Date", "Amount", "Category", "Description"]
ws.append(headers)

# Sample data rows
data = [
    ["StroyMontaj LLC", "INV-2026-001", date(2026, 3, 15), 2500000, "Materials", "Concrete for foundation"],
    ["TechnoKran AŞ", "INV-2026-002", date(2026, 3, 18), 1800000, "Equipment", "Crane rental - March"],
    ["Elite İnşaat", "INV-2026-003", date(2026, 3, 20), 5200000, "Subcontractor", "Electrical wiring Phase 1"],
    ["BetaSteel Corp", "INV-2026-004", date(2026, 3, 22), 3750000, "Materials", "Steel reinforcement bars"],
    ["İstanbul Beton AŞ", "INV-2026-005", date(2026, 3, 25), 1200000, "Materials", "Ready-mix concrete delivery"],
    ["Güvenlik Ltd", "INV-2026-006", date(2026, 4, 1), 450000, "Other", "Site security - March"],
    ["İşçi Yönetim AŞ", "INV-2026-007", date(2026, 4, 3), 8500000, "Labor", "Construction crew wages March"],
    ["Permit Office", "INV-2026-008", date(2026, 4, 5), 320000, "Permits", "Building permit extension fee"],
    ["MegaKran Services", "INV-2026-009", date(2026, 4, 8), 2100000, "Equipment", "Heavy machinery maintenance"],
    ["Demir Çelik AŞ", "INV-2026-010", date(2026, 4, 10), 4800000, "Materials", "Structural steel beams"],
]

for row in data:
    ws.append(row)

# Auto-fit column widths
for col in ws.columns:
    max_len = 0
    col_letter = col[0].column_letter
    for cell in col:
        if cell.value:
            max_len = max(max_len, len(str(cell.value)))
    ws.column_dimensions[col_letter].width = max_len + 2

output_path = r"C:\Projects\construction-dashboard\test_expenses.xlsx"
wb.save(output_path)
print(f"Test Excel file created: {output_path}")
print(f"Contains {len(data)} expense rows")
