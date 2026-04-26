"""Create a sample Excel file for testing the budget item import feature."""
import openpyxl
from pathlib import Path

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Budget"

# Header row - mix of EN and TR aliases on purpose to exercise the
# fuzzy header mapping.
headers = ["Kategori", "Item Name", "Tutar", "Notes"]
ws.append(headers)

# Sample data:
#   * Materials, Labor, Equipment, Subcontractor — match existing system categories.
#   * "HVAC", "Steel Works" — NEW categories, will be auto-created.
#   * One duplicate (intentional, for in-file dup detection demo).
data = [
    ["Materials",      "Concrete C30/37",          5_000_000,  "Mix design A"],
    ["Materials",      "Steel rebar B500B",        8_500_000,  "Tons: 850"],
    ["Labor",          "Foundation crew Q1",       12_000_000, "60 workers x 3 months"],
    ["Equipment",      "Tower crane rental",        3_200_000, "Manitowoc 999"],
    ["Subcontractor",  "Electrical works Phase 1", 18_500_000, "Pavlov LLC"],
    ["HVAC",           "Air handling units",        4_750_000, "12 units, AHU-1500"],
    ["HVAC",           "Ductwork install",          2_300_000, ""],
    ["Steel Works",    "Structural columns",       22_000_000, "Phase 1 only"],
    ["Steel Works",    "Roof trusses",              9_800_000, ""],
    ["Materials",      "Concrete C30/37",           5_000_000, "Duplicate intentional"],
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

output_dir = Path(r"C:\Projects\construction-dashboard\tests\fixtures")
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / "test_budget_items.xlsx"
wb.save(output_path)
print(f"Test Excel file created: {output_path}")
print(f"Contains {len(data)} budget item rows")
print(f"  - 5 in existing categories (Materials, Labor, Equipment, Subcontractor)")
print(f"  - 4 in NEW categories (HVAC x2, Steel Works x2) -> auto-create")
print(f"  - 1 duplicate row (intentional, for warning test)")
