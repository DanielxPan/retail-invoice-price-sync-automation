"""CLI entry point: sync the store/supplier reference table with the accounting system."""

from product_price_update_automation.config import SupplierUpdateSettings
from product_price_update_automation.supplier_update.supplier_reference import run

if __name__ == "__main__":
    result = run(SupplierUpdateSettings())
    for label, path in result.items():
        print(f"{label}: {path}")
