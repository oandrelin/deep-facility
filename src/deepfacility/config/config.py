from __future__ import annotations

import geopandas as gpd
import json
import logging
import pandas as pd
import re
import tomli
import shutil

from dataclasses import dataclass, asdict, fields
from pathlib import Path

from deepfacility.utils import util, spatial


# Config base data classes
@dataclass
class BaseData:
    """Base abstract config data class."""
    @classmethod
    def from_instance(cls, instance: object):
        return cls(**asdict(instance))


# Base data classes
@dataclass
class AdmFile(BaseData):
    """Admin file data class."""
    file: Path           # admin file path
    adm_cols: list[str]  # admin column names


@dataclass
class PointsFile(BaseData):
    """Points file data class."""
    file: Path          # file path
    xy_cols: list[str]  # coordinates column names


@dataclass
class DownloadFile(BaseData):
    """Download file data class."""
    file: Path  # file path
    url: str    # download url
    dir: Path   # download directory
    
    def __post_init__(self):
        self.file = self.dir.joinpath(Path(self.url).name)
    

@dataclass
class Section(BaseData):
    """Config section data abstract class."""
    
    def ready(self):
        """Check if all required files are ready."""
        raise NotImplementedError("ready method must be implemented.")
    
    def remove_files(self):
        """Remove section files."""
        raise NotImplementedError("remove_files method must be implemented.")


@dataclass
class Operation:
    """Config operation data abstract class."""
    control_file: Path  # control file path
    log_file: Path      # log file path
    _logger: logging.Logger
    
    def __post_init__(self):
        """Set up logging and the 'stop' file."""
        # Remove log and control files if they exist
        if self.control_file:
            self.control_file.unlink(missing_ok=True)

    @property
    def logger(self):
        """Get the logger."""
        if not self._logger:
            self.init_logger()
            
        return self._logger
    
    @logger.setter
    def logger(self, value):
        """Set the logger."""
        self._logger = value

    def init_logger(self):
        """Initialize the file logger."""
        self._logger = util.init_logger(file=self.log_file)
    
    @property
    def dir(self):
        """Run results directory."""
        return self.log_file.parent

    @property
    def root_dir(self):
        """Root 'results' directory for the selected country."""
        return self.log_file.parent.parent

    def stop(self):
        """Update the 'stop' file."""
        self.control_file.parent.mkdir(parents=True, exist_ok=True)
        self.control_file.touch()

    def clear(self):
        """Update the 'stop' file."""
        self.control_file.unlink(missing_ok=True)

    def is_stopped(self):
        """Check if the operation is stopped."""
        if not self.control_file.is_file():
            return False

        ts0 = self.log_file.stat().st_atime if self.log_file.is_file() else 0
        ts1 = self.control_file.stat().st_mtime if self.control_file.is_file() else 0
        return ts1 >= ts0

    def raise_if_stopped(self):
        """Raise an exception if the operation is stopped."""
        if self.is_stopped():
            self.logger.warning("Stopping...")
            raise InterruptedError("Stopped by the user.")

    def cleanup(self):
        """Clean up logging and the 'stop' file."""
        self.logger.handlers.clear()


class WorkflowEntity:
    cfg: Config
    logger: logging.Logger

    def __init__(self, cfg: Config, logger: logging.Logger = None):
        self.cfg = cfg
        self.logger = logger


class Workflow(WorkflowEntity):
    pass


@dataclass
class AdmPointsFile(PointsFile, AdmFile):
    """Admin points file data class."""
    pass


@dataclass
class BaselineFile(PointsFile):
    """Baseline file data class."""
    info_cols: list[str]  # Info column names

# Config section data classes


@dataclass
class Args(Section):
    """Config args section data class."""
    country: str
    data_dir: Path  # root data for all config paths
    country_code: str = ""
    # Village centers args subsection
    village_centers: AdmPointsFile = None
    # Baseline args subsection
    baseline_facilities: BaselineFile = None
    # The number of households below which a village is considered small.
    threshold_households: int = -1
    # Max allowed percent of small villages
    threshold_village_perc: int = -1

    def __post_init__(self):
        """Init country code and root data directory."""
        assert len(self.country.strip()) > 0, "Country not specified."
        if len(self.country_code.strip()) == 0:
            self.country_code = get_country_code(self.country)
        self.data_dir = Path(str(self.data_dir).format(country=self.country, country_code=self.country_code))

    def has_baseline(self):
        """Check if the baseline file is set."""
        return util.file_ready(self.baseline_facilities.file)


@dataclass
class BuildingsDownload(DownloadFile, PointsFile):
    """Buildings download file data class."""
    pass


@dataclass
class ShapesDownload(DownloadFile):  # AdmFile
    """Shapes download file data class."""
    pass


@dataclass
class Downloads(Section):
    """Config downloads section data class."""
    buildings: BuildingsDownload
    shapes: ShapesDownload


@dataclass
class Inputs(Section, Operation):
    """Config inputs section data class."""
    all_locations_file: Path            # all locations file path
    buildings: PointsFile               # buildings file
    shapes: AdmFile                     # shapes file
    village_centers: AdmPointsFile      # village centers file
    baseline_facilities: AdmPointsFile  # baseline facilities file
    households: AdmPointsFile           # households file

    @property
    def shape_files(self):
        """Shape files list. Populate shape file pattern with levels 0 and 3."""
        return [Path(str(self.shapes.file).format(level=i)) for i in [0, 3]]
    
    def ready(self):
        """Check if all required files are ready."""
        required_files = [
            self.all_locations_file,
            self.buildings.file,
            self.village_centers.file,
            self.households.file]
        # Add admin shape files to the list
        required_files += self.shape_files  # merge two lists
        return all([util.file_ready(f) for f in required_files])

    def remove_files(self):
        """Remove all input files."""
        # self.shapes.file.unlink(),
        # self.buildings.file.unlink(),
        self.households.file.unlink(missing_ok=True)
        self.households.file.with_suffix('.stats.csv').unlink(missing_ok=True)
        self.village_centers.file.unlink(missing_ok=True)
        self.village_centers.file.with_suffix('.geojson').unlink(missing_ok=True)
        self.baseline_facilities.file.unlink(missing_ok=True)
        self.baseline_facilities.file.with_suffix('.geojson').unlink(missing_ok=True)

    def has_baseline(self):
        """Check if the baseline file is set."""
        return util.file_ready(self.baseline_facilities.file)


@dataclass
class ResultsAdmFile(AdmFile):
    """Results admin file data class."""
    data_cols: list[str]


@dataclass
class ResultsAdmPointsFile(PointsFile, ResultsAdmFile):
    """Results admin points file data class."""
    pass


@dataclass
class Facilities(ResultsAdmPointsFile):
    """Facilities data class."""
    n_facilities: int


@dataclass
class ResultsClusteredHouseholds(ResultsAdmPointsFile):
    """Results clustered households data class."""
    centers_file: Path
    counts_file: Path


@dataclass
class Results(Section, Operation):
    """Config results section data class."""
    locations_file: Path    # locations file path
    # max locations for displaying visualization
    viz_max_locations: int  # to avoid unresponsive UI
    clusters: ResultsClusteredHouseholds  # clustered households file
    shapes: ResultsAdmFile  # village shapes files
    facilities: Facilities  # recommended facilities file

    def ready(self):
        """Check if all required files are ready."""
        required_files = [self.clusters.file, self.shapes.file, self.facilities.file]
        required_files = [spatial.location_path(f, "") for f in required_files]
        required_files += [self.locations_file]
        return all([util.file_ready(f) for f in required_files])

    def remove_files(self):
        """Remove run result directory."""
        if self.locations_file.parent.is_dir():
            shutil.rmtree(self.locations_file.parent, ignore_errors=True)


def prim_items(cfg):
    """Get non-dict items from a dict."""
    return {k: v for k, v in cfg.items() if not isinstance(v, dict)}


@dataclass
class RuntimeArgs(BaseData):
    """Runtime args, not specified in the config."""
    config_file: Path = None
    command: str = ""
    locations: list[str] = None
    location_filter: list[str] = ""
    run_name: str = ""
    result_dir: str = ""

    def __post_init__(self):
        """Init config file path."""
        if self.config_file and isinstance(self.config_file, str):
            self.config_file = Path(self.config_file)

    def init_run_name(self):
        """Init run name."""
        if not self.run_name:
            if self.location_filter:
                self.run_name = util.format_run_name(self.location_filter)
            else:
                self.run_name = "all"
        
    @classmethod
    def from_dict(cls, args_dict: dict) -> RuntimeArgs:
        a = {k: v for k, v in args_dict.items() if k in RuntimeArgs().__dict__}
        return cls(**a)
    

class DataClassFactory:
    """Data class factory responsible for constructing data classes from a config."""
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.unused = []
        self.missing = []

    def make(self, dc: dataclass, key_path: list[str], ignore: list[str] = None) -> dataclass:
        """
        Constructs a data class using a specified config sub-dict and reports validation.
        For example, to construct the input buildings data class the "inputs.buildings" sub-dict
        is located in the self.cfg and used to initialize the `dc` data class.
        :param dc: data class to construct
        :param key_path: list of a nested dict keys
        :param ignore: list is keys to ignore
        :return: data class object
        """
        # Locate the config sub-dict per the key path
        visited = []         # visited is the visited key list
        current = self.cfg   # current config dict level
        for k in key_path:   # for all keys in the path
            visited.append(k)  # add the key to the visited list
            if k in current:   # if path key is found
                current = current[k]  # go to the next level
            else:            # if not found, record as missing
                self.missing.append(self.key_str(visited))
                return None  # and bail out

        # Determine required, missing and unused key paths
        ignore = ignore or []
        expected_fields = [f.name for f in fields(dc) if f.name not in ignore]
        missing = [k for k in expected_fields if k not in current]
        unused = [k for k in current if k not in expected_fields]
        
        if unused:  # Report unused key paths
            self.unused.extend([self.key_str(key_path + [k]) for k in unused])
        
        if missing:  # Report missing key paths
            self.missing.extend([self.key_str(key_path + [k]) for k in missing])
    
        # Construct dict to init the `dc` data class (from required fields)
        ok = {k: v for k, v in current.items() if k in expected_fields}
        if ignore:  # skip ignored fields
            for f in ignore:
                ok[f] = ""
        
        try:
            res = dc(**ok)  # instantiate the data class
        except Exception as ex:
            # Get the config console logger
            logger = util.init_logger(name="config")
            for m in ex.args:  # Report instantiation errors
                logger.error(f"Unable to instantiate: {dc}\n{m}")
                logger.error(f"Please update the config file.")
            return None

        return res

    @staticmethod
    def key_str(key_path: list[str]):
        return '/'.join(key_path)


@dataclass
class Config(RuntimeArgs):
    """Config data singleton class. Encapsulates all config data."""
    args: Args = None            # Args section (user files and parameters)
    downloads: Downloads = None  # Downloads section
    inputs: Inputs = None        # Inputs section
    results: Results = None      # Results section
    _load: bool = True           # Load the config file flag
    _instance = None             # Singleton instance
    default_file: str = util.app_dir() / "config.toml"  # Default config file name
    # Default config template files
    default_template_sys_file: Path = Path(__file__).parent / "template_sys.toml"
    default_template_user_file: Path = Path(__file__).parent / "template_user.toml"
    
    def __post_init__(self):
        """Init config file path and load the config."""
        self.config_file = Path(self.config_file or Config.default_file)
        self.init_run_name()
        if self._load:
            self._load_config_file()
      
    def _load_config_file(self, config_file: Path = None, run_args: RuntimeArgs = None) -> None:
        """Load the config file."""
        if config_file:  # update config file
            self.config_file = config_file
            
        if run_args:  # update runtime args
            assert isinstance(run_args, RuntimeArgs), "run_args must be a RuntimeArgs data class"
            self.__dict__.update(asdict(run_args))
        
        assert self.config_file is not None, "Config config_file must be set at this point."
        # Read system and user configs and merge them
        try:
            cfg = read_toml_file(Config.default_template_sys_file)
            cfg_user = read_toml_file(self.config_file)
        except (FileNotFoundError, tomli.TOMLDecodeError) as ex:
            # Get the config console logger
            logger = util.init_logger(name="config")
            logger.error(f"Unable to reading the config file: {str(self.config_file)}")
            for m in ex.args[1:]:
                logger.error(f"{str(config_file)}: {m}")
            exit(1)
            
        cfg.update(cfg_user)
        
        # Create the data class factory, in charge of producing config sections
        dc = DataClassFactory(cfg=cfg)  # by populating template variables

        # Ignore attributes not in the config
        args_ignore = [v for v in ["country_code"] if v not in cfg["args"]]

        # Create Args, Downloads, Inputs and Results config sections using DataClassFactory and the merged config.
        
        # Create Args config section
        self.args = dc.make(Args, ["args"], ignore=args_ignore)
        dc.cfg = path_to_obj(populate(data=dc.cfg,
                                      args={
                                          'app_dir': util.app_dir(),
                                          **self.__dict__, 
                                          **prim_items(self.args.__dict__)
                                      }))
        
        self.args.village_centers = dc.make(AdmPointsFile, ["args", "village_centers"])
        self.args.baseline_facilities = dc.make(BaselineFile, ["args", "baseline_facilities"])
        
        # Create Downloads config section
        self.downloads = Downloads(buildings=dc.make(BuildingsDownload, ["downloads", "buildings"], ignore=["file"]),
                                   shapes=dc.make(ShapesDownload, ["downloads", "shapes"], ignore=["file"]))
        
        # Create Inputs config section
        dc.cfg["inputs"]["_logger"] = None
        self.inputs = Inputs(**prim_items(dc.cfg["inputs"]),
                             buildings=dc.make(PointsFile, ["inputs", "buildings"]),
                             shapes=dc.make(AdmFile, ["inputs", "shapes"]),
                             village_centers=dc.make(AdmPointsFile, ["inputs", "village_centers"]),
                             baseline_facilities=dc.make(AdmPointsFile, ["inputs", "baseline_facilities"]),
                             households=dc.make(AdmPointsFile, ["inputs", "households"]))
        
        # Create Results config section
        dc.cfg["results"]["_logger"] = None
        self.results = Results(**prim_items(dc.cfg["results"]),
                               clusters=dc.make(ResultsClusteredHouseholds, ["results", "clusters"]),
                               shapes=dc.make(ResultsAdmFile, ["results", "shapes"]),
                               facilities=dc.make(Facilities, ["results", "facilities"]))

        if dc.unused:  # Report unused keys
            self.results.logger.warning(f"Unused config keys (can be removed) in file: {self.config_file}")
            self.results.logger.info('\n'.join(dc.unused))
            
        if dc.missing: # Report missing keys
            self.results.logger.error(f"Missing required fields (must be set) in file: {self.config_file}")
            self.results.logger.info('\n'.join(dc.missing))
            exit(1)

        # Load locations, filtered or all
        self._parse_location_filter()
    
    # Locations properties and methods

    def _parse_location_filter(self):
        """Parse the location filter and apply it to the `inputs.all_locations_file`
        to construct the list of target locations to be processed."""
        # Read all locations from the input `all_locations_file`
        if self.location_filter:  # if location filter is specified, parse it and apply it
            locations = [util.strip_accents(p) for p in self.location_filter]
            self.locations = [loc for loc in get_all_locations(self) if any([re.match(p, loc) for p in locations])]
        else:  # if location filter is not specified return all locations
            self.locations = get_all_locations(self)

    @property
    def has_locations(self):
        return isinstance(self.locations, list) and len(self.locations) > 0

    def update_locations(self, location_filter: list[str], run_name: str = ""):
        """Update the locations and run name."""
        self.location_filter = location_filter  # update location filter
        self.run_name = run_name  # update run name
        self.init_run_name()      # init run name is not set
        self._load_config_file()  # reload the config to reflect changes

    # Config singleton methods

    @classmethod
    def create_instance(cls, config_file: Path = None, run_args: RuntimeArgs = None) -> Config:
        """Create an instance of the Config class."""
        if run_args:
            # use runtime args if provided
            run_args.config_file = config_file or run_args.config_file
            run_args.init_run_name()
            cfg = cls(**asdict(run_args))
        else:
            # use config file if provided, else the default is used
            cfg = cls(config_file=config_file)

        return cfg


# Config dict helper functions

def read_toml_file(config_file: Path) -> dict:
    """Read a TOML config file and return a dict."""
    assert isinstance(config_file, Path), f"read_toml_file fn. expects Path (got {type(config_file)} instead)."
    if config_file.is_file():
        # Load the config file
        cfg_dict = tomli.loads(config_file.read_text())
    else:
        # Report and exit if the config file is not found
        raise FileNotFoundError(f"File not found: {str(config_file)}.")

    # Figure out the run name if not set in the config
    return cfg_dict


def populate(data: dict, args: dict) -> dict:
    """Populate input dict with values from the args dict."""
    d = str(data)
    for k, v in args.items():
        if is_str_item(k, v):
            if isinstance(v, Path):
                v = str(v)
            d = d.replace("{" + k + "}", v)

    return eval(d.replace("\\", "/"))


def is_str_item(k: str, v: Path) -> bool:
    """Check if the key is of string type and value of string or path types."""
    k_type_ok = isinstance(k, str) and not k.startswith("_")
    v_type_ok = isinstance(v, Path) or isinstance(v, str)
    return k_type_ok and v_type_ok


def is_path_key(k: str) -> bool:
    """Check if the key represents a file or dir."""
    return k in ["file", "dir"] or re.match(".*(_file|_dir)$", str(k))


def path_to_obj(data: dict):
    """Convert all file and dir items to Path objects, recursively."""
    for k, v in data.items():
        if is_str_item(k, v) and is_path_key(k):
            data[k] = Path(v)
        elif isinstance(v, dict):
            data[k] = path_to_obj(data[k])
    return data


def path_to_str(data: dict) -> dict:
    """Convert all Path objects to string values, recursively."""
    for k, v in data.items():
        if isinstance(v, Path):
            data[k] = str(v)
        elif isinstance(v, dict):
            data[k] = path_to_str(data[k])

    return data


@dataclass
class ResultFiles:
    """Encapsulate result files."""
    shape_file: Path
    clusters_file: Path
    centers_file: Path
    counts_file: Path
    facilities_file: Path


@dataclass
class ResultData:
    """Encapsulate result data."""
    gdf_shapes: gpd.GeoDataFrame
    df_clusters: pd.DataFrame
    df_centers: pd.DataFrame
    df_counts: pd.DataFrame
    df_facilities: pd.DataFrame

    def save(self, rf: ResultFiles):
        """Save result data to files."""
        self.gdf_shapes.to_file(rf.shape_file.with_suffix('.geojson'), driver='GeoJSON')
        self.df_clusters.to_csv(rf.clusters_file, index=False, encoding='utf-8')
        self.df_centers.to_csv(rf.centers_file, index=False, encoding='utf-8')
        self.df_counts.to_csv(rf.counts_file, index=False, encoding='utf-8')
        self.df_facilities.to_csv(rf.facilities_file, index=False, encoding='utf-8')


def read_s2_dict() -> dict[str, dict[str, object]]:
    """Read the `country to S2 geometry` lookup dict, used to download Google Open Buildings files."""
    with open(Path(__file__).parent.joinpath("countries_s2_tokens.json"), encoding="utf-8") as fp:
        s2s: dict = json.load(fp)
    return s2s


def get_country_code(country: str) -> str:
    """Get country code from the country name."""
    return str(read_s2_dict()[country]["code"])


def get_supported_countries() -> list[str]:
    """Get the list of supported countries."""
    return sorted(read_s2_dict())


def create_config_file(config_file, force: bool = False):
    """Create a new config file from the default template."""
    cfg_file = Path(config_file)
    # Get the config console logger
    logger = util.init_logger(name="config")
    if force or not cfg_file.is_file():
        util.make_dir(cfg_file.parent)
        shutil.copy2(Config.default_template_user_file, cfg_file)
        logger.info(f"Created the config file: {str(cfg_file)}")
    else:
        logger.warning(f"Skipping. Config {str(cfg_file)} already exists.")


def get_adm_columns(ins: Inputs, df: pd.DataFrame):
    """Get the admin columns from a dataframe."""
    if util.has_cols(df, ins.households.adm_cols):
        cols = ins.households.adm_cols
    elif util.has_cols(df, ins.shapes.adm_cols):
        cols = ins.shapes.adm_cols
    elif util.has_cols(df, ins.village_centers.adm_cols):
        cols = ins.households.adm_cols
    else:
        raise ValueError("Dataframe admin columns can't be detected.")

    return cols


def get_all_locations(cfg: Config) -> list[str]:
    """Get all locations from the `all_locations_file`."""
    if cfg.inputs.all_locations_file.is_file():
        return cfg.inputs.all_locations_file.read_text().splitlines()
    else:
        return []


def filter_by_locations(ins: Inputs, df: pd.DataFrame, locations: list[str], columns: list[str] = None):
    """Filter a dataframe by locations."""
    if not locations:
        return df

    return spatial.filter_locations(df=df, locations=locations, columns=columns or get_adm_columns(ins=ins, df=df))
