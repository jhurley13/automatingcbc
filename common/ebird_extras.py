import sys
import traceback
from io import StringIO
from pathlib import Path
from typing import Optional, List, Union

import geopandas as gpd
import pandas as pd
import requests
# https://pypi.org/project/ebird-api/
from ebird.api import Client
from shapely.geometry import Point
from singleton_decorator import singleton
from datetime import datetime
from typing import List, Dict

from utilities_misc import get_credential, compute_hash
from common_paths import cache_path

EBIRD_DEFAULT_LOCALE = 'en'

"""
This class contains additional methods to access eBird not supported by the ebird.api
package (https://pypi.org/project/ebird-api/).
"""


@singleton
class EBirdExtra(object):
    def __init__(self, ebird_credential_path: Path,
                 xcache_path: Path = cache_path, country: str = 'US'):
        """

        :param ebird_credential_path: Path to YAML files for eBird API Key credentials
        :param xcache_path: Where files like subnational2 codes and taxonomy are cached
        :param country: This is only important when retrieving and caching subnational2 codes
        """
        self.ebird_credential_path = ebird_credential_path
        self.cache_path = xcache_path
        self.country = country
        self.ebird_client = None
        self.__ebird_api_key = get_credential(self.ebird_credential_path)
        if not self.__ebird_api_key:
            print(f'No API key found for eBird')

        self._cache_path = cache_path
        self._cached_visits_path = self._cache_path / 'visits'
        self._cached_historic_path = self._cache_path / 'historic'
        self._cached_details_path = self._cache_path / 'details'

        if self.__ebird_api_key:
            self.ebird_client = Client(self.__ebird_api_key, EBIRD_DEFAULT_LOCALE)

        # We do this as a side effect as a user convenience. The list of subnational2 codes
        # are saved in the cache for reference. subnational2 codes are the region codes
        # needed in the parameters file. Not fatal if we can't get it. Files saved e.g.:
        #      cache_path / 'regions-US-subnational2.csv'
        # Note that this also calls and caches subnational1 codes
        try:
            # print(f'Calling get_subnational2_cached with {(ebird_client, country, cache_path)}')
            _ = self.get_subnational2_cached()
        except Exception as ee:
            print(f'Failed to get subnational2 codes: {ee}')

    def get_taxonomy_from_ebird(self) -> Optional[pd.DataFrame]:
        taxonomy_from_ebird = None
        if self.ebird_client:
            taxonomy_from_ebird = pd.DataFrame(self.ebird_client.get_taxonomy()).fillna('')

        return taxonomy_from_ebird

    # These are very high level stats, so not particularly useful unless looking at the whole state
    # For example, https://api.ebird.org/v2/product/stats/US-CA-085/2019/12/15 returns
    # {'numChecklists': 0, 'numContributors': 0, 'numSpecies': 0}
    def get_regional_statistics_on_a_date(self, region_code: str, year: int, month: int, day: int):
        # Regional statistics on a date
        # Note that it works for 'US-CA' but not 'US-CA-085'
        #   returns e.g. {'numChecklists': 1129, 'numContributors': 996, 'numSpecies': 299}
        # https://api.ebird.org/v2/product/stats/{{regionCode}}/{{y}}/{{m}}/{{d}}
        stats = pd.DataFrame()
        try:
            api_url_base = 'https://api.ebird.org/v2/product/stats/'
            url = f'{api_url_base}{region_code}/{year}/{month}/{day}'
            api_auth_header = {'X-eBirdApiToken': self.__ebird_api_key}

            print(url)
            rr = requests.get(url, params=None, headers=api_auth_header, stream=True)
            if rr.status_code == requests.codes.ok:
                stats = rr.json()  # pd.DataFrame()
            rr.raise_for_status()

        except Exception as ee:
            print(ee)
            traceback.print_exc(file=sys.stdout)

        return stats

    # For a myriad of reasons we cannot ever expand the CBC period beyond the current date range
    # of December 14th through January 5th and CBC counts cannot take place outside of these dates.

    def get_historic_observations_on_a_date(self, region_code: str, year: int, month: int,
                                            day: int):
        # Regional statistics on a date
        # https://api.ebird.org/v2/data/obs/{{regionCode}}/historic/{{y}}/{{m}}/{{d}}
        stats = pd.DataFrame()
        try:
            api_url_base = 'https://api.ebird.org/v2/data/obs/'
            url = f'{api_url_base}{region_code}/historic/{year}/{month}/{day}'
            api_auth_header = {'X-eBirdApiToken': self.__ebird_api_key}

            rr = requests.get(url, params=None, headers=api_auth_header, stream=True)
            if rr.status_code == requests.codes.ok:
                stats = pd.DataFrame(rr.json())
            rr.raise_for_status()

        except Exception as ee:
            print(ee)
            traceback.print_exc(file=sys.stdout)

        return stats

    def get_checklist_feed_for_region_on_date(self, region_code: str, xdate: str) -> pd.DataFrame:
        # xdate is e.g. '2020-12-26'
        # https://api.ebird.org/v2/product/lists/{{regionCode}}/{{y}}/{{m}}/{{d}}
        oxdate = datetime.strptime(xdate, '%Y-%m-%d')
        results = pd.DataFrame()
        try:
            api_url_base = 'https://api.ebird.org/v2/product/lists'
            api_auth_header = {'X-eBirdApiToken': self.__ebird_api_key}
            url = f'{api_url_base}/{region_code}/{oxdate.year}/{oxdate.month}/{oxdate.day}'
            xparams = {'maxResults': 200}

            rr = requests.get(url, params=xparams,
                              headers=api_auth_header,
                              stream=True)  # params=params, headers=api_auth_header,
            if rr.status_code == requests.codes.ok:
                results = pd.DataFrame(rr.json())
            rr.raise_for_status()

        except Exception as ee:
            print(f'get_recent_observations_for_region: {ee}')

        return results

    def get_species_list_at_a_location(self, loc_id):
        # GET Species List at a Location [IN DEVELOPMENT]
        # https://api.ebird.org/v2/product/spplist/{{locId}}
        # e.g. "locId": "L99381"
        # Seems to be returned in taxonomic order

        results = pd.DataFrame()
        try:
            api_url_base = 'https://api.ebird.org/v2/product/spplist'
            api_auth_header = {'X-eBirdApiToken': self.__ebird_api_key}
            url = f'{api_url_base}/{loc_id}'

            rr = requests.get(url, params=None, headers=api_auth_header, stream=True)
            #         print(rr.request.headers)
            if rr.status_code == requests.codes.ok:
                results = pd.DataFrame(rr.json())
            rr.raise_for_status()

        except Exception as ee:
            print(ee)
            traceback.print_exc(file=sys.stdout)

        return results

    def get_subnational1_cached(self) -> pd.DataFrame:
        # subnational_1. In the US, these are states
        subnational1_df = pd.DataFrame()
        subnational1_path = self._cache_path / f'regions-{self.country}-subnational1.csv'

        try:
            if not subnational1_path.exists():
                print(f'Creating eBird subnational1 region cache...')
                subnational1_df = pd.DataFrame(self.ebird_client.get_regions('subnational1',
                                                                             self.country)).fillna(
                    '')
                subnational1_df.to_csv(subnational1_path, index=False)
            else:
                subnational1_df = pd.read_csv(subnational1_path, index_col=False)

        except Exception as ee:
            print(ee)
            pass
            traceback.print_exc(file=sys.stdout)

        return subnational1_df

    def get_subnational2_cached(self) -> pd.DataFrame:
        # client is global ebird_client
        # Country is the two character ISO code, e.g. 'US'
        # https://www.nationsonline.org/oneworld/country_code_list.htm

        subnational2_path = self._cache_path / f'regions-{self.country}-subnational2.csv'
        subnational2_df = pd.DataFrame()

        try:
            if not subnational2_path.exists():
                print(f'Creating eBird subnational2 region cache...')

                # Get "states"
                subnational1_df = self.get_subnational1_cached()

                # Get "counties" for each "state"
                subnational2_list = []
                for row in subnational1_df.itertuples():
                    state, code = row.name, row.code
                    subnational2s = pd.DataFrame(
                        self.ebird_client.get_regions('subnational2', code))
                    subnational2s['state'] = state
                    subnational2_list.append(subnational2s)

                subnational2_df = pd.concat(subnational2_list)
                subnational2_df.to_csv(subnational2_path, index=False)

            else:
                subnational2_df = pd.read_csv(subnational2_path, index_col=False)

        except Exception as ee:
            print(ee)
            traceback.print_exc(file=sys.stdout)

        return subnational2_df

    def get_visits_expanded(self, region_code: str, date_of_count: str) -> pd.DataFrame:
        """
        A wrapper on top of eBird.api's get_visits that expands the
        loc field (which is a dictionary) into additional columns in the dataframe

        This also allows us to cache this as a CSV file

        :param region_code: eBird region code, e.g. 'US-CA-085'
        :param date_of_count: YYYY-MM-DD format e.g. '2019-12-28',
        :return: dataframe with every checklist filed in eBird on date for region
        """

        # EBIRD_DEFAULT_LOCALE = 'en'
        # credentials = xutilities.load_credentials(eBirdCredential_path)['credentials']
        # ebird_api_key = credentials['api_key']
        # ebird_client = Client(ebird_api_key, EBIRD_DEFAULT_LOCALE)

        visits_expanded = pd.DataFrame()
        cached_visits_path = self._cached_visits_path / f'visits-{region_code}-{date_of_count}.csv'
        try:
            if cached_visits_path.is_file():
                visits_expanded = pd.read_csv(cached_visits_path, index_col=False)
            else:
                visits = pd.DataFrame(self.ebird_client.get_visits(region_code, date_of_count))

                # Make a dataframe out of the 'loc' column
                locs = []
                for idx, row in visits.iterrows():
                    locs.append(row['loc'])

                locs_df = pd.DataFrame(locs)
                locs_cols = ['loc_' + col for col in locs_df.columns]
                locs_df.columns = locs_cols

                visits_expanded = pd.concat([visits, locs_df],
                                            axis=1).drop(['loc'],
                                                         axis=1).reset_index(drop=True)

                visits_expanded['RegionCode'] = region_code

                visits_expanded.to_csv(cached_visits_path, index=False)
        except Exception as ee:
            print(ee)
            traceback.print_exc(file=sys.stdout)

        return visits_expanded

    def get_checklist(self, sub_id: str):
        return self.ebird_client.get_checklist(sub_id)

    # --------------------------- HOTSPOTS ---------------------------

    def get_hotspots(self, region_codes: List[str]):
        # was: hotspot_data_for_regions
        first_region, *remaining_regions = region_codes
        combined = self._get_hotspots_for_region_cached(first_region)

        for rc in remaining_regions:
            region_hotspots = self._get_hotspots_for_region_cached(rc)
            combined = pd.concat([combined, region_hotspots], ignore_index=True)

        combined_hotspot_geometry = [Point(x, y) for x, y in zip(combined.lng, combined.lat)]
        combined_hotspot_gdf = gpd.GeoDataFrame(combined,
                                                geometry=combined_hotspot_geometry,
                                                crs='epsg:4269')
        center_pt = combined_hotspot_gdf.unary_union.convex_hull.centroid.coords[0][::-1]

        return combined_hotspot_gdf, center_pt

    def get_hotspots_for_region(self, region_code: str) -> pd.DataFrame:
        # https://ebird.org/ws2.0/ref/hotspot/geo?lat=37.4407&lng=-122.0936&fmt=json&dist=6
        # https://api.ebird.org/v2/ref/hotspot/{{regionCode}}
        # Sample returned row (includes geometry column too)
        # L6530472	US	US-CA	US-CA-085	37.435150	-122.102342	Adobe Creek--north of US-101
        # 2020-06-06 10:03	113	POINT (-122.10234 37.43515)
        headers = ['locid', 'r1', 'r2', 'r3', 'lat', 'lng', 'name', 'date', 'num']
        results = pd.DataFrame()
        try:
            api_url_base = 'https://api.ebird.org/v2/ref/hotspot'
            # API token not currently required, but may be in future
            # api_auth_header = {'X-eBirdApiToken': self.__ebird_api_key}
            url = f'{api_url_base}/{region_code}'
            # params = None  # { 'maxResults' : 200}
            rr = requests.get(url, stream=True)  # params=params, headers=api_auth_header,
            if rr.status_code == requests.codes.ok:
                results = pd.read_csv(StringIO(rr.text), names=headers, index_col=False)
            rr.raise_for_status()

        except Exception as ee:
            print(ee)

        return results

    def _get_hotspots_for_region_cached(self, region_code: str) -> pd.DataFrame:
        fpath = self._cache_path / f'hotspots-{region_code}.csv'
        if not fpath.is_file():
            hs_df = self.get_hotspots_for_region(region_code)
            hs_df.to_csv(fpath, index=False)
            return hs_df
        else:
            return pd.read_csv(fpath, index_col=False)

    # --------------------------- VISITS ---------------------------

    def get_visits(self, region_codes: List[str], date_of_count: str):
        # was: hotspot_data_for_regions
        first_region, *remaining_regions = region_codes
        combined = self.get_visits_expanded(first_region, date_of_count)

        for rc in remaining_regions:
            region_visits = self.get_visits_expanded(rc, date_of_count)
            combined = pd.concat([combined, region_visits], ignore_index=True)

        return combined

    def get_visits_for_dates(self, region_codes: List[str], dates: List[str]):
        first_date, *remaining_dates = dates
        combined = self.get_visits(region_codes, first_date)

        for xdate in remaining_dates:
            date_visits = self.get_visits(region_codes, xdate)
            combined = pd.concat([combined, date_visits], ignore_index=True)

        return combined

    def get_recent_observations_for_region(self, region_code: str,
                                           back: int = 14,
                                           cat: str = '(all)',
                                           hotspot: bool = False,
                                           include_provisional: bool = False,
                                           max_results: Union[int, str] = '(all)') -> pd.DataFrame:
        # https://api.ebird.org/v2/data/obs/{{regionCode}}/recent
        # Sample returned row (includes geometry column too)
        # L6530472	US	US-CA	US-CA-085	37.435150	-122.102342	Adobe Creek--north of US-101
        # 2020-06-06 10:03	113	POINT (-122.10234 37.43515)
        results = pd.DataFrame()
        try:
            api_url_base = 'https://api.ebird.org/v2/data/obs'
            api_auth_header = {'X-eBirdApiToken': self.__ebird_api_key}
            url = f'{api_url_base}/{region_code}/recent'
            xparams = None  # { 'maxResults' : 200}
            rr = requests.get(url, params=xparams,
                              headers=api_auth_header,
                              stream=True)  # params=params, headers=api_auth_header,
            if rr.status_code == requests.codes.ok:
                results = pd.DataFrame(rr.json())
            rr.raise_for_status()

        except Exception as ee:
            print(f'get_recent_observations_for_region: {ee}')

        return results

    # --------------------------- DETAILS ---------------------------

    @staticmethod
    def convert_date_range_to_date_str(drange) -> List[str]:
        return [ds.strftime('%Y-%m-%d') for ds in drange]

    def get_details_for_dates(self, subids_by_date: Dict[str, List[str]], dates: List[str]):
        # Note that by construction, visits only contains data for dates we care about
        # so we don't need to filter for that
        first_date, *remaining_dates = dates
        subids = subids_by_date.get(first_date, None)
        combined = self.get_details(subids, first_date)

        for xdate in remaining_dates:
            subids = subids_by_date.get(xdate, None)
            details = self.get_details(subids, xdate)
            combined = pd.concat([combined, details], ignore_index=True)

        return combined

    def get_details(self, subids: List[str], date_of_count: str):
        """
        Return a dataframe with the "obs" fields flattened. Will cache on disk
        Leave enhancement and other expansions for elsewhere
        Pass in all subids for date
        :param subids: list of checklist IDs
        :param date_of_count: This is used for caching; assumes all subids are for same date
        :return: dataframe with the "obs" fields flattened

        visits-US-CA-085-2019-12-15.csv
        ebird_details_path
        """
        subids_hash = compute_hash(''.join(subids), 12)
        sdate = datetime.strptime(date_of_count, '%Y-%m-%d').strftime('%Y%m%d')

        details = pd.DataFrame()

        # Look in cache first
        # Name is S<date>-<hash>.csv
        details_path = self._cached_details_path / f'S{sdate}-{subids_hash}.csv'

        try:
            if not details_path.exists():
                detailed_checklists = []
                for subid in subids:
                    cdict = self.get_checklist(subid)
                    # if cdict is None:
                    #     continue
                    # print(subid, cdict)
                    # Birdathon iOS version 1.4.1 adds the subAux field, which breaks
                    # turning this into a dataframe directly
                    if 'subAux' in cdict.keys():
                        del cdict['subAux']
                    if 'subAuxAi' in cdict.keys():
                        del cdict['subAuxAi']
                    checklist = pd.DataFrame(cdict)
                    # Not every checklist has groupId, so add if not there
                    # We need it later for detecting duplicate checklists (e.g. shared)
                    if 'groupId' not in checklist.columns:
                        checklist['groupId'] = None
                    if not checklist.empty:
                        detailed_checklists.append(checklist)

                if len(detailed_checklists) == 0:
                    details = pd.DataFrame()
                else:
                    if len(detailed_checklists) > 1:
                        details = pd.concat(detailed_checklists, axis=0, ignore_index=True)
                    elif len(detailed_checklists) == 1:
                        details = detailed_checklists[0]
                    details = self.flatten_detail_observations(details)
                details.to_csv(details_path, index=False)
            else:
                details = pd.read_csv(details_path, index_col=False)

        except Exception as ee:
            print(ee)
            print(cdict)
            traceback.print_exc(file=sys.stdout)

        return details

    def get_api_key(self):
        return self.__ebird_api_key

    """
    Sample observation entry
        {'speciesCode': 'rocpig1',
        'hideFlags': [],
        'obsDt': '2019-12-15 11:16',
        'subnational1Code': 'US-CA',
        'howManyAtleast': 92,
        'howManyAtmost': 92,
        'subId': 'S62345617',
        'projId': 'EBIRD',
        'obsId': 'OBS838617722',
        'howManyStr': '92',
        'present': False}
    """

    @staticmethod
    def flatten_detail_observations(details: pd.DataFrame) -> pd.DataFrame:

        details_list = []  # make a list of dictionaries, then dataframe
        for ix, row in details.iterrows():
            rowdict = row.to_dict().copy()
            rowdict.update(row.obs)
            del rowdict['obs']
            details_list.append(rowdict)

        flattened_details = pd.DataFrame(details_list)

        return flattened_details
