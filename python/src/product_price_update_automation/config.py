"""Settings, loaded from environment variables (see .env.example).

Every path that used to be hardcoded in the original scripts lives here
instead, so the same code runs on any machine by just supplying a
`.env` file - no source edits required.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value



########## Step 4: Root folder differs per machine, loaded from .env ##########
DATA_ROOT = _env("DATA_ROOT")



########## Step 5: Folder structure below DATA_ROOT is identical across machines - hardcoded here ##########

# Supplier Update (weekly) - identifies valid/new/unrecognized suppliers from the accounting system export
DIR_SUPPLIER_LIST_FROM_SAGE = os.path.join(
    DATA_ROOT, "invoice-system", "01.Supplier_Update", "01.SupplierList_From_AccountingSystem"
)
DIR_NEW_SUPPLIER_LIST = os.path.join(
    DATA_ROOT, "invoice-system", "01.Supplier_Update", "02.New_Supplier_List"
)
DIR_MISSING_SUPPLIER_LIST = os.path.join(
    DATA_ROOT, "invoice-system", "01.Supplier_Update", "03.Missing_Supplier_List"
)

# Store-Supplier reference table - shared between Supplier Update (writes/overwrites it)
# and Price Update (reads it) - one folder, two consumers.
DIR_STORE_SUPPLIER_REFERENCE = os.path.join(
    DATA_ROOT, "invoice-system", "02.Price_Update", "01.Reference_Table"
)

# Price Update (daily) - joins today's price files with the reference table,
# produces the upload file and an error log for RPA to write back into.
DIR_PRICE_FILES = os.path.join(
    DATA_ROOT, "invoice-system", "02.Price_Update", "02.Price_Files"
)
DIR_PRICE_UPLOAD_FILES = os.path.join(
    DATA_ROOT, "invoice-system", "02.Price_Update", "03.Upload_Files"
)
DIR_PRICE_ERROR_MESSAGE = os.path.join(
    DATA_ROOT, "invoice-system", "02.Price_Update", "04.Error_Message"
)



########## Step 6: One settings dataclass per program - each gets exactly what it needs ##########

@dataclass(frozen=True)
class SupplierUpdateSettings:
    """Settings for supplier_reference.py (runs weekly)."""

    supplier_list_from_sage_dir: str = field(default_factory=lambda: DIR_SUPPLIER_LIST_FROM_SAGE)
    new_supplier_list_dir: str = field(default_factory=lambda: DIR_NEW_SUPPLIER_LIST)
    missing_supplier_list_dir: str = field(default_factory=lambda: DIR_MISSING_SUPPLIER_LIST)
    store_supplier_reference_dir: str = field(default_factory=lambda: DIR_STORE_SUPPLIER_REFERENCE)


@dataclass(frozen=True)
class PriceUpdateSettings:
    """Settings for update_prices.py (runs daily)."""

    store_supplier_reference_dir: str = field(default_factory=lambda: DIR_STORE_SUPPLIER_REFERENCE)
    price_files_dir: str = field(default_factory=lambda: DIR_PRICE_FILES)
    upload_files_dir: str = field(default_factory=lambda: DIR_PRICE_UPLOAD_FILES)
    error_message_dir: str = field(default_factory=lambda: DIR_PRICE_ERROR_MESSAGE)
    
