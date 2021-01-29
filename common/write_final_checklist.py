import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np
import pandas as pd
from IPython.display import display

from utilities_excel import add_workbook_formats, choose_format_accent, excel_columns, \
    Xlformat, make_sheet_banded

# TWO_COL_SPLIT_ROWS = 80  # 59 # About 59 rows fit on normal Excel page for printing
MAX_SPECIES_ALTERNATIVES = 6

# This number seems to vary a lot; not sure why. I has been 59 and 80 previously
EXCEL_ROWS_PER_PRINTED_PAGE = 95


def unfill_species_group(local_checklist):
    # Keep for eventual printing
    # https://stackoverflow.com/questions/46479437/perform-operation-opposite-to-pandas-ffill
    zlocal_checklist = local_checklist.copy()
    ffinv = lambda s: s.mask(s == s.shift())
    zlocal_checklist = zlocal_checklist.assign(Group=ffinv(zlocal_checklist.Group)).fillna('')

    return zlocal_checklist


# Additional args for write_final_checklist_spreadsheet:
# - cols_to_hide: default = ['Group', 'R', 'TaxonOrder']
# - cols_to_highlight: ['Total']
# - cols_to_drop:
# This will also apply to the '_' versions of these cols (i.e. the second column)


def transform_checklist_into_two_columns(checklist,
                                         excel_rows_per_printed_page=EXCEL_ROWS_PER_PRINTED_PAGE):
    page_breaks = None
    # # Do some transformations on the incoming dataframe
    # col_subset = [cc for cc in ['Group', 'CommonName', 'Rare', 'Total',
    #                             'Ad', 'Im', 'TaxonOrder', 'D',
    #                             'Adult', 'Immature', 'W-morph', 'B-Morph', 'Difficulty'] if
    #               cc in checklist.columns]

    preferred_order = ['Group', 'CommonName', 'Rare', 'D', 'Total', 'Ad', 'Im',
                       'TaxonOrder', 'Category', 'Difficulty',
                       'Adult', 'Immature', 'W-morph', 'B-Morph', 'CountSpecial']
    col_subset = [col for col in preferred_order if col in checklist.columns]

    checklist = unfill_species_group(checklist.copy()[col_subset])
    # Rename columns
    #     checklist.columns = ['Group', 'CommonName', 'R', 'Total', 'TaxonOrder']
    checklist.Group = checklist.Group.apply(lambda xs: xs.upper())

    # We can fit 59 species per column, roundup(176/59) gives us 4
    checklist_rows = checklist.shape[0]
    # There is a closed-form solution to this, but this works
    rpp = excel_rows_per_printed_page  # Might vary, but this is what Excel splits it at
    rpp_bin_tuples = [(1, rpp), (rpp, 2 * rpp)]
    top = int(np.round(1 + (checklist_rows / rpp)))
    for lhs in list(range(2, top, 2)):
        rpp_bin_tuples.append((lhs * rpp, (lhs + 2) * rpp))

    rpp_bins = pd.IntervalIndex.from_tuples(rpp_bin_tuples)
    num_splits = 2 * rpp_bins.get_loc(checklist_rows)

    # print(f'Rows per page: {rpp}')
    # print(f'RPP Bins: {rpp_bins}')
    # print(TWO_COL_SPLIT_ROWS, rpp, top, rpp_bin_tuples)
    if num_splits == 0:
        # Nothing to do
        checklist2col = checklist.copy()
    else:
        # Unfortunately, array_split makes equal chunks, which are too small
        # dfs = np.array_split(checklist, num_splits, axis=0)

        dfs = []
        for start in range(0, checklist.shape[0], excel_rows_per_printed_page):
            df = checklist.iloc[start:start + excel_rows_per_printed_page].copy()
            dfs.append(df)

        # Get the last non-empty group to supply to next df

        previous_group = None

        for ix, _ in enumerate(dfs):
            # print(dfs[ix].shape)
            if previous_group:
                dfs[ix].reset_index(drop=True, inplace=True)
                if dfs[ix].loc[0, 'Group'] == '':
                    dfs[ix].loc[0, 'Group'] = previous_group + ' (cont.)'

            last_taxon_order = dfs[ix].iloc[-1]['TaxonOrder']
            blank_row = pd.Series([''] * dfs[ix].shape[1], index=dfs[ix].columns)
            blank_row['TaxonOrder'] = last_taxon_order + 0.1
            dfs[ix] = dfs[ix].append(blank_row, ignore_index=True)
            # Get the last non-empty group to supply to next df
            groups = dfs[ix]['Group']
            previous_group = [x for x in groups if x != ''][-1]
            # print(previous_group)

        df_pages = []
        for ix in range(0, len(dfs), 2):
            # reset_index(drop=True) not needed for ix==0, but easier to just do it
            if ix + 1 < len(dfs):
                df_page = pd.concat(
                    [dfs[ix].reset_index(drop=True), dfs[ix + 1].reset_index(drop=True)], axis=1,
                    ignore_index=True)
            else:
                df_empty = pd.DataFrame(columns=dfs[ix].columns,
                                        index=range(dfs[ix].shape[0])).fillna('')
                df_empty.Total = ''
                df_empty.TaxonOrder = 0
                df_page = pd.concat([dfs[ix].reset_index(drop=True), df_empty], axis=1,
                                    ignore_index=True)
            df_pages.append(df_page)
        checklist2col = pd.concat(df_pages, axis=0, ignore_index=True)

        zcol = pd.Series(checklist.columns)
        zcols = list(zcol) + list(zcol.apply(lambda xs: xs + ' '))
        checklist2col.columns = zcols

        # page_breaks = [43, 86, 129]

    return checklist2col, None


def recombine_transformed_checklist(checklist, taxonomy):
    # Undo transform_checklist_into_two_columns
    columns = checklist.columns
    if (len(columns) % 2) != 0:
        return checklist

    # Double check that it was made by our function transform_checklist_into_two_columns
    hwp = int(len(columns) / 2)
    first_half_cols = list(columns[0:hwp])
    second_half_cols = list(columns[hwp:])
    if not (first_half_cols == [xs.strip() for xs in second_half_cols]):
        return checklist

    top_half = checklist[first_half_cols]
    bottom_half = checklist[second_half_cols]
    bottom_half.columns = top_half.columns
    #     print(top_half.shape, bottom_half.shape)

    combined_checklist = top_half.append(bottom_half).reset_index(drop=True)
    # Rows with a TaxonOrder of 99999 are an artifact of making two columns
    mask_blank = (combined_checklist.CommonName.astype(str) == '')
    #     display(combined_checklist[mask_blank])
    combined_checklist.drop(combined_checklist[mask_blank].index, inplace=True)  # mask_99999 |
    combined_checklist = combined_checklist.sort_values(by=['TaxonOrder']).reset_index(drop=True)

    species_groups = []
    for cn in combined_checklist.CommonName:
        common_name, taxon_order, species_group, nacc_sort_order = taxonomy.find_local_name(cn)
        species_groups.append(species_group)
    combined_checklist.Group = species_groups

    # Fix total column, may be blanks instead of zeros
    totals = [(0 if xx == '' else xx) for xx in combined_checklist.Total]
    combined_checklist.Total = totals

    return combined_checklist


# Additional args for write_final_checklist_spreadsheet:
# - cols_to_hide: default = ['Group', 'R', 'TaxonOrder']
# - cols_to_highlight: ['Total']
# - cols_to_drop:
# This will also apply to the '_' versions of these cols (i.e. the second column)

#         format_rare = workbook.add_format({'bold': True})  # 'bg_color': '#FFC7CE',
def format_col_if_other_col(checklist, worksheet,
                            cols_to_format: List[str],
                            condition_cols: List[str],
                            xformat,
                            to_match: str = 'X'):
    # Make CommonName background yellow if CountSpecial column is set
    # Assumes format has been added to workbook already
    # condition_col is the "other col"

    xl_last_data_row = checklist.shape[0] + 1  # plus 1 is because data starts at row 2

    # Add variants with blanks to handle two column layouts (Double)
    # For example, both 'Adult' and 'Adult ' could be in columns
    cols_to_format.extend([xs + ' ' for xs in cols_to_format])
    condition_cols.extend([xs + ' ' for xs in condition_cols])

    cols_to_format_idxs = [idx for idx, xs in enumerate(checklist.columns) if xs in cols_to_format]
    # What column do we look for an 'X' in? These are the condition columns
    x_cols_idxs = [idx for idx, xs in enumerate(checklist.columns) if xs in condition_cols]
    col_letters = excel_columns()
    for cn_idx, cond_idx in zip(cols_to_format_idxs, x_cols_idxs):
        col2fmt_letter = col_letters[cn_idx]
        cond_col_letter = col_letters[cond_idx]
        to_format_cells = f'{col2fmt_letter}2:{col2fmt_letter}{xl_last_data_row}'
        criteria_cells = f'{cond_col_letter}2'
        criteria = f'=EXACT({criteria_cells}, {to_match})'
        # print(f'rarity_criteria: {rarity_criteria}')
        worksheet.conditional_format(to_format_cells,
                                     {'type': 'formula', 'criteria': criteria,
                                      'format': xformat})


def write_final_checklist_spreadsheet(checklist, checklist_path: Path,
                                      parameters: dict,
                                      additional_sheets: Optional[List[dict]],
                                      cols_to_hide: list = None,
                                      cols_to_highlight: list = None,
                                      header_cell_groups: List[str] = None
                                      ):
    # updated_checklist is the filled-in local_checklist
    # It may be wrapped to a two column (printing) format
    if cols_to_highlight is None:
        cols_to_highlight = ['Total']
    if cols_to_hide is None:
        cols_to_hide = ['Group', 'R', 'TaxonOrder']
    if checklist.empty:
        return None

    checklist = checklist.copy()
    xsheet_name = 'Final Checklist'

    # Columns
    # Group, CommonName, R, Total, TaxonOrder, Group_, CommonName_, R_, Total_, TaxonOrder_
    #   A        B       C    D         E        F         G        H     I         J

    real_cols_to_hide = [x for x in checklist.columns if
                         x.rstrip() in cols_to_hide] if cols_to_hide else []
    real_cols_to_highlight = [x for x in checklist.columns if x.rstrip() in cols_to_highlight] \
        if cols_to_highlight else []
    cols_to_center = ['R', 'Total', 'TaxonOrder', 'Rare', 'Category', 'NACC_SORT_ORDER',
                      'ABA_SORT_ORDER']
    stripped_widths = {'Group': 20, 'CommonName': 40, 'R': 5, 'Total': 7, 'TaxonOrder': 8,
                       'LocalName': 35, 'may_need_writeup': 35, 'Rare': 10,
                       'D': 3, 'Adult': 6, 'Immature': 6, 'W-morph': 6, 'B-Morph': 6,
                       'Difficulty': 6, 'Adult/White': 11, 'Immature/Blue': 11,
                       'Ad': 3, 'Im': 3, 'CountSpecial': 3,
                       'Category': 10, 'NACC_SORT_ORDER': 8, 'ABA_SORT_ORDER': 8}
    xl_last_data_row = checklist.shape[0] + 1  # plus 1 is because data starts at row 2

    fill_values = {'Group': '', 'CommonName': '', 'Rare': '', 'TaxonOrder': 99999,
                   'Group ': '', 'CommonName ': '', 'Rare ': '', 'TaxonOrder ': 99999}
    checklist = checklist.fillna(value=fill_values)

    # Probably sector names
    standard_cols_base = ['CommonName', 'LocalName', 'Group',
                          'Category', 'TaxonOrder', 'NACC_SORT_ORDER', 'ABA_SORT_ORDER', 'Total']
    standard_cols = standard_cols_base.copy()
    for col in standard_cols_base:
        standard_cols.append(col + ' ')
    non_standard_cols = [col for col in checklist.columns if col not in standard_cols]
    for col in non_standard_cols:
        cols_to_center.append(col)
        if not stripped_widths.get(col, None):
            stripped_widths[col] = 14

    try:
        intcols = [col for col in checklist.columns if col.startswith('Taxon')]
        for col in intcols:
            checklist[col] = pd.to_numeric(checklist[col], errors='coerce')
            # checklist = checklist.astype({col: 'int32'}, errors='ignore')
    except Exception as ee:
        print(f'Failed to set type of column "{col}" to numeric', ee)
        checklist.to_csv(checklist_path.parent / f'failure-checklist.csv', index=False)
        unknown_idxs = checklist.index[checklist[col] == 'UNKNOWN']
        display(checklist.loc[unknown_idxs])
        traceback.print_exc(file=sys.stdout)
        # pass

    checklist.astype({'Total': str})

    with pd.ExcelWriter(checklist_path.as_posix(), engine='xlsxwriter') as writer:
        checklist.to_excel(writer, index=False, sheet_name=xsheet_name)

        # Get the xlsxwriter workbook and worksheet objects.
        workbook = writer.book
        xlfmts = add_workbook_formats(workbook)

        # https://stackoverflow.com/questions/43991505/xlsxwriter-set-global-font-size
        workbook.formats[0].set_font_size(14)  # to make it readable when printed

        # ----------------------------------------------
        # Populate col_infos with formatting information
        col_infos = {}

        col_letters = excel_columns()
        assert (len(checklist.columns) <= len(col_letters))  # 702
        for ix, col in enumerate(checklist.columns):
            stripped_col = col.rstrip()
            col_letter = col_letters[ix]
            col_info = {
                'hide': col in real_cols_to_hide,
                'highlight': col in real_cols_to_highlight,
                'format': xlfmts[Xlformat.CENTER] if col in cols_to_center else None,
                'width': stripped_widths.get(stripped_col, 10),
                'xl_col_letter': f'{col_letter}'
            }
            col_infos[col] = col_info

        colspec = pd.DataFrame(col_infos).T
        # ----------------------------------------------

        worksheet = writer.sheets[xsheet_name]

        date_of_count = parameters['CountDate']
        dtcount = datetime.strptime(date_of_count, '%Y-%m-%d')
        dtcstr = dtcount.strftime("%d %b %Y")
        yr = dtcount.strftime("%Y")
        title = parameters.get('FinalChecklistTitle', '')

        worksheet.set_header(f'&C&16&"Times New Roman,Regular"{title} {yr}')

        region = parameters['CircleAbbrev']
        party = parameters['CircleID']
        footer_fmt = f'&C&12&"Times New Roman,Regular"'
        worksheet.set_footer(
            f'{footer_fmt}Region: {region}       Party: {party}       Date: {dtcstr}')

        # print(f'parameters: {parameters}')
        page_breaks = parameters.get('page_breaks', None)
        if page_breaks:
            # When splitting into 2 columns, the page breaks are known
            print(f'page_breaks: {page_breaks}')
            worksheet.set_h_pagebreaks(page_breaks)
        else:
            # https://xlsxwriter.readthedocs.io/page_setup.html
            # A common requirement is to fit the printed output to n pages wide but
            # have the height be as long as necessary
            # print('fitting to 1 page wide')
            worksheet.fit_to_pages(1, 0)

        # Highlight numbers > 0 for species count
        for ix, col_info in colspec[colspec.highlight].iterrows():
            xl_col_letter = col_info['xl_col_letter']
            v_total_cell_range = f'{xl_col_letter}2:{xl_col_letter}{xl_last_data_row}'
            worksheet.conditional_format(v_total_cell_range,
                                         {'type': 'cell',
                                          'criteria': '>',
                                          'value': 0,
                                          'format': xlfmts[Xlformat.GREEN]})

        excel_letters = excel_columns()
        # Make CommonName bold if Rare column is set
        cols_to_bold_idxs = [idx for idx, xs in enumerate(checklist.columns) if
                             xs.startswith('CommonName')]
        rare_cols_idxs = [idx for idx, xs in enumerate(checklist.columns) if xs.startswith('Rare')]
        for cn_idx, ra_idx in zip(cols_to_bold_idxs, rare_cols_idxs):
            letter = excel_letters[cn_idx]
            letter_rare = excel_letters[ra_idx]
            format_rare = workbook.add_format({'bold': True})  # 'bg_color': '#FFC7CE',
            rare_name_cells = f'{letter}2:{letter}{xl_last_data_row}'
            rarity_criteria_cells = f'{letter_rare}2'
            rarity_criteria = f'=EXACT({rarity_criteria_cells},"X")'
            # print(f'rarity_criteria: {rarity_criteria}')
            worksheet.conditional_format(rare_name_cells,
                                         {'type': 'formula', 'criteria': rarity_criteria,
                                          'format': format_rare})

        # Make CommonName background yellow if CountSpecial column is set
        format_col_if_other_col(checklist, worksheet, ['CommonName'], ['CountSpecial'],
                                xlfmts[Xlformat.COUNTSPECIAL])
        # format_col_if_other_col(checklist, worksheet, col_to_format, condition_cols, xformat)

        # Color the 'D' (Difficulty) column based on value in 'Difficulty' column
        xformats = [xlfmts[idx] for idx in [Xlformat.EASY, Xlformat.MARGINAL, Xlformat.DIFFICULT]]
        for to_match, xformat in zip(['E', 'M', 'D'], xformats):
            format_col_if_other_col(checklist, worksheet, ['D'], ['Difficulty'], xformat, to_match)

        # Color the 'Ad' (Adult) column based on value in 'Adult' column
        format_col_if_other_col(checklist, worksheet, ['Ad', 'Im'], ['Adult', 'Immature'],
                                xlfmts[Xlformat.AGE], 'X')

        # Highlight the 'Ad', 'Im' if non-zero values in 'W-morph', 'B-Morph'
        # The 'Ad', 'Im' columns are overloaded here since there is no species overlap
        format_col_if_other_col(checklist, worksheet, ['Ad', 'Im'], ['W-morph', 'B-Morph'],
                                xlfmts[Xlformat.MORPH], 'X')

        # Italicize non-species
        try:
            if 'Category' in checklist.columns:
                cols_to_italicize_idxs = [idx for idx, xs in enumerate(checklist.columns) if
                                          xs.startswith('CommonName')]
                category_cols_idxs = [idx for idx, xs in enumerate(checklist.columns) if
                                      xs.startswith('Category')]
                for cn_idx, ca_idx in zip(cols_to_italicize_idxs, category_cols_idxs):
                    letter = excel_letters[cn_idx]
                    letter_category = excel_letters[ca_idx]
                    common_name_cells = f'{letter}2:{letter}{xl_last_data_row}'
                    category_criteria_cells = f'{letter_category}2'
                    # category_criteria = f'=EXACT({category_criteria_cells},"slash")'
                    category_criteria = f'={category_criteria_cells}<>"species"'
                    # print(f'category_criteria: {category_criteria}')
                    worksheet.conditional_format(common_name_cells,
                                                 {'type': 'formula', 'criteria': category_criteria,
                                                  'format': xlfmts[Xlformat.ITALIC]})
        except Exception as ee:
            print(ee)
            print(checklist.columns)
            print(category_cols_idxs)
            traceback.print_exc(file=sys.stdout)
            raise

        # rare_name_cells = f'G2:G{xl_last_data_row}'
        # rarity_criteria = '=EXACT(H2,"X")'
        # worksheet.conditional_format(rare_name_cells,
        #         {'type': 'formula', 'criteria': rarity_criteria, 'format': format_rare})

        # Set the column width and format.
        # Set formats with e.g. 'C:C'
        for col_num, col_info in colspec.iterrows():
            xl_col_letter = col_info['xl_col_letter']
            wid = col_info['width']
            fmt = col_info['format']
            worksheet.set_column(f'{xl_col_letter}:{xl_col_letter}', wid, fmt)

        for col in non_standard_cols:
            idx = list(checklist.columns).index(col)
            xl_col_letter = excel_letters[idx]
            wid = stripped_widths[col]
            fmt = xlfmts[Xlformat.ACCOUNTING]
            worksheet.set_column(f'{xl_col_letter}:{xl_col_letter}', wid, fmt)

        # https://xlsxwriter.readthedocs.io/worksheet.html#set_column
        for ix, col_info in colspec[colspec.hide].iterrows():
            xl_col_letter = col_info['xl_col_letter']
            worksheet.set_column(f'{xl_col_letter}:{xl_col_letter}', None, None, {'hidden': 1})

        # Make the sheet banded
        make_sheet_banded(worksheet, checklist)

        # Set the width, and other properties of a row
        # row (int) – The worksheet row (zero indexed).
        # height (float) – The row height.
        worksheet.set_row(0, 70, None, None)
        worksheet.freeze_panes(1, 0)  # Freeze the first row.

        # header_cell_groups
        if header_cell_groups is not None:
            for ix, header_cell_group in enumerate(header_cell_groups):
                category_criteria = f'=True'
                # print(header_cell_group, ix, fmt)
                worksheet.conditional_format(header_cell_group,
                                             {'type': 'formula',
                                              'criteria': category_criteria,
                                              'format': choose_format_accent(xlfmts, ix)})

        # Write the column headers with the defined format.
        for col, col_info in colspec.iterrows():
            # fmt = col_info['format']
            col_num = list(colspec.index).index(col)
            worksheet.write(0, col_num, col, xlfmts[Xlformat.HEADER])

        # ***
        if additional_sheets is not None:
            for sheet_info in additional_sheets:
                # print(sheet_info['sheet_name'])
                df = sheet_info['data']

                df.to_excel(writer, index=False, sheet_name=sheet_info['sheet_name'])
                worksheet = writer.sheets[sheet_info['sheet_name']]
                make_sheet_banded(worksheet, df)

                center_cols = sheet_info['to_center']
                for col, wid in sheet_info['widths'].items():
                    col_index = list(df.columns).index(col)
                    col_letter = excel_letters[col_index]
                    fmt = xlfmts[Xlformat.CENTER] if col in center_cols else None
                    worksheet.set_column(f'{col_letter}:{col_letter}', wid, fmt)

                # Set the width, and other properties of a row
                # row (int) – The worksheet row (zero indexed).
                # height (float) – The row height.
                # worksheet.set_row(0, 70, None, None)
                worksheet.freeze_panes(1, 0)  # Freeze the first row.
                # Set the header format
                worksheet.write_row(0, 0, list(df.columns), xlfmts[Xlformat.HEADER])
                # Write out cells


def expand_group_rows(checklist: pd.DataFrame) -> pd.DataFrame:
    # Move group to its own row before the species in its group
    temp_checklist = checklist.copy()  # local1

    fill_values = {'Group': '', 'CommonName': '', 'Rare': '', 'TaxonOrder': 99999}
    temp_checklist = temp_checklist.fillna(value=fill_values).sort_values(by=['TaxonOrder'])
    # unfill_species_group utterly fails if not sorted by TaxonOrder

    temp_checklist = unfill_species_group(temp_checklist).reset_index(drop=True)
    group_indices = temp_checklist[temp_checklist.Group != ''].index

    # ---------------------------------
    expanded_rows = []
    group_keep_cols = ['Group', 'TaxonOrder']
    for ix, row in temp_checklist.iterrows():

        if ix in group_indices:
            # insert group row before current row
            expanded_rows.append(row.copy()[group_keep_cols])
            row['Group'] = ''

        # Now add the current row with group blanked out
        expanded_rows.append(row)

    expanded_checklist = pd.DataFrame(expanded_rows).reset_index(drop=True).fillna('')

    return expanded_checklist


def write_local_checklist_with_group(updated_checklist, output_file_path, parameters: dict):
    # Together
    local3_df = pd.DataFrame()
    output_directory_path = output_file_path.parent
    excel_rows_per_printed_page = parameters.get('ExcelRowsPerPrintedPage',
                                                 EXCEL_ROWS_PER_PRINTED_PAGE)

    try:
        local2_df = expand_group_rows(updated_checklist)

        preferred_order = ['Group', 'CommonName', 'Rare', 'D', 'Total', 'Ad', 'Im',
                           'Category', 'TaxonOrder', 'NACC_SORT_ORDER', 'ABA_SORT_ORDER',
                           'Difficulty',
                           'Adult', 'Immature', 'W-morph', 'B-Morph', 'CountSpecial']
        # ToDo: use filter()
        newcols = [col for col in preferred_order if col in local2_df.columns]

        local2_df['Total'] = ''  # Since this is for printing
        local3_df, page_breaks = transform_checklist_into_two_columns(local2_df[newcols],
                                                                      excel_rows_per_printed_page)

        fill_values = {'Group': '', 'CommonName': '', 'Rare': '', 'TaxonOrder': 99999,
                       'Group ': '', 'CommonName ': '', 'Rare ': '', 'TaxonOrder ': 99999}
        local3_df = local3_df.fillna(value=fill_values)

        # if page_breaks:
        #     parameters['page_breaks'] = page_breaks

        cols_to_hide = ['Category', 'TaxonOrder', 'NACC_SORT_ORDER', 'ABA_SORT_ORDER', 'Rare',
                        'Adult', 'Immature', 'W-morph', 'B-Morph',
                        'Difficulty', 'CountSpecial']
        write_final_checklist_spreadsheet(local3_df, output_file_path,
                                          parameters,
                                          additional_sheets=None,
                                          cols_to_hide=cols_to_hide,
                                          cols_to_highlight=None)  # ['TOTAL']
    except Exception as ee:
        updated_checklist.to_csv(output_directory_path / f'failure-local1_df.csv', index=False)
        if not local3_df.empty:
            local3_df.to_csv(output_directory_path / f'failure-local3_df.csv', index=False)
        print(f'Failed to write {output_file_path.as_posix()}, {ee}')
        traceback.print_exc(file=sys.stdout)


def write_possible_translations_spreadsheet(translations_df, translations_xl_path):
    if translations_df.empty:
        return None

    # LocalSpeciesName	eBirdSpeciesName	levd	match_whole_line	regex	circle	AltName1	Lev2	AltName2

    col_widths = [50, 50, 12, 16, 12, 12, 30]
    for ix in range(MAX_SPECIES_ALTERNATIVES - 1):
        col_widths.append(30)
        col_widths.append(10)

    xsheet_name = 'Possible Translations'

    sheet_names = banded_sheets = [xsheet_name]
    center_cols = [col for col in translations_df.columns if col.startswith('lev')]
    for col in ['match_whole_line', 'regex', 'circle']:
        center_cols.append(col)

    with pd.ExcelWriter(translations_xl_path, engine='xlsxwriter') as writer:
        translations_df.to_excel(writer, index=False, sheet_name=xsheet_name)

        # Get the xlsxwriter workbook and worksheet objects.
        workbook = writer.book
        xlfmts = add_workbook_formats(workbook)

        excel_letters = excel_columns()
        for sheet_num, sheet_name in enumerate(sheet_names):
            worksheet = writer.sheets[xsheet_name]

            # Set the column width and format.
            widths = col_widths
            col_vals = translations_df.columns.values  # df_columns[sheet_num].values

            for ix, wid in enumerate(widths):
                col_letter = excel_letters[ix]
                fmt = xlfmts[Xlformat.CENTER] if col_vals[ix] in center_cols else None
                worksheet.set_column(f'{col_letter}:{col_letter}', wid, fmt)

            if sheet_name in banded_sheets:
                make_sheet_banded(worksheet, translations_df)

            # Write the column headers with the defined format.
            for col_num, value in enumerate(col_vals):
                worksheet.write(0, col_num, value, xlfmts[Xlformat.HEADER])


# -----------

def write_nlp_statistics(nlp_statistics, stats_path: Path):
    if nlp_statistics.empty:
        return None

    nlp_statistics = nlp_statistics.copy()
    xsheet_name = 'ParsePDF Statistics'

    # Columns
    # ['family', 'unknown', 'intersections', 'line_token_count', 'line', 'original_line', 'guess',
    #   'levd',  'line_len', 'lev_len_pct', 'species_inferred', 'is_species_line',
    #   'guess_correct', 'source']

    cols_to_center = ['is_group', 'non_avian', 'intersections', 'line_token_count', 'levd',
                      'tx_line_len',
                      'species_inferred', 'is_species_line', 'guess_correct', 'source']
    column_widths = {
        'classification': 20, 'original_line': 45, 'transformed_line': 45, 'species': 45,
        'closest_match': 45,
        'is_group': 12, 'non_avian': 12, 'intersections': 12, 'line_token_count': 12,
        'levd': 11, 'tx_line_len': 11, 'lev_len_pct': 11,
        'species_inferred': 14, 'exact_match': 14, 'verified': 14, 'source': 14
    }

    numeric_cols = ['intersections', 'line_token_count', 'levd', 'line_len']
    text_cols = ['classification', 'transformed_line', 'original_line', 'species',
                 'closest_match']  # force otherwise may interpret original_line as a formula

    with pd.ExcelWriter(stats_path.as_posix(), engine='xlsxwriter') as writer:
        nlp_statistics.to_excel(writer, index=False, sheet_name=xsheet_name)

        # Get the xlsxwriter workbook and worksheet objects.
        workbook = writer.book
        xlfmts = add_workbook_formats(workbook)

        # ----------------------------------------------
        # Populate col_infos with formatting information
        col_infos = {}

        excel_letters = excel_columns()
        for ix, col in enumerate(nlp_statistics.columns):
            col_letter = excel_letters[ix]
            col_info = {}
            # col_info['hide'] = col in real_cols_to_hide
            # col_info['highlight'] = col in real_cols_to_highlight
            if col in numeric_cols:
                fmt = xlfmts[Xlformat.NUMERIC_CENTERED]
            elif col == 'lev_len_pct':
                fmt = xlfmts[Xlformat.PERCENTAGE]
            elif col in text_cols:
                fmt = xlfmts[Xlformat.TEXT]
            else:
                fmt = xlfmts[Xlformat.CENTER] if col in cols_to_center else None
            col_info['format'] = fmt
            col_info['width'] = column_widths.get(col, 10)
            col_info['xl_col_letter'] = f'{col_letter}'
            col_infos[col] = col_info

        colspec = pd.DataFrame(col_infos).T
        # ----------------------------------------------

        worksheet = writer.sheets[xsheet_name]

        title = 'NLP Statistics'
        worksheet.set_header(f'&C&16&"Times New Roman,Regular"{title}')

        # footer_fmt = f'&C&12&"Times New Roman,Regular"'
        # worksheet.set_footer(f'{footer_fmt}Region: {region} Party: {party}       Date: {dtcstr}')

        # https://xlsxwriter.readthedocs.io/page_setup.html
        # A common requirement is to fit the printed output to n pages wide but have the
        # height be as long as necessary
        # worksheet.fit_to_pages(1, 0)

        # rare_name_cells = f'G2:G{xl_last_data_row}'
        # rarity_criteria = '=EXACT(H2,"X")'
        # worksheet.conditional_format(rare_name_cells,
        #       {'type': 'formula', 'criteria': rarity_criteria, 'format': format_rare})

        # Set the column width and format.
        # Set formats with e.g. 'C:C'
        for col_num, col_info in colspec.iterrows():
            xl_col_letter = col_info['xl_col_letter']
            wid = col_info['width']
            fmt = col_info['format']
            worksheet.set_column(f'{xl_col_letter}:{xl_col_letter}', wid, fmt)

        # https://xlsxwriter.readthedocs.io/worksheet.html#set_column
        # for ix, col_info in colspec[colspec.hide].iterrows():
        #     xl_col_letter = col_info['xl_col_letter']
        #     worksheet.set_column(f'{xl_col_letter}:{xl_col_letter}', None, None, {'hidden': 1})

        # Make the sheet banded
        make_sheet_banded(worksheet, nlp_statistics)

        # Write the column headers with the defined format.
        for col, col_info in colspec.iterrows():
            # fmt = col_info['format']
            col_num = list(colspec.index).index(col)
            worksheet.write(0, col_num, col, xlfmts[Xlformat.HEADER])

        # Close the Pandas Excel writer and output the Excel file.
        # writer.save()


def write_ground_truths(truths, out_path: Path):
    if truths.empty:
        return None

    truths = truths.copy()
    xsheet_name = 'Ground Truths'

    # Columns
    # name	Category	ABED-1	ABED-1v	ABED-2	ABED-2v	ABED-3	ABED-3v	ABED-4	ABED-4v...

    cols_to_center = truths.columns.drop('name').drop('Category')  # everything else is centered
    column_widths = {'name': 40, 'Category': 10}
    for col in cols_to_center:
        column_widths[col] = 5 if col.endswith('v') else 11

    numeric_cols = cols_to_center
    text_cols = ['name', 'Category']  # force otherwise may interpret original_line as a formula

    xl_last_data_row = truths.shape[0] + 1  # plus 1 is because data starts at row 2

    with pd.ExcelWriter(out_path.as_posix(), engine='xlsxwriter') as writer:
        truths.to_excel(writer, index=False, sheet_name=xsheet_name)

        # Get the xlsxwriter workbook and worksheet objects.
        workbook = writer.book
        xlfmts = add_workbook_formats(workbook)

        # ----------------------------------------------
        # Populate col_infos with formatting information
        col_infos = {}

        col_letters = excel_columns()
        for ix, col in enumerate(truths.columns):
            col_letter = col_letters[ix]
            col_info = {}
            # col_info['hide'] = col in real_cols_to_hide
            # col_info['highlight'] = col in real_cols_to_highlight
            if col in numeric_cols:
                fmt = xlfmts[Xlformat.NUMERIC_CENTERED]
            elif col in text_cols:
                fmt = xlfmts[Xlformat.TEXT]
            else:
                fmt = xlfmts[Xlformat.CENTER] if col in cols_to_center else None
            col_info['format'] = fmt
            col_info['width'] = column_widths.get(col, 10)
            col_info['xl_col_letter'] = f'{col_letter}'
            col_infos[col] = col_info

        colspec = pd.DataFrame(col_infos).T
        # ----------------------------------------------

        worksheet = writer.sheets[xsheet_name]

        title = 'Ground Truths'
        worksheet.set_header(f'&C&16&"Times New Roman,Regular"{title}')

        # footer_fmt = f'&C&12&"Times New Roman,Regular"'
        # worksheet.set_footer(f'{footer_fmt}Region: {region} Party: {party}  Date: {dtcstr}')

        # https://xlsxwriter.readthedocs.io/page_setup.html
        # A common requirement is to fit the printed output to n pages wide but
        # have the height be as long as necessary
        # worksheet.fit_to_pages(1, 0)

        # Highlight numbers > 0 for species count
        last_column_letter = col_letters[truths.shape[1] - 1]
        v_total_cell_range = f'C2:{last_column_letter}{xl_last_data_row}'
        worksheet.conditional_format(v_total_cell_range,
                                     {'type': 'cell',
                                      'criteria': 'equal to',
                                      'value': True,
                                      'format': xlfmts[Xlformat.GREEN]})

        # Set the column width and format.
        # Set formats with e.g. 'C:C'
        for col_num, col_info in colspec.iterrows():
            xl_col_letter = col_info['xl_col_letter']
            wid = col_info['width']
            fmt = col_info['format']
            worksheet.set_column(f'{xl_col_letter}:{xl_col_letter}', wid, fmt)

        # https://xlsxwriter.readthedocs.io/worksheet.html#set_column
        # for ix, col_info in colspec[colspec.hide].iterrows():
        #     xl_col_letter = col_info['xl_col_letter']
        #     worksheet.set_column(f'{xl_col_letter}:{xl_col_letter}', None, None, {'hidden': 1})

        # Make the sheet banded
        make_sheet_banded(worksheet, truths)

        # Write the column headers with the defined format.
        for col, col_info in colspec.iterrows():
            # fmt = col_info['format']
            col_num = list(colspec.index).index(col)
            worksheet.write(0, col_num, col, xlfmts[Xlformat.HEADER])


def sheet_info_for_party_efforts(df: pd.DataFrame) -> dict:
    # ['Party Lead', 'Duration (Hrs)', 'Distance (mi)']
    column_widths = {
        'Party Lead': 25,
        'Duration (Hrs)': 10,
        'Distance (mi)': 10
    }
    columns_to_center = ['Duration (Hrs)', 'Distance (mi)']

    sheet_info = {
        'sheet_name': 'Individual Efforts',
        'data': df,
        'widths': column_widths,
        'to_center': columns_to_center,
        'to_hide': None
    }

    return sheet_info


def sheet_info_for_party_details(df: pd.DataFrame) -> dict:
    # ['locId', 'subId', 'Total', 'Name', 'Observers', 'sharing', 'groupId',
    #        'location_group', 'Date/Time', 'url', 'LocationName', 'Duration (Hrs)',
    #        'Distance (mi)', 'Distance (km)', 'comments']
    column_widths = {'locId': 10, 'subId': 10, 'Total': 10, 'Name': 25, 'Observers': 10,
                     'sharing': 10, 'groupId': 10, 'location_group': 20, 'Date/Time': 20, 'url': 28,
                     'LocationName': 25, 'Duration (Hrs)': 10, 'Distance (mi)': 10,
                     'comments': 60}

    columns_to_center = ['locId', 'subId', 'groupId', 'Date/Time', 'Total', 'Observers',
                         'effortDistanceKm', 'durationHrs', 'sharing', 'location_group']

    sheet_info = {
        'sheet_name': 'Individual Details',
        'data': df,
        'widths': column_widths,
        'to_center': columns_to_center,
        'to_hide': None
    }

    return sheet_info


def sheet_info_for_rarities(df: pd.DataFrame) -> dict:
    # ['locId', 'subId', 'Name', 'obsDt', 'Total', 'CommonName', 'effortDistanceKm',
    # 'effortDistanceEnteredUnit', 'durationHrs', 'Observers', 'comments', 'Reason', 'Where']
    column_widths = {
        'locId': 10, 'subId': 10, 'Name': 25, 'obsDt': 15, 'Total': 8, 'CommonName': 20,
        'DistanceMi': 8, 'durationHrs': 10,
        'Observers': 8, 'comments': 60, 'Reason': 10, 'Where': 60
    }

    columns_to_center = ['locId', 'subId', 'obsDt', 'Total', 'Observers',
                         'DistanceMi', 'durationHrs', 'Reason']

    sheet_info = {
        'sheet_name': 'Rarities',
        'data': df,
        'widths': column_widths,
        'to_center': columns_to_center,
        'to_hide': None
    }

    return sheet_info


def sheet_info_for_filers(df: pd.DataFrame) -> dict:
    # ['locId', 'Name', 'LocationName']
    column_widths = {
        'locId': 10, 'Name': 25, 'LocationName': 60
    }

    columns_to_center = ['locId']

    sheet_info = {
        'sheet_name': 'Filers',
        'data': df,
        'widths': column_widths,
        'to_center': columns_to_center,
        'to_hide': None
    }

    return sheet_info


def sheet_info_for_locations(df: pd.DataFrame) -> dict:
    # ['locId', 'Name', 'LocationName']
    column_widths = {
        'locId': 10, 'Name': 25, 'LocationName': 60
    }

    columns_to_center = ['locId']

    sheet_info = {
        'sheet_name': 'Filers',
        'data': df,
        'widths': column_widths,
        'to_center': columns_to_center,
        'to_hide': None
    }

    return sheet_info
