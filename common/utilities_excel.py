"""
Some common code for working with xlsxwriter and Excel files

References
https://www.htmlcsscolor.com/hex/33CCCC
https://www.schemecolor.com/sample?getcolor=ffff99
http://dmcritchie.mvps.org/excel/colors.htm
https://www.excelsupersite.com/what-are-the-56-colorindex-colors-in-excel/
https://stackoverflow.com/questions/20648149/what-are-numberformat-options-in-excel-vba
"""

# from excel_utilities import add_workbook_formats, choose_format_accent, excel_columns, Xlformat

import string
from enum import IntEnum
from typing import Dict

import pandas as pd
import webcolors
import xlsxwriter
from xlsxwriter.format import Format
from xlsxwriter.worksheet import Worksheet

# Any colors not defined in webcolors CSS3 are listed here
# Names generally from https://www.schemecolor.com/
# Approximate CSS3 color in comment
excel_colorindices = {
    # https://www.excelsupersite.com/what-are-the-56-colorindex-colors-in-excel/
    # Colors 33-46
    'vividskyblue': '#00CCFF',  # 33 'deepskyblue'
    'water': '#CCFFFF',  # 34 'lightcyan'
    'teagreen': '#CCFFCC',  # 35   'palegreen'
    'fuschia2': '#FF00FF', # canary is too close to header color 'canary': '#FFFF99',  # 36
    'babyblueeyes': '#99CCFF',  # 37  'powderblue'
    'palemagentapink': '#FF99CC',  # 38  'lightpink'
    'paleviolet': '#CC99FF',  # 39 'orchid'
    'peachorange': '#FFCC99',  # 40 'peachpuff'
    'ultramarineblue': '#3366FF',  # 41 'royalblue'
    'maximumbluegreen': '#33CCCC',  # 42  'mediumturquoise'
    'sheengreen': '#99CC00',  # 43 'yellowgreen'
    'tangerineyellow': '#FFCC00',  # 44  'darkorange'
    'vividgamboge': '#FF9900',  # 45 'orange'
    'orange2': '#FF6600',  # 46 'orangered'
    # Usually from format specifications
    'teagreen2': '#C6EFCE',
    'darkgreen2': '#006100',  # 'darkgreen'
    'indigo2': '#333399',  # 'indigo'
    'canary': '#FFFF99'
}


def cn2h(cname: str) -> str:
    return color_name_to_hex(cname)


def color_name_to_hex(cname: str) -> str:
    """

    :param cname: e..g 'darkviolet' (a CSS3 color)
    :return: e.g. #9400d3
    """
    try:
        hexv = webcolors.name_to_hex(cname)
        return hexv
    except ValueError:
        pass

    return excel_colorindices.get(cname, None)


# Generate names for colorindices with:
# TOTALVAL = 18
# for ix in range(len(excel_colorindices.keys())):
#     print(f'CI{ix+1:02d} = {TOTALVAL+ix+1}')

class Xlformat(IntEnum):
    AGE = 1
    CENTER = 2
    COORD = 3
    COUNTSPECIAL = 4
    DIFFICULT = 5
    EASY = 6
    GREEN = 7
    HEADER = 8
    ITALIC = 9
    MARGINAL = 10
    MORPH = 11
    NUMERIC_CENTERED = 12
    PERCENTAGE = 13
    RARE = 14
    TAXON = 15
    TEXT = 16
    TIME_DIST = 17
    TOTAL = 18
    CI01 = 19
    CI02 = 20
    CI03 = 21
    CI04 = 22
    CI05 = 23
    CI06 = 24
    CI07 = 25
    CI08 = 26
    CI09 = 27
    CI10 = 28
    CI11 = 29
    CI12 = 30
    CI13 = 31
    CI14 = 32
    CI15 = 33
    CI16 = 34
    CI17 = 35
    CANARY = 36


XLCIFORMATBASE = int(Xlformat.CI01)
XLCIFORMATEND = int(Xlformat.CI17)


def choose_format_accent(xlfmts, counter: int):
    # wrap around if we run out; counter can be greater than number of choices
    ix = (XLCIFORMATBASE - 0) + (counter % (XLCIFORMATEND - XLCIFORMATBASE + 2))
    # print(f'Format accent : {ix}')
    return xlfmts[ix]


# xlfmts = add_workbook_formats(workbook)
# xlsxwriter.format.Format
def add_workbook_formats(workbook: xlsxwriter.Workbook) -> Dict[Xlformat, Format]:
    excel_workbook_formats = {}

    def addfmt(fmtnum: Xlformat, fmt: dict):
        excel_workbook_formats[fmtnum] = workbook.add_format(fmt)

    addfmt(Xlformat.HEADER, {'bold': True, 'text_wrap': True, 'valign': 'top', 'align': 'center',
                             'fg_color': cn2h('canary'), 'border': 1})

    # ---------- ALIGNMENT FORMATS ----------
    addfmt(Xlformat.CENTER, {'align': 'center'})

    # ---------- FONT FORMATS ----------
    addfmt(Xlformat.ITALIC, {'italic': True})
    addfmt(Xlformat.RARE, {'bold': True})

    # ---------- CELL FORMATS ----------
    addfmt(Xlformat.TEXT, {'num_format': '@'})
    addfmt(Xlformat.AGE, {'bg_color': cn2h('vividskyblue'), 'font_color': cn2h('darkgreen2')})
    addfmt(Xlformat.COORD, {'num_format': '0.000000'})
    addfmt(Xlformat.COUNTSPECIAL, {'bg_color': cn2h('yellow'), 'font_color': cn2h('darkgreen2')})
    addfmt(Xlformat.GREEN, {'bg_color': cn2h('teagreen2'), 'font_color': cn2h('darkgreen2')})

    # See CAHF 'Difficulty'
    addfmt(Xlformat.EASY, {'bg_color': cn2h('teagreen'), 'font_color': cn2h('darkgreen2')})
    addfmt(Xlformat.MARGINAL, {'bg_color': cn2h('canary'), 'font_color': cn2h('darkgreen2')})
    addfmt(Xlformat.DIFFICULT, {'bg_color': cn2h('palemagentapink'),
                                'font_color': cn2h('darkgreen2')})

    addfmt(Xlformat.MORPH, {'bg_color': cn2h('fuchsia'), 'font_color': cn2h('darkgreen2')})
    addfmt(Xlformat.NUMERIC_CENTERED, {'num_format': '0', 'align': 'center'})
    addfmt(Xlformat.PERCENTAGE, {'num_format': '0.00%', 'align': 'center'})
    addfmt(Xlformat.TAXON, {'num_format': '0', 'align': 'center'})
    addfmt(Xlformat.TIME_DIST, {'num_format': '0.00'})
    addfmt(Xlformat.TOTAL, {'bold': True, 'font_color': cn2h('indigo2'), 'num_format': '0.00'})

    for ix, acolor in enumerate(excel_colorindices.values()):
        addfmt(Xlformat(XLCIFORMATBASE + ix), {'bg_color': f'{acolor}'})

    return excel_workbook_formats


def excel_columns():
    # or at least 702 of them
    uc = list(string.ascii_uppercase)
    excel_cols = uc.copy()
    for tens in uc:
        for ones in uc:
            excel_cols.append(f'{tens}{ones}')

    return excel_cols


# Make the sheet banded
# : xlsxwriter.Worksheet
def make_sheet_banded(worksheet: Worksheet, df: pd.DataFrame):
    col_vals = df.columns.values
    xl_cols_dict = [{'header': col} for col in df.columns.values]
    last_col_letter = excel_columns()[len(col_vals) - 1]
    xl_last_data_row = df.shape[0] + 1  # plus 1 is because data starts at row 2
    table_style = {
        'banded_rows': True,
        'header_row': True,
        'columns': xl_cols_dict,
        'style': 'Table Style Light 16'
    }

    worksheet.add_table(f'A1:{last_col_letter}{xl_last_data_row}', table_style)

# https://rdrr.io/cran/tidyxl/man/xlsx_color_theme.html
#                  name      rgb
# 1         background1 FFFFFFFF
# 2               text1 FF000000
# 3         background2 FFEEECE1
# 4               text2 FF1F497D
# 5             accent1 FF4F81BD
# 6             accent2 FFC0504D
# 7             accent3 FF9BBB59
# 8             accent4 FF8064A2
# 9             accent5 FF4BACC6
# 10            accent6 FFF79646
# 11          hyperlink FF0000FF
# 12 followed-hyperlink FF800080

# Drop the leading FFs from above

# excel_accent_colors = [
#     '4F81BD', # 5             accent1 FF4F81BD
#     'C0504D', # 6             accent2 FFC0504D
#     '9BBB59', # 7             accent3 FF9BBB59
#     '8064A2', # 8             accent4 FF8064A2
#     '4BACC6', # 9             accent5 FF4BACC6
#     'F79646', # 10            accent6 FFF79646
# ]
