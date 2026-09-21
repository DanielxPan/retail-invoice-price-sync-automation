"""Delete stale automation output files (30-60 days old) from shared folders.

Refactored from ``PriceUpdate_DeleteFiles_OverPast30Days.py``. Files are
named with a leading ``YYYY-MM-DD_`` date, which is what determines
eligibility for deletion - anything newer than 30 days is kept as a
recent audit trail, anything older than 60 days is assumed already
cleaned up by a previous run.
"""

from __future__ import annotations

import datetime
import os

from product_price_update_automation.config import ProductSettings


def delete_files_in_date_range(
    folder_path: str, start_date: datetime.date, end_date: datetime.date
) -> list[str]:
    """Delete files in ``folder_path`` whose leading date falls in range.

    Returns the list of deleted filenames. Files without a parseable
    leading date are left alone.
    """
    deleted = []
    for file_name in os.listdir(folder_path):
        date_str = file_name.split("_")[0]
        try:
            file_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        if start_date <= file_date <= end_date:
            os.remove(os.path.join(folder_path, file_name))
            deleted.append(file_name)
    return deleted


def run(settings: ProductSettings) -> dict[str, list[str]]:
    """Clean up all configured folders and return {folder: deleted_files}."""
    today = datetime.date.today()
    end_date = today - datetime.timedelta(days=30)
    start_date = today - datetime.timedelta(days=60)

    return {
        folder: delete_files_in_date_range(folder, start_date, end_date)
        for folder in settings.old_file_cleanup_dirs
    }
