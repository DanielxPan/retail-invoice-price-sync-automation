"""Build per-store, per-supplier price update files for the RPA upload bot.

Refactored from ``PriceUpdate_ForAutomation.py``. Joins the day's raw
price list against department and supplier reference tables, applies a
per-supplier price tolerance, and splits the result into one CSV per
store/supplier pair (the format the RPA bot consumes), plus the
reference tables the RPA uses to know which files to process.

.. note::
   ``select_output_columns`` reproduces the original script's column
   selection, which picks columns by *position* rather than by name
   because it runs against a merged dataframe whose column set comes
   from external reference CSVs not included in this repo. If those
   reference CSVs change column order, this will silently pick the
   wrong columns - this is flagged as a known fragility rather than
   guessed at, since the actual reference file schema wasn't available
   to verify a name-based rewrite against.
"""

from __future__ import annotations

import os

import pandas as pd

import logging



from product_price_update_automation.config import PriceUpdateSettings

HIGH_TOLERANCE_SUPPLIERS = ["Supplier1", "Supplier2", "Supplier3", "Supplier4"]
HIGH_TOLERANCE = 10
DEFAULT_TOLERANCE = 0.05



def load_supplier_reference(store_supplier_reference_dir: str) -> pd.DataFrame:
    df = pd.read_csv(
        os.path.join(store_supplier_reference_dir, "Ref_Store_Supplier.csv"),
        low_memory=False,
        encoding="latin-1",
    )
    return df.dropna(subset=["SupplierID"]).rename(columns={"SupplierID": "Supplier"})


def load_price_list(price_files_dir: str, today_str: str) -> pd.DataFrame:
    df = pd.read_excel(os.path.join(price_files_dir, f"{today_str}_PriceUpdate.xlsx"))
    df = df.dropna(how="all")
    keep_cols = [c for c in df.columns if not c.startswith("Unnamed")]
    return df[keep_cols]


def load_department_reference(store_supplier_reference_dir: str) -> pd.DataFrame:
    return pd.read_csv(
        os.path.join(store_supplier_reference_dir, "Ref_Dept_Cd.csv"),
        low_memory=False,
        encoding="latin-1",
    )


def join_price_with_references(
    df_price: pd.DataFrame, df_department: pd.DataFrame, df_suppliers: pd.DataFrame
) -> pd.DataFrame:
    df = pd.merge(df_price, df_department, on="Department", how="left")
    df = pd.merge(df, df_suppliers, on="Supplier", how="left")
    return df


def find_missing_supplier_rows(df_joined: pd.DataFrame) -> pd.DataFrame:
    """Rows whose supplier isn't in the reference table (StoreCode stays blank)."""
    return df_joined[df_joined["StoreCode"].isna()]


def add_default_gl_code(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Default GL Code"] = df.apply(
        lambda row: f"{row['StoreCode']}-5250-{row['DepartmentCode']}"
        if row["Department"] == 301
        else f"{row['StoreCode']}-5000-{row['DepartmentCode']}",
        axis=1,
    )
    return df



def add_price_tolerance(df: pd.DataFrame) -> pd.DataFrame:
    """Suppliers in HIGH_TOLERANCE_SUPPLIERS get a wider acceptable price band."""
    is_high_tolerance = df["Supplier"].isin(HIGH_TOLERANCE_SUPPLIERS)
    df = df.copy()
    df.loc[is_high_tolerance, "Tolerance(+/-)"] = HIGH_TOLERANCE
    df.loc[~is_high_tolerance, "Tolerance(+/-)"] = DEFAULT_TOLERANCE
    return df



def select_output_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Select and rename the columns the RPA upload files need.

    See the module docstring: this selection is positional, matching the
    original script, because it depends on the column order produced by
    external reference CSVs not present in this repo.
    """

    selected = ['Manuf Code'
                , 'Description'
                , 'Default GL Code'
                , 'Cost Excl GST'
                , 'Tolerance(+/-)'
                , 'VENDORID'
                , 'VENDNAME'
                , 'StoreCode'
                , 'Supplier']
    
    df = df[selected].rename(columns={"Manuf Code": "Product Code", "Cost Excl GST": "Current Price"})
    df["Current Price"] = df["Current Price"].round(2)
    df = df[df["Current Price"] >= 0]
    return df.dropna(subset=["Product Code"])



def write_store_supplier_files(df: pd.DataFrame, upload_files_dir: str, today_str: str) -> list[str]:
    """Write one CSV per store/supplier pair into the configured output dir."""
    written_files = []
    for store_code, df_store in df.groupby("StoreCode"):
        logging.info(f"Subset: {store_code}")
        print(f"Subset: {store_code}")
        
        df_store_ref = df_store[["StoreCode", "VENDNAME", "Supplier"]].drop_duplicates()
        
        df_store_ref["FileName"] = today_str + "_" + df_store["StoreCode"] + "_" + df_store["Supplier"] + ".csv"

        file_str_ref = f"{today_str}_{store_code}.csv"
        
        path_str_ref = os.path.join(upload_files_dir, file_str_ref)
        
        df_store_ref.to_csv(path_str_ref, sep=",", index=False, header=True)

        for supplier, df_store_supplier in df_store.groupby("Supplier"):
            
            file = f"{today_str}_{store_code}_{supplier}.csv"
            path = os.path.join(upload_files_dir, file)
            df_store_supplier.to_csv(path, sep=",", index=False, header=True)
            print(f"Save out: {file}")
            logging.info(f"Save out: {file}")
            
            written_files.append(path)
    return written_files



def build_rpa_reference_tables(
    df: pd.DataFrame, store_reference_file: str, upload_files_dir: str, today_str: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the store-selection and store/supplier reference tables the RPA reads."""
    df_store_ref = pd.read_csv(store_reference_file, low_memory=False, encoding="latin-1").dropna()

    ##### Step1: Create store selection files
    df_stores_used = df[["StoreCode"]].drop_duplicates().dropna()
    df_store_selection = pd.merge(df_store_ref, df_stores_used, on="StoreCode", how="inner")
    df_store_selection['StoreFilePathName'] = (
        upload_files_dir + "\\" + today_str + "_" + df_store_selection["StoreCode"] + ".csv")

    ##### Step2: Create Store_Supplier_File
    df_store_supplier = df[["VENDNAME", "StoreCode", "Supplier"]].drop_duplicates()
    df_store_supplier = pd.merge(df_store_ref, df_store_supplier, on="StoreCode", how="inner")
    df_store_supplier["FileName"] = (
        today_str + "_" + df_store_supplier["StoreCode"] + "_" + df_store_supplier["Supplier"]
    )

    return df_store_selection, df_store_supplier



def run(settings: PriceUpdateSettings) -> dict[str, object]:
    """Run the full price-update pipeline and write all output files.

    Returns a summary dict with counts of files written and any missing
    supplier rows found, useful for logging/alerting.
    """
    today_str = str(pd.Timestamp.today().date())

    ##### Step1: configure logging - one log file per day, written to error_files_dir #####
    logging.basicConfig(
        filename=os.path.join(settings.error_message_dir, f"{today_str}_update_prices.log"),
        level=logging.INFO,
        format="%(asctime)s - %(message)s",
        force=True,
    )

    try:
        ##### Step2: load files #####
        df_suppliers = load_supplier_reference(settings.store_supplier_reference_dir)
        df_price = load_price_list(settings.price_files_dir, today_str)
        logging.info(f"Price file loaded: {len(df_price)} rows")
        df_department = load_department_reference(settings.store_supplier_reference_dir)
    
        df_joined = join_price_with_references(df_price, df_department, df_suppliers)
    
        df_missing_suppliers = find_missing_supplier_rows(df_joined)
        logging.info(f"Missing supplier rows: {len(df_missing_suppliers)}")
        df_missing_suppliers.to_csv(
            os.path.join(settings.error_message_dir, f"{today_str}_Missing_Supplier_File.csv"),
            sep=",",
            index=False,
            header=True,
        )
    
    
    
        ##### Step3: join files #####
        df_joined = add_default_gl_code(df_joined)
        df_joined = add_price_tolerance(df_joined)
        df_output = select_output_columns(df_joined)
    
    
    
        ##### Step4: write files #####
        written_files = write_store_supplier_files(df_output, settings.upload_files_dir, today_str)
        logging.info(f"Total files written: {len(written_files)}")
    
    
        ##### Step5: write reference tables for RPA #####
        df_store_selection, df_store_supplier = build_rpa_reference_tables(
            df_output
            , os.path.join(settings.store_supplier_reference_dir, "Ref_StoreNameCode.csv")
            , settings.upload_files_dir
            , today_str
        )
        
        df_store_selection.to_csv(
            os.path.join(settings.upload_files_dir, f"{today_str}_0_Store_Selection_File.csv"),
            sep=",",
            index=False,
            header=True,
        )
        
        df_store_supplier.to_csv(
            os.path.join(settings.upload_files_dir, f"{today_str}_0_Store_Supplier_File.csv"),
            sep=",",
            index=False,
            header=True,
        )
    
        return {
            "files_written": len(written_files),
            "missing_supplier_rows": len(df_missing_suppliers),
        }
    
    except Exception:
        logging.exception("update_prices.py failed")
        raise
        
        
        
        
