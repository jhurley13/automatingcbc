"""
References
https://stackoverflow.com/questions/59857949/how-to-add-cluster-markers-to-choropleth-with-folium
https://georgetsilva.github.io/posts/mapping-points-with-folium/
https://python-visualization.github.io/folium/modules.html
See https://github.com/masajid390/BeautifyMarker for icon_shape etc.
Also https://getbootstrap.com/docs/3.3/components/ (don't set prefix then)
https://medium.com/@nchristiansen/making-an-interactive-web-map-in-python-with-folium-part-2-map-makery-d40db1d4101a
See e.g. https://github.com/python-visualization/folium/blob/master/folium/vector_layers.py
https://jsfiddle.net/syrdh76a/

"""

from typing import Optional

# For making map
import folium
import geopandas as gpd
import pandas as pd
import webcolors
from folium import plugins
from folium.features import DivIcon
from folium.map import FeatureGroup
from folium.plugins import MarkerCluster, FeatureGroupSubGroup
from scipy.constants import foot
from shapely import geometry

from common_paths import reports_path
from utilities_misc import miles_to_kilometers
from parameters import Parameters

# For making sample data for article
# For hotspot circles

srgb_black = '#000000'

marker_color_names = [
    'HotPink', 'Red', 'Orange', 'Yellow', 'Maroon', 'Plum',
    'Magenta', 'BlueViolet', 'Indigo', 'Lime', 'ForestGreen', 'Cyan',
    'Navy', 'Blue', 'Teal', 'Silver', 'cornflowerblue',
    'indianred', 'indigo', 'ivory', 'khaki', 'lavender', 'lavenderblush', 'lawngreen',
    'lemonchiffon', 'lightblue', 'lightcoral', 'lightcyan', 'lightgoldenrodyellow',
    'lightgray', 'lightgrey', 'lightgreen', 'lightpink', 'lightsalmon', 'lightseagreen',
    'lightskyblue'
]

marker_colors = dict(
    [(colorname, webcolors.name_to_hex(colorname.lower())) for colorname in marker_color_names])


def base_count_circle_map(circle_center) -> folium.Map:
    mm = folium.Map(location=circle_center, zoom_start=12, prefer_canvas=True)

    return mm


def create_coverage_map(visits: pd.DataFrame,
                        parameters: Parameters,
                        geo_data: Optional[pd.DataFrame],
                        centers_df: Optional[pd.DataFrame],
                        near_duplicates: Optional[pd.DataFrame],
                        radius_in_miles=7.5):
    """
    Create a Folium map with layers for various interesting data
    :param visits:
    :param parameters:
    :param geo_data:
    :param centers_df:
    :param near_duplicates:
    :param radius_in_miles: e.g. 5 or 7.5 for a count circle
    :rtype: object
    :return:
    """

    # The layers in the map:
    # - Circle boundary
    # - Observations
    # - Sector Boundaries
    # - Duplicate locations
    # - Sector centers, for pseudo-sectors. Only if centers_df not None

    # Don't really want to drop duplicates since it will show density of coverage
    circle_center = (parameters.parameters['CircleLatitude'],
                     parameters.parameters['CircleLongitude'])
    circle_code = parameters.parameters.get('CircleAbbrev', 'XXXX')
    circle_radius = 1000 * miles_to_kilometers(radius_in_miles)

    base_map = base_count_circle_map(circle_center)

    # Start of loop
    draw_circle_boundary(base_map, circle_center, circle_radius)
    create_location_markers(base_map, visits)
    add_sector_information(base_map, geo_data)
    create_potential_duplicates_map(base_map, near_duplicates)
    create_center_markers(base_map, centers_df)
    # End of loop

    # Done
    folium.map.LayerControl(collapsed=False).add_to(base_map)
    map_path = reports_path / f'{circle_code}-CountCircleMap.html'
    base_map.save(outfile=map_path.as_posix())

    return base_map


def draw_circle_boundary(base_map, center_pt, circle_radius):
    # Draw the circle
    # marker_cluster = MarkerCluster(control=False)
    # marker_cluster.add_to(base_map)
    feature_group = FeatureGroup(name='circle boundary', control=True, show=True)

    circle_boundary = folium.vector_layers.Circle(center_pt, circle_radius, stroke=5,
                                                  color='Magenta',
                                                  opacity=0.5, dash_array='4 1')
    circle_boundary.add_to(feature_group)
    feature_group.add_to(base_map)

    return circle_boundary


def color_for_marker(marker_size):
    colors = [marker_colors.get(mn, 'HotPink') for mn in
              ['lightgrey', 'lightcyan', 'cornflowerblue']]
    return colors[marker_size - 1]


def assign_marker_colors(locations_df):
    names = sorted(list(set(locations_df.Name.dropna())))

    marker_colors_by_name = dict((name,
                                  marker_colors.get(
                                      marker_color_names[ix % len(marker_color_names)], 'HotPink'))
                                 for ix, name in enumerate(names))
    return marker_colors_by_name


def marker_color_for_cluster(cluster_id: int):
    if cluster_id < 0:
        return marker_colors.get('HotPink')
    return marker_colors.get(marker_color_names[cluster_id % len(marker_color_names)], 'HotPink')


def make_observation_popup_html(row: pd.Series):
    # was: row.to_frame().to_html()
    checklist_base_url = 'https://ebird.org/checklist'
    checklist_url = f'{checklist_base_url}/{row.subId}'
    html = """
        <b>Observer   :</b> {observer_name}<br>
        <b>When       :</b> {observation_dt}<br>
        <b>Species    :</b> {num_species}<br>
        <b>Location   :</b> {location_name}<br>
        <b>Coordinates:</b> {coordinates}<br>
        <b>LocationID :</b> {locationID}<br>
        <b>Checklist  :</b> <a href="{checklist_url}">{checklist_subid}</a><br>
        """

    observation_dt = f'{row.obsDt} {row.obsTime}'
    coordinates = f'({row.latitude}, {row.longitude})'
    popup_contents = folium.Html(html.format(observer_name=row.Name,
                                             observation_dt=observation_dt,
                                             num_species=row.numSpecies,
                                             location_name=row.loc_name,
                                             coordinates=coordinates,
                                             locationID=row.locId,
                                             checklist_url=checklist_url,
                                             checklist_subid=row.subId
                                             ),
                                 script=True)

    return popup_contents


def create_location_markers(base_map, locations_df):
    # hotspots_df has columns ['locid', 'lat', 'lng', 'name', 'num', 'marker_size']
    marker_cluster = MarkerCluster(control=False)
    marker_cluster.add_to(base_map)
    sub_group = FeatureGroupSubGroup(marker_cluster, name='Observations',
                                     control=True, show=True)

    marker_colors_by_name = assign_marker_colors(locations_df)

    color_by_sectors = 'cluster_label' in locations_df.columns
    for index, row in locations_df.iterrows():
        hname = row['Name']
        marker_color = marker_color_for_cluster(row['cluster_label']) if color_by_sectors else \
            marker_colors_by_name.get(hname)
        marker_size = 1
        xpopup = folium.Popup(make_observation_popup_html(row), max_width=600)  # pixels
        marker = folium.Marker(
            location=[row['latitude'], row['longitude']],
            popup=xpopup,
            tooltip=hname,
            icon=folium.plugins.BeautifyIcon(
                prefix='fa',
                icon='binoculars',
                # icon_shape='rectangle',
                # icon='twitter',
                icon_shape='marker',
                # icon_size=Point(),
                text_color=marker_colors.get('Yellow', 'HotPink'),  # actually icon color
                background_color=marker_color,
                border_width=marker_size,
                border_color=marker_colors.get('Silver', 'HotPink')

            )
        )

        marker.add_to(sub_group)

    sub_group.add_to(base_map)

    return None


def create_center_markers(base_map, centers_df):
    # cluster_table has columns ['locId', 'latitude', 'longitude', 'cluster_label', 'GeoName']
    if centers_df is None:  # No pseudo-sectors
        return None

    marker_cluster = MarkerCluster(control=False)
    marker_cluster.add_to(base_map)
    sub_group = FeatureGroupSubGroup(marker_cluster, name='Pseudo-sector Centers',
                                     control=True, show=True)

    for index, row in centers_df.iterrows():
        hname = row['GeoName']

        # marker_color = marker_colors.get('Yellow')
        # marker_size = 10
        xpopup = folium.Popup(row.to_frame().to_html())
        # options = {
        #     'isAlphaNumericIcon': True,
        #     'borderColor': '#00ABDC',
        #     'textColor': '#00ABDC',
        #     'innerIconStyle': 'margin-top:0;'
        # }
        marker = folium.Marker(
            location=(row['latitude'], row['longitude']),
            popup=xpopup,
            tooltip=hname,
            icon=folium.plugins.BeautifyIcon(
                icon='circle',
                borderColor='#00ABDC',
                textColor='#00ABDC',
                innerIconStyle='margin-top:0;'

                # icon=L.BeautifyIcon.icon(options),
                # icon_shape='circle-dot',
                # text_color=srgb_black,  # actually icon color
                # background_color=marker_color,
                # border_width=marker_size
            )
        )

        marker.add_to(sub_group)

    sub_group.add_to(base_map)

    return None


def add_sector_information(base_map, geo_data):
    if geo_data is not None:  # Have real sectors
        feature_group = FeatureGroup(name='Sector Information', control=True, show=True)

        gdf_cols = ['CircleCode', 'GeoName', 'geometry']
        geo_data_sectors = geo_data[geo_data['type'] == 'sector']
        gdf = gpd.GeoDataFrame(geo_data_sectors[gdf_cols], crs="EPSG:4326")
        folium.GeoJson(gdf).add_to(feature_group)
        add_sector_labels(feature_group, geo_data)
        feature_group.add_to(base_map)


# https://stackoverflow.com/questions/46400769/numbers-in-map-marker-in-folium
def add_sector_labels(feature_group, geo_data):
    # display(geo_data)
    for ix, sector in geo_data.iterrows():
        if sector.geometry is None or sector.polygon is None:
            continue
        polygon = geometry.Polygon(sector.geometry)

        font_size = 'font-size: 9pt'
        xcolor = 'color : Indigo'
        xalign = 'text-align:center'
        folium.map.Marker(
            (polygon.centroid.y, polygon.centroid.x),
            icon=DivIcon(
                icon_size=(150, 36),
                icon_anchor=(75, 18),
                html=f'<div style="{font_size}; {xcolor}; {xalign}"> {sector.GeoName}</div>',
            )
        ).add_to(feature_group)


# [('L12991087', 'L12991801'),
#  ('L12990701', 'L5505337'),
#  ('L12987938', 'L12988158')]

def create_potential_duplicates_map(base_map, near_duplicates: pd.DataFrame):
    if near_duplicates is None:
        return

    marker_cluster = MarkerCluster(control=False)
    marker_cluster.add_to(base_map)
    sub_group = FeatureGroupSubGroup(marker_cluster, name='Near-Duplicate Locations',
                                     control=True, show=True)

    # # add markers
    # ['LocationA', 'NameA', 'coordinatesA', 'LocationB', 'NameB', 'coordinatesB', 'dist_m']
    for ix, row in near_duplicates.iterrows():
        for is_row_a in [True, False]:
            dup_location_marker(row, is_row_a).add_to(sub_group)
        # add lines
        folium.PolyLine((row.coordinatesA, row.coordinatesB),
                        color="red", weight=2.5, opacity=1).add_to(sub_group)

    sub_group.add_to(base_map)

    return None

    # map_path = reports_path / f'{circle_code}-PossibleDuplicateLocationsMap.html'
    # mm.save(outfile=map_path.as_posix())


def make_dup_location_popup_html(row: pd.Series):
    # was: row.to_frame().to_html()
    # ['LocationA', 'NameA', 'coordinatesA', 'LocationB', 'NameB', 'coordinatesB', 'dist_m']

    html = """
        <b>Location A   :</b> {location_a}<br>
        <b>Coordinates  :</b> {coordinates_a}<br>
        <b>LocationA ID :</b> {location_a_id}<br>
        <b></b> <br>
        <b>Location B   :</b> {location_b}<br>
        <b>Coordinates  :</b> {coordinates_b}<br>
        <b>LocationB ID :</b> {location_b_id}<br>
        <b></b> <br>
        <b>Distance (m) :</b> {distance_m}<br>
        <b>Distance (ft):</b> {distance_ft}<br>
        """

    distance_ft = f'{float(row.dist_m) / foot:.02f}'
    popup_contents = folium.Html(html.format(location_a=row.NameA,
                                             coordinates_a=row.coordinatesA,
                                             location_a_id=row.LocationA,
                                             location_b=row.NameB,
                                             coordinates_b=row.coordinatesB,
                                             location_b_id=row.LocationB,
                                             distance_m=row.dist_m,
                                             distance_ft=distance_ft
                                             ),
                                 script=True)

    return popup_contents


def dup_location_marker(row: pd.Series, location_a: bool = True) -> folium.Marker:
    marker_color = marker_colors.get('HotPink')
    marker_size = 2
    marker = folium.Marker(
        location=row['coordinatesA'] if location_a else row['coordinatesB'],
        popup=folium.Popup(make_dup_location_popup_html(row), max_width=1000),  # pixels
        tooltip=row['NameA'] if location_a else row['NameB'],
        icon=folium.plugins.BeautifyIcon(
            icon='twitter',
            icon_shape='marker',
            text_color=marker_colors.get('Yellow', 'HotPink'),  # actually icon color
            background_color=marker_color,
            border_width=marker_size
        )
    )

    return marker
