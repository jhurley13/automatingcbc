# taxonomy_clements
# from taxonomy_clements import TaxonomyClements

import re
from pathlib import Path

import numpy as np
import pandas as pd

# Base Path
from singleton_decorator import singleton

"""
This file only processes "eBird Taxonomy v2019" as described below.
--------------------------------------------------------------------------------

Suggested citation for the current version of the Clements Checklist, including the August 2019 
Updates and Corrections:

Clements, J. F., T. S. Schulenberg, M. J. Iliff, S. M. Billerman, T. A. Fredericks, B. L. Sullivan, 
and C. L. Wood. 2019. The eBird/Clements Checklist of Birds of the World: v2019. Downloaded from 
https://www.birds.cornell.edu/clementschecklist/download/ 

https://www.birds.cornell.edu/clementschecklist/download/
Three checklists are available. The first is the 2019 edition of the Clements Checklist (Clements 
Checklist v2019); the second is the 2019 edition of the eBird taxonomy (eBird v2019); and the third 
is the “master” or integrated checklist, which includes all entries in both the Clements Checklist 
and the eBird taxonomy.

clements_base = 'https://www.birds.cornell.edu/clementschecklist/wp-content/uploads/2019/08'
Clements Checklist v2019: 
    {clements_base}/Clements-Checklist-v2019-August-2019.xlsx
eBird Taxonomy v2019: 
    {clements_base}/eBird_Taxonomy_v2019.xlsx
eBird/Clements Checklist v2019: 
    {clements_base}/eBird-Clements-v2019-integrated-checklist-August-2019.xlsx
--------------------------------------------------------------------------------
"""


@singleton
class TaxonomyClements(object):
    """ Taxonomy from NACC

    Attributes:
     """

    def __init__(self):
        taxonomy_base_path = Path(__file__).parent.absolute()
        self.taxonomy_reference_path = taxonomy_base_path / 'reference'
        self._taxonomy_path = self.taxonomy_reference_path / 'eBird_Taxonomy_v2019.xlsx'
        self._taxonomy = pd.read_excel(self._taxonomy_path, engine="openpyxl")

        # ['TAXON_ORDER', 'CATEGORY', 'SPECIES_CODE', 'PRIMARY_COM_NAME',
        #  'SCI_NAME', 'ORDER1', 'FAMILY', 'SPECIES_GROUP', 'REPORT_AS']

        # The taxonomy only shows SPECIES_GROUP for first species in group so do a "Fill Down"
        self._taxonomy['SPECIES_GROUP'] = self._taxonomy.SPECIES_GROUP.fillna(method='ffill')

        # For use in main Taxonomy class; some columns not helpful in main taxonomy
        # Columns may also be re-ordered for convenience
        # Here we keep all columns
        self.columns_to_keep = self._taxonomy.columns

    def get_taxonomy(self) -> pd.DataFrame:
        return self._taxonomy[self.columns_to_keep]

    def get_taxonomy_full(self) -> pd.DataFrame:
        return self._taxonomy
