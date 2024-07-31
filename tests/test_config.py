import pandas as pd
import pytest
import tempfile

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from deepfacility.config.config import Config, DataClassFactory, create_config_file, filter_by_locations
from deepfacility.config.config import populate, is_str_item, is_path_key, path_to_obj, path_to_str


@pytest.fixture
def config_file():
    config_file = Path(tempfile.mktemp(suffix=".toml"))
    create_config_file(config_file)
    yield config_file
    config_file.unlink(missing_ok=True)


@pytest.fixture
def cfg(config_file):
    return Config(config_file=config_file)


@pytest.mark.unit
def test_config_init(cfg):
    assert cfg.args.country_code == "BFA"
    assert Path(str(cfg.inputs.buildings.file)) == Path("app-data/data/BFA/inputs/buildings_BFA.feather")


@pytest.mark.unit
def test_config_load_config_file():
    with patch.object(Config, "_load_config_file") as mock_load:
        config = Config(config_file=Path("test_config.toml"), _load=True)
        mock_load.assert_called_once(), "_load_config_file should be called once when _load is True"


@pytest.mark.unit
def test_config_load_config_file_not_called():
    with patch.object(Config, "_load_config_file") as mock_load:
        config = Config(config_file=Path("test_config.toml"), _load=False)
        mock_load.assert_not_called(), "_load_config_file should not be called when _load is False"


# populate tests


@pytest.mark.unit
def test_populate_handles_valid_args():
    data = {"path": "{app_dir}/data", "file": "{file_dir}/file.txt"}
    args = {"app_dir": "/app", "file_dir": "/files"}
    expected = {"path": "/app/data", "file": "/files/file.txt"}
    assert populate(data, args) == expected


@pytest.mark.unit
def test_populate_handles_missing_args():
    data = {"path": "{app_dir}/data", "file": "{file_dir}/file.txt"}
    args = {"app_dir": "/app"}
    expected = {"path": "/app/data", "file": "{file_dir}/file.txt"}
    assert populate(data, args) == expected


@pytest.mark.unit
def test_populate_handles_extra_args():
    data = {"path": "{app_dir}/data"}
    args = {"app_dir": "/app", "file_dir": "/files"}
    expected = {"path": "/app/data"}
    assert populate(data, args) == expected


@pytest.mark.unit
def test_populate_handles_path_objects():
    data = {"path": "{app_dir}/data"}
    args = {"app_dir": Path("/app")}
    expected = {"path": "/app/data"}
    assert populate(data, args) == expected


# is_str_item tests


@pytest.mark.unit
def test_is_str_item_handles_string_and_path():
    assert is_str_item("app_dir", Path("/app")) == True


@pytest.mark.unit
def test_is_str_item_handles_string_and_string():
    assert is_str_item("app_dir", "/app") == True


@pytest.mark.unit
def test_is_str_item_handles_non_string_key():
    assert is_str_item(123, "/app") == False


@pytest.mark.unit
def test_is_str_item_handles_non_string_or_path_value():
    assert is_str_item("app_dir", 123) == False


# is_path_key tests


@pytest.mark.unit
def test_is_path_key_identifies_file_and_dir_keys():
    assert is_path_key("file")
    assert is_path_key("dir")
    assert is_path_key("test_file")
    assert is_path_key("test_dir")


@pytest.mark.unit
def test_is_path_key_handles_non_file_and_dir_keys():
    assert not is_path_key("test")
    assert not is_path_key("file_test")
    assert not is_path_key("dir_test")


# path_to_obj tests


@pytest.mark.unit
def test_path_to_obj_converts_string_paths_to_path_objects():
    data = {"file": "/path/to/file", "dir": "/path/to/dir", "nested": {"file": "/path/to/nested/file"}}
    converted_data = path_to_obj(data)
    assert isinstance(converted_data["file"], Path)
    assert isinstance(converted_data["dir"], Path)
    assert isinstance(converted_data["nested"]["file"], Path)


@pytest.mark.unit
def test_path_to_obj_handles_non_string_paths():
    data = {"file": 123, "dir": None, "nested": {"file": ["not", "a", "path"]}}
    converted_data = path_to_obj(data)
    assert converted_data["file"] == 123
    assert converted_data["dir"] is None
    assert converted_data["nested"]["file"] == ["not", "a", "path"]


# path_to_str tests


@pytest.mark.unit
def path_to_str_converts_path_objects_to_strings():
    data = {"file": Path("/path/to/file"), "dir": Path("/path/to/dir"), "nested": {"file": Path("/path/to/nested/file")}}
    converted_data = path_to_str(data)
    assert isinstance(converted_data["file"], str)
    assert isinstance(converted_data["dir"], str)
    assert isinstance(converted_data["nested"]["file"], str)


@pytest.mark.unit
def path_to_str_handles_non_path_objects():
    data = {"file": 123, "dir": None, "nested": {"file": ["not", "a", "path"]}}
    converted_data = path_to_str(data)
    assert converted_data["file"] == 123
    assert converted_data["dir"] is None
    assert converted_data["nested"]["file"] == ["not", "a", "path"]


# DataClassFactory tests


@dataclass
class MockDataClass:
    field1: str
    field2: int


@pytest.mark.unit
def test_dataclass_factory_creates_dataclass_with_valid_config():
    factory = DataClassFactory(cfg={"mock": {"field1": "value1", "field2": 2}})
    dataclass_instance = factory.make(MockDataClass, ["mock"])
    assert isinstance(dataclass_instance, MockDataClass)
    assert dataclass_instance.field1 == "value1"
    assert dataclass_instance.field2 == 2


@pytest.mark.unit
def test_dataclass_factory_handles_missing_fields_in_config():
    factory = DataClassFactory(cfg={"mock": {"field1": "value1"}})
    with patch.object(factory, "missing", new_callable=list) as mock_missing:
        dataclass_instance = factory.make(MockDataClass, ["mock"])
            
    assert dataclass_instance is None
    assert mock_missing == ["mock/field2"]



@pytest.mark.unit
def test_dataclass_factory_handles_unused_fields_in_config():
    factory = DataClassFactory(cfg={"mock": {"field1": "value1", "field2": 2, "field3": "value3"}})
    with patch.object(factory, "unused", new_callable=list) as mock_unused:
        dataclass_instance = factory.make(MockDataClass, ["mock"])
    assert isinstance(dataclass_instance, MockDataClass)
    assert mock_unused == ["mock/field3"]


@pytest.mark.unit
def test_dataclass_factory_handles_nonexistent_key_path():
    factory = DataClassFactory(cfg={"mock": {"field1": "value1", "field2": 2}})
    with patch.object(factory, "missing", new_callable=list) as mock_missing:
        dataclass_instance = factory.make(MockDataClass, ["nonexistent"])
    assert dataclass_instance is None
    assert mock_missing == ["nonexistent"]


# filter_by_locations tests


@pytest.fixture()
def df_data() -> pd.DataFrame:
    return pd.DataFrame({
        "id": [1, 2, 3, 4],
        "adm2": ["p1", "p1", "p2", "p3"],
        "adm3": ["c1", "c2", "c3", "c4"]})


@pytest.fixture()
def filter_tuples() -> list[tuple[str, str]]:
    return [("p1", "c2"), ("p3", "c4")]


@pytest.fixture()
def df_x(filter_tuples, adm_cols):
    return pd.DataFrame(filter_tuples, columns=adm_cols)


@pytest.fixture()
def adm_cols() -> list[str]:
    return ["adm2", "adm3"]


@pytest.mark.unit
def test_filter_by_locations_list(cfg: Config, df_data, df_x, filter_tuples, adm_cols):
    locs = [":".join(list(t)) for t in filter_tuples]
    df_res = filter_by_locations(ins=cfg.inputs, df=df_data, locations=locs, columns=adm_cols)
    assert df_x.equals(df_res[adm_cols])
