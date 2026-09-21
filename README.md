# Product Price Update Automation

> This is a de-identified portfolio version of an automation I built and
> ran for a real multi-site retail business. Employer, coworker, and
> internal system/infrastructure names have been replaced with generic
> placeholders; the code and architecture are unchanged.

Keeps store-supplier relationships and daily prices in sync between the
accounting system, the price update spreadsheet, and the RPA bot
that uploads the results into Invoice Platform.

This repo contains two parts:

```
python/   Python package + entry-point scripts (Supplier Update, Price Update)
rpa/      UiPath Studio project that uploads the files Python produces
```

## Setup

```
cd python
pip install -e ".[dev]"
cp .env.example .env   # then fill in DATA_ROOT for this machine
```

Everything below `DATA_ROOT` is hardcoded in `config.py` since the folder
structure is identical across machines — only `DATA_ROOT` itself changes
per machine.

---

## Python — Supplier Update (weekly)

Keeps the store-supplier reference table in sync with the Accounting System's vendor
list. A store-supplier relationship only enters the reference table once
it has a `SupplierID` — either because another store already buys from
that supplier, or because the business team manually assigns one for a
supplier that's new to the whole company. Either path needs an initial
load job, so both feed the New Suppliers export. Unmatched rows roll
forward to next week's list instead of disappearing.

```mermaid
flowchart TD
    A[Load Accounting System export] --> D[classify_new_and_inactive_suppliers]
    B[Load current reference table] --> D
    B --> F[build_supplier_id_lookup]
    C[Load last week's not-matched file] --> K[split_last_week_by_supplier_id]

    D --> E[remove_inactive_suppliers]
    E --> F

    D --> G[match_new_suppliers]
    F --> G
    G --> H{SupplierID already<br/>known?}
    H -->|Yes| I[Matched: ready to add]
    H -->|No| J[Unmatched: new to the company]

    K --> L{SupplierID filled in<br/>by the business team?}
    L -->|Yes| M[Filled: ready to add]
    L -->|No| N[Still missing: carries forward]

    I --> O[Combine: newly established]
    M --> O
    O --> P[("New_Suppliers.csv<br/>for initial load job")]

    E --> Q[Combine: updated reference table]
    O --> Q
    Q --> R[("Ref_Store_Supplier.csv")]

    J --> S[Combine: still missing]
    N --> S
    S --> T[("Supplier_NotMatched.csv<br/>rolls forward next week")]
```

Entry point: `python/scripts/run_supplier_reference_update.py`
Logic: `python/src/product_price_update_automation/supplier_update/supplier_reference.py`

---

## Python — Price Update (daily)

Joins the day's price file against the supplier and department reference
tables, flags rows whose supplier isn't recognised, applies GL codes and
price tolerance bands, then writes one upload CSV per store/supplier
pair plus the reference files the RPA needs.

```mermaid
flowchart TD
    A[Load supplier reference] --> D[join_price_with_references]
    B[Load today's price list] --> D
    C[Load department reference] --> D

    D --> E[find_missing_supplier_rows]
    E --> F[("Missing_Supplier_File.csv")]

    D --> G[add_default_gl_code]
    G --> H[add_price_tolerance]
    H --> I[select_output_columns]

    I --> J[write_store_supplier_files]
    J --> K[("One CSV per store/supplier pair")]

    I --> L[build_rpa_reference_tables]
    L --> M[("Store_Selection_File.csv")]
    L --> N[("Store_Supplier_File.csv")]
```

Entry point: `python/scripts/run_price_update.py`
Logic: `python/src/product_price_update_automation/price_update/update_prices.py`

---

## RPA — Price Upload (UiPath)

Reads the two reference files Price Update produces, then for every
store and every supplier within it, uploads that day's price file into
Invoice Platform. Each supplier upload is wrapped in its own Try/Catch so one
failure doesn't stop the rest of the run — failures are logged to a
table instead and included in the summary email.

```mermaid
flowchart TD
    A[Read Store Selection File] --> B[For each store]
    B --> C[Open store in Invoice Platform]
    C --> D[Read Store Supplier File for this store]
    D --> E[For each supplier]

    E --> F[Search &amp; select supplier]
    F --> G[Open Products tab]
    G --> H[Check upload box, confirm]
    H --> I[Choose template, confirm]
    I --> J{Any step failed?}

    J -->|No| K[Next supplier]
    J -->|Yes, exception| L[Log store, supplier,<br/>error message to table]

    K --> E
    L --> E

    E -->|all suppliers done| M[Refresh page]
    M --> B

    B -->|all stores done| N[("Write error log CSV")]
    N --> O[("Email summary + 3 files<br/>to the team")]
```

Entry point: `rpa/price-update-cross-stores/Main.xaml`
Logic: `rpa/price-update-cross-stores/UpdateProductList_TryCatch.xaml`

---

## Running (Python)

```python
from product_price_update_automation.config import SupplierUpdateSettings, PriceUpdateSettings
from product_price_update_automation.supplier_update.supplier_reference import run as run_supplier_update
from product_price_update_automation.price_update.update_prices import run as run_price_update

run_supplier_update(SupplierUpdateSettings())
run_price_update(PriceUpdateSettings())
```

Both are scheduled independently via Windows Task Scheduler (weekly and
daily respectively) — see each script's docstring for the exact command
line used. The RPA project is triggered separately once Price Update's
output files land in the shared upload folder.
