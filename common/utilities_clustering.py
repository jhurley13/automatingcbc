import sys
import traceback

import pandas as pd
import seaborn as sns
from sklearn.cluster import KMeans
from geopy.distance import distance
from parameters import Parameters
from typing import Tuple, List, Optional
import matplotlib.pyplot as plt
# from IPython.display import display
from utilities_kml import update_geo_data_with_clustering

sns.set()


def generate_cluster_table(visits_of_interest: pd.DataFrame,
                           geo_data: pd.DataFrame,
                           parameters: Parameters,
                           quiet: bool = True) -> Tuple[pd.DataFrame,
                                                        Optional[pd.DataFrame],
                                                        Optional[pd.DataFrame]]:
    # https://levelup.gitconnected.com/clustering-gps-co-ordinates-forming-regions-4f50caa7e4a1
    # Keep in mind this is non-deterministic, so clusters and cluster labels can change
    # If an ndarray is passed, it should be of shape (n_clusters, n_features)
    # and gives the initial centers.
    reference_sector_names = parameters.parameters.get('ReferenceSectorNames', None)
    if reference_sector_names == '':
        reference_sector_names = None

    reference_sector_centers = parameters.parameters.get('ReferenceSectorCenters', None)
    if reference_sector_centers == '':
        reference_sector_centers = None

    have_real_sectors = 'sector' in geo_data.type.values
    # 18 is arbitrary threshold value for not constructing pseudo-sectors
    if have_real_sectors or visits_of_interest.shape[0] < 18:
        return geo_data, None, None

    voi = visits_of_interest.copy()
    # Remove rows where the Longitude and/or Latitude are null values
    voi.dropna(axis=0, how='any', subset=['latitude', 'longitude'], inplace=True)
    xdata = voi.loc[:, ['locId', 'latitude', 'longitude']]

    cluster_size = 6 if reference_sector_names is None else len(reference_sector_names.split(','))

    if not quiet:
        print(f'cluster_size: {cluster_size}')
        plot_elbow_curve(visits_of_interest)

    kmeans = KMeans(n_clusters=cluster_size, init='k-means++')
    kmeans.fit(xdata[xdata.columns[1:3]])  # Compute k-means clustering.
    xdata['cluster_label'] = kmeans.fit_predict(xdata[xdata.columns[1:3]])
    # labels = kmeans.predict(xdata[xdata.columns[1:3]])  # Labels of each point
    centers = kmeans.cluster_centers_  # Coordinates of cluster centers.

    if reference_sector_names is None or reference_sector_centers is None:
        obscounts = xdata.cluster_label.value_counts().to_dict()
        print(f'Counts for each observation cluster: {obscounts}')

    if reference_sector_names is None:
        reference_sector_names = [f'Sector{ix}' for ix in range(cluster_size)]
    else:
        reference_sector_names = reference_sector_names.split(',')

    if reference_sector_centers is not None:
        reference_sector_centers = unpack_reference_sector_centers(reference_sector_centers)

    if reference_sector_centers is None:
        reference_sector_centers = [(x, y) for x, y in centers]
        sc_str = ','.join([str(z) for z in reference_sector_centers])
        print(f'\nPossible generated sector centers: {sc_str}')

    sector_info = {k: v for k, v in zip(reference_sector_names, reference_sector_centers)}
    # print(sector_info)
    cluster_table = deduce_sector_names(xdata, centers, sector_info, quiet)
    centers_df = convert_centers_to_dataframe(centers, cluster_table)

    if not cluster_table.empty:
        geo_data = update_geo_data_with_clustering(geo_data, cluster_table, centers_df)

    return geo_data, cluster_table, centers_df


def convert_centers_to_dataframe(centers, cluster_table) -> pd.DataFrame:
    xcenters_df = cluster_table.copy().drop_duplicates(['cluster_label']).sort_values(
        by=['cluster_label']).reset_index(drop=True)
    # display(xcenters_df)
    ccdf = pd.DataFrame(centers, columns=['latitude', 'longitude'])
    xcenters_df.latitude = ccdf.latitude
    xcenters_df.longitude = ccdf.longitude
    xcenters_df.drop(['locId'], axis=1, inplace=True)
    return xcenters_df


def deduce_sector_names(cluster_table: pd.DataFrame,
                        cluster_centers: pd.DataFrame,
                        sector_info,
                        quiet: bool = True
                        ) -> pd.DataFrame:
    # Deduce Sector Names
    # Do this if no 'sector' in types column of geo_data
    # make type 'generated-sector'
    # ref build_location_meta

    # https://towardsdatascience.com/finding-distant-pairs-in-python-with-pandas-fa02df50d14b
    fixed_columns = ['Name', 'latitude', 'longitude', 'cluster_label', 'coordinates']

    # print('deduce_sector_names cluster_centers')
    # display(cluster_centers)
    if not quiet:
        print(f'sector_info: {sector_info}')
    centers = []
    for ix, cluster in enumerate(cluster_centers):
        lat, lng = cluster
        row = {'Name': f'C{ix}', 'latitude': lat, 'longitude': lng, 'cluster_label': ix}
        centers.append(row)

    centers_df = pd.DataFrame(centers)
    centers_df['coordinates'] = [(x, y) for x, y in zip(centers_df.latitude, centers_df.longitude)]

    for sname, rcoords in sector_info.items():
        centers_df[sname] = centers_df.coordinates.apply(lambda cc: round(distance(cc, rcoords).m))

    # Find index of row with the minimum distance
    zmins = centers_df.iloc[:, len(fixed_columns):].idxmin(axis=0)

    if not quiet:
        print(f'deduce_sector_names centers_df zmins: {zmins.to_dict()}')
    centers_df['TrueName'] = list(zmins.sort_values().index)
    # display(centers_df)

    sname = cluster_table.cluster_label.apply(lambda cl:
                                              centers_df[
                                                  centers_df.cluster_label == cl].TrueName.values[
                                                  0])
    cluster_table['GeoName'] = sname

    return cluster_table


def unpack_reference_sector_centers(reference_sector_centers: str) -> \
        Optional[List[Tuple[float, float]]]:
    ursc = None
    try:
        rsc = reference_sector_centers.split('),')
        xtuples = [xs + ')' for xs in rsc[:-1]]
        xtuples.append(rsc[-1])
        # SECURITY WARNING: eval
        ursc = [eval(xs) for xs in xtuples]
    except Exception as ee:
        print(ee)
        print(reference_sector_centers)
        traceback.print_exc(file=sys.stdout)

    return ursc


def plot_elbow_curve(visits_of_interest):
    df = visits_of_interest
    k_clusters = range(1, 10)
    kmeans = [KMeans(n_clusters=i) for i in k_clusters]
    y_axis = df[['latitude']]
    # X_axis = df[['longitude']]
    score = [kmeans[i].fit(y_axis).score(y_axis) for i in range(len(kmeans))]
    # Visualize
    plt.plot(k_clusters, score)
    plt.xlabel('Number of Clusters')
    plt.ylabel('Score')
    plt.title('Elbow Curve')
    plt.show()
