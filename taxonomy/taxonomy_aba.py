# taxonomy_aba
# from taxonomy_aba import TaxonomyABA

import re
from pathlib import Path

import numpy as np
import pandas as pd

# Base Path
from singleton_decorator import singleton

from typing import Optional

"""
--------------------------------------------------------------------------------
ABA  8.0.7 https://www.aba.org/aba-checklist/ January 2021
	ABA_Checklist-8.0.7.csv


--------------------------------------------------------------------------------
"""

@singleton
class TaxonomyABA(object):
    """ Taxonomy from ABA

    Attributes:
     """

    def __init__(self):
        taxonomy_base_path = Path(__file__).parent.absolute()
        self.taxonomy_reference_path = taxonomy_base_path / 'reference'

        self.INVALID_ABA_SORT_ORDER = 999999.1

        self._aba_taxonomy_path = self.taxonomy_reference_path / 'ABA_Checklist-8.0.7.csv'
        xheader = None
        self.aba_taxonomy = pd.read_csv(self._aba_taxonomy_path, dtype=str, header=xheader,
                                   low_memory=False, skiprows=3).fillna('')
        self.aba_taxonomy.columns = ['aba_'+xs for xs in ['Group', 'common_name', 'nom_commun',
                                           'scientific_name', 'code4', 'v5']]
        # Get rid of all the "Group" rows
        self.aba_taxonomy[self.aba_taxonomy.aba_common_name != ''].reset_index(drop=True)
        self.aba_taxonomy.drop(columns=['aba_Group', 'aba_v5'], inplace=True)

        # Add ordering column
        # AOS/AOU ordering seems to be the literal order in the checklist, not the id
        self.aba_taxonomy['ABA_SORT_ORDER'] = list(self.aba_taxonomy.index.astype(int))

        # add lower case column for faster lookups
        self.aba_taxonomy['aba_common_name_lower'] = \
            self.aba_taxonomy.aba_common_name.apply(lambda xs: xs.lower())


    def get_taxonomy(self) -> pd.DataFrame:
        return self.aba_taxonomy

    def find_local_name_row(self, local_name) -> Optional[pd.Series]:
        # Look for exact matches and return a single record
        if not local_name:
            return None

        record = None
        try:
            local_name_lower = local_name.lower()
            mask =  self.aba_taxonomy.nacc_common_name_lower == local_name_lower
            records = self.aba_taxonomy[mask]
            # there should only be one
            record = records.iloc[0]

        except IndexError:
            pass

        return record

