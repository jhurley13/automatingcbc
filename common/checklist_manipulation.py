import pandas as pd
import numpy as np
from parameters import Parameters
from geopy.distance import distance

from pathlib import Path
from typing import Tuple, Optional, List
from utilities_misc import compute_hash

from write_basic_spreadsheet import write_basic_spreadsheet
from utilities_misc import kilometers_to_miles_r2

LOCATION_CLOSENESS_DISTANCE = 200  # in meters


def create_checklist_meta(personal_checklists: pd.DataFrame,
                          visits: pd.DataFrame,
                          location_data) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    To use this when writing sector summaries, ignore rows where 'sharing' == 'secondary'.
    For the remaining rows, if 'location_group' is None, use SUM, otherwise apply MAX
    to each location_group.
    :param personal_checklists:
    :param visits:
    :return: dataframe with one line per subId. Has extra data beyond original checklist details
    """
    # original columns for ppp are:
    # ['locId', 'subId', 'Name', 'groupId', 'speciesCode', 'obsDt', 'Total',
    #        'CommonName', 'effortDistanceKm', 'effortDistanceEnteredUnit',
    #        'durationHrs']

    cm = personal_checklists.copy().sort_values(by=['locId', 'Name', 'obsDt'])

    # https://stackoverflow.com/questions/39279824/use-none-instead-of-np-nan-for-null-values-in-pandas-dataframe
    # Convert any null entries to None. GroupId is a str 'nan'
    cm = cm.where(cm.notnull() & (cm.values != 'nan'), None)

    # A lot of information is duplicated across all species. Collapse to single row
    cm.drop_duplicates(['subId'], inplace=True)
    # Get rid of duplicate or irrelevant columns
    cm.drop(['speciesCode', 'CommonName', 'effortDistanceEnteredUnit'], axis=1, inplace=True)
    # Pull in the correct Total from visits or visits_of_interest
    cm.Total = cm.subId.apply(find_total_in_visits, args=(visits,))

    # ---------------------------------------------------------------------
    # Now add some features that will help with de-duplication
    # ---------------------------------------------------------------------

    cm.sort_values(by=['locId', 'obsDt', 'groupId', 'Name'], inplace=True)

    # 'sharing' is set if it is one of a set of shared checklists, based on groupId
    cm['sharing'] = None
    # 'location_group' will be non-empty if there is more than one name for a locId
    cm['location_group'] = None

    checklist_base_url = 'https://ebird.org/checklist'
    cm['url'] = cm.subId.apply(lambda subid: f'{checklist_base_url}/{subid}')
    # print(f'All checklists: {cm.shape[0]}')

    cm_with_group = cm[~cm.groupId.isnull()]
    # print(f'Shared checklists (including duplicates): {cm_with_group.shape[0]}')

    # These are the ones we are keeping
    shared_primary_subids = list(
        cm_with_group.drop_duplicates(['locId', 'groupId', 'obsDt', 'Total']).subId.values)
    duplicate_shared_subids = list(set(cm_with_group.subId) - set(shared_primary_subids))
    # print(f'Shared duplicate checklists: {len(duplicate_shared_subids)}')
    dsc_mask = cm.subId.isin(duplicate_shared_subids)
    cm.loc[dsc_mask, 'sharing'] = 'secondary'

    # These are the ones whose groupId is one of the groupIds for the duplicate shared checklists
    shared_primary_groupids = list(set(cm[dsc_mask].groupId))
    shared_primary_subids = list(set(cm_with_group.subId))
    shg_mask = cm.groupId.isin(shared_primary_groupids) & cm.subId.isin(shared_primary_subids)
    cm.loc[shg_mask & ~dsc_mask, 'sharing'] = 'primary'

    # These are cases where multiple people birded the same location (excluding secondary shares)
    multiple_at_location = {}
    for ix, (locid, grp) in enumerate(cm[cm.sharing != 'secondary'].groupby(['locId'])):
        if len(set(grp.Name.values)) > 1:
            multiple_at_location[locid] = list(grp.subId.values)

    for locid, subids in multiple_at_location.items():
        cm.loc[cm.subId.isin(subids), 'location_group'] = locid

    cm, near_duplicates = add_near_duplicates(cm, location_data)

    # Not clear that fingerprints are useful now
    # cm['fingerprints'] = add_fingerprints(cm, personal_checklists)

    cm.sort_values(by=['location_group', 'locId', 'obsDt', 'groupId', 'Name'],
                   na_position='first', inplace=True)

    # Returned dataframe has these columns
    # ['locId', 'subId', 'Name', 'groupId', 'obsDt', 'Total',
    #        'effortDistanceKm', 'durationHrs', 'sharing', 'location_group', 'url']

    return cm.reset_index(drop=True), near_duplicates


def add_near_duplicates(checklist_meta: pd.DataFrame, location_data: pd.DataFrame):
    near_duplicates = find_location_near_duplicates(checklist_meta,
                                                    location_data,
                                                    LOCATION_CLOSENESS_DISTANCE)
    if near_duplicates is None:
        return checklist_meta, None

    near_dups_flat = list(np.concatenate((near_duplicates.LocationA.values,
                                          near_duplicates.LocationB.values), axis=0))
    ndo = checklist_meta[checklist_meta.locId.isin(near_dups_flat) &
                         (checklist_meta.location_group.isnull())]
    near_dups = list(zip(near_duplicates.LocationA.values, near_duplicates.LocationB.values))
    for ix, row in ndo.iterrows():
        for px in near_dups:
            if row.locId in px:
                checklist_meta.at[ix, 'location_group'] = '+'.join(px)

    return checklist_meta, near_duplicates


def write_checklist_meta(checklist_meta: pd.DataFrame, fpath: Path):
    # cm.to_csv(debug_path / 'checklist_meta.csv', index=False)
    # e.g. fpath = reports_path / 'checklist_summary.xlsx'
    column_widths = {
        'locId': 10,
        'subId': 10,
        'Name': 25,
        'groupId': 10,
        'obsDt': 20,
        'Total': 10,
        'effortDistanceKm': 10,
        'durationHrs': 10,
        'sharing': 10,
        'url': 28,
        'location_group': 18
    }
    columns_to_center = ['locId', 'subId', 'groupId', 'obsDt', 'Total',
                         'effortDistanceKm', 'durationHrs', 'sharing', 'location_group']

    write_basic_spreadsheet(checklist_meta, fpath, column_widths, columns_to_center)


def find_total_in_visits(subid: str, visits: pd.DataFrame):
    total = 0
    try:
        total = visits[visits.subId == subid].numSpecies.values[0]
    except IndexError as ie:
        pass
    return total


def find_location_near_duplicates(checklist_meta: pd.DataFrame,
                                  location_data: pd.DataFrame,
                                  horseshoe_closeness_threshold=LOCATION_CLOSENESS_DISTANCE) \
        -> Optional[pd.DataFrame]:
    # ToDo: naming of intermediate variables is a mess here, due to how it evolved
    # in meters

    unique_locids = sorted(list(set(checklist_meta.locId)))
    unique_locations = location_data[location_data.locId.isin(unique_locids)].copy()
    unique_locations = unique_locations.drop_duplicates(keep='first').reset_index()

    coords = list(zip(unique_locations.latitude, unique_locations.longitude))

    # Distance Matrix

    x1 = np.array([distance(a, b).m for a in coords for b in coords]).reshape(len(coords),
                                                                              len(coords))
    pairwise_distances = pd.DataFrame(x1, index=unique_locations.locId.values,
                                      columns=unique_locations.locId.values)

    # This is a subset where at least one column in each row is "close"
    possible_close_rows = pairwise_distances[(pairwise_distances.values > 0) &
                                             (pairwise_distances.values <
                                              LOCATION_CLOSENESS_DISTANCE)]
    if possible_close_rows.empty:
        return None

    cols_to_keep = list(set(possible_close_rows.index))

    potential_dups_df = possible_close_rows[cols_to_keep].copy().drop_duplicates(
        keep='first').replace(0, 7777.0)
    potential_dups_x = potential_dups_df[cols_to_keep].idxmin()
    potential_dups = list(set(
        [(a, b) if a < b else (b, a) for a, b in
         zip(potential_dups_x.index, potential_dups_x.values)]))

    rows = []
    for loc_a, loc_b in potential_dups:
        dist = potential_dups_df.loc[loc_a, loc_b]
        # print(dist)
        if dist > horseshoe_closeness_threshold:
            continue
        loc1 = location_data[location_data.locId == loc_a]
        loc2 = location_data[location_data.locId == loc_b]

        loc1name = loc1.LocationName.values[0]
        loc2name = loc2.LocationName.values[0]
        l1coords = (loc1.latitude.values[0], loc1.longitude.values[0])
        l2coords = (loc2.latitude.values[0], loc2.longitude.values[0])

        row = {
            'LocationA': loc_a, 'NameA': loc1name, 'coordinatesA': l1coords,
            'LocationB': loc_b, 'NameB': loc2name, 'coordinatesB': l2coords,
            'dist_m': f'{dist:0.2f}'
        }
        rows.append(row)

    return pd.DataFrame(rows)


def add_fingerprints(checklist_meta: pd.DataFrame, personal_checklists: pd.DataFrame) -> List[str]:
    fingerprints = []
    for subid in checklist_meta.subId.values:
        try:
            subid_checklists = personal_checklists[personal_checklists.subId == subid]
            plain_text = ''.join(
                subid_checklists.speciesCode.append(subid_checklists.Total.astype(str),
                                                    ignore_index=True))
            fingerprint = compute_hash(plain_text, 8)
            fingerprints.append(fingerprint)

        except IndexError as ie:
            # print(subid, ie)
            continue

    return fingerprints


def construct_team_efforts(checklist_meta: pd.DataFrame) -> pd.DataFrame:
    party_efforts = checklist_meta.copy()
    party_efforts.fillna({'durationHrs': 0, 'effortDistanceKm': 0}, inplace=True)
    party_efforts['Distance (mi)'] = party_efforts['effortDistanceKm'].apply(kilometers_to_miles_r2)

    dfgb = party_efforts.groupby('Name').sum()[['durationHrs', 'effortDistanceKm', 'Distance (mi)']]

    # margins_name defaults to 'All'
    dfpt = dfgb.pivot_table(index='Name', margins=True, margins_name='Totals', aggfunc=sum)

    df2r = pd.DataFrame(dfpt.to_records())
    df2r.rename(columns={'Name': 'Party Lead', 'durationHrs': 'Duration (Hrs)'}, inplace=True)

    return df2r[['Party Lead', 'Duration (Hrs)', 'Distance (mi)']]


def construct_team_details(checklist_meta: pd.DataFrame,
                           location_data: pd.DataFrame) -> pd.DataFrame:
    party_details = pd.merge(checklist_meta, location_data[['locId', 'LocationName']],
                             how='left', on='locId',
                             left_index=False, right_index=False, sort=True,
                             copy=True, indicator=False,
                             validate=None)
    party_details.fillna({'durationHrs': 0, 'effortDistanceKm': 0}, inplace=True)
    party_details['Distance (mi)'] = party_details['effortDistanceKm'].apply(kilometers_to_miles_r2)
    party_details.rename(columns={'durationHrs': 'Duration (Hrs)',
                                  'effortDistanceKm': 'Distance (km)',
                                  'obsDt': 'Date/Time'
                                  }, inplace=True)

    new_col_order = ['locId', 'subId', 'Total', 'Name', 'Observers', 'sharing', 'groupId',
                     'location_group', 'Date/Time', 'url', 'LocationName',
                     'Duration (Hrs)', 'Distance (mi)', 'Distance (km)', 'comments']
    party_details = party_details[new_col_order]

    return party_details
