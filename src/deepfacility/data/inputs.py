import geopandas as gpd
import pandas as pd
import time

from pathlib import Path

from deepfacility.config.config import Config, WorkflowEntity, AdmPointsFile
from deepfacility.utils import spatial
from deepfacility.utils import util


# Initialize data cache
memory = util.memory_cache()


class DataInputs(WorkflowEntity):
    """Data inputs preparation."""
    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.logger = self.cfg.inputs.logger
        
    def prepare_country_shapes(self, zip_file: Path) -> list[Path]:
        """
        Prepare country shapes from the GADM database.
        :param zip_file: Path to the downloaded zip file.
        :return: List of paths to the shape files.
        """
        cfg: Config = self.cfg
        assert zip_file.is_file(), "Raw shape file not found."
        shape_files: list[Path] = cfg.inputs.shape_files
        # Check if all shape files exist
        if all([f.is_file() for f in shape_files]):
            return shape_files
    
        # Load shapes
        gdf_list: list[gpd.GeoDataFrame] = [
            gpd.read_file(format_zip_path(zip_file, f)) for f in shape_files]
    
        # Clean gdf objects
        adm_cols = cfg.inputs.shapes.adm_cols
        gdf_list: list[gpd.GeoDataFrame] = [util.clean_dataframe(gdf, adm_cols, keep=True) for gdf in gdf_list]
    
        # Save shape files to inputs dir
        for gdf, f in zip(gdf_list, shape_files):
            util.make_dir(f)
            gdf.to_file(f)
    
        return shape_files  # [adm0_file, adm3_file]
      
    def prepare_households(self,
                           buildings_file: Path,
                           buildings_xy_cols: list[str],
                           shapes_file: Path,
                           shapes_adm_cols: list[str]) -> Path:
        """
        Prepare google households data and the country shapefile.
        :param buildings_file: Path to the Google buildings file.
        :param buildings_xy_cols: Google buildings longitude and latitude columns names.
        :param shapes_file: Path to the country shapefile.
        :param shapes_adm_cols: Shapefile admin column names.
        :return: Path to the prepared households file, as configured in the input section.
        """
        # Get the households file path from the config.
        hh_file: Path = self.cfg.inputs.households.file
    
        # Check if the households file already exists.
        if hh_file.is_file():
            self.logger.info("Skipping households prep, file already exists.")
            return hh_file
    
        # Create an empty file to indicate household preparation has started.
        hh_file.write_text("")  # This is used to track the workflow progress.
        
        # Load the shapefile
        gdf = gpd.read_file(shapes_file)
        
        # Load the buildings data
        df_xy = pd.read_feather(buildings_file, columns=buildings_xy_cols)
        
        # Process the buildings data
        df = self.process_buildings(gdf_shapes=gdf, adm_cols=shapes_adm_cols, df_xy=df_xy, xy_cols=buildings_xy_cols)

        # Save the prepared households data
        df.to_csv(hh_file, index=False, encoding='utf-8')
        
        return hh_file
    
    def process_buildings(self,
                          gdf_shapes: gpd.GeoDataFrame,
                          adm_cols: list[str],
                          df_xy: pd.DataFrame,
                          xy_cols: list[str]) -> pd.DataFrame:
        """Wrapper for the process_google_buildings function."""
        st = time.time()  # Capture start time
        
        df_hh = process_google_buildings(
            gdf_shapes=gdf_shapes,
            adm_cols=adm_cols,
            df_xy=df_xy,
            xy_cols=xy_cols,
            hh_adm_cols=self.cfg.inputs.households.adm_cols,
            hh_xy_cols=self.cfg.inputs.households.xy_cols,
            stop_fn=self.cfg.inputs.raise_if_stopped)
        
        self.logger.info(f"Completed processing buildings in: {util.elapsed_time_str(st)}.")
        
        return df_hh

    def prepare_village_locality(self, village_locality: AdmPointsFile, shape_files: list[Path]) -> Path:
        """
        Prepare user provided village centers file.
        :param village_locality: User provided village centers file.
        :param shape_files: Shape files.
        :return: Path to the prepared village centers file.
        """
        # Set village centers config section alias
        vc: AdmPointsFile = self.cfg.inputs.village_centers
    
        # # Check if the village centers file already exists
        # if vc.file.is_file():
        #     self.logger.info("Skipping village centers prep, file already exists.")
        #     return vc.file
    
        self.logger.info(f"Preparing village centers from: {vc.file.name}")
        # Create an empty file to indicate village centers preparation has started.
        vc.file.write_text("")  # This is used to track the workflow progress.
    
        # Prepare village centers
        df = self.prepare_village_centers(village_locality_file=village_locality.file,
                                          xy_cols=village_locality.xy_cols,
                                          village_col=village_locality.adm_cols[-1],
                                          shape_file=shape_files[-1],
                                          adm_cols=self.cfg.inputs.shapes.adm_cols)
    
        # Validate columns
        cols = vc.adm_cols + vc.xy_cols
        assert util.has_cols(df, cols), f"Prepared village centers are missing columns: {str(cols)}"
    
        # Save the prepared village centers
        df.to_csv(vc.file, index=False, encoding='utf-8')
        spatial.create_geojson(vc.file, Path(vc.file).stem, Path(vc.file.parent), vc.xy_cols[0], vc.xy_cols[1])
    
        return vc.file

    def prepare_village_centers(self,
                                village_locality_file: Path,
                                xy_cols: list[str],
                                village_col: str,
                                shape_file: Path,
                                adm_cols) -> pd.DataFrame:
        """
        Prepare village centers.
        :param village_locality_file: Path to the village centers file.
        :param xy_cols: Village centers longitude and latitude columns names.
        :param village_col: Village column name.
        :param shape_file: Path to the shape file.
        :param adm_cols: Shapefile admin column names.
        :return: DataFrame with prepared village centers.
        """
        # Set a village center section alias
        vc: AdmPointsFile = self.cfg.inputs.village_centers
        
        # Load village centers
        df = pd.read_csv(village_locality_file, encoding='utf-8')
        df = util.clean_dataframe(df, [village_col])

        # Validate columns
        old_cols = [village_col] + xy_cols
        assert util.has_cols(df, old_cols), f"Village centers are missing columns: {str(old_cols)}"
        df = df[old_cols].copy()

        # Clean village names
        df[village_col] = df[village_col].apply(util.text_to_id)

        # Rename baseline columns if needed
        if xy_cols != vc.xy_cols:
            df = util.rename_df_cols(df, xy_cols, vc.xy_cols)

        # Join villages to shapes

        new_cols = vc.adm_cols + vc.xy_cols

        # Rename village column if needed
        if village_col != vc.adm_cols[-1]:
            df = util.rename_df_cols(df, village_col, vc.adm_cols[-1])

        # Spatial join of village centers and shapes
        gdf_shp = gpd.read_file(shape_file)
        if adm_cols != vc.adm_cols[:-1]:
            gdf_shp = util.rename_df_cols(gdf_shp, adm_cols, vc.adm_cols[:-1])

        gdf = spatial.join_xy_shapes(df, vc.xy_cols, gdf_shp)
        df = pd.DataFrame(gdf[new_cols])

        # Clean strings
        df = df[new_cols].sort_values(vc.adm_cols)

        return df

    def prepare_baseline_facilities(self,
                                    baseline_file: Path,
                                    baseline_xy_cols: list[str],
                                    shape_file: Path,
                                    shape_adm_cols: list[str],
                                    info_cols: list[str],
                                    id_col: str = 'facility_id',
                                    baseline_info_col = 'info_col') -> Path:
        """
        Prepare baseline facilities.
        :param baseline_file: Path to the baseline facilities file.
        :param baseline_xy_cols: Baseline facilities longitude and latitude columns names.
        :param shape_file: Path to the shape file.
        :param shape_adm_cols: Shapefile admin column names.
        :param info_cols: Info columns used for results visualization.
        :param id_col: Facility ID column name.
        :param baseline_info_col: Info column name for baseline facilities.
        :return: Path to the prepared baseline facilities file.
        """
        # Set baseline facilities config section alias
        bs: AdmPointsFile = self.cfg.inputs.baseline_facilities

        self.logger.info(f"Preparing baseline facilities from: {baseline_file.name}")

        # Load user provided baseline facilities
        df = pd.read_csv(baseline_file, encoding='utf-8')

        # If the ID column is missing, create it
        if id_col not in df.columns:
            # create facility_id and set as index with incremental IDs
            df[id_col] = range(1, len(df) + 1)

        # Rename baseline columns if needed
        if baseline_xy_cols != bs.xy_cols:
            df = util.rename_df_cols(df, baseline_xy_cols, bs.xy_cols)

        # Create info_col column
        if baseline_info_col:
            def add_info_cols(r):
                r = "</tr><tr>".join([f"<th>{c.lower()}</th><td>{r[c]}</td>" for c in info_cols])
                return f"<tr>{r}</tr>"

            df[baseline_info_col] = df.apply(lambda r: add_info_cols(r), axis=1)
        else:
            df[baseline_info_col] = ''

        # Join villages to shapes

        # Spatial join of village centers and shapes
        gdf_shp = gpd.read_file(shape_file)
        gdf = spatial.join_xy_shapes(df, bs.xy_cols, gdf_shp)

        # Rename shape columns if needed
        if shape_adm_cols != bs.adm_cols:
            gdf = util.rename_df_cols(gdf, shape_adm_cols, bs.adm_cols)

        # Prepare the output DataFrame
        new_cols = bs.adm_cols + bs.xy_cols + [id_col, baseline_info_col]
        df = pd.DataFrame(gdf[new_cols])

        # Generate Google Plus codes based on baseline coordinates
        df["plus"] = df.apply(lambda r: spatial.get_plus_code(r.lon, r.lat), axis=1)

        # Save the prepared baseline facilities
        Path.mkdir(bs.file.parent, exist_ok=True)
        df.to_csv(bs.file, index=False, encoding='utf-8')

        # Create baseline facilities GeoJSON file for results visualizations
        spatial.create_geojson(bs.file, bs.file.stem, bs.file.parent, *bs.xy_cols)

        return bs.file


def format_zip_path(zf: Path, af: Path):
    """
    Format the path to a shape file within a zip archive.
    :param zf: Path to the zip file.
    :param af: Path to the target shape file (when extracted).
    :return: Path to the shape file within the zip archive.
    """
    return Path(f"{str(zf)}!{af.stem}.shp")


@memory.cache
def process_google_buildings(gdf_shapes: gpd.GeoDataFrame,
                             adm_cols: list[str],
                             df_xy: pd.DataFrame,
                             xy_cols: list[str],
                             hh_adm_cols: list[str],
                             hh_xy_cols: list[str],
                             stop_fn) -> pd.DataFrame:
    """
    Process the Google buildings data.
    :param gdf_shapes: GeoDataFrame with shapes.
    :param adm_cols: Shapes admin column names.
    :param df_xy: DataFrame with building coordinates.
    :param xy_cols: Building longitude and latitude columns names.
    :param hh_adm_cols: Households file admin columns.
    :param hh_xy_cols: Households file coordinates columns.
    :return: DataFrame with processed Google buildings data.
    """
    # Get configured column names
    hh_cols = hh_adm_cols + hh_xy_cols
    
    # Rename columns if needed
    if xy_cols != hh_xy_cols:
        df_xy = util.rename_df_cols(df_xy, xy_cols, hh_xy_cols)

    # Prepare the shapefile
    gdf_shp = gdf_shapes[adm_cols + [spatial.geom_col]].copy()
    if adm_cols != hh_adm_cols:
        gdf_shp = util.rename_df_cols(gdf_shp, adm_cols, hh_adm_cols)

    # Process the buildings data in chunks due to memory constraints
    point_count = len(df_xy)
    chunk_size = 1000000  # TODO: cacl based on available RAM
    chunk_count = point_count // chunk_size
    
    df_hh: pd.DataFrame = None
    for p in range(chunk_count + 1):
        # Check if the process should stop
        stop_fn()
        
        # Calculate the start and end indices for the current chunk
        start = p * chunk_size
        end = min((p + 1) * chunk_size, point_count)
        df = df_xy.iloc[start:end]
        
        # Clip buildings chunk to shapes
        gdf = spatial.join_xy_shapes(df, hh_xy_cols, gdf_shp)

        # Concatenate the processed chunk results to the final DataFrame
        df = pd.DataFrame(gdf[hh_cols])
        df_hh = df if df_hh is None else pd.concat([df_hh, df])

    # Validate the number of households
    assert len(df_hh) <= point_count, "The number of households is too large."
    
    # Finalize the output DataFrame
    df_hh = df_hh.dropna()
    df_hh = df_hh.sort_values(hh_cols)
    
    return df_hh
    

