import geopandas as gpd
import pandas as pd
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
import numpy as np

from scipy.spatial import distance

from pathlib import Path

from deepfacility.config.config import Config
from deepfacility.utils import spatial, util

if util.is_linux():
    lock = None
else:
    import threading
    lock = threading.Lock()


# Initialize data cache
memory = util.memory_cache()


def convert_to_cartesian(lon, lat, elevation=0):
    """
    Convert longitude, latitude, and elevation to Cartesian coordinates.
    :param lon: Longitude in degrees (float).
    :param lat: Latitude in degrees (float).
    :param elevation: Elevation in meters (float, optional). Default is 0.
    :return: tuple: Cartesian coordinates (x, y, z).
    """
    # Radius of the Earth in meters
    earth_radius = 6378137.0  # unit: meter

    # Convert latitude and longitude from degrees to radians
    lat = np.radians(lat)  # divide by 180 and multiply by pi
    lon = np.radians(lon)

    # Convert using law of cosines
    R = (earth_radius + elevation)

    # Calculate Cartesian coordinates
    x = R * np.cos(lat) * np.cos(lon)
    y = R * np.cos(lat) * np.sin(lon)
    z = R * np.sin(lat)

    return x, y, z


def find_nearest_facility(location_xy: np.ndarray, facility_xy: np.ndarray):
    """
    Find the nearest facility for each location.
    :param location_xy: numpy.ndarray. Array of location coordinates.
    :param facility_xy: numpy.ndarray. Array of facility coordinates.
    :returns: tuple. A tuple containing two lists:
        - List of indices of the nearest facility for each location.
        - List of shortest distances from each location to its nearest facility.
    """
    # Calculate pairwise Euclidean distances using cdist
    distances = distance.cdist(location_xy, facility_xy, metric='euclidean')

    # Find the nearest facility for each household
    nearest_facility_indices = distances.argmin(axis=1)

    return nearest_facility_indices, distances.min(axis=1)


def calculate_minkowski_from_cartesian(df_locations: pd.DataFrame,
                                       df_facilities:  pd.DataFrame,
                                       left_on: str,
                                       right_on: str,
                                       p: float = 1.54,
                                       distance_col: str = 'minkowski'):
    """
    Calculate the Minkowski distance between location and facility coordinates. Both data must have x, y, z columns.
    :param df_locations: pd.DataFrame. DataFrame containing location coordinates.
    :param df_facilities: pd.DataFrame. DataFrame containing facility coordinates.
    :param left_on: str: Column name in df_locations to join on.
    :param right_on: str: Column name in df_facility to join on.
    :param p: float, optional: Minkowski distance parameter. Default is 1.54.
    :param distance_col: str: The name of the column where the Minkowski distance will be stored. Default is 'minkowski'.
    :returns: pd.DataFrame: DataFrame with Minkowski distances.
    """
    suffixes = ('_loc', '_facility')
    df_merged = pd.merge(df_locations, df_facilities, left_on=left_on, right_on=right_on, suffixes=suffixes)
    # Calculate the Minkowski distance using x, y, z coordinates
    df_merged[distance_col] = df_merged.apply(
        lambda row: distance.minkowski(
            [row['x_loc'], row['y_loc'], row['z_loc']],
            [row['x_facility'], row['y_facility'], row['z_facility']],
            p=p), axis=1)

    df_merged.columns = [col.rstrip('_loc') if col.endswith('_loc') else col for col in df_merged.columns]
    cols_to_keep = list(df_locations.columns) + [distance_col]
    merged_df = df_merged[cols_to_keep]
    return merged_df


def calculate_distance_df(df: pd.DataFrame,
                          xy_cols: list[str],
                          df2: pd.DataFrame,
                          xy_cols2: list[str],
                          col_prefix: str,
                          id_col: str = 'facility_id') -> pd.DataFrame:
    """
    Calculate the distance between each point in two dataframes.
    :param df: pd.DataFrame: The DataFrame containing the points.
    :param xy_cols: list[str]: The column names in `df` representing the lon and lat coordinates.
    :param df2: pd.DataFrame: The DataFrame containing the facility locations.
    :param xy_cols2: list[str]: The column names in `df2` representing the lon and lat coordinates.
    :param col_prefix: str: The prefix for the distance column names in the output DataFrame, which will be
                               {prefix}_minkowski and {prefix}_euclidean.
    :param id_col: Facility ID column name.
    :returns: pd.DataFrame: The input DataFrame with additional columns for the assigned facility and the distances.
    """
    # Calculate the cartesian coordinates for the points and the facilities
    if len(df) == 0 or len(df2) == 0:
        return df
    
    xy = convert_to_cartesian(df[xy_cols[0]].values, df[xy_cols[1]].values)
    df['x'] = xy[0]
    df['y'] = xy[1]
    df['z'] = xy[2]
    # df[['x', 'y', 'z']] = df.apply(
    #     lambda row: pd.Series(convert_to_cartesian(row[df_xy[0]], row[df_xy[1]])), axis=1)
    xy2 = convert_to_cartesian(df2[xy_cols2[0]].values, df2[xy_cols2[1]].values)
    df2['x'] = xy2[0]
    df2['y'] = xy2[1]
    df2['z'] = xy2[2]

    # get Series values as array for pair-wise distance calculation
    xy_ser = df[['x', 'y', 'z']].values
    xy_ser2 = df2[['x', 'y', 'z']].values

    nearest_indices, distances = find_nearest_facility(xy_ser, xy_ser2)

    # assign facilities id to household for easier calculation
    nearest_ids = df2[id_col][nearest_indices]
    assigned_id_col = f'{col_prefix}_assigned_id'
    df[assigned_id_col] = nearest_ids.values
    df[f'{col_prefix}_euclidean'] = distances

    df = calculate_minkowski_from_cartesian(df_locations=df,
                                            df_facilities=df2,
                                            left_on=assigned_id_col,
                                            right_on=id_col,
                                            p=1.54,
                                            distance_col=f'{col_prefix}_minkowski')

    df = df.copy().drop(['x', 'y', 'z'], axis=1)

    return df


@memory.cache
def calculate_distance(cfg: Config,
                       df_clusters: pd.DataFrame,
                       df_centers: pd.DataFrame,
                       center_xy_cols: list[str],
                       df_facilities: pd.DataFrame,
                       gdf_shp: gpd.GeoDataFrame = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Calculate the distance between the facility and households/centroids
    :param cfg: Config. The configuration object.
    :param df_clusters: pd.DataFrame. The DataFrame containing the clustered households.
    :param df_centers: pd.DataFrame. The DataFrame containing the cluster centroids.
    :param center_xy_cols: list[str]. The column names in `df_centers` representing the lon and lat coordinates.
    :param df_facilities: pd.DataFrame. The DataFrame containing the facility locations.
    :param gdf_shp: gpd.GeoDataFrame, optional. The GeoDataFrame containing the shapefile data. Default is None.
    :returns: tuple[pd.DataFrame, pd.DataFrame]. The DataFrames containing the distances between the df_facilities 
        and the households/centroids.
    """
    res = cfg.results

    df_clusters_in = df_clusters.reset_index(drop=True)
    df_centers_in = df_centers.reset_index(drop=True)

    if len(df_clusters_in) > 0 and len(df_facilities) > 0:
        # calculate distance between households and df_facilities
        df_clusters = calculate_distance_df(df=df_clusters_in,
                                            xy_cols=res.clusters.xy_cols,
                                            df2=df_facilities,
                                            xy_cols2=res.facilities.xy_cols,
                                            col_prefix='hh')
        
        # calculate distance between cluster centroids and df_facilities
        df_centers = calculate_distance_df(df=df_centers_in,
                                           xy_cols=center_xy_cols,
                                           df2=df_facilities,
                                           xy_cols2=res.facilities.xy_cols,
                                           col_prefix='village')
    else:
        df_clusters = df_clusters_in
        df_centers = df_centers_in
        cfg.results.logger.warning(f"No data for distance computation, skipped for optimal dataframes!")

    # calculate baseline distances if needed (baseline is provided)
    if gdf_shp is not None and cfg.inputs.has_baseline():
        # Load baseline facilities, covert to GeoDataFrame and join with shapefile
        df_pts = pd.read_csv(cfg.inputs.baseline_facilities.file, encoding='utf-8')
        gdf_loc = spatial.join_xy_shapes(df_pts, cfg.inputs.baseline_facilities.xy_cols, gdf_shp)
        
        if len(df_clusters) > 0 and len(gdf_loc) > 0:
            # calculate distances
            gdf_loc.drop(columns=['geometry'], inplace=True)
            gdf_loc.reset_index(drop=True, inplace=True)
            
            # calculate distance between households and baseline df_facilities
            df_clusters = calculate_distance_df(df=df_clusters,
                                                xy_cols=res.clusters.xy_cols,
                                                df2=pd.DataFrame(gdf_loc),
                                                xy_cols2=cfg.inputs.baseline_facilities.xy_cols,
                                                col_prefix='baseline_hh')
            
            # calculate distance between cluster centroids and baseline df_facilities
            df_centers = calculate_distance_df(df=df_centers,
                                               xy_cols=center_xy_cols,
                                               df2=pd.DataFrame(gdf_loc),
                                               xy_cols2=cfg.inputs.baseline_facilities.xy_cols,
                                               col_prefix='baseline_village')
        else:
            cfg.results.logger.warning(f"Unable to find any baseline locations within adm2 boundary!: "
                                       f"{df_centers.head(1)[cfg.results.clusters.adm_cols].values}")

    return df_clusters, df_centers


def plot_ecdf_distance(cfg: Config,
                       df: pd.DataFrame,
                       distance_col: str = 'minkowski',
                       scale: float = 1e-3,
                       location: str = "",
                       filename: Path = None,
                       plot_properties=None) -> bool | None:
    """
    Plots the empirical cumulative distribution function (ECDF) of the given distance data.
    :param cfg: Config: The configuration object.
    :param df: pd.DataFrame: The input dataframe containing the distance columns.
    :param distance_col: str, optional. The name of the column in df that contains the distance values. Default is 'minkowski'.
    :param scale: float, optional: The scaling factor to apply to the distance values. Default is 1e-3. assuming unit is kilometer
    :param location: str, optional: The location information to include in the plot title. Default is an empty string.
    :param filename: Path, optional: The file path to save the plot as an image. If not provided, the plot will not be saved.
    :param plot_properties: dict, optional: The dictionary of keyword arguments (kwargs) to be used in plot function.
    :returns: None
    """
    if distance_col not in df.columns:
        cfg.results.logger.warning(f"Column does not exist in dataframe, unable to plot ECDF, skipped: {distance_col}")
        return None

    minkowski_distance = (df[distance_col] * scale).sort_values()
    default_properties = {
        'color': 'blue',  # Default color
        'linestyle': 'solid',  # Default line style
        'marker': '.'
    }

    if plot_properties is not None:
        final_properties = {**default_properties, **plot_properties}
    else:
        final_properties = default_properties

    # Calculate the ECDF values
    ecdf = np.arange(1, len(minkowski_distance) + 1) / len(minkowski_distance) * 100.0

    plot_args = (minkowski_distance, ecdf, location, filename, final_properties)

    if lock:
        with lock:
            res = plot_minkowski_distance(*plot_args)
    else:
        res = plot_minkowski_distance(*plot_args)

    return res


def plot_minkowski_distance(minkowski_distance: np.ndarray,
                            ecdf: np.ndarray,
                            location: str,
                            filename: Path = None,
                            final_properties=None) -> bool:
    """
    Plot the Minkowski distance and ECDF.
    :param minkowski_distance: np.ndarray. The Minkowski distance values.
    :param ecdf: np.ndarray: The ECDF values.
    :param location: str: The location information to include in the plot title.
    :param filename: Path, optional. The file path to save the plot as an image. If not provided, the plot will not be saved.
    :param final_properties: dict, optional. The dictionary of keyword arguments (kwargs) to be used in plot function.
    :returns: bool: True if the plot is saved successfully, False otherwise.
    """
    final_properties = final_properties or {}
    # Plotting the ECDF
    plt.plot(minkowski_distance, ecdf, **final_properties)
    plt.xlabel('Minkowski Distance (KM)')
    plt.ylabel('Cumulative distribution %')
    plt.title(f'Cumulative Distribution of Minkowski Distance {location}')
    plt.grid(True)
    if filename is not None:
        Path(filename).parent.mkdir(exist_ok=True, parents=True)
        plt.savefig(filename)
    plt.close()
    return True
