import pandas as pd

from product_price_update_automation.price_update.detect_failed_upload import find_genuine_failures

COLUMNS = [
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


def _row(store, product, status, reason="", price=1.0):
    return {
        "StoreCodes": store,
        "VENDORID": "V1",
        "VENDNAME": "Vendor",
        "Supplier": "SUP",
        "Product Code": product,
        "Current Price": price,
        "Success/Fail": status,
        "Reason": reason,
        "FileName": "file.csv",
    }


def test_failure_that_never_succeeded_is_reported():
    df = pd.DataFrame([_row("ST1", "P1", "Fail", reason="timeout")], columns=COLUMNS)

    result = find_genuine_failures(df)

    assert len(result) == 1
    assert result.iloc[0]["Product Code"] == "P1"


def test_failure_that_later_succeeded_is_dropped():
    df = pd.DataFrame(
        [
            _row("ST1", "P1", "Fail", reason="timeout"),
            _row("ST1", "P1", "Success"),
        ],
        columns=COLUMNS,
    )

    result = find_genuine_failures(df)

    assert result.empty
