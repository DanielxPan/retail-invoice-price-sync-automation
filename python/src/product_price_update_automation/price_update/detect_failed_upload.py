"""Detect which price-update rows failed to upload via RPA.

Refactored from ``PriceUpdate_DetectFailedUploadResult.py``. The RPA
writes one result CSV per store/supplier file with a Success/Fail
column; this scans the last 7 days of results, and for each failed row
checks whether the *same* store/supplier/product later succeeded
(e.g. on a retry) before reporting it as a genuine failure.
"""

from __future__ import annotations

import datetime
import os

import pandas as pd

from product_price_update_automation.config import ProductSettings

RESULT_COLUMNS = [
    "StoreCodes",
    "VENDORID",
    "VENDNAME",
    "Supplier",
    "Product Code",
    "Current Price",
    "Success/Fail",
    "Reason",
    "FileName",
]

JOIN_KEYS = ["StoreCodes", "Supplier", "Product Code"]


def load_recent_upload_results(results_dir: str, lookback_days: int = 7) -> pd.DataFrame:
    """Load and concatenate every RPA result CSV from the last ``lookback_days``."""
    today = datetime.date.today()
    recent_dates = {
        (today - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(1, lookback_days + 1)
    }

    frames = []
    for file_name in os.listdir(results_dir):
        if any(file_name.startswith(date_str) for date_str in recent_dates):
            df = pd.read_csv(os.path.join(results_dir, file_name))
            df["FileName"] = file_name
            frames.append(df)

    if not frames:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    return pd.concat(frames, ignore_index=True).drop_duplicates()


def find_genuine_failures(df_results: pd.DataFrame) -> pd.DataFrame:
    """Return failed rows that never later succeeded for the same product."""
    is_failed = df_results["Success/Fail"] == "Fail"
    df_failed = df_results[is_failed][RESULT_COLUMNS].drop_duplicates()
    df_succeeded = df_results[~is_failed]

    df_joined = pd.merge(
        df_failed,
        df_succeeded,
        how="left",
        on=JOIN_KEYS,
        indicator=True,
        suffixes=("_failed", "_success"),
    )
    df_genuine = df_joined[df_joined["_merge"] == "left_only"]

    failed_columns = [f"{col}_failed" if col not in JOIN_KEYS else col for col in RESULT_COLUMNS]
    return df_genuine[failed_columns].drop_duplicates()


def run(settings: ProductSettings) -> str:
    """Run detection and write the failed-upload report to CSV."""
    df_results = load_recent_upload_results(settings.upload_results_dir)
    df_failed = find_genuine_failures(df_results)

    today_str = str(datetime.date.today())
    output_path = os.path.join(
        settings.error_files_dir, f"{today_str}_Upload_Failed_Store_Supplier_File.csv"
    )
    df_failed.to_csv(output_path, sep=",", index=False, header=True)
    return output_path
