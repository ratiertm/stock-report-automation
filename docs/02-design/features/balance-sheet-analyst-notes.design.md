# Balance Sheet + Analyst Notes Design Document

> **Feature**: balance-sheet-analyst-notes
> **Project**: Stock Report Hub
> **Date**: 2026-03-02
> **Status**: Draft
> **Plan Reference**: `docs/01-plan/features/balance-sheet-analyst-notes.plan.md`

---

## 1. Task 1: CFRA Balance Sheet Parsing

### 1.1 PDF Data Structure

CFRA PDF pages 2-3 contain financial history tables. The structure is:

```
Per Share Data (USD) 2025 2024 2023 2022 2021 2020 2019 2018 2017 2016
  ← year header (8~10 years, varies by company age)
...per share rows (skip)...

Income Statement Analysis (Million USD)
...income rows (skip)...

Balance Sheet and Other Financial Data (Million USD)
Cash              94,565  75,543  111,256  ...
Current Assets    191,131 159,734 184,257  ...
...13 rows total...
```

**Key observations:**
- Year header is on "Per Share Data (USD)" line — reused for all sections
- Year count varies: PLTR=8, others=10
- Values can be: numbers, "N/A", "NM", negative (e.g., "-297.00")
- Decimal format: "996.00" (small values) vs "94,565" (large values)

### 1.2 Dataclass: `CFRABalanceSheet`

Add to `cfra_parser.py` after `CFRAFinancial`:

```python
@dataclass
class CFRABalanceSheet:
    """Maps to stock_balance_sheets table."""
    fiscal_year: int = 0
    cash: Optional[str] = None
    current_assets: Optional[str] = None
    total_assets: Optional[str] = None
    current_liabilities: Optional[str] = None
    long_term_debt: Optional[str] = None
    total_capital: Optional[str] = None
    capital_expenditures: Optional[str] = None
    cash_from_operations: Optional[str] = None
    current_ratio: Optional[str] = None
    ltd_to_cap_pct: Optional[str] = None
    net_income_to_revenue_pct: Optional[str] = None
    return_on_assets_pct: Optional[str] = None
    return_on_equity_pct: Optional[str] = None
```

Add `balance_sheets: List[CFRABalanceSheet]` to `CFRAParseResult`.

### 1.3 Parser Method: `_parse_balance_sheet()`

**Algorithm:**

```
1. Find "Per Share Data (USD)" line → extract years array
   regex: r'Per Share Data \(USD\)\s+([\d\s]+)'
   → split → [2025, 2024, 2023, ...]

2. Find "Balance Sheet and Other Financial Data" line
   → start index

3. Parse 13 rows after start:
   For each row:
     - Match label via LABEL_MAP
     - Split values by whitespace
     - Pair each value with corresponding year from step 1
```

**Label → Field Mapping:**

```python
BS_LABEL_MAP = {
    "Cash": "cash",
    "Current Assets": "current_assets",
    "Total Assets": "total_assets",
    "Current Liabilities": "current_liabilities",
    "Long Term Debt": "long_term_debt",
    "Total Capital": "total_capital",
    "Capital Expenditures": "capital_expenditures",
    "Cash from Operations": "cash_from_operations",
    "Current Ratio": "current_ratio",
    "% Long Term Debt of Capitalization": "ltd_to_cap_pct",
    "% Net Income of Revenue": "net_income_to_revenue_pct",
    "% Return on Assets": "return_on_assets_pct",
    "% Return on Equity": "return_on_equity_pct",
}
```

**Value Parsing Rules:**
- "N/A", "NM", "NR" → `None`
- "-297.00" → `-297.00` (negative values allowed)
- "94,565" → `94565` (comma removal)
- "996.00" → `996.00` (decimal preservation)

**Output:** List of `CFRABalanceSheet` objects, one per year.

### 1.4 Integration Points

| File | Change |
|------|--------|
| `cfra_parser.py` | `CFRABalanceSheet` dataclass, `_parse_balance_sheet()` method |
| `cfra_parser.py` | `CFRAParseResult.balance_sheets` field |
| `cfra_parser.py` | `parse()` method: call `_parse_balance_sheet()` |
| `cfra_parser.py` | `parse_cfra()`: include `balance_sheets` in return dict |

---

## 2. Task 2: CFRA Analyst Notes Enhancement

### 2.1 PDF Data Structure

"Analyst Research Notes and other Company News" section has **two-column layout**:

```
Analyst Research Notes and other Company News
January 29, 2026                          October 29, 2025
06:05 AM ET... CFRA Maintains Strong Buy  05:30 PM ET... MSFT: Sep-Q Results...
Opinion on Shares of Microsoft            542.07*****):
Corporation (MSFT 449.18*****):           MSFT posted Sep-Q adjusted EPS...
We cut our target to $550 from $620...    ...content...
/ Angelo Zino, CFA                        / Angelo Zino, CFA
```

**Key observations:**
- Two columns merged into single lines by pdfplumber
- Date pattern: `{Month} {DD}, {YYYY}` appears at start of each note pair
- Timestamp: `HH:MM {AM|PM} ET...`
- Action verbs in title: Maintains, Retains, Reiterates, Raises, Upgrades, Lowers, Downgrades, Initiates
- Price: `(TICKER NNN.NN****)` or `(TICKER NNN.NN*****)`
- Signature: `/ {Analyst Name}` or `/ {Analyst Name}, CFA`

### 2.2 Enhanced Dataclass: `CFRAAnalystNote`

Update existing dataclass:

```python
@dataclass
class CFRAAnalystNote:
    """Maps to stock_analyst_notes table."""
    source: str = "CFRA"
    published_at: Optional[str] = None        # "January 29, 2026 06:05 AM"
    analyst_name: Optional[str] = None        # "Angelo Zino, CFA"
    title: Optional[str] = None               # "CFRA Maintains Strong Buy..."
    action: Optional[str] = None              # "maintain" | "upgrade" | ...
    stock_price_at_note: Optional[str] = None # "449.18"
    target_price: Optional[str] = None        # "550" (from "target to $550")
    content: Optional[str] = None             # full note text
```

### 2.3 Parser Method: `_parse_analyst_notes()` Rewrite

**Algorithm:**

```
1. Find "Analyst Research Notes" section start
2. Collect all text until end-of-page boilerplate ("Source:", "Copyright")
3. Split into individual notes using timestamp pattern:
   regex: r'(\d{2}:\d{2}\s+[AP]M\s+ET\.\.\.)'
4. For each note, extract:
   a. published_at: nearest date + timestamp
   b. title: text from "ET..." to first "(" with ticker
   c. action: detect verb in title (Maintains→maintain, Raises→upgrade, etc.)
   d. stock_price_at_note: from "(TICKER NNN.NN***)"
   e. target_price: from "target (?:price )?(?:to |at )?\$([\d.,]+)" in content
   f. analyst_name: from "/ {Name}" at end
   g. content: everything between title and signature
```

**Action Classification:**

```python
ACTION_KEYWORDS = {
    "Maintains": "maintain",
    "Retains": "maintain",
    "Reiterates": "reiterate",
    "Raises": "upgrade",
    "Upgrades": "upgrade",
    "Lowers": "downgrade",
    "Downgrades": "downgrade",
    "Initiates": "initiate",
    "Resumes": "initiate",
}
```

**Two-column handling:**
- Due to pdfplumber merging, each line contains content from both columns
- Use timestamp pattern `\d{2}:\d{2}\s+[AP]M\s+ET\.\.\.` to detect note boundaries
- Each timestamp occurrence is one note (left column notes and right column notes)
- Don't try to separate columns — collect all notes sequentially

### 2.4 Integration Points

| File | Change |
|------|--------|
| `cfra_parser.py` | `CFRAAnalystNote` dataclass: add title, action, target_price, content |
| `cfra_parser.py` | `_parse_analyst_notes()`: full rewrite |

---

## 3. Task 3: CRUD + Service Layer

### 3.1 New Function: `upsert_balance_sheet()`

Add to `app/crud/stock.py`:

```python
def upsert_balance_sheet(session: Session, profile_id: int, data: dict):
    values = {
        "stock_profile_id": profile_id,
        "fiscal_year": data.get("fiscal_year", 0),
        "cash": _to_decimal(data.get("cash")),
        "current_assets": _to_decimal(data.get("current_assets")),
        "total_assets": _to_decimal(data.get("total_assets")),
        "current_liabilities": _to_decimal(data.get("current_liabilities")),
        "long_term_debt": _to_decimal(data.get("long_term_debt")),
        "total_capital": _to_decimal(data.get("total_capital")),
        "capital_expenditures": _to_decimal(data.get("capital_expenditures")),
        "cash_from_operations": _to_decimal(data.get("cash_from_operations")),
        "current_ratio": _to_decimal(data.get("current_ratio")),
        "ltd_to_cap_pct": _to_decimal(data.get("ltd_to_cap_pct")),
        "net_income_to_revenue_pct": _to_decimal(data.get("net_income_to_revenue_pct")),
        "return_on_assets_pct": _to_decimal(data.get("return_on_assets_pct")),
        "return_on_equity_pct": _to_decimal(data.get("return_on_equity_pct")),
    }
    stmt = insert(StockBalanceSheet).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_balance_sheet_profile_year",
        set_={k: v for k, v in values.items()
              if k not in ("stock_profile_id", "fiscal_year")},
    )
    session.execute(stmt)
```

### 3.2 Update: `save_analyst_notes()`

Add missing field mappings to existing function:

```python
def save_analyst_notes(session: Session, profile_id: int, source: str, notes: list[dict]):
    for n in notes:
        published = _to_datetime(n.get("published_at"))
        note = StockAnalystNote(
            stock_profile_id=profile_id,
            source=source,
            published_at=published,
            analyst_name=n.get("analyst_name"),
            title=n.get("title"),                         # NEW
            action=n.get("action"),                       # NEW
            stock_price_at_note=_to_decimal(n.get("stock_price_at_note")),
            target_price=_to_decimal(n.get("target_price")),  # NEW
            content=n.get("content"),                     # NEW
        )
        session.add(note)
    session.flush()
```

### 3.3 Update: `parser_service.py`

Add balance_sheet handling:

```python
# After financials loop, add:

# 8. Upsert balance sheets (CFRA)
bs_count = 0
for bs in data.get("balance_sheets", []):
    if bs.get("fiscal_year"):
        upsert_balance_sheet(session, profile.id, bs)
        bs_count += 1
```

Add `upsert_balance_sheet` to imports. Add `bs_count` to return dict.

---

## 4. Task 4: Test Plan

### 4.1 Parser Unit Test

| Test | Expected |
|------|----------|
| CFRA 6 PDFs: balance_sheets count | 8~10 per PDF |
| CFRA 6 PDFs: balance_sheets[0].cash not None | All pass |
| CFRA 6 PDFs: balance_sheets handles "N/A" | Returns None |
| CFRA 6 PDFs: balance_sheets handles negative | Correct sign |
| CFRA 6 PDFs: analyst_notes count | 4~8 per PDF |
| CFRA 6 PDFs: analyst_notes[0].title not None | All pass |
| CFRA 6 PDFs: analyst_notes[0].action in valid set | All pass |
| Zacks 5 PDFs: no regressions | Revenue/EPS/Peers unchanged |

### 4.2 E2E Pipeline Test

```bash
# Clear DB and re-run
DELETE FROM stock_balance_sheets;
DELETE FROM stock_analyst_notes;

# Re-run parse_and_store for all 11 PDFs
# Verify counts:
#   stock_balance_sheets: ~60 rows (CFRA 6 × 10)
#   stock_analyst_notes:  ~30 rows (CFRA 6 × 5 avg)
```

### 4.3 Regression Checks

- Revenue: 30 per CFRA PDF (unchanged)
- EPS: 30 per CFRA PDF (unchanged)
- Highlights: non-empty for all 6 CFRA PDFs
- Zacks: all fields unchanged

---

## 5. Implementation Order

```
1. cfra_parser.py — CFRABalanceSheet dataclass
2. cfra_parser.py — _parse_balance_sheet() method
3. cfra_parser.py — CFRAAnalystNote fields + _parse_analyst_notes() rewrite
4. cfra_parser.py — parse() + parse_cfra() integration
5. app/crud/stock.py — upsert_balance_sheet()
6. app/crud/stock.py — save_analyst_notes() field update
7. app/services/parser_service.py — balance_sheet pipeline
8. Test: parser unit (6 CFRA + 5 Zacks)
9. Test: E2E pipeline (11 PDFs → DB)
10. Test: DB verification queries
```

---

## 6. File Change Summary

| File | Type | Description |
|------|------|-------------|
| `cfra_parser.py` | Modify | Add `CFRABalanceSheet`, update `CFRAAnalystNote`, add `_parse_balance_sheet()`, rewrite `_parse_analyst_notes()` |
| `app/crud/stock.py` | Modify | Add `upsert_balance_sheet()`, update `save_analyst_notes()` |
| `app/services/parser_service.py` | Modify | Add balance_sheet loop + import |

**Total: 3 files modified, 0 new files**
