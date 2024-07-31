import pandas as pd
import tempfile

from pathlib import Path

from deepfacility.config.config import WorkflowEntity, read_s2_dict, get_country_code
from deepfacility.utils import util


class Downloads(WorkflowEntity):
    """External data downloads."""
    def download_country_shapes(self, country: str) -> Path:
        """
        Download country shapes from the GADM database.
        :param country: Country name.
        :return: Path to the downloaded zip file.
        """
        country_code = get_country_code(country)
        url = self.cfg.downloads.shapes.url.format(country_code=country_code)
        zip_file = util.download_url(url, self.cfg.downloads.shapes.dir)
        assert zip_file.is_file(), "Download zip not found."
        return zip_file
        
    def download_buildings(self, country: str) -> Path:
        """
        Download, merge and save Google building files.
        :param country: Country name.
        :return: Path to the downloaded file.
        """
        buildings_file = self.cfg.inputs.buildings.file
        if buildings_file.is_file():
            self.logger.info("Skipping buildings download, file already exists.")
            return buildings_file
        else:
            buildings_file.write_text("")  # Create an empty file to indicate shapes are ready.
    
        files = self.download_google_buildings(country, dir_name=self.cfg.downloads.buildings.dir)
        xy_cols = self.cfg.downloads.buildings.xy_cols
        df_list = [pd.read_csv(f, compression="gzip", usecols=xy_cols, dtype=float, index_col=False, encoding='utf-8') for f in files]
        df_all = pd.concat(df_list).reset_index(drop=True)
    
        xy_cols2 = self.cfg.inputs.buildings.xy_cols
        if xy_cols != xy_cols2:
            df_all = util.rename_df_cols(df_all, xy_cols, xy_cols2)
    
        util.make_dir(buildings_file)
    
        df_all.to_feather(buildings_file)
        return buildings_file
    
    def download_google_buildings(self, country: str, dir_name: Path = None, s2_dict: dict[str, list] = None) -> list[Path]:
        """
        Download Google Open Building data.
        :param country: Country name.
        :param dir_name: Directory to download the files to.
        :param s2_dict: S2 tokens dictionary.
        :return: List of downloaded files.
        """
        s2_dict = s2_dict or read_s2_dict()
        assert country in s2_dict, f"Country {country} not supported or misspelled."
        s2tokens = s2_dict[country]["s2"]
        assert s2tokens and len(s2tokens) > 0, "Country s2 token list can't be empty."
    
        dir_name = Path(dir_name or Path(tempfile.mkdtemp(suffix="GB")))
        util.make_dir(dir_name)
        file_list = [self.download_s2_token(t, dir_name) for t in s2tokens]
        return file_list
    
    def download_s2_token(self, s2token: str, dir_name: Path):
        """
        Download Google Open Building data for a given S2 token.
        :param s2token: S2 token.
        :param dir_name: Directory to download the files to.
        :return: Path to the downloaded file.
        """
        url = self.cfg.downloads.buildings.url.format(s2token=s2token)
        filename = util.download_url(url, dir_name)
        return filename


# country shapes
# https://biogeo.ucdavis.edu/data/diva/adm/BFA_adm.zip
# https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_BFA_3.json.zip
# https://geodata.ucdavis.edu/gadm/gadm4.1/shp/gadm41_BFA_shp.zip


