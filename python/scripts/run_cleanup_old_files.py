"""CLI entry point: delete price-update output files older than 30-60 days."""

from product_price_update_automation.config import ProductSettings
from product_price_update_automation.price_update.cleanup_old_files import run

if __name__ == "__main__":
    deleted = run(ProductSettings())
    for folder, files in deleted.items():
        print(f"{folder}: deleted {len(files)} file(s)")
