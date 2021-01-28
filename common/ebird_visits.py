import geopandas as gpd
import pandas as pd
from shapely import geometry
from shapely.geometry import Point

from taxonomy import Taxonomy


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


def transform_checklist_details(details: pd.DataFrame, taxonomy: Taxonomy) -> pd.DataFrame:
    # Circle/sector data kept in checklists_meta
    cols_to_keep = [col for col in ['locId', 'subId', 'userDisplayName', 'groupId',
                    'speciesCode', 'obsDt', 'howManyStr', 'numObservers',
                    'effortDistanceKm', 'effortDistanceEnteredUnit', 'durationHrs',
                    'comments'] if col in details.columns]
    personal_checklists = details.copy()[cols_to_keep]

    rename_cols = ['userDisplayName', 'howManyStr', 'numObservers']
    if all(elem in personal_checklists.columns for elem in rename_cols):
        personal_checklists.rename(columns={'userDisplayName': 'Name', 'howManyStr': 'Total',
                                            'numObservers': 'Observers'},
                                   inplace=True)
    personal_checklists['CommonName'] = personal_checklists.speciesCode.apply(
        taxonomy.species6_to_common_name)
    personal_checklists.sort_values(by=['locId', 'Name'], inplace=True)

    personal_checklists = fix_total_column(personal_checklists)
    xdtypes = {
        'locId': str, 'subId': str, 'Name': str, 'groupId': str,
        'speciesCode': str, 'obsDt': str, 'Total': int, 'CommonName': str,
        'effortDistanceKm': float, 'effortDistanceEnteredUnit': str, 'durationHrs': float
    }
    personal_checklists = personal_checklists.astype(dtype=xdtypes)

    personal_checklist_column_order = ['locId', 'subId', 'Name', 'groupId', 'speciesCode',
                                       'obsDt', 'Total', 'CommonName',
                                       'effortDistanceKm', 'effortDistanceEnteredUnit',
                                       'durationHrs', 'Observers', 'comments']

    personal_checklists = personal_checklists[personal_checklist_column_order]

    return personal_checklists
