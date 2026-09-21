"""CLI entry point: detect price rows that failed RPA upload in the last 7 days."""

from product_price_update_automation.config import ProductSettings
from product_price_update_automation.price_update.detect_failed_upload import run

if __name__ == "__main__":
    output_path = run(ProductSettings())
    print(f"Failed-upload report written to: {output_path}")
