# eBird Basic Dataset. Version: EBD_relDec-2020.
# Cornell Lab of Ornithology, Ithaca, New York. Dec 2020.

# The date in the raw data dump is most similar to the data returned from the eBird API
# get_details. Our main purpose here is to find any missing subIds. We could morph the
# data in the bulk dump, but for the small number of missing records, it is easier to
# just add them to visits

from typing import List, Optional

import pandas as pd
from shapely.geometry import Point

from common_paths import raw_data_path
from datetime_manipulation import normalize_time_for_visits


def load_bulk_data() -> pd.DataFrame():
    bulk_data = None
    # This is really specific, so hardwire paths for now
    bulk_data_dir = raw_data_path / 'ebd_US-CA_202012_202101_prv_relDec-2020'
    bulk_data_path = bulk_data_dir / 'ebd_US-CA_202012_202101_prv_relDec-2020.txt'
    if not bulk_data_path.exists():
        return None

    bulk_data = pd.read_csv(bulk_data_path, dtype=str, header=0, sep='\t', low_memory=False).fillna(
        '')
    provisional_data_path = bulk_data_dir / 'ebd_US-CA_202012_202101_prv_relDec-2020_provisional.txt'
    if provisional_data_path.exists():
        prov_data = pd.read_csv(provisional_data_path, dtype=str, header=0, sep='\t',
                                low_memory=False).fillna('')
        bulk_data = pd.concat([bulk_data, prov_data], axis=0, ignore_index=True)

    return bulk_data


def find_missing_subids(visits: pd.DataFrame, bulk_data: Optional[pd.DataFrame],
                        xdates: List[str], region_codes: List[str]):
    if bulk_data is None:
        return []
    mask = (bulk_data['OBSERVATION DATE'].isin(xdates)) & (
        bulk_data['COUNTY CODE'].isin(region_codes))
    bulk_subids = set(bulk_data[mask]['SAMPLING EVENT IDENTIFIER'].values)
    base_subids = set(visits.subId.values)

    return sorted(list(bulk_subids - set(base_subids)))


def use_basic_dataset(visits: pd.DataFrame, xdates: List[str],
                      region_codes: List[str]) -> pd.DataFrame:
    # Consult Basic Dataset (EBD) bulk data from eBird to find missing subIds
    # Append records to visits if any are found
    # Takes about 13s to load BDS for Dec 2020
    bulk_data = load_bulk_data()
    if bulk_data is None:
        return visits

    missing_subids = find_missing_subids(visits, bulk_data, xdates, region_codes)
    bds = bulk_data[bulk_data['SAMPLING EVENT IDENTIFIER'].isin(missing_subids)].copy().reset_index(
        drop=True)
    if bds.empty:
        return visits

    # Names match those in visits
    new_col_names = {
        'LOCALITY ID': 'locId', 'SAMPLING EVENT IDENTIFIER': 'subId', 'OBSERVER ID': 'Name',
        'OBSERVATION DATE': 'obsDt', 'TIME OBSERVATIONS STARTED': 'obsTime',
        'LOCALITY': 'loc_name', 'LATITUDE': 'latitude', 'LONGITUDE': 'longitude',
    }
    bds.rename(columns=new_col_names, inplace=True)

    numSpecies_df = bds.groupby(['subId']).size().reset_index(name='numSpecies').sort_values(
        by=['subId'])

    bds = bds.drop_duplicates(['subId', 'obsDt', 'obsTime', 'latitude', 'longitude']).reset_index(
        drop=True)

    bds['numSpecies'] = numSpecies_df.numSpecies.values
    bds.obsTime = bds.obsTime.apply(normalize_time_for_visits)

    new_col_order = ['locId', 'subId', 'Name', 'numSpecies', 'obsDt', 'obsTime', 'loc_name',
                     'latitude', 'longitude']
    bds = bds[new_col_order].sort_values(by=['subId']).reset_index(drop=True)

    for col in ['latitude', 'longitude']:
        bds[col] = bds[col].apply(pd.to_numeric).fillna(0).astype(float)

    vgeometry = [Point(x, y) for x, y in zip(bds.longitude, bds.latitude)]  # Longitude first
    bds['geometry'] = vgeometry

    # We could fix 'Name' with 'userDisplayName' field from get_details, but not important here

    return pd.concat([visits, bds], axis=0, ignore_index=True)
