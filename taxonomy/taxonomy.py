# taxonomy
# from taxonomy import Taxonomy

import sys
import traceback
from pathlib import Path
from typing import Tuple, Optional, Any, List
from IPython.display import display

# https://pandas.pydata.org/pandas-docs/stable/user_guide/categorical.html
from pandas.api.types import CategoricalDtype

import numpy as np
import pandas as pd
from singleton_decorator import singleton
import numbers

from ebird_extras import EBirdExtra
from taxonomy_clements import TaxonomyClements
from taxonomy_ioc import TaxonomyIOC
from taxonomy_nacc import TaxonomyNACC

# Base Path


"""
https://ebird.org/science/the-ebird-taxonomy  
Spuh:  Genus or identification at broad level, e.g., swan sp. Cygnus sp.

Slash: Identification to Species-pair, e.g., Tundra/Trumpeter Swan Cygnus
columbianus/buccinator

Species: e.g., Tundra Swan Cygnus columbianus

ISSF or Identifiable Sub-specific Group: Identifiable subspecies or group of
subspecies, e.g., Tundra Swan (Bewick’s) Cygnus columbianus bewickii or Tundra
Swan (Whistling) Cygnus columbianus columbianus

Hybrid: Hybrid between two species, e.g., Tundra x Trumpeter Swan (hybrid)

Intergrade: Hybrid between two ISSF (subspecies or subspecies groups), e.g.,
Tundra Swan (Whistling x Bewick’s) Cygnus columbianus columbianus x bewickii

Domestic: Distinctly-plumaged domesticated varieties that may be free-flying
(these do not count on personal lists) e.g., Mallard (Domestic type)

Form: Miscellaneous other taxa, including recently-described species yet to be
accepted or distinctive forms that are not universally accepted, e.g.,
Red-tailed Hawk (abieticola), Upland Goose (Bar-breasted)

https://www.birds.cornell.edu/clementschecklist/

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
https://www.worldbirdnames.org/new/
Gill F, D Donsker & P Rasmussen  (Eds). 2020. IOC World Bird List (v10.2). 
doi :  10.14344/IOC.ML.10.2.

https://www.worldbirdnames.org/new/ioc-lists/master-list-2/

Comparison of IOC 10.2 with Clements 2019 (Dave Sargeant)
    http://www.worldbirdnames.org/IOC%20v10-2%20v%20Clements%202019.xlsx
    This is the one we use for IOC as it has both Clements and IOC sequence numbers. This is
    also the only one on this site with "tidy" data suitable for data science

Master List
    http://www.worldbirdnames.org/master_ioc_list_v10.2.xlsx
    
Cross reference between IOC 10.2 and Clements v2019, HBW/BL(vol1, vol2), H&M4.1, HBW, Peters, 
    TiF 3.10, HBW/BirdLife v4 (2019), S&M '93, IOC10.1. Simplified version.
    http://www.worldbirdnames.org/IOC_10.2_vs_other_lists.xlsx



http://www.worldbirdnames.org/IOC_Names_File_Plus-10.2_full_ssp.xlsx
--------------------------------------------------------------------------------
OTHERS
The Howard & Moore Complete Checklist of the Birds of the World, 4th Edition
The Trust for Avian Systematics
https://www.aviansystematics.org/index
    Not used; not available in electronic form

Zoological Nomenclature Resource
http://www.zoonomen.net
Alan Peterson, M.D.
--------------------------------------------------------------------------------
   
"""

MISSING_TAXON_ORDER = 0  # or 99999, depends where we want those to sort


@singleton
class Taxonomy(object):
    """Combined Taxonomy

    Attributes:
     """

    def __init__(self, cache_path: Path = None, ebird_extra: EBirdExtra = None):
        self._cache_path = cache_path
        self._ebird_extra = ebird_extra
        taxonomy_base_path = Path(__file__).parent.absolute()
        self.taxonomy_reference_path = taxonomy_base_path / 'reference'

        # Fill these lazily
        self.taxonomy = None
        self._taxonomy_clements = None  # TaxonomyClements().get_taxonomy()
        self._taxonomy_ioc = None  # TaxonomyIOC().get_taxonomy()
        self._taxonomy_nacc = None  # TaxonomyNACC().get_taxonomy()
        self._taxonomy_ebird = None
        self.INVALID_NACC_SORT_ORDER = 999999.1 # set again from NACC

        self.taxonomy = self.get_taxonomy_cached()

    def fix_up_merged_taxonomy(self):
        self.taxonomy['taxonOrder'] = self.taxonomy['taxonOrder'].fillna(MISSING_TAXON_ORDER)
        self.taxonomy['extinct'] = self.taxonomy['extinct'].fillna(False)
        self.taxonomy['extinctYear'] = self.taxonomy['extinctYear'].replace(0.0, '')
        # self.INVALID_NACC_SORT_ORDER = self._taxonomy_nacc.INVALID_NACC_SORT_ORDER

        # Renames
        try:
            self.taxonomy.rename(columns={'category': 'Category'}, inplace=True)
        except AttributeError:
            pass

        # species should be first, spuh last, the others don't matter
        ordered_categories = ['species', 'issf', 'slash', 'hybrid', 'form',
                              'intergrade', 'domestic', 'spuh']
        cat_type = CategoricalDtype(categories=ordered_categories, ordered=True)
        # Writing to CSV will strip categorical information, so need to add after reading cache
        self.taxonomy.Category = self.taxonomy.Category.astype(cat_type)

        # self.taxonomy.NACC_SORT_ORDER.fillna(0, inplace=True)
        xdtypes = {
            'sciName': str, 'comName': str, 'speciesCode': str, 'Category': str,
            'taxonOrder': int,
            'bandingCodes': str, 'comNameCodes': str, 'sciNameCodes': str, 'order': str,
            'familyComName': str, 'familySciName': str, 'reportAs': str, 'extinct': bool,
            'extinctYear': str,
            'comNameLower': str, 'sciNameLower': str, 'TAXON_ORDER': int, 'CATEGORY': str,
            'SPECIES_CODE': str, 'PRIMARY_COM_NAME': str, 'SCI_NAME': str, 'ORDER1': str,
            'FAMILY': str,
            'SPECIES_GROUP': str, 'REPORT_AS': str, 'ioc_seq': int,
            'ioc_scientific_name': str,
            'ioc_common_name': str, 'ioc_clements_seq': int,
            'ioc_clements_scientific_name': str,
            'ioc_clements_common_name': str, 'ioc_range': str, 'NACC_SORT_ORDER': float,
            'nacc_id': str,
            'nacc_avibase_id': str, 'nacc_rank': str, 'nacc_common_name': str, 'nacc_order': str,
            'nacc_family': str, 'nacc_subfamily': str, 'nacc_genus': str, 'nacc_species': str,
            'nacc_common_name_lower': str
        }

        self.taxonomy.ioc_seq = self.taxonomy.ioc_seq.replace('', 0)
        self.taxonomy.ioc_clements_seq = self.taxonomy.ioc_clements_seq.replace('', 0)
        self.taxonomy.NACC_SORT_ORDER = self.taxonomy.NACC_SORT_ORDER.replace('', 0.0)

        self.taxonomy = self.taxonomy.astype(dtype=xdtypes)

        # Fix up any remaining NA values
        colnames_numerics_only = self.taxonomy.select_dtypes(include=np.number).columns.tolist()
        if 'Category' in colnames_numerics_only:
            colnames_numerics_only.remove('Category')
        almost_all_cols = list(self.taxonomy.columns)
        almost_all_cols.remove('Category')
        fill_values = {col: 0 if col in colnames_numerics_only else ''
                       for col in almost_all_cols}
        self.taxonomy.fillna(fill_values, inplace=True)
        #
        # for col in colnames_numerics_only:
        #     self.taxonomy[col] = self.taxonomy[col].astype(int)



    # for col in self.taxonomy.columns:
    #     newtype = xdtypes.get(col, str)
    #     self.taxonomy[col] = self.taxonomy[col].astype(newtype)

    def get_taxonomy_cached(self) -> pd.DataFrame:
        cached_taxonomy_path = self._cache_path / 'taxonomy_full.csv'
        try:
            if cached_taxonomy_path.is_file():
                self.taxonomy = pd.read_csv(cached_taxonomy_path,
                                            index_col=False, low_memory=False)
                self.fix_up_merged_taxonomy()
            else:
                print(f'Creating full taxonomy cache...')
                # EBird API taxonomy is the base
                self._taxonomy_ebird = self.get_taxonomy_api_cached()
                self.taxonomy = self._taxonomy_ebird.copy()
                # print(f'ebird: {self.taxonomy.shape}')

                self._taxonomy_clements = TaxonomyClements().get_taxonomy()
                self._taxonomy_ioc = TaxonomyIOC().get_taxonomy()
                self._taxonomy_nacc = TaxonomyNACC().get_taxonomy()
                # Now merge in Clements, IOC and NACC checklists
                self.taxonomy = self.merge_clements_into_taxonomy()
                # print(f'clements: {self.taxonomy.shape}')
                self.taxonomy = self.merge_ioc_into_taxonomy()
                # print(f'ioc: {self.taxonomy.shape}')
                self.taxonomy = self.merge_nacc_into_taxonomy()
                # print(f'nacc: {self.taxonomy.shape}')

                self.fix_up_merged_taxonomy()
                # print(f'fixu: {self.taxonomy.shape}')

                print('Adding synthesized NACC sort orders')
                self.add_synthesized_nacc_sort_orders()

                self.taxonomy.to_csv(cached_taxonomy_path, index=False)
                print(f'Written to cache: {self.taxonomy.shape[0]} records')
        except Exception as ee:
            print(ee)
            traceback.print_exc(file=sys.stdout)

        # Fill in code4 column
        # self.fill_code4s()

        # print(f'exit: {self.taxonomy.shape}')
        return self.taxonomy

    def fill_code4s(self):
        code4s = []
        for ix, row in self.taxonomy.iterrows():
            if row.Category != 'species':
                code4s.append(None)
            elif len(row.banding_codes) == 1:
                code4s.append(list(row.banding_codes)[0])
            elif len(row.comname_codes) > 0:
                code4s.append(list(row.comname_codes)[0])
            else:
                code4s.append(None)

        self.taxonomy['code4'] = code4s

    def get_taxonomy_api_cached(self) -> pd.DataFrame:
        taxonomy_df = pd.DataFrame()
        cached_taxonomy_path = self._cache_path / 'taxonomy_ebird_api.csv'
        try:
            if cached_taxonomy_path.is_file():
                taxonomy_df = pd.read_csv(cached_taxonomy_path, index_col=False)
            else:
                print(f'Creating eBird taxonomy cache...')
                taxonomy_df = self._ebird_extra.get_taxonomy_from_ebird()
                taxonomy_df['comNameLower'] = taxonomy_df.comName.apply(lambda x: x.lower())
                taxonomy_df['sciNameLower'] = taxonomy_df.sciName.apply(lambda x: x.lower())
                taxonomy_df.to_csv(cached_taxonomy_path, index=False)
        except Exception as ee:
            print(ee)
            traceback.print_exc(file=sys.stdout)

        return taxonomy_df

    def find_local_name(self, local_name) -> \
            Tuple[Optional[Any], Optional[Any], Optional[Any], Optional[Any]]:
        record = self.find_local_name_row(local_name)
        if not record:
            return None, None, None, None

        return record.comName, record.TAXON_ORDER, record.SPECIES_GROUP, record.NACC_SORT_ORDER

    def find_local_name_row(self, common_name) -> Optional[pd.Series]:
        # Look for exact matches
        if not common_name:
            return None

        record = None
        try:
            common_name_lower = common_name.lower()
            mask = self.taxonomy.comNameLower == common_name_lower
            records = self.taxonomy[mask]
            record = records.iloc[0]

        except IndexError:
            pass

        return record

    def find_scientific_name_row(self, scientific_name) -> Optional[pd.Series]:
        # Look for exact matches
        if not scientific_name:
            return None

        record = None
        try:
            scientific_name_lower = scientific_name.lower()
            mask = self.taxonomy.sciNameLower == scientific_name_lower
            records = self.taxonomy[mask]
            record = records.iloc[0]

        except IndexError:
            pass

        return record


    # @property
    # def local_to_ebird_translations(self):
    #     return self._local_to_ebird_translations

    def species6_to_common_name(self, species6):
        commonname = species6
        try:
            commonname = self.taxonomy[self.taxonomy.speciesCode == species6.lower()].iloc[
                0].comName
        except Exception as ee:
            print(f'{species6} not found: {ee}')
            traceback.print_exc(file=sys.stdout)

        return commonname

    # def species6_to_common_name_aou(self, species6):
    #     commonname = species6
    #     try:
    #         species6u = species6.upper()
    #         commonname = aou_codes[aou_codes.SPEC6 == species6.upper()][0].COMMONNAME
    #     except Exception as ee:
    #         print(f'{species6} not found: {ee}')
    #
    #     return commonname

    def find_species6_ebird(self, common_name):
        try:
            #         common_name_u = common_name.upper()
            #         commonname = ebird_taxonomy[ebird_taxonomy.SPECIES_CODE ==
            #               species6.lower()].iloc[0].COMMON_NAME
            # ebird-api uses speciesCode
            species6 = self.taxonomy[self.taxonomy.comName == common_name].iloc[0].speciesCode
        except Exception as ee:
            #         print(f'{common_name} not found: {ee} [find_species6_ebird]')
            species6 = None

        return species6

    def merge_clements_into_taxonomy(self) -> pd.DataFrame:
        self.taxonomy = self.taxonomy.merge(self._taxonomy_clements,
                                            left_on='comName',
                                            right_on='PRIMARY_COM_NAME', how='left').fillna('')

        return self.taxonomy

    def merge_ioc_into_taxonomy(self) -> pd.DataFrame:
        self.taxonomy = self.taxonomy.merge(self._taxonomy_ioc, left_on='comName',
                                            right_on='ioc_clements_common_name',
                                            how='left').fillna('')

        return self.taxonomy

    def merge_nacc_into_taxonomy(self) -> pd.DataFrame:
        self.taxonomy = self.taxonomy.merge(self._taxonomy_nacc, left_on='comName',
                                            right_on='nacc_common_name', how='left').fillna('')

        return self.taxonomy

    def get_nacc_taxonomy(self) -> pd.DataFrame:
        return self._taxonomy_nacc

    # -------------------------------- NACC Ordering --------------------------------------------

    @staticmethod
    def identify_family_sort_orders(family: pd.DataFrame) -> list:
        # family e.g. 'Grebes'
        need_order = family[family.Category != 'species']
        family_species = family[family.Category == 'species'] #.reset_index(drop=True)
        sort_orders = []
        base_sort_order = 0

        for ix, row in need_order.iterrows():
            try:
                base_sort_order = 0
                if row.Category == 'spuh':
                    base_sort_order = max(family.NACC_SORT_ORDER)
                else:
                    bc_mask = [len(row.comname_codes & bc) > 0 for bc in
                               family_species.banding_codes]
                    if any(bc_mask):
                        mask = bc_mask
                    else:
                        cn_mask = [len(row.comname_codes & bc) > 0 for bc in
                                   family_species.comname_codes]
                        mask = cn_mask or bc_mask
                    parents = family_species[mask]
                    if not parents.empty:
                        base_sort_order = max(parents.NACC_SORT_ORDER)

                # "diurnal raptor sp." is weird
                if not isinstance(base_sort_order, numbers.Number):
                    base_sort_order = 0

                if base_sort_order > 0:
                    sort_orders.append({'comNameLower': row.comNameLower,
                                        'NACC_SORT_ORDER': base_sort_order,
                                        'Category': row.Category})

            except Exception as ee:
                print(ee)
                display(row)
                display(family)
                print(f'base_sort_order: {base_sort_order}, type: {type(base_sort_order)}')
                raise

        return sort_orders

    def add_synthesized_nacc_sort_orders(self):
        # Only species have NACC sort orders, so make up some for issf, slash, etc.
        # this takes 16s to run, so try to cache results

        # SECURITY WARNING: using eval. Trust your taxonomy file.
        # These columns contain Python objects, so not appropriate for CSV file
        self.taxonomy['banding_codes'] = [set(eval(cnc)) for cnc in self.taxonomy.bandingCodes]
        self.taxonomy['comname_codes'] = [set(eval(cnc)) for cnc in self.taxonomy.comNameCodes]

        sort_orders = []

        for ix, group in enumerate(self.taxonomy.groupby(['order', 'familyComName'])):
            fam_order, grp = group
            # order, family = fam_order
            familydf = grp #.reset_index(drop=True)
            grp_sort_orders = self.identify_family_sort_orders(familydf)
            sort_orders.extend(grp_sort_orders)

        # print(f'len(sort_orders): {len(sort_orders)}')
        sort_orders_df = pd.DataFrame(sort_orders)

        # print(f'sort_orders_df: {sort_orders_df.columns}')
        addl_sort_orders = sort_orders_df.groupby('NACC_SORT_ORDER').NACC_SORT_ORDER.transform(
            self.smear_orders)
        sort_orders_df = sort_orders_df.assign(NACC_SORT_ORDER=addl_sort_orders)

        # Now set those rows in taxonomy
        # mask = [(cn in list(sort_orders_df.comNameLower)) for cn in self.taxonomy.comNameLower]
        # self.taxonomy.loc[mask, 'NACC_SORT_ORDER'] = list(sort_orders_df.NACC_SORT_ORDER)

        # Crappy way, the proper way is eluding me
        for ix, row in sort_orders_df.iterrows():
            self.taxonomy.loc[self.taxonomy.comNameLower == row.comNameLower, 'NACC_SORT_ORDER'] = row.NACC_SORT_ORDER

        # Cleanup
        self.taxonomy.drop(labels=['banding_codes', 'comname_codes'], axis=1, inplace=True)

    # https://stackoverflow.com/questions/59951415/how-do-you-replace-duplicate-values-with-multiple-unique-strings-in-pandas
    @staticmethod
    def smear_orders(orders):
        """
        On input, all elements of orders have the same value, e.g. 777
        This routine smears them across a range so that we would have something like
        [777.01, 777.02, 777.03, ...]
        :param orders:
        :return:
        """
        nn = len(orders)
        step_size = 0.01 if nn > 9 else 0.1
        addends = np.linspace(step_size, nn * step_size, nn)

        return orders.radd(addends)

   # -------------------------------- ISSF Helpers --------------------------------------------


    # https://support.ebird.org/en/support/solutions/articles/48000837816-the-ebird-taxonomy
    # Subspecies (ISSF or Identifiable Sub-specific Group): Identifiable subspecies or group
    # of subspecies, e.g., Tundra Swan (Bewick’s) or Tundra Swan (Whistling)

    def filter_issf(self, common_names: List[str]) -> List[str]:
        issfs = []
        for cn in common_names:
            row = self.find_local_name_row(cn)
            if row is not None and row.Category == 'issf':
                issfs.append(cn)

        return issfs

    def report_as(self, common_name: str) -> Optional[str]:
        row = self.find_local_name_row(common_name)
        base_species = self.taxonomy[self.taxonomy.speciesCode == row.reportAs]
        if base_species.empty:
            return None
        else:
            return base_species.comNameLower.values[0]

    def filter_species(self, common_names: List[str]) -> List[str]:
        species = []
        for cn in common_names:
            row = self.find_local_name_row(cn)
            if row is not None and row.Category == 'species':
                species.append(cn)

        return species