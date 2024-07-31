import geopandas as gpd
import pandas as pd
import pycountry

from pathlib import Path
from pyproj import CRS
from shapely import Geometry, Polygon

from deepfacility.utils import util
from typing import Any
from sklearn.cluster import KMeans

# Frequently used spatial global variables
geom_col = 'geometry'
default_crs: CRS = CRS("EPSG:4326")
default_projected_crs: CRS = CRS("EPSG:3857")


# Initialize data cache
memory = util.memory_cache()


def location_parts(location: str):
    """Split location string into parts."""
    return location.strip().split(":")


def locations_to_dataframe(locations: list[str], columns: list[str]):
    """
    Convert locations to DataFrame.
    :param locations: locations
    :param columns: columns
    :return: DataFrame
    """
    return pd.DataFrame([location_parts(c) for c in locations], columns=columns)


def filter_locations(df: pd.DataFrame, locations: list[str], columns: list[str]):
    """
    Filter DataFrame by locations.
    :param df: DataFrame
    :param locations: locations
    :param columns: columns
    :return: filtered DataFrame
    """
    # Convert locations to DataFrame
    df2: pd.DataFrame = locations_to_dataframe(locations, columns=columns)
    df2 = util.clean_dataframe(df2)
    df2 = df2.drop_duplicates()
    assert util.has_cols(df=df, columns=columns) and util.has_cols(df=df2, columns=columns)
    
    # Filter by joining with locations dataframe
    df_res = pd.merge(df, df2, on=columns)
    return df_res


def location_path(pattern: Path, location: str, mkdir: bool = True) -> Path:
    """
    Create file path with location.
    :param pattern: file path pattern
    :param location: location
    :param mkdir: create directory if not exists
    :return: file path
    """
    # Cleanup and populate file pattern with location
    pattern = str(pattern)
    loc_path = location.replace(":", "/")
    if '{location}' in pattern:
        file = str(pattern).format(location=loc_path)
    else:
        file = str(pattern)
    
    # Convert to Path
    file = Path(file)
    if mkdir:
        util.make_dir(file)
    return file


def point_to_polygon(g: Geometry):
    """Convert point geometry to a polygon geometry."""
    return Polygon(g.buffer(0.00001, cap_style=3)) if g.type == "Point" else g


def xy_to_gdf(df: pd.DataFrame, xy_cols) -> gpd.GeoDataFrame:
    """
    Convert coordinates DataFrame into GeoDataFrame with points.
    :param df: DataFrame
    :param xy_cols: columns with x, y coordinates
    :return: GeoDataFrame
    """
    gdf = gpd.GeoDataFrame(data=df,
                           geometry=gpd.points_from_xy(df[xy_cols[0]], df[xy_cols[1]]),
                           crs=default_crs)
    gdf = gdf.dropna()
    return gdf


@memory.cache
def join_xy_shapes(df: pd.DataFrame, xy_cols: list[str], gdf: gpd.GeoDataFrame, predicate: str = "within") -> gpd.GeoDataFrame:
    """
    Join DataFrame with xy columns to GeoDataFrame. Returns filtered points as GeoDataFrame.
    :param df: DataFrame
    :param xy_cols: xy columns
    :param gdf: GeoDataFrame
    :param predicate: Spatial join predicate
    """
    gdf_pts = xy_to_gdf(df, xy_cols)
    return gpd.sjoin(gdf_pts, gdf, predicate=predicate)


@memory.cache
def join_shapes_xy(gdf: gpd.GeoDataFrame,
                   df: pd.DataFrame,
                   xy_cols: list[str],
                   predicate: str = "contains") -> gpd.GeoDataFrame:
    """
    Join GeoDataFrame with DataFrame with xy columns. Returns filtered shapes GeoDataFrame.
    :param gdf: GeoDataFrame
    :param df: DataFrame
    :param xy_cols: xy columns
    :param predicate: Spatial join predicate
    :return: GeoDataFrame with shapes
    """
    gdf_pts = xy_to_gdf(df, xy_cols)
    return gpd.sjoin(gdf, gdf_pts, predicate=predicate)


def detect_country(df, xy_cols: list[str]):
    """
    Detect country from DataFrame with xy columns.
    :param df: DataFrame
    :param xy_cols: xy columns
    :return: country name, country code
    """
    
    if df.empty:
        raise ValueError("DataFrame is empty")
    
    if xy_cols[0] not in df.columns or xy_cols[1] not in df.columns:
        raise KeyError("Longitude and latitude columns are not found")
    
    # Read GeoPandas built-in country shapes
    gdf_shp = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
    gdf_shp = gdf_shp[['name', 'iso_a3', 'gdp_md_est', 'geometry']]

    # Determine the country by spatially joining country shapes with village
    # centers and taking the country containing the most village centers.
    gdf = join_shapes_xy(gdf_shp, df[xy_cols], xy_cols)
    gdf = gdf.groupby(['name', 'iso_a3']).size().to_frame(name='count')
    gdf = gdf.sort_values(by='count', ascending=False).head(n=1)

    name, code = gdf.iloc[0].name
    # Get the standardized country name and ISO code
    cnt = pycountry.countries.search_fuzzy(code)[0]
    assert code == cnt.alpha_3, "ISO code is not valid"

    return cnt.name, code

 
def get_plus_code(longitude: float, latitude: float) -> str:
    """
    Generates Google Plus Code
    :param latitude: latitude
    :param longitude: longitude
    :return: plus code string
    """
    from openlocationcode import openlocationcode as olc
    code = olc.encode(latitude, longitude)
    return code


def create_geojson(file: Path,
                   output_prefix: str,
                   working_dir: Path,
                   lon: str = None,
                   lat: str = None,
                   rename_geocol: bool = False) -> Path:
    """
    Create GeoJSON file from CSV or SHP file.
    :param file: input file
    :param output_prefix: output file prefix
    :param working_dir: working directory
    :param lon: longitude column
    :param lat: latitude column
    :param rename_geocol: rename columns to "lon", "lat"
    :return: GeoJSON file
    """
    # Create output GeoJSON file path
    geojson_filename = working_dir / (output_prefix + ".geojson")

    if file.suffix == '.csv':
        # Read CSV file and convert to GeoDataFrame
        assert lon is not None and lat is not None
        df = pd.read_csv(file, encoding='utf-8')
        gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon], df[lat]), crs="EPSG:4326")
    elif file.suffix == '.shp':
        # Read SHP file
        gdf = gpd.read_file(file, crs="EPSG:4326")
    else:
        raise NotImplementedError(f'file extension not supported! {file.name}')
    
    # Rename to "lon", "lat" if rename_geocol set to True
    if rename_geocol:
        gdf = util.rename_df_cols(gdf, [lon, lat], ['lon', 'lat'])
    
    # Write to GeoJSON file
    gdf.to_file(geojson_filename, driver='GeoJSON')
    
    return geojson_filename


@memory.cache
def kmeans_fit(X: Any, n_clusters: int, **kwargs) -> KMeans:
    """
    Create and fit the KMeans model.
    :param X: data
    :param n_clusters: number of clusters
    :param kwargs: additional arguments
    :return: KMeans model
    """
    kmeans_model: KMeans = KMeans(n_clusters=n_clusters, **kwargs)
    kmeans_model.fit(X)
    return kmeans_model
    