import pandas as pd
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)

from deepfacility.config.config import Config, AdmPointsFile, ResultsClusteredHouseholds
from deepfacility.utils import util, spatial


# Initialize data cache
memory = util.memory_cache()


class ClusteredHouseholds:
    """
    Facilitates household clustering for a location. 
    Encapsulate clustered households and village centers data.
    """
    cfg: Config
    location: str
    df_households: pd.DataFrame
    df_village_centers: pd.DataFrame
        
    def __init__(self, cfg: Config, location: str, df_households: pd.DataFrame, df_village_centers: pd.DataFrame):
        self.cfg: Config = cfg         # configuration instance
        self.location: str = location  # location name

        self._valid: bool = True           # data is valid
        self._converged: bool = False      # clustering has converged
        self._df_counts: pd.DataFrame = None  # cluster counts statistics dataframe
        self._df_clusters: pd.DataFrame = df_households.copy()      # clustered households dataframe
        self._df_centers: pd.DataFrame = df_village_centers.copy()  # village centers dataframe
        
        # aliases for households and village centers config section
        hh = self.cfg.inputs.households
        vc = self.cfg.inputs.village_centers

        # rename village centers xy columns to match households
        if vc.xy_cols != hh.xy_cols:
            self._df_centers = util.rename_df_cols(self._df_centers, [vc.xy_cols, 'index'], hh.xy_cols)

        # add cluster column to centers if not present
        if self.cluster_col not in list(self._df_centers.columns):
            self._df_centers[self.cluster_col] = pd.Series(self._df_centers.index)

    @property
    def center_xy_cols(self):
        """Return the cluster center xy columns."""
        return [f"{self.cluster_col}_lon", f"{self.cluster_col}_lat"]
    
    @property
    def cluster_col(self):
        """Return the cluster column name."""
        return self.cfg.results.clusters.data_cols[0]
    
    @property
    def clusters_file(self):
        """Return the clusters file path."""
        file_pattern = self.cfg.results.clusters.file
        return spatial.location_path(file_pattern, self.location)
    
    @property
    def centers_file(self):
        """Return the cluster centers file path."""
        file_pattern = self.cfg.results.clusters.centers_file
        return spatial.location_path(file_pattern, self.location)

    @property
    def counts_file(self):
        """Return the cluster counts file path."""
        file_pattern = self.cfg.results.clusters.counts_file
        return spatial.location_path(file_pattern, self.location)
    
    @property
    def converged(self) -> bool:
        """Return True if clustering has converged."""
        return self._converged

    @property
    def valid(self) -> bool:
        """Return True if data is valid."""
        ok = self._converged is not None and self._valid
        ok &= self._df_clusters is not None and len(self._df_clusters) > 0
        ok &= self._df_centers is not None and len(self._df_centers) > 0
        return ok
    
    @valid.setter
    def valid(self, value):
        """Set the data validity flag."""
        self._valid = value
    
    @property
    def centers_df(self) -> pd.DataFrame:
        """Return the village centers dataframe."""
        return self._df_centers

    @centers_df.setter
    def centers_df(self, value):
        """Set the village centers dataframe."""
        self._df_centers = value

    @property
    def clusters_df(self):
        """Return the clustered households dataframe."""
        return self._df_clusters

    @clusters_df.setter
    def clusters_df(self, value):
        """Set the clustered households dataframe."""
        self._df_clusters = value

    def _prep_centers(self) -> None:
        """Prepare the village centers dataframe."""
        vc: AdmPointsFile = self.cfg.inputs.village_centers
        cc_cols = [self.cluster_col] + vc.adm_cols + vc.xy_cols + self.center_xy_cols
        self._df_centers = self._df_centers[cc_cols]

    def _prep_clusters(self):
        """Prepare the clustered households dataframe."""
        vc: AdmPointsFile = self.cfg.inputs.village_centers
        cs: ResultsClusteredHouseholds = self.cfg.results.clusters
        
        name_col = vc.adm_cols[-1]
        if self._converged:
            # join by cluster to match the village name
            df_cc = self._df_centers[[self.cluster_col, name_col]]
            self._df_clusters = self._df_clusters.merge(df_cc, on=self.cluster_col)
        else:
            self._df_clusters[name_col] = self._df_clusters[self.cluster_col]
        
        # finalize clusters dataframe
        sel_cols = cs.adm_cols + [self.cluster_col] + cs.xy_cols
        sort_cols = [self.cluster_col] + cs.adm_cols + cs.xy_cols
        self._df_clusters = self._df_clusters[sel_cols].sort_values(sort_cols)

    def _calc_counts(self):
        """Calculate cluster counts and small clusters."""
        cs: ResultsClusteredHouseholds = self.cfg.results.clusters
        cols = cs.adm_cols + cs.data_cols
        # Count households in each cluster
        self._df_counts = self._df_clusters.groupby(by=cols).agg(counts=(cs.xy_cols[0], 'count'))
        # Set small clusters flag
        self._df_counts['small'] = self._df_counts.counts < self.cfg.args.threshold_households

    def finalize(self, converged: bool):
        """Finalize the clustering process. Prepare the dataframes and calculate cluster counts."""
        self._converged = converged
        self._prep_centers()
        self._prep_clusters()
        self._calc_counts()
        return True

    def save(self) -> object:
        """Save the clustered households and village centers data to files."""
        if self.valid:
            self._df_clusters.to_csv(self.clusters_file, index=False, encoding='utf-8')
            self._df_centers.to_csv(self.centers_file, index=False, encoding='utf-8')
            self._df_counts.reset_index().to_csv(self.counts_file, index=False, encoding='utf-8')
        else:
            raise ValueError(f"Invalid data for '{self.location}'")
        return self


def cluster_houses_by_villages_centers(cfg: Config,
                                       df_households: pd.DataFrame,
                                       df_villages_centers: pd.DataFrame,
                                       location: str) -> ClusteredHouseholds:
    """Script to cluster households initialized at given village centers via K-means"""
    ok = True
    if df_households is None or len(df_households) == 0:
        cfg.results.logger.warning(f"No household data for: {location}")
        ok = False

    if df_villages_centers is None or len(df_villages_centers) == 0:
        cfg.results.logger.warning(f"No villages centers data for: {location}")
        ok = False

    hh: AdmPointsFile = cfg.inputs.households
    ch = ClusteredHouseholds(cfg=cfg,
                             location=location,
                             df_households=df_households,
                             df_village_centers=df_villages_centers)

    if not ok:
        cfg.results.logger.info(f"Skipping clustering for: {location}.")
        return ch

    try:
        # Cluster households by village centers in parallel
        converged = cluster_points(df_points=ch.clusters_df,
                                   df_centers=ch.centers_df,
                                   xy_cols=hh.xy_cols,
                                   cluster_col=ch.cluster_col,
                                   center_xy_cols=ch.center_xy_cols)
    except ValueError as ex:
        cfg.results.logger.error(f"Failed to cluster households:")
        for m in ex.args:
            cfg.results.logger.error(f"{location}: {m}")

        ch.valid = False
        return ch
    
    # Finalize dataframes
    ch.finalize(converged)
    
    if not converged:
        cfg.results.logger.warning(f"Clustering has not converged for: '{location}'")
        
    return ch


def cluster_points(df_points: pd.DataFrame,
                   df_centers: pd.DataFrame,
                   xy_cols: list[str],
                   cluster_col: str = None,
                   center_xy_cols: list[str] = None) -> bool:
    """Cluster points by centers using K-means algorithm."""
    # Determine cluster column and center xy columns
    cluster_col = cluster_col or 'cluster'
    center_xy_cols = center_xy_cols or [f"{cluster_col}_lon", f"{cluster_col}_lat"]
    
    # Prepare data for KMeans clustering
    points = df_points[xy_cols].to_numpy()
    centers = df_centers[xy_cols].to_numpy()
    n_clusters = len(centers)
    
    # Perform KMeans clustering
    kmeans_model = spatial.kmeans_fit(X=points, n_clusters=n_clusters, init=centers, n_init=1)

    # Capture cluster assignments and cluster centers
    df_points[cluster_col] = kmeans_model.labels_
    df_centers[center_xy_cols[0]], df_centers[center_xy_cols[1]] = kmeans_model.cluster_centers_[:, 0], kmeans_model.cluster_centers_[:, 1]
    
    # Check if clustering has converged
    converged = kmeans_model.n_iter_ < kmeans_model.max_iter
    return converged

    

