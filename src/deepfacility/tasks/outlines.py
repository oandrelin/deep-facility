import geopandas as gpd
import pandas as pd
import matplotlib
matplotlib.use('agg')
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)

from pathlib import Path
from shapely import Polygon

from deepfacility.utils import util, spatial

from deepfacility.utils.spatial import location_path, geom_col
from deepfacility.config.config import Config, ResultsClusteredHouseholds, Results, ResultFiles, ResultData


def create_clusters_shapes(cfg: Config,
                           gdf_adm_shape: gpd.GeoDataFrame,
                           df_clusters: pd.DataFrame,
                           location: str,) -> gpd.GeoDataFrame:
    """
    Create cluster shapes from cluster centers.
    :param cfg: configuration
    :param gdf_adm_shape: admin shapefile
    :param df_clusters: cluster centers
    :param location: location name
    :return: cluster shapes
    """
    res: ResultsClusteredHouseholds = cfg.results.clusters

    cols = res.adm_cols + [res.data_cols[0]]   # admin and cluster columns
    gdf = spatial.xy_to_gdf(df_clusters, res.xy_cols)     # convert to GeoDataFrame
    gdf = gdf[cols + [geom_col]]               # select columns
    gdf = gdf.dissolve(by=cols).reset_index()  # dissolve clusters to create shapes
    
    # create cluster shapes using convex hull
    gdf[geom_col] = gdf.geometry.apply(spatial.point_to_polygon)
    gdf[geom_col] = gdf.geometry.convex_hull

    # Ensure village shapes are only within admin boundaries.
    gdf = gpd.clip(gdf, gdf_adm_shape)

    # join household counts
    cluster_col = res.data_cols[0]
    counts_col = 'counts'
    counts_file = location_path(res.counts_file, location, mkdir=False)
    df_cnt = pd.read_csv(counts_file, encoding='utf-8')[[cluster_col, counts_col]]
    gdf = gdf.merge(df_cnt, on=cluster_col)
    gdf = gdf[cols + [counts_col, geom_col]]
    gdf = util.rename_df_cols(gdf, 'counts', 'households')
    return gdf


def export_cluster_shapes(cluster_shapes: gpd.GeoDataFrame, shape_file: Path) -> gpd.GeoDataFrame:
    """
    Export cluster shapes to shapefile.
    :param cluster_shapes: cluster shapes
    :param shape_file: output shape file
    :return: shapefile path
    """
    gdf = cluster_shapes[[isinstance(g, Polygon) for g in cluster_shapes.geometry]]
    gdf.to_file(filename=shape_file, driver="ESRI Shapefile")
    return gdf


def merge_results(cfg: Config, results: dict[str, ResultFiles]) -> ResultFiles:
    """
    Merge results from multiple locations.
    :param cfg: configuration
    :param results: results from multiple locations
    :return: merged results
    """
    # merge results
    res: Results = cfg.results
    rd: ResultData = merge_result_data(results)
    
    # save final results
    rf = ResultFiles(
            location_path(pattern=res.shapes.file, location=""),
            location_path(pattern=res.clusters.file, location=""),
            location_path(pattern=res.clusters.centers_file, location=""),
            location_path(pattern=res.clusters.counts_file, location=""),
            location_path(pattern=res.facilities.file, location=""))

    rd.save(rf)

    return rf


def merge_result_data(results: dict[str, ResultFiles]) -> ResultData:
    """
    Merge results data from multiple locations.
    :param results: results from multiple locations
    :return: merged results data
    """
    # Concatenate dataframes
    gdf_shapes: gpd.GeoDataFrame = gpd.GeoDataFrame(pd.concat([gpd.read_file(rf.shape_file) for rf in results.values()]))
    df_clusters: pd.DataFrame = pd.concat([pd.read_csv(rf.clusters_file, encoding='utf-8') for rf in results.values()])
    df_centers: pd.DataFrame = pd.concat([pd.read_csv(rf.centers_file, encoding='utf-8') for rf in results.values()])
    df_counts:  pd.DataFrame = pd.concat([pd.read_csv(rf.counts_file, encoding='utf-8') for rf in results.values()])
    df_facilities: pd.DataFrame = pd.concat([pd.read_csv(rf.facilities_file, encoding='utf-8') for rf in results.values()])
    
    # Sort dataframes
    gdf_shapes.sort_values(by=gdf_shapes.columns.to_list(), inplace=True)
    df_clusters.sort_values(by=df_clusters.columns.to_list(), inplace=True)
    df_centers.sort_values(by=df_centers.columns.to_list(), inplace=True)
    df_counts.sort_values(by=df_counts.columns.to_list(), inplace=True)
    df_facilities.sort_values(by=df_facilities.columns.to_list(), inplace=True)
    
    # Encapsulate results data
    rd = ResultData(gdf_shapes=gdf_shapes,
                    df_clusters=df_clusters,
                    df_centers=df_centers,
                    df_counts=df_counts,
                    df_facilities=df_facilities)
    return rd
