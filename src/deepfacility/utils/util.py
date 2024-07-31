import hashlib
import joblib
import logging
import logging.handlers
import geopandas as gdp
import pandas as pd
import re
import requests
import shutil
import tempfile
import time
import unicodedata
import zipfile

from pathlib import Path
from uuid import uuid4

from unidecode import unidecode


def hash_str(v: str, max_len: int = None):
    """Calculate the MD5 hash of a string."""
    hsh = hashlib.md5(str(v).encode()).hexdigest()
    if max_len:
        hsh = hsh[:max_len]

    return hsh


# String helpers

def strip_accents(text: str) -> str:
    """Strip accents from input String."""
    text = text.strip()
    text = unicodedata.normalize('NFD', text)
    text = text.encode('ascii', 'ignore')
    text = text.decode("utf-8")
    text = text.replace("'", "")
    return str(text)


def text_to_id(text: str) -> str:
    """Convert input text to id."""
    text = str(text)
    text = strip_accents(text)
    text = re.sub('[ ]+', '_', text)
    text = re.sub('[^0-9a-zA-Z_-]', '', text)
    return text


def clean_series(series: pd.Series) -> pd.Series:
    """Clean a Series."""
    # -> unidecode -> normalize -> encode -> decode -> replace
    new_series = (series
                  .astype("str")  # Ensure all entries are strings
                  .str.strip()  # Strip leading and trailing spaces
                  .apply(unidecode)  # Remove accents
                  .str.normalize('NFKD')  # Normalize unicode
                  .str.encode('ascii', errors='ignore')  # Encode to ascii
                  .str.decode('utf-8')  # Decode to utf-8
                  .str.replace("'", ""))  # Remove apostrophes
    # Detect if any entries are difference after cleaning
    # TODO: remove below
    not_na = ~pd.isna(series)
    diff = series[not_na][series[not_na] != new_series[not_na]]
    if len(diff) > 0:
        print(f"Fixed {len(diff)} entries.")

    return new_series


def clean_dataframe(df: pd.DataFrame, columns: list[str] = None, keep: bool = False):
    """Clean a DataFrame."""
    cols = df.columns.to_list()
    if columns is None:
        columns = cols.copy()
    else:
        columns = [c for c in columns if c in cols]
        if len(columns) == 0:
            return df

    for c in columns:
        if keep:
            cc = f"{c}_raw"
            if c.isupper():
                cc = cc.upper()

            df[cc] = df[c]
            cols.insert(cols.index(c), cc)

        df[c] = clean_series(df[c])

    if keep:
        df = df[cols]

    return df


def rename_df_cols(df: pd.DataFrame | gdp.GeoDataFrame,
                   from_cols: list[str] | str,
                   to_cols: list[str] | str = None) -> pd.DataFrame | gdp.GeoDataFrame:
    """Rename columns in a DataFrame."""
    # string to list
    from_cols = [from_cols] if isinstance(from_cols, str) else from_cols
    to_cols = [to_cols] if isinstance(to_cols, str) else to_cols
    
    # validate: lists, from-columns all exist
    assert isinstance(from_cols, list), "from_cols must be a list."
    assert isinstance(to_cols, list), "to_cosl must be a list."
    assert all([c in df.columns for c in from_cols]), f"Columns not found: {from_cols}"

    # Create dictionary of from-to columns which are not the same
    cols = lists_to_dict(from_cols, to_cols)
    cols = {k: v for k, v in cols.items() if k != v}
    
    # Drop 'to' columns already in the DataFrame to allow renaming
    to_drop = [c for c in cols.values() if c in df.columns]
    df.drop(columns=to_drop, inplace=True)
    
    # Rename columns
    return df.rename(columns=cols)


# Download helpers

def download_url(url: str, download_dir: Path) -> Path:
    """Download a file from a URL."""
    assert len(url.strip()) > 0, "Download URL must be provided."
    assert download_dir, "Download path not specified."
    
    # Determine the download file name and path
    download_dir = Path(download_dir)
    name = str(Path(url).name)
    file = download_dir.joinpath(name)
    
    if not file.is_file():
        # Download the URL into the file if it doesn't already exist
        print(f"Downloading {name} into {str(download_dir)}")
        r = requests.get(url, allow_redirects=True)
        if r.status_code == 200:
            # If OK, write the content to the file
            make_dir(file)
            with open(file, "wb") as f:
                f.write(r.content)
            print(f"Download of {name} complete.")
        else:
            # If not OK, log the error
            file = None
    else:
        print(f"Skipping download, file already exists: {name}")

    return file


# dict helpers


def lists_to_dict(list1: list, list2: list) -> dict:
    """Create a dictionary with 1st list as keys and 2nd list as values."""
    return {k: v for k, v in zip(list1, list2)}


# DataFrame helpers

def has_cols(df: pd.DataFrame, columns: list[str]):
    """Check if all columns are in the DataFrame."""
    return all([c in df.columns.values for c in columns])


# Path helpers

def make_dir(f: Path):
    """Create a directory if it does not exist"""
    d = f.parent if f.suffix else f
    d.mkdir(exist_ok=True, parents=True)
    return d


def elapsed_time(start_time: float) -> dict[str, str]:
    """Get the elapsed time as a dictionary."""
    ts = (time.time() - start_time)
    h = ts // 3600
    m = ts % 3600 // 60
    s = ts % 3600 % 60
    rj = lambda t: str(int(t)).rjust(2, '0')
    # def rj(t):
    #     return str(int(t)).rjust(2, '0')

    return {'h': rj(h), 'm': rj(m), 's': rj(s)}


def elapsed_time_str(start_time: float):
    """Get the elapsed time as a formatted string."""
    dt = elapsed_time(start_time=start_time)
    return "{h}h:{m}m:{s}s".format(**dt)


def copy_to_dir(f, d):
    """Copy a file to a directory."""
    shutil.copy(f, d.joinpath(f.name))


def letters(loc: str, z):
    """Get the first z letters of a location"""
    return ''.join([s[0:z] for s in loc.split(':')])


def format_run_name(locations: list[str]) -> str:
    """Format the run name from locations with 1st location as prefix."""
    assert locations, "Locations are not specified."

    # Location count and hash
    n = len(locations)
    hsh = f"_{hash_str(''.join(locations), max_len=7)}"

    # Get the run name from the first location and suffix
    run_name = text_to_id(f"{locations[0].replace(':', '-')}_{n}{hsh}")
    run_name = run_name.strip('-').strip()

    return run_name


def file_ready(f: Path) -> bool:
    """Check if the file exists and is not empty."""
    return f.is_file() and f.stat().st_size > 0


def create_zip(file_list: list[Path], zip_name: str):
    """Create a zip archive from a list of files."""
    archive_path = Path(tempfile.mkdtemp()) / zip_name
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zip_archive:
        for file_path in file_list:
            try:
                zip_archive.write(str(file_path), arcname=file_path.name)
            except FileNotFoundError:
                print(f"Warning: File '{file_path}' not found. Skipping.")

    return archive_path


def report_progress(logger, name, items, done_perc, total_count) -> int:
    """Report progress of a task."""
    # Calculate the percentage of done items
    done_count = len(items)
    new_done_perc = round(100 * done_count / total_count)
    # Log the progress if the percentage has changed
    if done_perc != new_done_perc:
        done_perc = new_done_perc
        logger.info(f"{name}: {done_count}/{total_count}: {done_perc}%")

    return done_perc


def app_dir() -> Path:
    """Get the application directory."""
    import os
    default_dir = str(Path.cwd() / "app-data")
    return Path(os.getenv("DEEPFACILITY_ROOT_DIR", default=default_dir))


def memory_cache_dir() -> Path:
    """Get the memory cache directory."""
    return app_dir() / "cache"


def memory_cache() -> joblib.Memory:
    """Get a memory cache used for caching data."""
    return joblib.Memory(memory_cache_dir(), verbose=0)


def is_linux() -> bool:
    """Check if the current system is Linux"""
    import platform
    return platform.system() == "Linux"


def new_session_id(length: int = None) -> str:
    """Generate a new session ID."""
    sid: str = str(uuid4()).replace("-", "")
    n = length or len(sid)
    return sid[:n]


def init_logger(name: str = None, file: Path = None):
    """Initialize a logger."""
    if file:
        # Set the name based on the file for uniqueness, if name is not provided
        name = name or hash_str(text_to_id(str(file)))
        # Create the parent directory if it doesn't exist
        file.parent.mkdir(parents=True, exist_ok=True)

        # Configure file handler
        file_handler = logging.handlers.WatchedFileHandler(str(file), mode="w")
        file_handler.setFormatter(logging.Formatter("%(message)s"))
    else:
        # Set the name to a random ID for uniqueness, if name is not provided
        name = name or new_session_id(8)
        file_handler = None
        
    # Configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    # Create and configure the logger
    logger = logging.getLogger(name)
    if file_handler:
        logger.addHandler(file_handler)
    
    # Add the console handler
    logger.addHandler(console_handler)
    
    # Set the logging level
    logger.setLevel(logging.INFO)

    return logger
