import time

import geopandas as gpd
import pandas as pd
import logging

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, Future
from pathlib import Path
from typing import Optional

from deepfacility.data import inputs, downloads
from deepfacility.tasks import outlines, placement, clustering, distance
from deepfacility.utils import util, spatial

from deepfacility.config.config import (Config, Args, Inputs, Workflow, 
                                        ResultsClusteredHouseholds, ResultFiles, filter_by_locations)
from deepfacility.tasks.clustering import ClusteredHouseholds
from deepfacility.tasks.distance import plot_ecdf_distance


# set pool executor variable to point to ThreadPoolExecutor if on Linux or ThreadPoolExecutor if on Windows or Mac
PoolExecutor = ProcessPoolExecutor if util.is_linux() else ThreadPoolExecutor

    
class DataPrepWorkflow(Workflow):
    """Data preparation workflow."""
    downloader: downloads.Downloads
    inputs: inputs.DataInputs
    
    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.logger = self.cfg.inputs.logger
        self.downloader = downloads.Downloads(cfg=self.cfg, logger=self.logger)
        self.data_inputs = inputs.DataInputs(cfg=self.cfg)
  
    def prepare_inputs(self, country: str) -> tuple[list[Path], Path, Path, Path, bool]:
        """
        Prepare input files for the clustering and placement tasks.
        :param country: str: Country name
        :return: Shape files, households file, village centers file, baseline file, success flag
        """
        cfg: Config = self.cfg
        
        try:
            # Prepare shapes and households files
            shp_files: list[Path] = self.prepare_shape_files(country=country)
            hh_file: Path = self.prepare_households_file(country=country, shape_files=shp_files)

            # Validate columns
            self.check_input_households(shapes_file=shp_files[-1],
                                                  households_file=hh_file,
                                                  stats_file=hh_file.with_suffix('.stats.csv'))
            
            # Prepare village centers
            cfg.inputs.raise_if_stopped()
            vc_file: Path = self.data_inputs.prepare_village_locality(village_locality=cfg.args.village_centers, shape_files=shp_files)
            
            # Prepare baseline facilities
            if cfg.args.has_baseline():
                cfg.inputs.raise_if_stopped()
                bl_file: Path = self.data_inputs.prepare_baseline_facilities(
                    baseline_file=cfg.args.baseline_facilities.file,
                    baseline_xy_cols=cfg.args.baseline_facilities.xy_cols,
                    shape_file=shp_files[-1],
                    shape_adm_cols=cfg.inputs.shapes.adm_cols,
                    info_cols=cfg.args.baseline_facilities.info_cols)
            else:
                bl_file = ''
                self.logger.info("Skipping baseline facilities, no file provided.")
    
        except InterruptedError as e:
            cfg.inputs.cleanup()
            cfg.inputs.remove_files()
            return [], Path(), Path(), Path(), False
        
        # Store the list of all locations in the input dir
        df = pd.read_csv(vc_file, encoding='utf-8')
        df = df[cfg.inputs.village_centers.adm_cols[:-1]].drop_duplicates()
        locations = [":".join(r) for r in df.to_numpy()]
        cfg.inputs.all_locations_file.write_text('\n'.join(locations))
    
        return shp_files, hh_file, vc_file, bl_file, True

    def check_input_households(self, shapes_file: Path, households_file: Path, stats_file: Path) -> bool:
        """
        Check the number of households per shape meets the configured threshold.
        :param shapes_file: Shapes file.
        :param households_file: Households file.
        :param stats_file: Path to save the stats.
        :return: True if the number of shapes is sufficient.
        """
        shapes: gpd.GeoDataFrame = gpd.read_file(shapes_file)
        df_households: pd.DataFrame = pd.read_csv(households_file)

        # Calculate household counts per shape stats
        df_adm = df_households.groupby(self.cfg.inputs.households.adm_cols).size().to_frame(name='counts')
        df_stats = df_adm["counts"].describe().apply(round)

        # Calculate the percentage of shapes with households
        actual, expected = df_stats['count'], len(shapes)
        perc: int = 100 * actual // expected

        # Create stats DataFrame
        df_stats = df_stats.reset_index().rename(columns={'index': 'metric', 'counts': 'households'})
        df_stats = df_stats[df_stats['metric'] != 'count']

        # Log stats
        self.logger.info("Shape/Household Stats:")
        self.logger.info(df_stats.to_string(index=False))
        self.logger.info(f"Shapes with households: {perc}% ({actual}/{expected})")

        # Check if the number of shapes is sufficient
        if perc < 100 - int(self.cfg.args.threshold_village_perc):
            self.logger.warning("The number of shapes is too low.")

        # Save stats
        df_stats.to_csv(stats_file, index=False, encoding='utf-8')

        return True
    
    def prepare_shape_files(self, country: str) -> list[Path]:
        """
        Download, extract and clean country shape files.
        :param country: str: Country name
        :return: List of admin shape files
        """
        # country adm3 shapes
        zip_file = self.downloader.download_country_shapes(country=country)
        shape_files: list[Path] = self.data_inputs.prepare_country_shapes(zip_file=zip_file)
        assert [f.is_file() for f in shape_files], "Shape files not ready."
        return shape_files
    
    def prepare_households_file(self, country: str, shape_files: list[Path]) -> Path:
        """
        Download, merge and transform buildings data into households.
        :param country: str: Country name
        :param shape_files: list[Path]: List of admin shape files
        :return: Households file
        """
        buildings_file = self.downloader.download_buildings(country=country)
        households_file = self.data_inputs.prepare_households(buildings_file=buildings_file,
                                                              buildings_xy_cols=self.cfg.inputs.buildings.xy_cols,
                                                              shapes_file=shape_files[-1],
                                                              shapes_adm_cols=self.cfg.inputs.shapes.adm_cols)
        assert households_file.is_file(), "Households file is not ready."
        return households_file


# Processing flows
class ScientificWorkflow(Workflow):
    """Scientific workflow for clustering and optimal facility"""
    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.logger = self.cfg.results.logger
    
    def process_locations(self) -> Optional[tuple[ResultFiles, list]]:
        """
        Run the scientific workflow for specified locations.
        :return: ResultFiles object, list of failed locations
        """
        ts = time.time()
        try:
            self.logger.info('Starting household clustering...')
            chs: dict[str, ClusteredHouseholds] = self.cluster_households(locations=self.cfg.locations)
            self.logger.info(f"Completed household clustering in: {util.elapsed_time_str(ts)}.")
        
            valid, failed = self.validate_clusters(chs)  # check required files exist
        
            # Outline and Place
            ts = time.time()
            self.logger.info('Starting optimal placement...')
            results: dict[str, ResultFiles] = self.outline_and_place(clustered_households=valid)
            self.logger.info(f"Completed optimal placement in: {util.elapsed_time_str(ts)}.")
            for loc, res in results.items():
                if res:  # record successful results
                    results[loc] = res
                else:    # remove failed locations
                    del results[loc]
                    failed.append(loc)
        
            ts = time.time()
            # Check if the processing was stopped
            self.cfg.results.raise_if_stopped()
            # Merge and plot final results
            final_results: ResultFiles = self.process_results(results)
            self.logger.info(f"Completed merging and plotting in: {util.elapsed_time_str(ts)}.")
    
        except InterruptedError as e:
            self.cfg.results.cleanup()
            return None, False
    
        return final_results, failed
    
    def cluster_households(self, locations: list[str]) -> dict[str, ClusteredHouseholds]:
        """
        Cluster households for specified locations.
        :param locations: list[str]: List of locations
        :return: dict[str, ClusteredHouseholds]: Clustered households for each location
        """
        ins: Inputs = self.cfg.inputs
        self.logger.info(f"Clustering households for locations: {len(locations)}")
        
        # read all households and village centers
        df_hh_all = pd.read_csv(ins.households.file, index_col=None, encoding='utf-8')
        df_vc_all = pd.read_csv(ins.village_centers.file, encoding='utf-8')
        
        with PoolExecutor() as executor:  # init parallel processing
            # Inti counts for tracking progress
            total_count, done_count, done_perc = len(self.cfg.locations), 0, 0
            fts, hh_cc = {}, {}  # futures and clustered households dicts
    
            def process_future(ft: Future):
                """Callback closure to handle the future result."""
                nonlocal hh_cc, total_count, done_count, done_perc
                if self.cfg.results.is_stopped():
                    return
    
                # Get and save the result
                ch: ClusteredHouseholds = ft.result()
                ch.save()
                
                # capture the result
                hh_cc[ch.location] = ch
    
                # Track and report progress
                done_perc = util.report_progress(logger=self.logger,
                                                 name="Clustering",
                                                 items=hh_cc,
                                                 done_perc=done_perc,
                                                 total_count=total_count)
    
                return
            
            # For each location, submit the task to the pool
            for location in self.cfg.locations:
                self.cfg.results.raise_if_stopped()
                # Filter households and village centers by location
                df_hh = filter_by_locations(ins=self.cfg.inputs, df=df_hh_all, locations=[location])
                df_vc = filter_by_locations(ins=self.cfg.inputs, df=df_vc_all, locations=[location])
                
                # Submit the clustering tasks to the pool
                fts[location] = executor.submit(
                    clustering.cluster_houses_by_villages_centers,
                    cfg=self.cfg,
                    df_households=df_hh,
                    df_villages_centers=df_vc,
                    location=location)
    
                self.cfg.results.raise_if_stopped()
                fts[location].add_done_callback(process_future)
    
        return hh_cc
    
    def outline_and_place(self, clustered_households: dict[str, ClusteredHouseholds]) -> dict[str, ResultFiles]:
        """
        Outline and optimally place facilities for clustered households.
        :param clustered_households: dict[str, ClusteredHouseholds]: Clustered households for each location
        :return: dict[str, ResultFiles]: Result files for each location
        """
        res = self.cfg.results
        # Init results dict and progress tracking
        results_dict: dict[str, Optional[ResultFiles]] = {}
        total_count, done_count, done_perc = len(clustered_households), 0, 0
        
        def process_future(ft: Future, location: str):
            """Callback closure to handle the future result."""
            nonlocal results_dict, total_count, done_count, done_perc
            if res.is_stopped():
                return
            
            # capture the result
            results_dict[location] = ft.result()
    
            # Track and report progress
            done_perc = util.report_progress(logger= self.logger,
                                             name="Placement",
                                             items=results_dict,
                                             done_perc=done_perc,
                                             total_count=total_count)
            return
        
        fts: dict[str, Future] = {}
        with PoolExecutor() as executor:  # init parallel processing
            # For each location, submit the task to the pool
            for loc, ch in clustered_households.items():
                res.raise_if_stopped()
                self.logger.debug(f"Outlining and placing for: {loc}...")
                fts[loc] = executor.submit(
                    self.outline_and_place_clustered_households,
                    ch=ch,
                    location=loc,
                    adm_files=self.cfg.inputs.shape_files,
                    has_baseline=self.cfg.inputs.has_baseline())
                
                from functools import partial
                process_future2 = partial(process_future, location=loc)
                fts[loc].add_done_callback(process_future2)
            
        return results_dict
    
    def outline_and_place_clustered_households(self,
                                               ch: ClusteredHouseholds,
                                               location: str,
                                               adm_files: list[Path],
                                               has_baseline: bool) -> Optional[ResultFiles]:
        """
        Create village shapes and recommend health facility placement.
        :param ch: ClusteredHouseholds: Clustered households
        :param location: str: Location name
        :param adm_files: list[Path]: List of admin shape files
        :param has_baseline: bool: Flag to indicate if baseline facilities are available
        :return: ResultFiles: Result files
        """
        # Prep shape GeoDataFrames
        gdf_adm3_all = gpd.read_file(adm_files[-1])
        gdf_adm3 = filter_by_locations(ins=self.cfg.inputs, df=gdf_adm3_all, locations=[location])
    
        # Check if the clustered households file exists and is not empty
        if not (ch.valid and ch.clusters_file.is_file()):
            return None
    
        df_cs = pd.read_csv(ch.clusters_file, encoding='utf-8')
        if len(df_cs) == 0:
            return None
    
        # Create cluster(village) shapes
        gdf_shp = outlines.create_clusters_shapes(cfg=self.cfg,
                                                  gdf_adm_shape=gdf_adm3,
                                                  df_clusters=df_cs,
                                                  location=location)
        
        self.logger.debug(f"Completed creating cluster shapes for: {location}.")
        
        # Save cluster shapes
        shape_file = spatial.location_path(pattern=self.cfg.results.shapes.file, location=location)
        outlines.export_cluster_shapes(cluster_shapes=gdf_shp, shape_file=shape_file)
        
        self.logger.debug(f"Completed exporting cluster shapes for: {location}.")
        
        # Place facilities
        df_facilities = placement.place_facilities(cfg=self.cfg, df_clusters=df_cs, location=location)
        self.logger.debug(f"Completed facility placement for: {location}.")
    
        # Calculate distances from household to nearest facility and save it
        ch.clusters_df, ch.centers_df = distance.calculate_distance(self.cfg,
                                                                    df_clusters=ch.clusters_df,
                                                                    df_centers=ch.centers_df,
                                                                    center_xy_cols=ch.center_xy_cols,
                                                                    df_facilities=df_facilities,
                                                                    gdf_shp=gdf_shp)
        
        # Save the calculated distances and cluster centers
        ch.clusters_df.to_csv(ch.clusters_file, index=False, encoding='utf-8')
        ch.centers_df.to_csv(ch.centers_file, index=False, encoding='utf-8')
        self.logger.debug(f"Completed distance calculations for: {location}.")
        
        self.cfg.results.raise_if_stopped()
        # Plot commune population coverage for recommended health facilities
        distance.plot_ecdf_distance(cfg=self.cfg,
                                    df=ch.clusters_df,
                                    filename=ch.clusters_file.with_suffix('.png'),
                                    location=location,
                                    distance_col='hh_minkowski')
    
        self.logger.debug(f"Completed plotting distance for: {location}.")
    
        if has_baseline:
            self.cfg.results.raise_if_stopped()
            
            # Plot commune population coverage for baseline health facilities
            distance.plot_ecdf_distance(
                cfg=self.cfg,
                df=ch.clusters_df,
                filename=ch.clusters_file.parent / "population_coverage_baseline.png",
                location=location + " (baseline)", 
                distance_col='baseline_hh_minkowski',
                plot_properties={'color': 'darkgoldenrod'})
            
            self.logger.debug(f"Completed plotting baseline distance for: {location}.")
    
        # Save recommended health facility placements to file
        facilities_file = spatial.location_path(pattern=self.cfg.results.facilities.file, location=location)
        df_facilities.to_csv(facilities_file, index=False, encoding='utf-8')
        
        self.logger.debug(f"Completed exporting facilities for: {location}.")
    
        # Store result files into a ResultFiles object
        results = ResultFiles(shape_file=shape_file,
                              clusters_file=ch.clusters_file,
                              centers_file=ch.centers_file,
                              counts_file=ch.counts_file,
                              facilities_file=facilities_file)
    
        self.logger.debug(f"Completed outlining and placing for: {location}.")
    
        if not facilities_file:
            self.logger.info(f"Skipping outlining, clustered households file not found or is empty: {location}")
    
        return results
    
    def validate_clusters(self, clustered_households: dict[str, ClusteredHouseholds]) -> tuple[dict[str, ClusteredHouseholds], list]:
        """
        Validate clustered households and check required files exist.
        :param clustered_households: dict[str, ClusteredHouseholds]: Clustered households for each location
        :return: dict[str, ClusteredHouseholds], list: Valid clustered households, failed locations    
        """
        # Validate clustered households
        valid = {}
        failed = []
        for loc, ch in clustered_households.items():
            if ch.valid:
                assert ch.clusters_file.is_file(), f"The {loc} clusters file {str(ch.clusters_file)} not found."
                assert ch.centers_file.is_file(), f"The {loc} centers file {str(ch.centers_file)} not found."
                assert ch.counts_file.is_file(), f"The {loc} counts file {str(ch.counts_file)} not found."
                valid[loc] = ch
            else:
                failed.append(loc)
    
        if len(failed) > 0:
            content = '\n'.join(failed)
            ff = self.cfg.results.locations_file.with_suffix(".failed.csv")
            ff.write_text(content)
    
        return valid, failed
    
    def process_results(self, results: dict[str, ResultFiles]) -> Optional[ResultFiles]:
        """
        Merge and plot final results.
        :param results: dict[str, ResultFiles]: Result files for each location
        :return: ResultFiles: Merged result files
        """
        if len(results) > 0:
            # Merge commune results, each result file 'type' into a single file
            rf: Optional[ResultFiles] = outlines.merge_results(cfg=self.cfg, results=results)
            self.logger.info(f"Completed merging results.")
        else:
            rf = None
    
        if rf:
            # Plot overall population coverage for recommended health facilities
            self.plot_distances(rf)
            self.logger.info(f"Completed distance calculations.")
        return rf
        
    def plot_distances(self, result_files: ResultFiles):
        """
        Plot cumulative health facility population coverage by distances.
        :param result_files: ResultFiles: Result files
        """
        hh_cluster = pd.read_csv(result_files.clusters_file, encoding='utf-8')
        optimal_png = result_files.clusters_file.parent / "population_coverage_optimal.png"
        plot_ecdf_distance(cfg=self.cfg,
                           df=hh_cluster,
                           filename=optimal_png,
                           location=self.cfg.run_name, 
                           distance_col='hh_minkowski')
    
        if self.cfg.inputs.has_baseline():
            baseline_png = result_files.clusters_file.parent / "population_coverage_baseline.png"
            plot_ecdf_distance(cfg=self.cfg,
                               df=hh_cluster,
                               filename=baseline_png,
                               location=self.cfg.run_name + " (baseline)",
                               distance_col='baseline_hh_minkowski',
                               plot_properties={'color': 'darkgoldenrod'})
    
        # Check clusters-households counts against thresholds
        cls: ResultsClusteredHouseholds = self.cfg.results.clusters
        self.check_thresholds(result_files.clusters_file, columns=cls.adm_cols + cls.data_cols)

    def check_thresholds(self, clusters_file: Path, columns: list[str]) -> bool:
        """
        Check the number of households per cluster meets the configured threshold.
        :param clusters_file: Path to the clusters file.
        :param columns: Columns to group by.
        :return: True if the number of households is sufficient.
        """
        # Get thresholds from configuration
        a: Args = self.cfg.args
        threshold_households = a.threshold_households
        threshold_village_perc = a.threshold_village_perc

        # Calculate household counts per cluster
        df: pd.DataFrame = pd.read_csv(clusters_file, encoding='utf-8')
        df_cnt = df.groupby(by=columns).size().to_frame(name='counts')

        # Set small village flag, save to CSV
        df_cnt['small'] = df_cnt.counts < threshold_households
        df_cnt.reset_index().to_csv(clusters_file.parent.joinpath("cluster_counts.csv"), index=False, encoding='utf-8')

        # Calculate invalid cluster counts and percentage
        df_inv = df_cnt[df_cnt.counts < threshold_households]
        invalid_cnt = len(df_inv)
        df_stats = df_cnt["counts"].describe().apply(round)
        invalid_perc = round(100.0 * invalid_cnt / df_stats['count'], 2)

        # Log stats
        self.logger.info(f"Village/Households Stats:")
        df_stats: pd.DataFrame = df_stats.reset_index()
        df_stats['index'] = df_stats.apply(lambda r: f"village households {str(r['index']).ljust(4)}", axis=1)
        df_stats.loc[len(df_stats)] = [f"small villages (<{threshold_households} hh)", f"{invalid_perc}%"]
        df_stats.loc[len(df_stats)] = [f"total number of villages", df_stats.iloc[0, 1]]
        df_stats = df_stats.iloc[1:, :].copy()

        # Prepare stats DataFrame
        df_stats = util.rename_df_cols(df_stats, 'index', 'metric')

        # Log stats and save to CSV
        self.logger.info(df_stats.to_string(index=False))
        df_stats.to_csv(clusters_file.parent.joinpath("cluster_stats.csv"), index=False, encoding='utf-8')

        # Log invalid clusters and their counts
        self.logger.info("Number households per location:")
        for t in df_inv.index:
            self.logger.info(f"    {':'.join([str(v) for v in t])} : {df_inv.loc[t][0]}")

        self.logger.info("")

        # Check if the number of invalid clusters is below the threshold
        ok = invalid_perc < threshold_village_perc
        if not ok:
            self.logger.warning(
                f"The percent of villages with low number of households: {invalid_perc} % (less than {threshold_households}).")

        return ok