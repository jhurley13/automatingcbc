# taxonomy_ioc
# from taxonomy_nacc import TaxonomyNACC

import re
from pathlib import Path

import numpy as np
import pandas as pd

# Base Path
from singleton_decorator import singleton

from typing import Optional

"""
--------------------------------------------------------------------------------
http://checklist.americanornithology.org
http://checklist.americanornithology.org/taxa.xls?type=charset%3Dutf-8%3Bsubspecies%3Dno%3B
This downloads "NACC_list_species.xls". To allow the xlsxwriter package to process this, change
the name of the avibase_id column to "avibase_id" and save as an "Excel Workbook (.xlsx)".

--------------------------------------------------------------------------------
"""


@singleton
class TaxonomyNACC(object):
    """ Taxonomy from NACC

    Attributes:
     """

    def __init__(self):
        taxonomy_base_path = Path(__file__).parent.absolute()
        self.taxonomy_reference_path = taxonomy_base_path / 'reference'
        # North America, Middle America, Pacific Ocean, Atlantic Ocean
        self._ranges_to_keep = {'NA', 'MA', 'PO', 'AO'}
        self.range_pattern = re.compile('^([^:]+)')
        self.INVALID_NACC_SORT_ORDER = 999999.1

        self._nacc_taxonomy_path = self.taxonomy_reference_path / 'NACC_list_species-u.xlsx'

        # https://stackoverflow.com/questions/60288732/pandas-read-excel-returns-pendingdeprecationwarning
        self.nacc_taxonomy = pd.read_excel(self._nacc_taxonomy_path, engine="openpyxl")

        # Rename columns with nacc_ prefix
        newcols = {}
        for col in self.nacc_taxonomy.columns:
            newcols[col] = f'nacc_{col}'

        self.nacc_taxonomy.rename(columns=newcols, inplace=True)

        # Add ordering column
        # AOS/AOU ordering seems to be the literal order in the checklist, not the id
        self.nacc_taxonomy['NACC_SORT_ORDER'] = list(self.nacc_taxonomy.index.astype(int))

        # add lower case column for faster lookups
        self.nacc_taxonomy['nacc_common_name_lower'] = \
            self.nacc_taxonomy.nacc_common_name.apply(lambda xs: xs.lower())

        self.columns_to_keep = [
            'NACC_SORT_ORDER',
            'nacc_id', 'nacc_avibase_id', 'nacc_rank', 'nacc_common_name',
            'nacc_order', 'nacc_family', 'nacc_subfamily', 'nacc_genus', 'nacc_species',
            'nacc_common_name_lower'
        ]

        # For use in main Taxonomy class; some columns not helpful in main taxonomy
        # Columns are also re-ordered for convenience
        # self.nacc_taxonomy = self.nacc_taxonomy[columns_to_keep]

        colnames_numerics_only = \
            self.nacc_taxonomy.select_dtypes(include=np.number).columns.tolist()
        fill_values = {col: 0 if col in colnames_numerics_only else ''
                       for col in self.nacc_taxonomy.columns}
        self.nacc_taxonomy.fillna(fill_values, inplace=True)

        for col in colnames_numerics_only:
            self.nacc_taxonomy[col] = self.nacc_taxonomy[col].astype(int)

    def get_taxonomy(self) -> pd.DataFrame:
        return self.nacc_taxonomy[self.columns_to_keep]

    def get_taxonomy_full(self) -> pd.DataFrame:
        return self.nacc_taxonomy

    def find_local_name_row(self, local_name) -> Optional[pd.Series]:
        # Look for exact matches and return a single record
        if not local_name:
            return None

        record = None
        try:
            local_name_lower = local_name.lower()
            mask =  self.nacc_taxonomy.nacc_common_name_lower == local_name_lower
            records = self.nacc_taxonomy[mask]
            # there should only be one
            record = records.iloc[0]

        except IndexError:
            pass

        return record

