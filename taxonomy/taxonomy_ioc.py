# taxonomy_ioc
# from taxonomy_ioc import TaxonomyIOC

import re
from pathlib import Path

import numpy as np
import pandas as pd

# Base Path
from singleton_decorator import singleton

"""
Note:
tt[(tt.TAXON_ORDER != tt.Clem_Seq) & (tt.Clem_Seq != '')] is empty, i.e. for records
with Clem_Seq, it matches TAXON_ORDER
"""

"""
Notes on reference sources

The base used for the taxonomy is the eBird/Clements taxonomy, for three main reasons.
- It will match up with species reported through eBird
- It has the taxon_order field for sorting
- It contains hybrids and SPUH entries

This file is only for pre-processing the Sargeant comparison file for later merging with
the Clements taxonomy.

--------------------------------------------------------------------------------

https://www.worldbirdnames.org/new/
Gill F, D Donsker & P Rasmussen  (Eds). 2020. IOC World Bird List (v10.2). 
doi :  10.14344/IOC.ML.10.2.

https://www.worldbirdnames.org/new/ioc-lists/master-list-2/

Comparison of IOC 10.2 with Clements 2019 (Dave Sargeant)
    http://www.worldbirdnames.org/IOC%20v10-2%20v%20Clements%202019.xlsx
    This is the one we use for IOC as it has both Clements and IOC sequence numbers. This is
    also the only one on this site with "tidy" data suitable for data science
--------------------------------------------------------------------------------

https://www.worldbirdnames.org/ioc-lists/range-terminology/
North  America (NA)–includes the Caribbean
Middle  America (MA)—Mexico through Panama
Atlantic, Pacific, Indian, Tropical, Temperate, Northern & Southern Oceans 
(AO, PO, IO, TrO, TO, NO, SO)

"""


@singleton
class TaxonomyIOC(object):
    """ Taxonomy from IOC

    Attributes:
     """

    def __init__(self):
        taxonomy_base_path = Path(__file__).parent.absolute()
        self.taxonomy_reference_path = taxonomy_base_path / 'reference'
        # North America, Middle America, Pacific Ocean, Atlantic Ocean
        self._ranges_to_keep = {'NA', 'MA', 'PO', 'AO'}
        self.range_pattern = re.compile('^([^:]+)')

        self._ioc_taxonomy_path = self.taxonomy_reference_path / 'IOC_v10-2_v_Clements_2019.xlsx'
        # https://stackoverflow.com/questions/60288732/pandas-read-excel-returns-pendingdeprecationwarning
        self.ioc_taxonomy = pd.read_excel(self._ioc_taxonomy_path, engine="openpyxl")

        # Rename columns with some sanity
        newcols = [
            'ioc_seq', 'ioc_scientific_name', 'ioc_common_name',
            'ioc_range', 'ioc_s',
            'ioc_c', 'ioc_degree_of_match', 'ioc_clements_seq',
            'ioc_clements_scientific_name',
            'ioc_clements_common_name', 'ioc_authority'
        ]

        # ioc_degree_of_match is sum of 'ioc_s' + 'ioc_c'
        self.ioc_taxonomy.columns = newcols

        # For use in main Taxonomy class; some columns not helpful in main taxonomy
        # Columns are also re-ordered for convenience
        self.columns_to_keep = [
            'ioc_seq', 'ioc_scientific_name', 'ioc_common_name',
            'ioc_clements_seq', 'ioc_clements_scientific_name', 'ioc_clements_common_name',
            'ioc_range'
        ]

        colnames_numerics_only = self.ioc_taxonomy.select_dtypes(include=np.number).columns.tolist()
        fill_values = {col: 0 if col in colnames_numerics_only else ''
                       for col in self.ioc_taxonomy.columns}
        self.ioc_taxonomy.fillna(fill_values, inplace=True)

        for col in colnames_numerics_only:
            self.ioc_taxonomy[col] = self.ioc_taxonomy[col].astype(int)

        # self.range_pattern = re.compile('^([^:]+)')
        # self.taxonomy_with_ioc = self.merge_ioc_into_taxonomy(self.taxonomy)
        # # Subset of taxonomy restricted to birds in ranges_to_keep
        # #    (North America, Middle America, Altantic Ocean, Pacific Ocean)
        # self.taxonomy_restricted = self.taxonomy_with_ioc.copy()[
        #     self.taxonomy_with_ioc.IOC_Range.apply(self.restricted_range)]

    def get_taxonomy(self) -> pd.DataFrame:
        return self.ioc_taxonomy[self.columns_to_keep]

    def get_taxonomy_full(self) -> pd.DataFrame:
        return self.ioc_taxonomy

    def restricted_range(self, test_range) -> bool:
        rx = False
        mm = re.search(self.range_pattern, test_range)
        if mm:
            just_range = [xs.strip() for xs in mm.group(1).split(',')]
            rx = len(set(just_range) & set(self._ranges_to_keep)) > 0

        return rx
