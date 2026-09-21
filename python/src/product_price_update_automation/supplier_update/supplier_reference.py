"""Keep the store/supplier reference table in sync with the accounting
system's vendor list: add newly-active suppliers, remove deactivated ones.

Refactored from ``Update_StoreSupplierReferenceTable.py``. Runs weekly
against the last 7 days of vendor changes. Uses ``pd.concat`` in place
of the original's ``DataFrame.append`` (removed in modern pandas).

A store-supplier relationship only enters the reference table once it has
a SupplierID. That ID comes from one of two places:
  - it already exists elsewhere in the reference table (another store
    already buys from this supplier), or
  - the business team manually filled it into last week's "not matched"
    report, for a supplier that was new to the whole company.
Either way, the week the relationship is established is the week it needs
an initial load job, so both paths feed the New Suppliers export.
"""

from __future__ import annotations

import os

import pandas as pd

from product_price_update_automation.config import SupplierUpdateSettings

ACTIVE_GROUPS = {"INV", "MET"}

##### The reference table and the not-matched report share this column set #####
REFERENCE_COLUMNS = [
    "VENDORID",
    "VENDNAME",
    "StoreCode",
    "VENDORID(4Digits)",
    "SupplierID",
    "DATE_LAST_Update",
]


def load_vendor_export(supplier_list_from_sage_dir: str, today_str: str) -> pd.DataFrame:
    """Load the day's vendor list export from the accounting system."""
    path = os.path.join(supplier_list_from_sage_dir,  f"{today_str}_AccountingSystem_Supplier_List.xlsx")
    df = pd.read_excel(path)
    df = df[["VENDORID", "VENDNAME", "IDGRP", "SWACTV", "DATELASTMN", "DATELASTIV"]].copy()
    df["DATELASTMN"] = df["DATELASTMN"].dt.date
    df["DATELASTIV"] = df["DATELASTIV"].dt.date
    df["StoreCode"] = df["IDGRP"].str[:3]
    df["GRP"] = df["IDGRP"].str[3:]
    return df


def load_active_store_codes(store_supplier_reference_dir: str) -> list[str]:
    df_store = pd.read_csv(
        os.path.join(store_supplier_reference_dir, "Ref_StoreNameCode.csv"), low_memory=False, encoding="latin-1"
    )
    return df_store["StoreCode"].unique().tolist()



def load_current_supplier_reference(store_supplier_reference_dir: str) -> pd.DataFrame:
    return pd.read_csv(
        os.path.join(store_supplier_reference_dir, "Ref_Store_Supplier.csv"),
        low_memory=False,
        encoding="latin-1",
    ).dropna(subset=["VENDORID"])



def load_last_week_not_matched(missing_supplier_list_dir: str, last_week_date: str) -> pd.DataFrame:
    """Load last week's not-matched report with all its columns intact.

    Returns an empty frame with the right columns if the file doesn't exist,
    so a missing prior week doesn't crash the run.
    """
    path = os.path.join(missing_supplier_list_dir, f"{last_week_date}_Supplier_NotMatched.csv")
    if not os.path.exists(path):
        return pd.DataFrame(columns=REFERENCE_COLUMNS)
    return pd.read_csv(path, low_memory=False, encoding="latin-1")



def split_last_week_by_supplier_id(df_last_week: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split last week's not-matched rows into ones the business team has
    since filled in, and ones still waiting for a SupplierID."""
    has_id = df_last_week["SupplierID"].notna()
    df_filled = df_last_week[has_id].copy()
    df_still_missing = df_last_week[~has_id].copy()
    return df_filled, df_still_missing



def classify_new_and_inactive_suppliers(
    df_vendors: pd.DataFrame, df_current_ref: pd.DataFrame, today, active_store_codes: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split the vendor export into newly-added and newly-inactive suppliers."""
    df_vendors = df_vendors[df_vendors["StoreCode"].isin(active_store_codes)]

    ##### Step: DATELASTMN/DATELASTIV are plain datetime.date (see load_vendor_export's #####
    ##### .dt.date conversion) - convert these Timestamp thresholds down to .date() too, #####
    ##### otherwise pandas raises TypeError comparing Timestamp against datetime.date.   #####
    today_date = today.date()
    last_week = (today - pd.Timedelta(days=7)).date()
    last_year = (today - pd.Timedelta(days=365)).date()

    is_recently_modified = (df_vendors["DATELASTMN"] > last_week) & (df_vendors["DATELASTMN"] <= today_date)
    known_vendor_ids = df_current_ref["VENDORID"].unique().tolist()
    is_not_already_known = ~df_vendors["VENDORID"].isin(known_vendor_ids)
    is_relevant_group = df_vendors["GRP"].isin(ACTIVE_GROUPS)
    is_active = df_vendors["SWACTV"] == 1
    is_inactive = df_vendors["SWACTV"] == 0
    has_recent_or_no_invoice = df_vendors["DATELASTIV"].isna() | (df_vendors["DATELASTIV"] >= last_year)

    df_new = df_vendors[
        is_recently_modified & is_not_already_known & is_relevant_group & is_active & has_recent_or_no_invoice
    ]
    df_inactive = df_vendors[is_inactive]
    return df_new, df_inactive



def remove_inactive_suppliers(df_current_ref: pd.DataFrame, df_inactive: pd.DataFrame) -> pd.DataFrame:
    inactive_ids = df_inactive["VENDORID"].unique().tolist()
    return df_current_ref[~df_current_ref["VENDORID"].isin(inactive_ids)]



def build_supplier_id_lookup(df_current_ref: pd.DataFrame) -> pd.DataFrame:
    """Build a VENDORID(4Digits) -> SupplierID lookup from the reference table.

    A supplier already used by any store gives its SupplierID to the same
    supplier at a new store.
    """
    return df_current_ref[["VENDORID(4Digits)", "SupplierID"]].drop_duplicates().dropna()



def match_new_suppliers(
    df_new: pd.DataFrame, lookup: pd.DataFrame, today_str: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Attach a SupplierID to this week's new vendors where one already exists.

    Returns (matched, unmatched): matched rows are ready for the reference
    table, unmatched rows are new to the whole company and need a manual
    SupplierID before they can be added.
    """
    df_new = df_new.copy()
    df_new["VENDORID(4Digits)"] = df_new["VENDORID"].str[3:]
    df_new = pd.merge(df_new, lookup, on="VENDORID(4Digits)", how="left")

    ##### Step: DATE_LAST_Update records the day a relationship was established #####
    df_new["DATE_LAST_Update"] = today_str

    has_id = df_new["SupplierID"].notna()
    df_matched = df_new[has_id][REFERENCE_COLUMNS].copy()

    ##### Step: unmatched rows carry no date yet - they aren't established until #####
    ##### someone fills in a SupplierID, which happens in a later week           #####
    df_unmatched = df_new[~has_id][REFERENCE_COLUMNS].copy()
    df_unmatched["DATE_LAST_Update"] = pd.NA

    return df_matched, df_unmatched



def run(settings: SupplierUpdateSettings) -> dict[str, str]:
    """Run the weekly supplier reference sync and write the updated files."""
    today = pd.Timestamp.today().normalize()
    today_str = str(today.date())
    last_week_date = str((today - pd.Timedelta(days=7)).date())

    active_store_codes = load_active_store_codes(settings.store_supplier_reference_dir)
    df_vendors = load_vendor_export(settings.supplier_list_from_sage_dir, today_str)
    df_current_ref = load_current_supplier_reference(settings.store_supplier_reference_dir)

    ##### Step1: drop deactivated suppliers from the reference table #####
    df_new_vendors, df_inactive = classify_new_and_inactive_suppliers(
        df_vendors, df_current_ref, today, active_store_codes
    )
    df_current_active = remove_inactive_suppliers(df_current_ref, df_inactive)



    ##### Step2: last week's not-matched rows - some now have a manually assigned ID #####
    df_last_week = load_last_week_not_matched(settings.missing_supplier_list_dir, last_week_date)
    df_last_week_filled, df_last_week_still_missing = split_last_week_by_supplier_id(df_last_week)
    df_last_week_filled["DATE_LAST_Update"] = today_str



    ##### Step3: this week's new vendors - matched ones inherit an existing SupplierID #####
    lookup = build_supplier_id_lookup(df_current_active)
    df_matched, df_unmatched = match_new_suppliers(df_new_vendors, lookup, today_str)



    ##### Step4: both newly-established paths go into the reference table and need an initial load #####
    df_newly_established = pd.concat(
        [df_matched, df_last_week_filled[REFERENCE_COLUMNS]], ignore_index=True
    )
    
    df_updated_ref = pd.concat([df_current_active, df_newly_established], ignore_index=True)


    ##### Step5: still-unmatched rows roll forward until someone assigns a SupplierID #####
    df_missing = pd.concat(
        [df_unmatched, df_last_week_still_missing[REFERENCE_COLUMNS]], ignore_index=True
    ).drop_duplicates(subset=["VENDORID"])



    ##### Step6: Assign file paths #####
    missing_path = os.path.join(
        settings.missing_supplier_list_dir, f"{today_str}_Supplier_NotMatched.csv"
    )
    
    new_suppliers_path = os.path.join(
        settings.new_supplier_list_dir, f"{today_str}_New_Suppliers.csv"
    )
    
    reference_path = os.path.join(settings.store_supplier_reference_dir, "Ref_Store_Supplier.csv")



    ##### Step7: Save out reulst #####
    df_missing.to_csv(missing_path, sep=",", index=False, header=True)
    df_newly_established.to_csv(new_suppliers_path, sep=",", index=False, header=True)
    df_updated_ref.to_csv(reference_path, sep=",", index=False, header=True)

    return {
        "missing_suppliers_file": missing_path,
        "new_suppliers_file": new_suppliers_path,
        "reference_table": reference_path,
    }