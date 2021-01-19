from typing import List, Any, Union, Dict, Tuple
import pandas as pd
import sys
import traceback
import re

from utilities_cbc import read_excel_or_csv_path
from common_paths import *
from taxonomy import Taxonomy
from local_translation_context import LocalTranslationContext
from text_transform import clean_common_names

from write_final_checklist import write_final_checklist_spreadsheet, \
    recombine_transformed_checklist, excel_columns
from parameters import Parameters



# mergable_filetypes = ['.xlsx', '.csv']
# possible_paths = {px.resolve() for px in Path(merge_inputs_path).glob("*") if
#                   px.suffix in mergable_filetypes and not px.stem.startswith('~$')}
#
# for fpath in possible_paths:
#     if 'template' in fpath.stem:
#         template_path = fpath
#         circle_abbrev, sector_id = circle_and_sector_abbrev_from_path(fpath)
#         print(
#             f'Using {fpath.stem} as template for circle summary file; circle: {circle_abbrev}')
#

# stem_to_colname is dict of fstem to column name
# e.g. {'CASJ-EBird-Summary-Agnews.xlsx' : '01-Agnews'}
# output_path e.g. reports_path / f'{circle_abbrev}-Summary.xlsx'
def merge_files(xinputs_merge_path: Path,
                taxonomy: Taxonomy,
                local_translation_context,
                prefix_to_strip=None):
    allowable_filetypes = ['.xlsx', '.csv']
    files_to_merge = []

    for fpath in xinputs_merge_path.glob('*'):
        if fpath.stem.startswith('~$') or fpath.stem.startswith('.') or \
                not fpath.suffix in allowable_filetypes:
            # system file or Excel tempfile or not CSV/Excel
            continue
        files_to_merge.append(fpath)

    # Must have at least two files to merge
    # Arbitrarily pick first as template
    if len(files_to_merge) < 2:
        print(f'Nothing to merge in {xinputs_merge_path}')
        return

    files_to_merge = sorted(files_to_merge)
    template_path, *other_paths = files_to_merge
    print(f'Using {template_path} as template')

    # Create some column names
    stem_to_colname = {}
    for ix, fpath in enumerate(other_paths):
        stem = fpath.stem.replace(prefix_to_strip, '') if prefix_to_strip else fpath.stem
        # Does it already have leading digits?
        mm = re.match(r'^([0-9]+-)', stem)
        col_name = stem if mm else f'{ix + 1:02d}-{stem}'
        stem_to_colname[fpath.stem] = col_name
        # could use compute_hash(txt, length=6):

    mcl = merge_checklists(template_path, other_paths, stem_to_colname,
                           taxonomy, local_translation_context)

    return mcl


def merge_checklists(summary_base: Any,
                     sector_files: List[Any],
                     stem_to_colname: Union[dict, List[str]],
                     taxonomy: Taxonomy,
                     local_translation_context: LocalTranslationContext,
                     ) -> Tuple[pd.DataFrame, List[str], List[str]]:
    # Easier to use single column summary_base, but this will transform it if needed
    if isinstance(summary_base, Path):
        template = read_excel_or_csv_path(summary_base)
        # Create a single column master for summary
        summary_base = recombine_transformed_checklist(template, taxonomy)
    elif isinstance(summary_base, pd.DataFrame):
        summary_base = summary_base

    base_has_adult_col = 'Ad' in summary_base.columns
    base_has_immature_col = 'Im' in summary_base.columns
    has_adult_col = False
    has_immature_col = False

    # Start of big processing loop
    summary = summary_base.copy()
    sector_unique = 1
    sector_cols = []
    for idx, fpath in enumerate(sector_files):
        try:
            if isinstance(fpath, Path):
                sector_col = stem_to_colname.get(fpath.stem, None)
            else:
                sector_col = stem_to_colname[idx]
        except Exception as ee:
            print(ee, idx, fpath)
            sector_col = None

        if not sector_col:
            sector_col = f'X{sector_unique}'
            sector_unique += 1

        sector_cols.append(sector_col)
        print(f'Processing {sector_col}')

        summary_common_names = summary.CommonName.values
        summary_common_names_lower = [xs.lower() for xs in summary_common_names]
        if isinstance(fpath, Path):
            checklist = read_excel_or_csv_path(fpath)
            # Only Excel files would be double column. CSV files could be hand made,
            # so clean them up. Double translation takes a long time, so avoid when
            # possible
            if fpath.suffix == '.xlsx':
                checklist = recombine_transformed_checklist(checklist, taxonomy)
            else:
                cleaned_common_names = clean_common_names(checklist.CommonName,
                                                          taxonomy, local_translation_context)
                checklist.CommonName = cleaned_common_names
            # print(checklist.Total)
            xdtypes = {'CommonName': str, 'Total': int}
            checklist = checklist.astype(dtype=xdtypes)

            # so = pd.to_numeric(summary.NACC_SORT_ORDER, errors='coerce')
            # summary.NACC_SORT_ORDER = pd.Series(so).fillna(taxonomy.INVALID_NACC_SORT_ORDER)

        else:  # isinstance(summary_base, pd.DataFrame):
            checklist = fpath

        # Drop any rows with a blank CommonName. This can occur if the checklist is a summary
        # report with a 'Total' row at the bottom, and 'Total' is not a valid species
        checklist = checklist[checklist.CommonName != '']

        # Sector checklists may have added species not on the template
        checklist['cnlower'] = [xs.lower() for xs in checklist.CommonName]
        checklist_common_names_lower = set([xs.lower() for xs in checklist.CommonName])
        names_to_add = checklist_common_names_lower - set(summary_common_names_lower)
        if not names_to_add == set():
            species_to_add = taxonomy.filter_species(list(names_to_add))
            if len(species_to_add) > 0:
                print(f'Added species: {species_to_add}')
            # Fix capitalization
            names_to_add = clean_common_names(names_to_add, taxonomy, local_translation_context)
            blank_row = pd.Series([''] * len(summary.columns), index=summary.columns)
            rows_to_add = []
            for cn in names_to_add:
                row = blank_row.copy()
                row['CommonName'] = cn
                if cn.lower() in species_to_add:
                    row['Rare'] = 'X'
                total = checklist[checklist.cnlower == cn.lower()]['Total'].values[0]
                row[sector_col] = total
                rows_to_add.append(row)

            summary = summary.append(rows_to_add, ignore_index=True)

        #
        has_adult_col = 'Ad' in checklist.columns
        has_immature_col = 'Im' in checklist.columns

        summary[sector_col] = 0  # 'Total' field for this sector

        if has_adult_col:
            ad_col = f'Ad-{sector_col}'
            summary[ad_col] = 0

        if has_immature_col:
            im_col = f'Im-{sector_col}'
            summary[im_col] = 0

        # # S
        # # Fill in total for existing names
        # already_present_names = set(summary_common_names) & set(checklist.CommonName)
        # for cn in set(checklist.CommonName):
        #     total = checklist[checklist.CommonName == cn]['Total'].values[0]
        #     summary.loc[summary.CommonName == cn, sector_col] = total

        # print(summary.shape, len(summary_common_names_lower))
        summary_common_names_lower = [xs.lower() for xs in summary.CommonName]

        summary['cnlower'] = summary_common_names_lower
        for ix, row in checklist.iterrows():
            # if row.Total:
            #     print(row)
            total = row.FrozenTotal if 'FrozenTotal' in checklist.columns else row.Total
            mask = summary.cnlower == row.cnlower
            summary.loc[mask, sector_col] = total

        summary.drop(['cnlower'], axis=1, inplace=True)
        #     if has_adult_col:
        #         adult_total = checklist[checklist.CommonName == cn]['Ad'].values[0]
        #         summary.loc[summary.CommonName == cn, ad_col] = adult_total
        #
        #     if has_immature_col:
        #         immature_total = checklist[checklist.CommonName == cn]['Im'].values[0]
        #         summary.loc[summary.CommonName == cn, im_col] = immature_total

    # Fill in zeros for missing sector_col values; may have blanks if species added
    # for col in sector_cols:
    #     summary[col] = summary[col].apply(pd.to_numeric).fillna(0)

    # Do sums for Ad/Im columns. Ad == 'Adult/White'
    if base_has_adult_col:
        ad_cols = [xs for xs in summary.columns if xs.startswith('Ad-')]
        summary['Ad'] = summary[ad_cols].apply(pd.to_numeric).fillna(0).sum(axis=1).astype(int)

    if base_has_immature_col:
        im_cols = [xs for xs in summary.columns if xs.startswith('Im-')]
        summary['Im'] = summary[im_cols].apply(pd.to_numeric).fillna(0).sum(axis=1).astype(int)

    # Look up Group and TaxonOrder for anything missing these (may have been added species)

    for idx, row in summary.iterrows():
        record = taxonomy.find_local_name_row(row['CommonName'])
        if record is not None:
            summary.at[idx, 'TaxonOrder'] = record.TAXON_ORDER
            summary.at[idx, 'Group'] = record.SPECIES_GROUP
            so = record.NACC_SORT_ORDER if record.NACC_SORT_ORDER != 0 else \
                taxonomy.INVALID_NACC_SORT_ORDER
            summary.at[idx, 'NACC_SORT_ORDER'] = so
            summary.at[idx, 'Category'] = record.Category

    # Re-sort by TaxonOrder
    # Must sort before creating formulae for Total
    so = pd.to_numeric(summary.NACC_SORT_ORDER, errors='coerce')
    summary.NACC_SORT_ORDER = pd.Series(so).fillna(taxonomy.INVALID_NACC_SORT_ORDER)

    try:
        summary = summary.sort_values(by=['NACC_SORT_ORDER']).reset_index(drop=True)
    except TypeError as te:
        print(te)
        traceback.print_exc(file=sys.stdout)
        return summary

    # Now set the overall total field:
    #     sector_cols = [xs for xs in summary.columns if xs.startswith('Sector')]
    # summary['Total'] = summary[sector_cols].apply(pd.to_numeric).fillna(0).sum(axis=1).astype(int)

    col_letters = excel_columns()
    #     team_start_col = col_letters[len(base_columns)]
    std_columns = ['Group', 'CommonName', 'Rare', 'Total', 'Category', 'TaxonOrder',
                   'NACC_SORT_ORDER']
    # team_start_col = col_letters[index_of_first_subtotal_column(summary)]
    sector_start_col = col_letters[len(std_columns)]
    sector_end_col = col_letters[len(summary.columns) - 1]
    total_formula = [f'=SUM(${sector_start_col}{ix}:${sector_end_col}{ix})' for ix in
                     range(2, summary.shape[0] + 2)]
    summary['Total'] = total_formula

    # Add last row for Total and each Sector total
    totals_row = pd.Series([''] * len(summary.columns), index=summary.columns)
    totals_row['Group'] = 'Totals'
    totals_row['TaxonOrder'] = 99999
    totals_row['NACC_SORT_ORDER'] = taxonomy.INVALID_NACC_SORT_ORDER

    # Formula for Grand Total, e.g. =SUM($D$2:$D$245)
    total_col_letter = col_letters[std_columns.index('Total')]
    total_formula = f'=SUM(${total_col_letter}2:${total_col_letter}{summary.shape[0] + 1})'
    totals_row.Total = total_formula

    # sector_cols = [xs for xs in summary.columns if xs.startswith('Sector')]
    sector_totals = summary[sector_cols].apply(pd.to_numeric).fillna(0).sum(axis=0).astype(int)
    for col, st in sector_totals.items():
        totals_row[col] = st

    summary = summary.append(totals_row, ignore_index=True)

    cols_to_drop = [col for col in summary.columns if
                    (col.startswith('Ad-') or col.startswith('Im-'))]
    summary.drop(labels=cols_to_drop, axis=1, inplace=True)

    summary.rename(columns={'Ad': 'Adult/White', 'Im': 'Immature/Blue'}, inplace=True)

    # Re-order columns
    # print(sector_cols)
    # print(summary.columns)

    new_col_order = ['Group', 'CommonName', 'Rare', 'Total',
                     'Category', 'TaxonOrder', 'NACC_SORT_ORDER']
    new_col_order.extend(sector_cols)
    summary = summary[new_col_order]

    # Don't hide 'Rare' since this will be frequently used in a filter
    cols_to_hide = ['D', 'Difficulty', 'Adult', 'Immature',
                    'W-morph', 'B-Morph']

    if 'Adult/White' in summary.columns:
        if summary['Adult/White'].apply(pd.to_numeric).fillna(0).sum() == 0:
            cols_to_hide.append('Adult/White')
    if 'Immature/Blue' in summary.columns:
        if summary['Immature/Blue'].apply(pd.to_numeric).fillna(0).sum() == 0:
            cols_to_hide.append('Immature/Blue')

    cols_to_highlight = list(set(summary.columns) & {'Total', 'Adult/White', 'Immature/Blue'})

    return summary, cols_to_hide, cols_to_highlight
# Still to do:
# - Write requirements: I think input files need only have Total and CommonName columns,
# # template also needs Rare
