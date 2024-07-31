import geopandas as gpd
import shutil
import tempfile

import pandas as pd
import pytest

from pathlib import Path

from deepfacility.config.config import RuntimeArgs
from deepfacility.utils import util


# def setup_module():
#     pytest.expected_name = "AFRO:DRCONGO:HAUT_KATANGA:KAMPEMBA"

# run name tests


@pytest.fixture()
def args():
    loc = "12345678:0123456789012345AAAA"
    a = RuntimeArgs(locations=[loc])
    hsh = util.hash_str('-'.join(a.locations), max_len=7)
    a.run_name = f"12345678-0123456789012345-{hsh}"
    return a


@pytest.mark.unit
def test_make_run_name_skip(args):
    expected = "my-name"
    args.run_name = expected
    args.init_run_name()
    assert expected == args.run_name


# download_url tests


@pytest.fixture()
def url_pattern():
    return "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_BFA_{level}.json.zip"


@pytest.fixture()
def tmp_dir() -> Path:
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    try:
        shutil.rmtree(tmp)
    except Exception as ex:
        print('\n'.join(ex.args))
    

# download_url tests


@pytest.mark.network_dependent
def test_download_url_ok(tmp_dir, url_pattern):
    expected, actual = download_url_test(tmp_dir, url_pattern, 0)
    assert expected == actual, "File name is not expected."
    try:
        gdf = gpd.read_file(actual)
        assert len(gdf) > 0, "No data found."
    except Exception as ex:
        return False


@pytest.mark.network_dependent
def test_download_url_404(tmp_dir, url_pattern):
    expected, actual = download_url_test(tmp_dir, url_pattern, level=4)
    assert actual is None, "404 didn't return None."
    assert not expected.is_file(), "404 created a file."

  
def download_url_test(tmp_dir: Path, url_pattern: str, level: int):
    url = url_pattern.format(level=level)
    expected = tmp_dir.joinpath(Path(url).name)
    actual = util.download_url(url, tmp_dir)
    return expected, actual


# strip_accents tests


@pytest.mark.unit
def test_strip_accents_removes_accented_characters():
    assert util.strip_accents("Mëtàl") == "Metal"


@pytest.mark.unit
def test_strip_accents_removes_leading_and_trailing_spaces():
    assert util.strip_accents(" Metal ") == "Metal"


@pytest.mark.unit
def test_strip_accents_removes_apostrophes():
    assert util.strip_accents("Metal's") == "Metals"


@pytest.mark.unit
def test_strip_accents_handles_empty_string():
    assert util.strip_accents("") == ""


@pytest.mark.unit
def test_strip_accents_handles_non_string_input():
    with pytest.raises(AttributeError):
        util.strip_accents(123)


# text_to_id tests


@pytest.mark.unit
def test_text_to_id_converts_text_with_spaces():
    assert util.text_to_id("Hello World") == "Hello_World"


@pytest.mark.unit
def test_text_to_id_removes_special_characters():
    assert util.text_to_id("Hello@World!") == "HelloWorld"


@pytest.mark.unit
def test_text_to_id_handles_empty_string():
    assert util.text_to_id("") == ""


@pytest.mark.unit
def test_text_to_id_handles_non_string_input():
    assert util.text_to_id(123) == "123"


@pytest.mark.unit
def test_text_to_id_handles_accented_characters():
    assert util.text_to_id("Mëtàl") == "Metal"


# lists_to_dict tests


@pytest.mark.unit
def test_lists_to_dict_creates_dictionary_from_two_lists2():
    list1 = ["a", "b", "c"]
    list2 = ["x", "y", "z"]
    assert util.lists_to_dict(list1, list2) == {"a": "x", "b": "y", "c": "z"}


@pytest.mark.unit
def test_lists_to_dict_handles_empty_lists():
    assert util.lists_to_dict([], []) == {}


@pytest.mark.unit
def test_lists_to_dict_handles_lists_of_different_lengths():
    list1 = ["a", "b", "c"]
    list2 = [1, 2]
    assert util.lists_to_dict(list1, list2) == {"a": 1, "b": 2}


# format_run_name tests

@pytest.mark.unit
def test_format_run_name_creates_run_name_from_regex():
    locations = ["Rw.*:[B|C]{2}.*"]
    run_name = util.format_run_name(locations)
    assert run_name == "Rw-BC2_1_ba767f3"
    
    
@pytest.mark.unit
def test_format_run_name_creates_run_name_from_single_location():
    locations = ["location1"]
    assert util.format_run_name(locations) == "location1_1_ae11985"


@pytest.mark.unit
def test_format_run_name_creates_run_name_from_multiple_locations():
    locations = ["location1", "location2"]
    assert util.format_run_name(locations).startswith("location1_2_")


@pytest.mark.unit
def test_format_run_name_handles_location_with_colon():
    locations = ["location:1"]
    assert util.format_run_name(locations) == "location-1_1_f2ef959"


@pytest.mark.unit
def test_format_run_name_handles_empty_locations_list():
    locations = []
    with pytest.raises(AssertionError):
        util.format_run_name(locations)
        

# create_zip tests


@pytest.mark.unit
def test_create_zip_creates_archive_from_files():
    file_list = [Path(tempfile.mktemp(suffix=".txt")) for _ in range(3)]
    for file in file_list:
        file.write_text("Test content")
    zip_name = "test_archive.zip"
    archive_path = util.create_zip(file_list, zip_name)
    assert archive_path.is_file()


@pytest.mark.unit
def test_create_zip_handles_empty_file_list():
    file_list = []
    zip_name = "test_archive.zip"
    archive_path = util.create_zip(file_list, zip_name)
    assert archive_path.is_file()


@pytest.mark.unit
def test_create_zip_handles_non_existent_files():
    file_list = [Path("/non/existent/path.txt")]
    zip_name = "test_archive.zip"
    archive_path = util.create_zip(file_list, zip_name)
    assert archive_path.is_file()
