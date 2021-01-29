# from ebird_summary import create_ebird_summary

import re
import sys
import traceback
from typing import List, Tuple, Any, Optional, Dict

import pandas as pd

from utilities_excel import excel_columns
from parameters import Parameters
from taxonomy import Taxonomy
from write_final_checklist import write_final_checklist_spreadsheet


def extract_locid_from_colname(colname):
    mm = re.match(r'^(L[0-9]+)', colname)
    if mm:
        return mm.group(1)
    return None


def extract_obs_time_from_obsdt(obsdt):
    mm = re.match(r'^[0-9]{4}-[0-9]{2}-[0-9]{2} ([0-9]{2}:[0-9]{2})', obsdt)
    if mm:
        return mm.group(1)
    return None


def extract_obstime_from_colname(colname):
    mm = re.search(r'([0-9]{2}:[0-9]{2})', colname)
    if mm:
        return mm.group(1)
    return None


def index_of_first_subtotal_column(summary: pd.DataFrame):
    for ix, col in enumerate(summary.columns):
        mm = re.match(r'^(L[0-9]+)', col)
        if mm:
            return ix
    return None


def filter_additional_rare(taxonomy: Taxonomy, additional_rare: List[str]) -> List[str]:
    rare_species = []
    for cn in additional_rare:
        row = taxonomy.find_local_name_row(cn)
        if row is not None and row.Category == 'species':
            rare_species.append(cn)

    return rare_species


def reorder_team_columns(team_cols: List[str], std_columns: List[str]) -> List[str]:
    reordered_columns = std_columns.copy()
    # Each team_col is of the form
    # f'{row0.locId}-{row0.Name}-{obstime}-{row0.SectorName}-{subid}'

    team_col_re = re.compile(
        r'^(?P<locId>L[0-9]+)-(?P<name>.*)-(?P<obstime>[0-9]{2}:[0-9]{2})-'
        r'(?P<sector>.*)-(?P<subId>S[0-9]+)$'
    )
    team_headers = ['locId', 'name', 'obstime', 'sector', 'subId']

    try:
        xteam_cols = []
        for team_col in team_cols:
            mm = team_col_re.search(team_col)
            dd = dict(zip(team_headers, [mm.group(gid) for gid in team_headers]))
            xteam_cols.append(dd)
    except Exception as ee:
        print(team_col, team_cols, ee)
        traceback.print_exc(file=sys.stdout)
    # print(team_cols)

    team_cols_df = pd.DataFrame(xteam_cols).sort_values(by=['locId', 'obstime', 'name'])

    new_team_column_order = []
    for ix, row in team_cols_df.iterrows():
        col = f'{row.locId}-{row["name"]}-{row.obstime}-{row.sector}-{row.subId}'
        new_team_column_order.append(col)

    reordered_columns.extend(new_team_column_order)

    return reordered_columns


def create_row_for_missing_species(common_name: str,
                                   summary: pd.DataFrame,
                                   taxonomy: Taxonomy) -> Optional[Tuple[pd.Series, bool]]:
    # can also be SPUH, ISSF etc., just something that wasn't on official list
    # The number of columns may vary based on the checklist, but we fill
    # in the ones that we know must be there
    taxonomy_row = taxonomy.find_local_name_row(common_name)
    if taxonomy_row is None:  # i.e. not found, drop it
        return None

    new_row = pd.Series([''] * len(summary.columns), index=summary.columns)
    new_row['Group'] = taxonomy_row.SPECIES_GROUP
    new_row['CommonName'] = common_name
    new_row['TaxonOrder'] = taxonomy_row.TAXON_ORDER
    new_row['NACC_SORT_ORDER'] = taxonomy_row.NACC_SORT_ORDER
    new_row['ABA_SORT_ORDER'] = taxonomy_row.ABA_SORT_ORDER
    new_row['Category'] = taxonomy_row.Category
    # Filled in later. This is the "Grand Total", not the total from an individual checklist
    new_row['Total'] = 0

    # Not on official list, so mark it Rare if it's a species (not SPUH etc.)
    rarity = taxonomy_row.Category == 'species'
    if rarity:
        new_row['Rare'] = 'X'

    return new_row, rarity


def create_category_column(summary: pd.DataFrame, taxonomy: Taxonomy) -> list:
    categories = []
    for common_name in summary.CommonName.values:
        taxonomy_row = taxonomy.find_local_name_row(common_name)
        category = '' if taxonomy_row is None else taxonomy_row.Category
        categories.append(category)

    return categories


def create_personal_checklist_columns(sector_checklist_meta: pd.DataFrame) -> Dict[str, str]:
    # Instead of just subId, make a more descriptive column header name
    # df.rename(columns={"A": "a", "B": "c"})
    # Format is {locid}-{subid}-{obsdt}-{name}
    column_renames = {}
    for ix, row in sector_checklist_meta.iterrows():
        obstime = extract_obs_time_from_obsdt(row.obsDt)
        if obstime is None:
            obstime = '12:01'
        colname = f'{row.locId}-{row.subId}-{obstime}-{row.Name}'
        column_renames[row.subId] = colname

    return column_renames


def create_ebird_summary(summary_base: pd.DataFrame,
                         personal_checklists: pd.DataFrame,
                         checklist_meta: pd.DataFrame,
                         circle_abbrev,
                         parameters: Parameters,
                         sector_name: str,
                         taxonomy: Taxonomy,
                         output_path) -> Tuple[Any, List[str]]:
    # Each checklist becomes a column in the summary sheet
    # Start of big processing loop
    summary = summary_base.copy()
    # team_cols = set()
    summary_common_names = list(summary.CommonName.values)

    checklist_meta = checklist_meta.copy()[checklist_meta.sharing != 'secondary']
    checklist_meta.sort_values(by=['location_group', 'locId', 'obsDt', 'groupId', 'Name'],
                               na_position='first', inplace=True)

    sector_subids = list(personal_checklists.subId.values)
    sector_checklist_meta = checklist_meta[checklist_meta.subId.isin(sector_subids)]

    # Group	CommonName	Rare	Total	TaxonOrder	NACC_SORT_ORDER
    summary['FrozenTotal'] = 0  # placeholder

    if 'Category' not in summary.columns:
        summary['Category'] = create_category_column(summary, taxonomy)

    std_columns = ['Group', 'CommonName', 'Rare', 'Total', 'FrozenTotal',
                   'Category', 'TaxonOrder', 'NACC_SORT_ORDER', 'ABA_SORT_ORDER']
    summary = summary[std_columns]

    # Sector checklists may have added species not on the template
    # Add on rows for these new species
    additional_rare = []
    names_to_add = set(personal_checklists.CommonName.values) - set(summary_common_names)
    if not names_to_add == set():
        # print(f'Need to add: {names_to_add}')
        # blank_row = pd.Series([''] * len(summary.columns), index=summary.columns)
        rows_to_add = []
        for common_name in names_to_add:
            row_rarity = create_row_for_missing_species(common_name, summary, taxonomy)
            if row_rarity is None:
                continue
            row, rarity = row_rarity
            rows_to_add.append(row)
            if rarity:
                additional_rare.append(common_name)

        summary = summary.append(rows_to_add, ignore_index=True)
        summary_common_names.extend(list(names_to_add))

    # Re-sort by TaxonOrder
    # Sorting has to be done before we create any formulae for Totals
    summary = summary.sort_values(by=['NACC_SORT_ORDER']).reset_index(drop=True)

    # Use the order from checklist_meta and add a column to summary for each checklist
    # personal_columns = []
    for subid in sector_checklist_meta.subId.values:
        pcsub = personal_checklists[personal_checklists.subId == subid]
        species_totals = []
        for common_name in summary.CommonName.values:
            species_row = pcsub[pcsub.CommonName == common_name]
            species_total = 0 if species_row.empty else species_row.Total.values[0]
            species_totals.append(species_total)
        # Add the column to summary
        summary[subid] = species_totals

    # Don't think we need the filter any more, since that was done above
    rare_species = filter_additional_rare(taxonomy, additional_rare)
    if len(rare_species) > 0:
        print(f'   Requires rare bird form: {", ".join(rare_species)} [not on master list]')

    # Re-sort by TaxonOrder
    # Sorting has to be done before we create any formulae for Totals
    summary = summary.sort_values(by=['NACC_SORT_ORDER']).reset_index(drop=True)

    # We don't rename columns until right before we create Excel file
    team_cols = sector_checklist_meta.subId.values

    # The complexity here is because we can have cases where a single birder birded
    # near-duplicate locations. This means location_group is e.g. L13065376+L13065792
    # but each of these checklist should be considered separate (use SUM not MAX)
    # Example in CAMP 2020/Rancho San Carlos:
    # L13065376-S78154180-09:24-Jeff Manker | L13065792-S78156572-10:10-Jeff Manker |
    # L13065792-S78184574-10:44-Jeff Manker
    mask = sector_checklist_meta.location_group.isnull()
    usemaxtmp = sector_checklist_meta[~mask]
    single_birder_locids = set()
    for locgrp, grp in usemaxtmp.groupby(['location_group']):
        # print(locgrp)
        if len(set(grp.Name)) == 1:  # Same birder but possible location dups
            single_birder_locids |= set(grp.locId.values)
    mask_single = checklist_meta.locId.isin(single_birder_locids)

    mask |= mask_single
    use_sum_locids = sector_checklist_meta[mask].locId.values
    # Remove duplicates but keep in order
    use_max_locids = list(dict.fromkeys(sector_checklist_meta[~mask].locId.values))

    # These are the columns we can just total up
    use_sum_subids = sector_checklist_meta[sector_checklist_meta.locId.isin(use_sum_locids
                                                                            )].subId.values
    use_sum_total = summary[use_sum_subids].apply(pd.to_numeric).fillna(0).sum(axis=1).astype(int)

    use_max_total = 0
    # ToDo: logic is duplicated below
    for locid in use_max_locids:
        # subIds are the column names right now
        # subids = sector_checklist_meta[sector_checklist_meta.locId == locid].subId.values
        mask = [(lg.startswith(locid) if lg is not None else False) for lg in
                checklist_meta.location_group.values]
        subids = checklist_meta[mask].subId.values
        # This can be empty if it is not the first in a set of duplicate locations
        if len(subids) == 0:
            continue
        # print(locid, subids)
        max_vals = summary[subids].apply(pd.to_numeric).fillna(0).max(axis=1).astype(int)
        use_max_total += max_vals

    summary_total = use_sum_total + use_max_total
    # print(sum(summary_total))

    # Values computed by formulae are only evaluated after a workbook has been opened and
    # saved by Excel. This means if we create these files but never open them, the Total
    # field will show up as 0 (a string formula converted to numeric)
    # Add this so that service_merge/merge_checklists has an actual value to use
    # ToDo: fix summary_total to use SUM/MAX
    summary['FrozenTotal'] = summary_total

    # Actually, make it a formula
    # Has to be after sorting
    #     base_columns = ['Group', 'CommonName', 'Rare', 'Total', 'TaxonOrder']
    #     Group	CommonName	Rare	Total	Ad	Im	CountSpecial
    # =SUM($F5:$Q5)
    col_letters = excel_columns()
    # std_columns = ['Group', 'CommonName', 'Rare', 'Total', 'Category', 'TaxonOrder',
    #                'NACC_SORT_ORDER']
    sum_start_index = len(std_columns)
    sum_end_index = len(std_columns) + len(use_sum_locids) - 1
    sum_start_col = col_letters[sum_start_index]
    sum_end_col = col_letters[sum_end_index]
    # Start template for total with non-duplicate columns
    sum_formula_template = f'=SUM(${sum_start_col}INDEX:${sum_end_col}INDEX)'

    header_cell_groups = []
    max_formula_totals = []
    max_formula = None
    for locid in use_max_locids:
        # subIds are the column names right now
        # subids = sector_checklist_meta[sector_checklist_meta.locId == locid].subId.values
        mask = [(lg.startswith(locid) if lg is not None else False) for lg in
                checklist_meta.location_group.values]
        subids = checklist_meta[mask].subId.values
        # This can be empty if it is not the first in a set of duplicate locations
        if len(subids) == 0:
            continue
        max_start_index = list(summary.columns).index(subids[0])
        max_end_index = list(summary.columns).index(subids[-1])
        max_start_col = col_letters[max_start_index]
        max_end_col = col_letters[max_end_index]
        max_formula_template = f'MAX(${max_start_col}INDEX:${max_end_col}INDEX)'
        max_formula_totals.append(max_formula_template)
        # Collect up the header cells so we can color different groups
        header_cell_group = f'${max_start_col}1:${max_end_col}1'
        header_cell_groups.append(header_cell_group)

    if len(max_formula_totals):
        max_formula = '+'.join(max_formula_totals)

    total_formula = []
    for ix in range(2, summary.shape[0] + 2):
        sft = sum_formula_template.replace('INDEX', str(ix))
        tf_sum = f'{sft}'
        if max_formula is None:
            total_formula.append(tf_sum)
        else:
            mft = max_formula.replace('INDEX', str(ix))
            tf_max = f'{mft}'
            total_formula.append(tf_sum + '+' + tf_max)

    # print(f'    {total_formula[0]}')

    summary['Total'] = total_formula

    # Add last row for Total and each Sector total
    totals_row = pd.Series([''] * len(summary.columns), index=summary.columns)
    totals_row['Group'] = 'Totals'
    totals_row['TaxonOrder'] = 99999
    totals_row['NACC_SORT_ORDER'] = taxonomy.INVALID_NACC_SORT_ORDER
    totals_row['ABA_SORT_ORDER'] = taxonomy.INVALID_NACC_SORT_ORDER

    # Formula for Grand Total, e.g. =SUM($D$2:$D$245)
    total_col_letter = col_letters[std_columns.index('Total')]
    total_formula = f'=SUM(${total_col_letter}2:${total_col_letter}{summary.shape[0] + 1})'
    totals_row.Total = total_formula

    # sector_cols = [xs for xs in summary.columns if xs.startswith('Sector')]
    sector_totals = summary[team_cols].apply(pd.to_numeric).fillna(0).sum(axis=0).astype(int)
    for col, st in sector_totals.items():
        totals_row[col] = st

    summary = summary.append(totals_row, ignore_index=True)

    # Rename columns to more human readable form
    newcols = create_personal_checklist_columns(sector_checklist_meta)
    summary.rename(columns=newcols, inplace=True)

    # Don't hide 'Rare' since this will be frequently used in a filter
    cols_to_hide = ['D', 'Difficulty', 'Adult', 'Immature',
                    'W-morph', 'B-Morph', 'Ad', 'Im', 'CountSpecial', 'FrozenTotal']
    cols_to_highlight = list(set(summary.columns) & {'Total', 'Adult/White', 'Immature/Blue'})

    outname = output_path / f'{circle_abbrev}-EBird-Summary-{sector_name}.xlsx'
    write_final_checklist_spreadsheet(summary, outname,
                                      parameters.parameters,
                                      additional_sheets=None,
                                      cols_to_hide=cols_to_hide,
                                      cols_to_highlight=cols_to_highlight,
                                      header_cell_groups=header_cell_groups
                                      )

    return summary, rare_species
