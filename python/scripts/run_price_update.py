"""CLI entry point: build per-store/supplier price update files for RPA upload."""


from product_price_update_automation.config import PriceUpdateSettings
from product_price_update_automation.price_update.update_prices import run



if __name__ == "__main__":
    summary = run(PriceUpdateSettings())
    print(f"Price update complete: {summary}")
