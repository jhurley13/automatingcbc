import geopandas as gpd
import pandas as pd
from shapely import geometry
from shapely.geometry import Point

from taxonomy import Taxonomy
from typing import Optional
from utilities_misc import kilometers_to_miles

def visits_in_circle(ebirders, geo_data, circle_code, visits):
    # Also filters by participants
    circle_geometry = geo_data[(geo_data.CircleCode == circle_code) &
                               (geo_data.type == 'circle')].geometry.values[0]

    # Note that by construction, visits only contains data for dates we care about
    # so we don't need to filter for that. We pass them to get_details grouped by date though.
    mask = [pt.within(circle_geometry) for pt in visits.geometry.values]
    if ebirders is not None:
        mask &= visits.Name.isin(ebirders)
    visits_of_interest = visits[mask].sort_values(by=['locId'])

    return visits_of_interest


def transform_visits(visits):
    # Drop columns we don't need and rename some others
    # Don't drop anything based on whether it is in the circle or not

    cols_to_drop = [
        'subID', 'loc_locId', 'loc_countryCode', 'loc_countryName', 'loc_subnational1Name',
        'loc_subnational1Code', 'loc_subnational2Code', 'loc_subnational2Name', 'loc_locName',
        'loc_lat', 'loc_lng', 'loc_hierarchicalName', 'loc_locID']
    visits.drop(labels=cols_to_drop, axis=1, inplace=True)
    visits.rename(columns={'userDisplayName': 'Name',
                           'loc_latitude': 'latitude', 'loc_longitude': 'longitude'}, inplace=True)

    vgeometry = [Point(x, y) for x, y in
                 zip(visits.longitude, visits.latitude)]  # Longitude first
    visits['geometry'] = vgeometry

    return visits


def add_circle_data(visits: pd.DataFrame, area_geo: gpd.GeoDataFrame) -> pd.DataFrame:
    circle_codes = []
    sector_names = []
    for ix, row in visits.iterrows():
        circle_code = None
        sector_name = None
        for jx, sector in area_geo.iterrows():
            polygon = geometry.Polygon(sector.geometry)

            pt = Point(row.loc_longitude, row.loc_latitude)
            if polygon.contains(pt):
                circle_code = sector.CircleCode
                sector_name = sector.SectorName
                break

        circle_codes.append(circle_code)
        sector_names.append(sector_name)

    visits['CircleCode'] = circle_codes
    visits['SectorName'] = sector_names

    return visits


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

WHAT_DOES_X_EQUAL = 3  # One, Two, Many: ref "The Pirahã people"  1000000)  # one meeelion


def fix_total_column(checklist) -> pd.DataFrame:
    # for numeric Total columns, not for formula-based ones
    # so = pd.to_numeric(summary.NACC_SORT_ORDER, errors='coerce')
    # summary.NACC_SORT_ORDER = pd.Series(so).fillna(taxonomy.INVALID_NACC_SORT_ORDER)
    # An eBird user can indicate "Many" by using an 'X' in the total field
    # Since this messes up counts, let's replace with 1000000 so we can fix manually
    checklist = checklist.replace({'Total': "X"}, WHAT_DOES_X_EQUAL)  # one meeelion

    return checklist

def row_to_miles(row) -> float:
    if row['effortDistanceEnteredUnit'] == 'mi':
        return row['effortDistanceKm']
    else:
        return kilometers_to_miles(row['effortDistanceKm'])

def convert_effort_distance_to_miles(checklist: pd.DataFrame) -> Optional[pd.Series]:
    distance_columns = ['effortDistanceKm', 'effortDistanceEnteredUnit']
    if not all(elem in checklist.columns for elem in distance_columns):
        return None

    return checklist.apply(row_to_miles, axis=1)


def transform_checklist_details(details: pd.DataFrame, taxonomy: Taxonomy) -> pd.DataFrame:
    # Circle/sector data kept in checklists_meta
    # Standardize column names
    personal_checklists = details.copy()

    # We don't use the columns later so get rid of them. Ignore error if column not present
    cols_to_drop = [
        'projId', 'protocolId', 'allObsReported', 'creationDt', 'lastEditedDt', 'obsTimeValid',
        'checklistId', 'subnational1Code', 'submissionMethodCode',
        'submissionMethodVersion', 'submissionMethodVersionDisp'
    ]
    personal_checklists.drop(columns=cols_to_drop, errors='ignore', inplace=True)

    common_name_synonyms = ['Species', 'species']
    total_synonyms = ['Count', 'howManyStr', 'Number']

    rename_cols = {'userDisplayName': 'Name', 'howManyStr': 'Total', 'numObservers': 'Observers'}
    personal_checklists.rename(columns=rename_cols, errors='ignore', inplace=True)

    # Data in 'obs' field returned from eBird has speciesCode but no CommonName
    if ('speciesCode' in personal_checklists.columns) and \
            ('CommonName' not in personal_checklists.columns):
        personal_checklists['CommonName'] = personal_checklists.speciesCode.apply(
            taxonomy.species6_to_common_name)

    # personal_checklists.sort_values(by=['locId', 'Name'], inplace=True)

    personal_checklists = fix_total_column(personal_checklists)

    distance_mi = convert_effort_distance_to_miles(personal_checklists)
    if distance_mi is not None:
        personal_checklists['DistanceMi'] = distance_mi
        personal_checklists.drop(columns=['effortDistanceKm', 'effortDistanceEnteredUnit'],
                                 errors='ignore', inplace=True)

    xdtypes = {
        'locId': str, 'subId': str, 'Name': str, 'groupId': str,
        'speciesCode': str, 'obsDt': str, 'Total': int, 'CommonName': str,
        'DistanceMi': float, 'durationHrs': float
    }
    for col, xtyp in xdtypes.items():
        if col not in personal_checklists.columns:
            continue
        personal_checklists[col] = personal_checklists[col].astype(xtyp, errors='ignore')

    personal_checklist_column_order = [col for col in [
        'locId', 'subId', 'Name', 'groupId', 'speciesCode', 'obsDt', 'Total',
        'CommonName', 'DistanceMi', 'durationHrs', 'Observers', 'comments'
        ] if col in personal_checklists.columns
    ]

    personal_checklists = personal_checklists[personal_checklist_column_order]

    return personal_checklists
