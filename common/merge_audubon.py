"""
Get count results as Excel from
https://netapp.audubon.org/CBCObservation/CurrentYear/ResultsByCount.aspx
"""

from numbers import Number
from pathlib import Path
from typing import Tuple

import pandas as pd
import io
import sys
import xlrd
import os

from common_paths import raw_data_path, inputs_merge_path
from datetime_manipulation import normalize_date_for_details
from local_translation_context import LocalTranslationContext
from service_merge import merge_checklists
from taxonomy import Taxonomy
from text_transform import clean_common_names
from utilities_excel import excel_columns
from write_final_checklist import write_final_checklist_spreadsheet


def merge_audubon_results(taxonomy: Taxonomy,
                          local_translation_context: LocalTranslationContext):
    results_path = raw_data_path / 'AudubonResults'
    stem_to_colnames = {}
    parameters = {}

    for fpath in results_path.glob('*.xls'):
        df, ci = extract_from_audubon_results(fpath)
        # print(circle_name, circle_code, count_date)
        print(f'Name: {ci["Name"]}, Code: {ci["Code"]}, Date: {ci["Date"]}, Count: {df.shape[0]}')

        xparameters = {
            'CountDate': normalize_date_for_details(ci['Date']),
            'FinalChecklistTitle': ci['Name'],
            'CircleAbbrev': ci["Code"],
            'CircleID': ci["Code"],
        }
        # Just need something to pass to write_final_checklist_spreadsheet
        # ToDo: Service-Merge should not depend on loading parameters #36
        parameters = xparameters

        cleaned_common_names = clean_common_names(df.CommonName, taxonomy,
                                                  local_translation_context)
        df.CommonName = cleaned_common_names

        year = ci["Date"][-4:]
        fname = f'{ci["Code"]}-{year}-AudubonResults.xlsx'
        outpath = inputs_merge_path / fname
        col_name = f'{ci["Name"]} ({ci["Code"]}) {xparameters["CountDate"]}'
        stem_to_colnames[outpath.stem] = col_name

        write_final_checklist_spreadsheet(df, outpath, xparameters, None)

    # Pick something local as base
    from common_paths import outputs_path
    summary_base = outputs_path / 'CASJ-2020-Single.xlsx'
    sector_files = list(inputs_merge_path.glob('*.xlsx'))
    summary, cols_to_hide, cols_to_highlight = merge_checklists(summary_base, sector_files,
                                                                stem_to_colnames, taxonomy,
                                                                local_translation_context)

    output_path = outputs_path / 'Merged-Audubon-Results.xlsx'
    write_final_checklist_spreadsheet(summary, output_path,
                                      parameters=parameters,
                                      additional_sheets=None,
                                      cols_to_hide=cols_to_hide,
                                      cols_to_highlight=cols_to_highlight
                                      )


# ----------------- XLRD ---------------

def str_with_comma_to_num(xs) -> Number:
    return pd.to_numeric(xs.replace(',', ''))


def extract_from_audubon_results(fpath: Path) -> Tuple[pd.DataFrame, dict]:
    # Kinda hacky, works for 121st count results (2020 season)
    # Use local version of open_workbook to fix:
    #   Suppress annoying xlrd warning "WARNING *** file size ..." #37
    encoding_override = None
    with open(fpath, 'rb') as fp:
        book = open_workbook(file_contents=fp.read(), encoding_override=encoding_override)
    sheet = book.sheet_by_index(0)

    # Count code is in cell $A6$AC, name in $A6$L, date in $A6$AO
    count_info_row = 5
    count_code_col = excel_columns().index('AC')
    count_name_col = excel_columns().index('L')
    count_date_col = excel_columns().index('AO')

    circle_code = sheet.cell_value(rowx=count_info_row, colx=count_code_col)
    circle_name = sheet.cell_value(rowx=count_info_row, colx=count_name_col)
    count_date = sheet.cell_value(rowx=count_info_row, colx=count_date_col)

    col_g = sheet.col_values(excel_columns().index('G'))
    col_s = sheet.col_values(excel_columns().index('S'))

    # Scan down column G to find boundaries for species list
    species_index = col_g.index('Species')
    total_individuals_index = col_g.index('Total Individuals')

    species = col_g[species_index + 1: total_individuals_index]
    totals = pd.Series(col_s[species_index + 1: total_individuals_index]).apply(
        str_with_comma_to_num).fillna(0).astype(int)

    # print(circle_name, circle_code, count_date)
    # print(f'Species count: {len(species)}')

    circle_info = {'Name': circle_name, 'Code': circle_code, 'Date': count_date}

    df = pd.DataFrame(list(zip(species, totals)), columns=['CommonName', 'Total'])

    return df, circle_info

# https://stackoverflow.com/questions/7619319/python-xlrd-suppress-warning-messages

# Mute xlrd warnings for OLE inconsistencies
class LogFilter(io.TextIOWrapper):
    def __init__(self, buffer=sys.stdout, *args, **kwargs):
        # self.buffer = buffer
        super(LogFilter, self).__init__(buffer, *args, **kwargs)
    def write(self, data):
        pass
        # if isinstance(data, str):
        #     if not data.startswith("WARNING *** file size"):
        #         print(data)
        #         # super(LogFilter, self).write(data)
        # elif isinstance(data, bytes):
        #     super(LogFilter, self).write(data.decode(self.buffer.encoding))
        # else:
        #     super(LogFilter, self).write(data)

def open_workbook(file_contents, encoding_override):
    fnull = open(os.devnull, 'w')
    logfilter = fnull #io.BufferedIOBase #LogFilter()

    return xlrd.open_workbook(file_contents=file_contents, logfile=logfilter,
                              encoding_override=encoding_override)

