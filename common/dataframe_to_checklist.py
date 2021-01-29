import pandas as pd
from text_transform import secondary_species_processing, pre_process_line
from parse_tally_sheets import strip_off_scientific_names
from taxonomy_token_identify import TaxonomyTokenIdentify
from spacy_extra import filter_to_possibles
from taxonomy import Taxonomy
from local_translation_context import LocalTranslationContext
from typing import Optional, Tuple
import re

from text_transform import clean_common_names

cn_names = ['CommonName', 'Common Name', 'species', 'SPECIES', 'Species']
total_names = ['Total', 'total', 'Number']


def get_species_from_dataframe(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    species, totals = None, None

    species_col_num = list(df.columns.isin(cn_names)).index(True)
    xspecies = df.iloc[0:, species_col_num:species_col_num + 1]
    species_is_blank = [sp == '' for sp in xspecies.values]
    species = xspecies[0:species_is_blank.index(True)].reset_index(drop=True)

    # Now look for the Total field
    total_names = ['Total', 'total', 'Number']
    if 'FrozenTotal' in df.columns:
        totals = df.loc[0:species_is_blank.index(True), 'FrozenTotal':'FrozenTotal']
    elif any(df.columns.isin(total_names)):
        totals_col_num = list(df.columns.isin(total_names)).index(True)
        # Totals might have zeros/blanks, so assume same length as species
        totals = df.iloc[0:species_is_blank.index(True), totals_col_num:totals_col_num + 1]

    return species, totals

def find_species_in_dataframe(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    species, totals = None, None
    numeric_columns = list(range(df.shape[1]))
    species_row = df[df.isin(cn_names).any(axis=1)].iloc[0]  # First occurence
    species_row_num = species_row.name

    mask = [cn in cn_names for cn in species_row.values]
    species_col_num = numeric_columns[mask.index(True)]

    xspecies = df.iloc[species_row_num + 1:, species_col_num:species_col_num + 1]
    species_is_blank = [sp == '' for sp in xspecies.values]
    species = xspecies[0:species_is_blank.index(True)].reset_index(drop=True)

    # Now look for the Total field
    totals_row = df[df.isin(total_names).any(axis=1)].iloc[0]  # First occurence
    totals_row_num = totals_row.name
    mask = [cn in total_names for cn in totals_row.values]
    totals_col_num = numeric_columns[mask.index(True)]

    # Totals might have zeros/blanks, so assume same length as species
    #
    xtotals = df.iloc[totals_row_num + 1:, totals_col_num:totals_col_num + 1]
    # totals_is_blank = [sp=='' for sp in xtotals.values]
    totals = xtotals[0:species_is_blank.index(True)].reset_index(drop=True)

    return species, totals

def sanitize_total(xt):
    # Can also find annotations such as "CW", "Miss" etc.
    if not isinstance(xt, str):
        return xt

    rgx = re.compile(r'[^0-9,\.]')
    if rgx.match(xt) is not None:
        return 0

    return xt.replace(',', '')

def dataframe_to_checklist(df: pd.DataFrame, taxonomy: Taxonomy,
                           local_translation_context: LocalTranslationContext):
    # Try to find the start of the species list
    if any(df.columns.isin(cn_names)):
        species, xtotals = get_species_from_dataframe(df)
    else:
        species, xtotals = find_species_in_dataframe(df)

    xtotals.columns = ['Total']
    xtotals['Total'] = xtotals['Total'].apply(sanitize_total).apply(
        pd.to_numeric, errors='raise').fillna(0).astype(int)

    results = pd.concat([species, xtotals], axis=1)
    results.columns = ['CommonNameOrig', 'Total']

    # tx_results = results[results.Total > 0].copy().reset_index(drop=True)
    tx_results = results.copy().reset_index(drop=True)

    tx_results.CommonNameOrig = tx_results.CommonNameOrig.fillna('')
    t2 = strip_off_scientific_names([secondary_species_processing(pre_process_line(line)
                                                                  ) for line in
                                     tx_results.CommonNameOrig.values], taxonomy)
    tx_results['BasicTx'] = t2
    tx_results['TaxonomyLookup'] = [get_common_name(cn, taxonomy) for cn in t2]
    tx_results['LocalTx'] = ''

    # See if we can fix the null common names with a translation
    null1 = tx_results[tx_results.TaxonomyLookup.isnull()]
    if len(null1.index):
        t3 = [local_translation_context.apply_translations(line.lower(), True)[0] for line in
              null1.BasicTx]
        tx_results.at[null1.index, 'LocalTx'] = t3
        tx_results.at[null1.index, 'TaxonomyLookup'] = [get_common_name(cn, taxonomy) for cn in t3]

    # Do one more translation round
    null2 = tx_results[tx_results.TaxonomyLookup.isnull()]
    if len(null2.index):
        t4 = [local_translation_context.apply_translations(line.lower(), True)[0] for line in
              null2.LocalTx]
        tx_results.at[null2.index, 'TaxonomyLookup'] = [get_common_name(cn, taxonomy) for cn in t4]

    null3 = tx_results[tx_results.TaxonomyLookup.isnull()]
    if len(null3.index):
        common_names = []
        for ix in null3.index:
            base_species = find_base_species(tx_results, ix, taxonomy)
            cn = tx_results.iloc[ix].CommonNameOrig.strip()
            # print(cn)
            # Just use basic species
            if cn in ['(immature)', '(form unidentified)']:
                # print(ix)
                common_names.append(base_species)
            else:
                # This is a variant of base
                cn2 = f'{base_species} {cn}'
                common_names.append(get_common_name(cn2, taxonomy))

        tx_results.at[null3.index, 'TaxonomyLookup'] = common_names

    no_translations = tx_results[tx_results.TaxonomyLookup.isnull()]
    if not no_translations.empty:
        print('No translation found for:')
        display(tx_results[tx_results.TaxonomyLookup.isnull()])

    tx_results['CommonName'] = clean_common_names(tx_results.TaxonomyLookup.values,
                                                  taxonomy, local_translation_context)
    tx_results.drop(columns=['BasicTx', 'TaxonomyLookup',
                             'LocalTx', 'CommonNameOrig'], inplace=True)
    tx_results = tx_results[['CommonName', 'Total']]

    # display(tx_results[tx_results.CommonName == ''])

    # We may have 'Bald Eagle', 'Bald Eagle (Adult)', 'Bald Eagle (Immature)',
    # which will end up as three entries for 'Bald Eagle'. Add up the totals and
    # collapse to one row
    tx_results = tx_results.groupby(['CommonName'], as_index=False).agg('sum')

    # Drop anything without a CommonName
    tx_results = tx_results[tx_results.CommonName != ''].reset_index(drop=True)

    return tx_results


def get_common_name(cn, taxonomy):
    row = taxonomy.find_local_name_row(cn)
    return row.comName if row is not None else None


def find_base_species(tx_results, unknown_idx, taxonomy):
    while unknown_idx > 0:
        tl = tx_results.iloc[unknown_idx].TaxonomyLookup
        if tl is not None:
            row = taxonomy.find_local_name_row(tl)
            return row.comName if row.Category == 'species' else taxonomy.report_as(tl)
        unknown_idx -= 1
    return None
