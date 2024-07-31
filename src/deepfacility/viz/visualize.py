import matplotlib
import tempfile
import os
from pathlib import Path
import shutil
import re

matplotlib.use('agg')
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)

from deepfacility.config.config import Config, WorkflowEntity
from deepfacility.lang import Translator
from deepfacility.utils import spatial


class Visualizer(WorkflowEntity):
    """Visualizing household clustering, village shapes and optimal placements."""
    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.logger = self.cfg.results.logger
    
    def create_js_file(self, file_path: Path, outfile_path: Path, varname: str, delete_infile: bool = False) -> None:
        """
        Create a JavaScript file with a variable declaration.
        :param file_path: The input file path.
        :param outfile_path: The output file path.
        :param varname: The variable name.
        :param delete_infile: Whether to delete the input file.
        """
        prefix = f'var {varname}= '
        # get only first line
        outfile = file_path.with_suffix('.js') if outfile_path is None else outfile_path
        logger = self.cfg.results.logger
        try:
            f = open(file_path, 'r', encoding='utf-8')
            first_line = f.readline()
            modified_contents = prefix + first_line
            of = open(outfile, "w")
            of.write(modified_contents)
            shutil.copyfileobj(f, of)
            f.close()
            of.close()
            logger.info(f"JavaScript file created successfully: {outfile}.")
            if delete_infile:
                file_path.unlink(missing_ok=True)
                logger.info(f"infile deleted: {str(file_path)}")
        except Exception as e:
            logger.info(f"File not found: {str(file_path)}")
            contents = f'var {varname} = null; '
            of = open(outfile, "w")
            of.write(contents)
            of.close()
            
    def create_leaflet_map(self, result_dir: Path, translator: Translator = None) -> Path:
        """
        Create a leaflet map from the results of the optimization.
        :param result_dir: The directory containing the optimization results.
        :param translator: Translator object
        :return: The directory containing the leaflet map.
        """
        cfg = self.cfg
        www_dir = result_dir / "www"
        try:
            if www_dir.exists():  # if previous viz exists archive it
                from datetime import datetime
                to_dir = www_dir.parent / 'www-archive' / datetime.now().strftime("%Y%m%d-%H%M%S")
                to_dir.parent.mkdir(exist_ok=True, parents=True)
                www_dir.rename(str(to_dir))
            
            # read lon/lat, shapes_file from config
            lon_col, lat_col = cfg.results.facilities.xy_cols
            shapes_file = cfg.inputs.shapes.file.with_suffix('.geojson')
            level = len(cfg.inputs.shapes.adm_cols) + 1
            shapes_file = Path(str(shapes_file).format(level=level))
    
            # constructing absolute paths ('use_abs_path' is likely not needed)
            root_path = cfg.config_file.parent
            input_shape = use_abs_path(root_path, shapes_file)
            input_village_centers = use_abs_path(root_path, cfg.inputs.village_centers.file.with_suffix('.geojson'))
            results_shapes = use_abs_path(root_path, (result_dir / cfg.results.shapes.file.name).with_suffix('.geojson'))
            result_facilities = use_abs_path(root_path, result_dir / cfg.results.facilities.file.name)
    
            # copy the leaflet template to the temporary directory
            template_dir = Path(__file__).parent.joinpath("leaflet_template")
            assert template_dir.is_dir(), f'{template_dir} is not a valid directory'
            with tempfile.TemporaryDirectory() as temp_dir:
                web_dir = Path(temp_dir) / "www"
                data_dir = web_dir / "data"
                if template_dir.is_dir() and 'index.html' in [f.name for f in template_dir.iterdir()]:
                    shutil.copytree(template_dir, web_dir)
                else:
                    raise FileNotFoundError(f'{template_dir} is not valid')
    
                # create map layers, must match those listed in 'leaflet_template/main.js'
                
                Path(data_dir).mkdir(parents=True, exist_ok=True)
    
                # create adm3, village and village centers layers
                in_shp, in_vil = "gadm", "village_centers"
                res_shp, res_fac = "village_shapes", "optimal_facilities"
                self.create_js_file(input_shape, (data_dir / in_shp).with_suffix('.js'), in_shp)
                self.create_js_file(results_shapes, (data_dir / res_shp).with_suffix('.js'), res_shp)
                self.create_js_file(input_village_centers, (data_dir / in_vil).with_suffix('.js'), in_vil)
                
                # create facilities layer
                self.logger.info(f"Creating facilities GeoJson layer for: {result_facilities.name}")
                facilities_geojson = spatial.create_geojson(result_facilities, res_fac, data_dir, lon_col, lat_col)
                self.create_js_file(facilities_geojson, (data_dir / res_fac).with_suffix('.js'), res_fac)
    
                # create baseline facilities layer
                in_bas = "baseline_facilities"
                outfile_path = (data_dir / in_bas).with_suffix('.js')
                if cfg.inputs.has_baseline():
                    bs_file = cfg.inputs.baseline_facilities.file.with_suffix('.geojson')
                    self.create_js_file(bs_file, outfile_path, in_bas)
                else:  # empty if the baseline file is not provided
                    outfile_path.write_text("")
                    
                shutil.copytree(web_dir, result_dir / "www")
    
                # translate main.js and index.html
                target_dir = result_dir / "www"
                target_files = []
                for path in target_dir.rglob('*'):
                    if path.is_file() and (path.name == 'index.html' or path.name == 'main.js'):
                        target_files.append(path)
                for target_file in target_files:
                    with open(target_file, 'r', encoding='utf-8') as file:
                        html_content = file.read()
                    # Translate the text within the template tags
                    translated_content = translate_html_template(translator, html_content)
                    # Overwrite the original HTML file with the translated content
                    with open(target_file, 'w', encoding='utf-8') as file:
                        file.write(translated_content)
    
        except PermissionError:
            self.logger.info("Map folder already exists.")
        
        images_dir = www_dir / 'images'
        images_dir.mkdir(parents=True, exist_ok=True)
        # prepare viz file for map display
        self.copy_viz_files(result_dir, images_dir, "*.png", "www")
        return Path(result_dir, "www")
        
    def copy_viz_files(self, results_dir: Path, images_dir: Path, filename_pattern: str, exclude_folder_pattern: str):
        """
        Copy visualization files matching a specific pattern from results_dir to images_dir.
    
        Parameters:
        - results_dir: The directory to search for .png files.
        - images_dir: The target directory where matching .png files are copied.
        - filename_pattern: Pattern to match filenames, supports wildcards (e.g., '*.png').
        - exclude_folder_pattern: Pattern that copy search should ignore
        """
        if not images_dir.exists():
            images_dir.mkdir(parents=True, exist_ok=True)
    
        for file in results_dir.rglob(pattern=filename_pattern):
            try:
                child_path = Path(file.parent).resolve()
                parent_path = Path(results_dir).resolve()
                relative_path = child_path.relative_to(parent_path)
                if not exclude_folder_pattern in str(relative_path):
                    target_dir = str(relative_path).replace(os.sep, "_")
                    new_filename = f"{target_dir}_{file.name}" if target_dir else file
                    shutil.copy(file, images_dir / new_filename)
                    self.logger.info(f"Copying viz files: {new_filename} -> {images_dir}")
            except ValueError as e:
                self.logger.er(f"Skip copying viz files : {e}")
    
        self.logger.info("Matching visualization files have been copied to the images directory.")


# Helpers
def use_abs_path(root: Path, rel_path: Path) -> Path:
    """
    Return an absolute path if the input path is relative, otherwise return the input path
    :param root: Root path
    :param rel_path: Relative path
    :return: Absolute path
    """
    if not rel_path.absolute():
        abs_dir = root / rel_path
        return abs_dir
    else:
        return rel_path


def translate_html_template(translator: Translator, content: str):
    """
    Translate the text within the template tags.
    :param translator: Translator object
    :param content: HTML content
    :return: Translated content
    """
    pattern = r'\{\{\s*_\("([^"]+)"\)\s*\}\}'

    def replace_word(match):
        """Replace the matched word with the translated word."""
        original_text = match.group(1)
        translated_text = translator.translate(original_text) if translator else original_text
        # replace single quotes with html encoding to avoid breaking javascript
        translated_text = re.sub(r"'", "&apos;", translated_text)
        return translated_text

    translated_content = re.sub(pattern, replace_word, content)
    return translated_content
