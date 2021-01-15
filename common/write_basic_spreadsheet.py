from pathlib import Path
from typing import List

import pandas as pd

from utilities_excel import excel_columns, make_sheet_banded, add_workbook_formats, Xlformat


def write_basic_spreadsheet(df: pd.DataFrame,
                            fpath: Path,
                            column_widths: dict,
                            columns_to_center: List[str]):
    if df.empty:
        return None
    df = df.fillna('')

    default_column_width = 14  # if not specified in column_widths
    xsheet_name = 'Basic'

    with pd.ExcelWriter(fpath.as_posix(), engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=xsheet_name)

        # Get the xlsxwriter workbook and worksheet objects.
        workbook = writer.book
        worksheet = writer.sheets[xsheet_name]
        xlfmts = add_workbook_formats(workbook)

        # https://stackoverflow.com/questions/43991505/xlsxwriter-set-global-font-size
        workbook.formats[0].set_font_size(14)  # to make it readable when printed

        # ----------------------------------------------
        # Populate col_infos with formatting information
        col_infos = {}

        excel_letters = excel_columns()
        for ix, col in enumerate(df.columns):
            col_letter = excel_letters[ix]
            col_info = {}
            fmt = xlfmts[Xlformat.CENTER] if (
                        columns_to_center is not None and col in columns_to_center) else None
            col_info['format'] = fmt
            col_info['width'] = column_widths.get(col, default_column_width)
            col_info['xl_col_letter'] = f'{col_letter}'
            col_infos[col] = col_info

        colspec = pd.DataFrame(col_infos).T

        # Set the column widths and format.
        # Set formats with e.g. 'C:C'
        for col_num, col_info in colspec.iterrows():
            xl_col_letter = col_info['xl_col_letter']
            wid = col_info['width']
            fmt = col_info['format']
            worksheet.set_column(f'{xl_col_letter}:{xl_col_letter}', wid, fmt)

        # Make the sheet banded
        make_sheet_banded(worksheet, df)

        worksheet.freeze_panes(1, 0)  # Freeze the first row.

        # Write the column headers with the defined format.
        for col, col_info in colspec.iterrows():
            col_num = list(colspec.index).index(col)
            worksheet.write(0, col_num, col, xlfmts[Xlformat.HEADER])
