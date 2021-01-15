import string
from pathlib import Path
from typing import List

import pandas as pd
import webcolors
from utilities_excel import make_sheet_banded, add_workbook_formats, Xlformat

"""
Write out categorized_lines Excel file. This is used to debug the translations.
note: trying to write this code so it can be used for a generic debug Excel file.

Columns: Line	Translation	Translated	Category

write_categorized_lines_spreadsheet(categorized_lines, 
    debug_path / 'categorized_lines.xlsx',
    col_widths = [40, 40, 11, 16],
    col_align = ['left', 'left', 'center', 'center'],
    sheet_name = 'Categorized Lines',
    )
"""


def write_categorized_lines_spreadsheet(df: pd.DataFrame, output_path: Path,
                                        col_widths: List[int],
                                        col_align: List[str],
                                        sheet_name: str
                                        ):
    if df.empty:
        return None

    sheet_names = banded_sheets = [sheet_name]

    with pd.ExcelWriter(output_path.as_posix(), engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)

        # Get the xlsxwriter workbook and worksheet objects.
        workbook = writer.book
        xlfmts = add_workbook_formats(workbook)

        for sheet_num, sheet_name in enumerate(sheet_names):
            worksheet = writer.sheets[sheet_name]

            # Set the column width and format.
            col_vals = df.columns.values
            row_count = df.shape[0]

            for ix, wid in enumerate(col_widths):
                col_letter = string.ascii_uppercase[ix]
                fmt = xlfmts[Xlformat.CENTER] if col_align[ix] == 'center' else None
                worksheet.set_column(f'{col_letter}:{col_letter}', wid, fmt)

            if sheet_name in banded_sheets:
                make_sheet_banded(worksheet, df)

            # ---------- Specific to categorized_lines ----------
            colorize_category_column(df, workbook, worksheet)

            # Write the column headers with the defined format.
            for col_num, value in enumerate(col_vals):
                worksheet.write(0, col_num, value, xlfmts[Xlformat.HEADER])



def ent_name_to_color(ent_name):
    # Excel doesn't process linear-gradient colors
    # "R" suffix is for reverse
    # purplish = 'linear-gradient(90deg, #aa9cfc, #fc9ce7)'  # original
    # purplishR = 'linear-gradient(45deg, #fc9ce7, #aa9cfc)'
    # yellowish = 'linear-gradient(90deg, #f9fc9c, #fac945)'
    # greenish = 'linear-gradient(90deg, #cdfc9c, #5cfa45)'
    # aquaish = 'linear-gradient(90deg, #9cfcea, #3cd3e7)'
    # aquaishR = 'linear-gradient(45deg, #3cd3e7, #9cfcea)'
    # fuchsiaish = 'linear-gradient(90deg, #fc9cde, #ff5aa4)'
    purplish = '#aa9cfc'  # original
    yellowish = '#f9fc9c'
    greenish = '#cdfc9c'
    aquaish = '#9cfcea'
    fuchsiaish = '#fc9cde'

    if ent_name.startswith('COM'):
        return purplish

    if ent_name.startswith('SCI'):
        return aquaish

    if ent_name.startswith('ORD'):
        return greenish

    if ent_name.startswith('FAMCOM'):
        return yellowish

    if ent_name.startswith('FAMSCI'):
        return fuchsiaish

    return webcolors.name_to_hex('HotPink'.lower())


def colorize_category_column(df, workbook, worksheet):
    ent_names = [
        'COMDOMESTIC', 'COMFORM', 'COMHYBRID', 'COMINTERGRADE', 'COMISSF', 'COMSLASH',
        'COMSPECIES', 'COMSPUH', 'FAMCOMDOMESTIC', 'FAMCOMFORM', 'FAMCOMHYBRID',
        'FAMCOMINTERGRADE', 'FAMCOMISSF', 'FAMCOMSLASH', 'FAMCOMSPECIES', 'FAMCOMSPUH',
        'FAMSCIDOMESTIC', 'FAMSCIFORM', 'FAMSCIHYBRID', 'FAMSCIINTERGRADE',
        'FAMSCIISSF', 'FAMSCISLASH', 'FAMSCISPECIES', 'FAMSCISPUH', 'ORDDOMESTIC',
        'ORDFORM', 'ORDHYBRID', 'ORDINTERGRADE', 'ORDISSF', 'ORDSLASH', 'ORDSPECIES'
                                                                        'ORDSPUH', 'SCIDOMESTIC',
        'SCIFORM', 'SCIHYBRID', 'SCIINTERGRADE', 'SCIISSF',
        'SCISLASH', 'SCISPECIES', 'SCISPUH',
    ]

    xl_last_data_row = df.shape[0] + 1  # plus 1 is because data starts at row 2

    category_idx = list(df.columns).index('Category')
    letter = string.ascii_uppercase[category_idx]
    category_cells = f'{letter}2:{letter}{xl_last_data_row}'

    for ent_name in ent_names:
        # Could update to a "startswith" criteria; see ent_name_to_color
        category_criteria = f'=EXACT({category_cells},"{ent_name}")'
        # print(category_criteria)
        category_color = ent_name_to_color(ent_name)
        category_format = workbook.add_format(
            {'bg_color': category_color})  # , 'font_color': '#006100'

        worksheet.conditional_format(category_cells,
                                     {'type': 'formula',
                                      'criteria': category_criteria,
                                      'format': category_format,
                                      'stop_if_true': True})
