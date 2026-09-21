import datetime

from product_price_update_automation.price_update.cleanup_old_files import delete_files_in_date_range


def test_deletes_only_files_within_date_range(tmp_path):
    today = datetime.date(2025, 6, 15)
    start_date = today - datetime.timedelta(days=60)
    end_date = today - datetime.timedelta(days=30)

    too_new = tmp_path / "2025-06-01_report.csv"
    in_range = tmp_path / "2025-05-01_report.csv"
    too_old = tmp_path / "2025-03-01_report.csv"
    no_date = tmp_path / "readme.txt"
    for f in (too_new, in_range, too_old, no_date):
        f.write_text("data")

    deleted = delete_files_in_date_range(str(tmp_path), start_date, end_date)

    assert deleted == ["2025-05-01_report.csv"]
    assert too_new.exists()
    assert not in_range.exists()
    assert too_old.exists()
    assert no_date.exists()
