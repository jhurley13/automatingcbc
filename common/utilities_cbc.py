# acbc_utilities

import re
from pathlib import Path

import pandas as pd

# https://stackoverflow.com/questions/60288732/pandas-read-excel-returns-pendingdeprecationwarning

CSV_EXTENSIONS = ['.csv', '.CSV']
EXCEL_EXTENSIONS = ['.xlsx', '.XLSX']
LEGACY_EXCEL_EXTENSIONS = ['.xls', '.XLS']

def read_excel_or_csv(fdir: Path, name_base: str, xheader=0) -> pd.DataFrame:
    # Prefer Excel over CSV under the assumption that Excel file is a richer format
    # For convenience, we assume that first row is a header
    result = pd.DataFrame()

    extensions_to_try = EXCEL_EXTENSIONS + CSV_EXTENSIONS
    for ext in extensions_to_try:
        fpath = fdir / f'{name_base}{ext}'
        try:
            if fpath.exists():
                if ext in EXCEL_EXTENSIONS:
                    result = pd.read_excel(fpath, header=xheader, engine="openpyxl").fillna('')
                elif ext in CSV_EXTENSIONS:
                    result = pd.read_csv(fpath, dtype=str, header=xheader,
                                         low_memory=False).fillna('')
                return result

        except Exception as ee:
            print(fpath, name_base, ee)
            raise

    return result


def read_excel_or_csv_path(fpath: Path, xheader=0) -> pd.DataFrame:
    # Prefer Excel over CSV under the assumption that Excel file is a richer format
    # For convenience, we assume that first row is a header
    result = pd.DataFrame()

    try:
        if fpath.exists():
            if (fpath.suffix in EXCEL_EXTENSIONS):
                result = pd.read_excel(fpath, header=xheader, engine="openpyxl").fillna('')
            elif (fpath.suffix in LEGACY_EXCEL_EXTENSIONS):
                result = pd.read_excel(fpath, header=xheader, engine="xlrd").fillna('')
            elif (fpath.suffix in CSV_EXTENSIONS):
                result = pd.read_csv(fpath, dtype=str, header=xheader, low_memory=False).fillna('')

    except Exception as ee:
        print(fpath, ee)
        raise

    return result


# https://stackoverflow.com/questions/28419877/check-whether-non-index-column-sorted-in-pandas
def is_df_sorted(df, colname):
    return pd.Index(df[colname]).is_monotonic


def circle_abbrev_from_path(fpath: Path) -> str:
    circle_abbrev = "XXXX"
    mm = re.search(r'([A-Z]{4})-*([0-9]*)', fpath.stem)
    if mm:
        circle_abbrev = f'{mm.group(1)}-{mm.group(2)}'

    return circle_abbrev


def debug_write_raw_text(text: str, fpath: Path, out_path: Path):
    abbrev = circle_abbrev_from_path(fpath)
    fout = out_path / f'{abbrev}-{fpath.suffix[1:]}-raw.txt'
    with open(fout, 'w', encoding="utf-8") as fp:
        _ = fp.write(text)
