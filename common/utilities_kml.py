# from kml_utilities import area_geo_to_hotspots
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List
from pandas.api.types import CategoricalDtype

from shapely.geometry import Point, Polygon
from shapely import geometry

import geopandas as gpd
import fiona

# For hotspot circles
import geog

# Local imports
from common_paths import outputs_path, reference_path, kml_path
from parameters import Parameters
# import KMeans
from sklearn.cluster import KMeans
from utilities_misc import miles_to_kilometers

# Constants and Globals
DEFAULT_CIRCLE_RADIUS = 7.5  # Miles

camh_latitude = 37.37
camh_longitude = -121.52

circle_radius_miles = DEFAULT_CIRCLE_RADIUS
circle_radius = 1000 * miles_to_kilometers(circle_radius_miles)  # radius in meters  1000 *


def build_location_data(hotspots, visits):
    # Use hotspots as a base, then add in data from visits
    # Don't drop anything based on whether it is in the circle or not
    location_data = hotspots.copy()
    cols_to_drop = ['r1', 'r2', 'date', 'num']
    location_data.drop(labels=cols_to_drop, axis=1, inplace=True)
    location_data.rename(columns={'locid': 'locId', 'r3': 'RegionCode',
                                  'lat': 'latitude', 'lng': 'longitude', 'name': 'LocationName'
                                  }, inplace=True)
    location_data['hotspot'] = True

    # Now add in visits. Assumes transform_visits has already been called
    xvisits = visits.copy()
    cols_to_drop = ['subId', 'Name', 'numSpecies', 'obsDt', 'obsTime']
    xvisits.drop(labels=cols_to_drop, axis=1, inplace=True)
    xvisits.rename(columns={'loc_name': 'LocationName', 'loc_isHotspot': 'hotspot',
                            'lat': 'latitude', 'lng': 'longitude'
                            }, inplace=True)
    # Already done by transform_visits
    # vgeometry = [Point(x, y) for x, y in
    #              zip(xvisits.longitude, xvisits.latitude)]  # Longitude first
    # xvisits['geometry'] = vgeometry

    location_data = pd.concat([location_data, xvisits], axis=0, ignore_index=True).reset_index(
        drop=True)
    # Latitude and longitude can differ very slightly, so round a bit
    location_data = location_data.round({'latitude': 8, 'longitude': 8})

    location_data.drop_duplicates(subset=['locId', 'RegionCode', 'latitude', 'longitude'],
                                  keep='first', inplace=True)

    location_data['coordinates'] = [(x, y) for x, y in zip(location_data.latitude,
                                                           location_data.longitude)]
    return location_data


def add_cluster_labels(visits_geos: pd.DataFrame, cluster_info: List[dict],
                       parameters: Parameters) -> pd.DataFrame:
    circle_code = parameters.parameters.get('CircleAbbrev', 'XXXX')

    # Each row in visits is an individual checklist filed at a set of coordinates
    # We only use visits here to get the points

    cluster_df = pd.DataFrame(cluster_info)  # Name, center
    xgeometry = [Point(x, y) for x, y in cluster_df.center.values]
    cluster_gdf = gpd.GeoDataFrame(cluster_df, geometry=xgeometry, crs='epsg:4269')

    # display(cluster_gdf)

    # geos = visits_geos.copy()[['subId', 'latitude', 'longitude']]
    # Kmeans is not ideal for this, but it's a proof-of-concept for CAMP
    pts = [[x, y] for x, y in
           zip(visits_geos.loc_latitude, visits_geos.loc_longitude)]  # create kmeans object
    # Add in the center points to make sure they are in cluster
    pts.extend([[x, y] for x, y in cluster_df.center])
    kmeans = KMeans(n_clusters=6)
    # fit kmeans object to data
    kmeans.fit(pts)
    # print location of clusters learned by kmeans object
    # print(kmeans.cluster_centers_, cluster_df.center)
    # save new clusters for chart
    cluster_labels = kmeans.fit_predict(pts)

    # geos = pd.DataFrame()
    # geos['cluster_label'] = cluster_labels
    # geos['latitude'] = [x for x,y in pts]
    # geos['longitude'] = [y for x,y in pts]

    # geos = visits_geos.copy()
    visits_geos['cluster_label'] = cluster_labels[0:visits_geos.shape[0]]

    cluster_label_to_sector_name = {}
    geo_sectors = []
    for ix, group in enumerate(visits_geos.groupby(['cluster_label'])):
        jx, grp = group
        # print(ix, jx)

        #     display(grp)
        xgeometry = [Point(x, y) for x, y in zip(grp.loc_latitude, grp.loc_longitude)]
        gdf = gpd.GeoDataFrame(grp, geometry=xgeometry, crs='epsg:4269')
        xhull = gdf.unary_union.convex_hull

        for kx, row in cluster_gdf.iterrows():
            pt = row.geometry
            if pt.within(xhull):  # matching pseudo-sector
                print(f'Group {ix} is sector {row.Name}')
                grp['SectorName'] = row.Name
                cluster_label_to_sector_name[ix] = row['Name']
                info = {
                    'SectorName': row['Name'],
                    'Description': 'pseudo-sector',
                    'geometry': xhull,
                    'CircleCode': circle_code
                }
                geo_sectors.append(info)
    # visits_geos['SectorName'] = visits_geos['cluster_label'].apply(
    #     lambda label: cluster_label_to_sector_name.get(label, None))

    # Need to build df with columns: ['SectorName', 'Description', 'geometry', 'CircleCode']
    return pd.DataFrame(geo_sectors)

    #
    # cluster_df = pd.DataFrame(cluster_info) # Name, center
    # # Kmeans is not ideal for this, but it's a proof-of-concept for CAMP
    # pts = [[x, y] for x, y in zip(visits_geos.lat, visits_geos.lng)]    # create kmeans object
    # # Add in the center points to make sure they are in cluster
    # pts.extend([[x,y] for x,y in cluster_df.center])
    # kmeans = KMeans(n_clusters=6)
    # # fit kmeans object to data
    # kmeans.fit(pts)
    # # print location of clusters learned by kmeans object
    # print(kmeans.cluster_centers_, cluster_df.center)
    # # save new clusters for chart
    # cluster_labels = kmeans.fit_predict(pts)
    # visits_geos['cluster_label'] = cluster_labels
    #
    # # Columns in scvas_geo: ['SectorName', 'Description', 'geometry', 'CircleCode']
    #
    # combined_hotspot_geometry = [Point(x, y) for x, y in zip(combined.lng, combined.lat)]
    # combined_hotspot_gdf = gpd.GeoDataFrame(combined,
    #                                         geometry=combined_hotspot_geometry,
    #                                         crs='epsg:4269')
    # center_pt = combined_hotspot_gdf.unary_union.convex_hull
    #
    #
    # return visits_geos


def geodataframe_basic(parameters: Parameters) -> pd.DataFrame:
    circle_code = parameters.parameters.get('CircleAbbrev', 'XXXX')
    latitude = parameters.parameters.get('CircleLatitude', None)
    longitude = parameters.parameters.get('CircleLongitude', None)
    geo_name = parameters.parameters.get('CircleName', circle_code)

    circle_center = geometry.Point([longitude, latitude])  # longitude first
    n_points = 20
    angles = np.linspace(0, 360, n_points)
    polygon = geog.propagate(circle_center, angles, circle_radius)
    geom = geometry.Polygon(polygon)
    gdf = pd.DataFrame.from_records([{'CircleCode': circle_code,
                                      'GeoName': geo_name,
                                      'Description': 'Count Circle Boundary',
                                      'geometry': geom,
                                      'type': 'circle',
                                      'source': 'parameters'}])

    return gdf


def build_geodata(parameters: Parameters) -> pd.DataFrame:
    # was: scvas_kml_to_geopandas
    # This is what can be built from looking at parameters
    circle_code = parameters.parameters.get('CircleAbbrev', 'XXXX')
    sector_names = parameters.parameters.get('SectorNames', None)

    geo_data = geodataframe_basic(parameters)

    fpaths = list(kml_path.glob('*.kml'))
    for fpath in fpaths:
        stem4 = fpath.stem[0:4]
        if stem4 != circle_code:
            continue

        sector_kml = None
        try:
            # Otherwise, read in the valid KML
            # 'CAMH'not a valid KML file for fiona, so make circle manually
            gpd.io.file.fiona.drvsupport.supported_drivers['KML'] = 'rw'
            sector_kml = gpd.read_file(fpath, driver='KML')
        except Exception as ee:
            print(f'Not a valid KML file: {fpath}')
            continue

        sector_kml.rename(columns={'Name': 'GeoName'}, inplace=True)

        if sector_names:
            sector_names = sector_names.split(',')
            sector_kml.GeoName = sector_names

        # Get rid of any slashes -- they mess up file names later on
        sector_kml.GeoName = sector_kml.GeoName.apply(lambda xs: xs.replace('/', '-'))
        # Add fields not in KML
        sector_kml['CircleCode'] = circle_code
        sector_kml['type'] = 'sector'
        sector_kml['source'] = f'KML: {fpath.stem}'
        geo_data = pd.concat([geo_data, sector_kml], axis=0, ignore_index=True).reset_index(
            drop=True)

    ordered_categories = ['sector', 'sector-generated', 'circle']
    cat_type = CategoricalDtype(categories=ordered_categories, ordered=True)
    geo_data['type'] = geo_data['type'].astype(cat_type)

    geo_data['polygon'] = geo_data.geometry.apply(
        lambda geo: geo if isinstance(geo, Polygon) else geometry.Polygon(geo))

    # Sorted like this so when are a looking to see if a point is in a sector, it will
    # find circle last, as a default
    geo_data.sort_values(by=['type'], inplace=True)

    return geo_data


# ['CircleCode', 'GeoName', 'Description', 'geometry', 'type', 'source',
#        'polygon']

def update_geo_data_with_clustering(geo_data: pd.DataFrame,
                                    cluster_table: pd.DataFrame,
                                    cluster_centers: pd.DataFrame) -> pd.DataFrame:
    representatives = cluster_table.drop_duplicates(['cluster_label'], keep='first').sort_values(
        by=['cluster_label'])
    circle_code = geo_data.iloc[0].CircleCode
    xdescription = 'Generated with k-Means'
    xtype = 'sector'  # -generated
    xsource = 'generated'
    xgeometry = [Point(lng, lat) for lng, lat in zip(
        cluster_centers.latitude, cluster_centers.longitude)]
    geo_names = representatives.GeoName
    sector_df = pd.DataFrame({'CircleCode': circle_code, 'GeoName': geo_names,
                              'Description': xdescription, 'geometry': xgeometry,
                              'type': xtype, 'source': xsource
                              }).reset_index(drop=True)

    updated_geo_data = pd.concat([geo_data, sector_df])

    ordered_categories = ['sector', 'sector-generated', 'circle']
    cat_type = CategoricalDtype(categories=ordered_categories, ordered=True)
    updated_geo_data['type'] = updated_geo_data['type'].astype(cat_type)
    updated_geo_data.sort_values(by=['type'])
    updated_geo_data = updated_geo_data.where(updated_geo_data.notnull() &
                                              (updated_geo_data.values != 'nan'), None)

    return updated_geo_data


def build_location_meta(geo_data, personal_checklists, location_data,
                        cluster_table: pd.DataFrame = None) -> pd.DataFrame:
    metas = []
    use_cluster_table = bool(cluster_table is not None and not cluster_table.empty)
    location_data_x = cluster_table if use_cluster_table else location_data
    for locid in set(personal_checklists.locId.values):
        try:
            location = location_data_x[location_data_x.locId == locid].iloc[0]
        except IndexError as ie:
            print(f'No location data for {locid}')
            meta = {'locId': locid, 'GeoName': None}
            metas.append(meta)
            continue

        if use_cluster_table:
            # Each location is already assigned to a cluster, by construction
            meta = {'locId': locid, 'GeoName': location.GeoName,
                    'latitude': location.latitude, 'longitude': location.longitude}
            metas.append(meta)
        else:
            pt = location.geometry  # Point
            for ix, row in geo_data.iterrows():
                if not row.polygon.contains(pt):
                    continue

                meta = {'locId': locid, 'GeoName': row.GeoName,
                        'latitude': location.latitude, 'longitude': location.longitude}
                metas.append(meta)
                break

    location_meta = pd.DataFrame(metas)

    return location_meta


def area_geo_to_hotspots(area_geo: gpd.GeoDataFrame, hotspots: pd.DataFrame) -> pd.DataFrame:
    # Only tested for SCVAS geo
    sector_hotspot_list = []
    for jx, sector in area_geo.iterrows():
        polygon = geometry.Polygon(sector.geometry)
        rx = hotspots.geometry.apply(lambda pt: polygon.contains(pt))
        #     print(f'{sector.SectorName}: {sum(rx)}')
        df = hotspots.loc[hotspots.index[rx], ['name', 'locid', 'lat', 'lng']]
        df['Circle'] = sector.CircleCode
        df['Sector'] = sector.SectorName

        sector_hotspot_list.append(df)
    #     break

    sector_hotspots = pd.concat(sector_hotspot_list, axis=0, ignore_index=True)
    sector_hotspots.rename(columns={'name': 'Name', 'lat': 'latitude', 'lng': 'longitude'},
                           inplace=True)
    new_cols = ['Circle', 'Sector', 'Name', 'locid', 'latitude', 'longitude']
    sector_hotspots = sector_hotspots[new_cols]
    # Should already be sorted, but make it explicit
    sector_hotspots.sort_values(by=['Circle', 'Sector', 'Name'], inplace=True)
    sector_hotspots.to_csv(outputs_path / f'SCVAS-sector_hotspots.csv', index=False)

    return sector_hotspots
