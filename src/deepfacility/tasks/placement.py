import geopandas as gpd
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use('agg')
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

from pathlib import Path

from deepfacility.config.config import Config
from deepfacility.utils import spatial, util


# Initialize data cache
memory = util.memory_cache()


@memory.cache
def place_facilities(cfg: Config, df_clusters: pd.DataFrame, location: str) -> pd.DataFrame:
    """
    Recommend health facility placements by placing a specified number of
    points to be optimally distant from village households.
    :param cfg: configuration object
    :param df_clusters: cluster centers
    :param location: location name
    :return: facilities dataframe
    """
    # Get column names
    res = cfg.results
    cluster_col = res.clusters.data_cols[0]
    village_col = res.facilities.data_cols[0]
    adm_cols = res.clusters.adm_cols
    xy_cols = res.clusters.xy_cols
    clusters_cols = adm_cols + [res.clusters.data_cols[0]]

    # Initialize village names from cluster ids
    df_clusters[village_col] = df_clusters[cluster_col]
 
    # Group households by cluster (village) process each cluster
    optimal_facilities = []
    for i, dat in df_clusters.groupby(clusters_cols):
        # Prepare data for clustering
        x = np.array(dat[xy_cols[0]])
        y = np.array(dat[xy_cols[1]])
        X = np.array(list(zip(x, y))).reshape(len(x), 2)

        # Cluster points if possible
        if X.shape[0] >= 3:
            kmeans_model = spatial.kmeans_fit(X, res.facilities.n_facilities)
            centers = np.array(kmeans_model.cluster_centers_)
            if kmeans_model.n_iter_ == kmeans_model.max_iter:
                cfg.results.logger.warning(f"Clustering facilities didn't converge for: {location}")
        else:
            centers = X

        # Create a dataframe of optimal facilities
        df = pd.DataFrame(centers, columns=res.clusters.xy_cols)
        df[village_col] = i[-1]  # use cluster label as a village name

        # Add admin names
        adm_vals = list(i[:-1])  # admin values
        for col, name in zip(adm_cols, adm_vals):
            df[col] = name  # fill in adm col values
        
        # Append to list
        optimal_facilities.append(df)
    
    # Merge optimal placements all clusters, add Google plus codes and id column
    df_of: pd.DataFrame = pd.concat(optimal_facilities)[adm_cols + [village_col] + xy_cols].copy()
    df_of["plus"] = df_of.apply(lambda r: spatial.get_plus_code(r.lon, r.lat), axis=1)
    unique_ids = [f"{location}_{i}" for i in range(len(df_of))]
    df_of['facility_id'] = unique_ids
    df_of.reset_index(drop=True, inplace=True)
    return df_of

