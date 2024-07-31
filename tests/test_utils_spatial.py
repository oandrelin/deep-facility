import pandas as pd
import geopandas as gpd
import pytest

from pathlib import Path
from shapely.geometry import Point
from unittest.mock import patch

from deepfacility.utils import spatial


@pytest.fixture
def mock_df():
    data = {
        'lon': [12.4924, 12.4925, 12.4926],
        'lat': [41.8902, 41.8903, 41.8904]
    }
    df = pd.DataFrame(data)
    return df


# detect_country tests


@pytest.fixture
def mock_gdf(mock_df):
    gdf = gpd.GeoDataFrame(
        mock_df, geometry=gpd.points_from_xy(mock_df.lon, mock_df.lat))
    return gdf


@pytest.mark.unit
def test_detect_country_with_valid_data(mock_gdf):
    country_name, country_code = spatial.detect_country(mock_gdf, ['lon', 'lat'])
    assert country_name == 'Italy'
    assert country_code == 'ITA'


@pytest.mark.unit
def test_detect_country_with_empty_dataframe(mock_df):
    mock_df = mock_df.iloc[0:0]
    with pytest.raises(ValueError):
        spatial.detect_country(mock_df, ['lon', 'lat'])


@pytest.mark.unit
def test_detect_country_with_invalid_column_names(mock_gdf):
    with pytest.raises(KeyError):
        spatial.detect_country(mock_gdf, ['longitude', 'latitude'])


@pytest.mark.unit
def test_detect_country_with_nonexistent_country(mock_df):
    mock_df['lon'] = [180]*3
    mock_df['lat'] = [90]*3
    with pytest.raises(IndexError):
        spatial.detect_country(mock_df, ['lon', 'lat'])
        

# plus_code tests


@pytest.mark.unit
def test_plus_code():
    latitude = 47.756917
    longitude = -122.260630
    plus_code = spatial.get_plus_code(longitude, latitude)
    assert plus_code == "84VVQP4Q+QP"


# filter_locations tests


@pytest.mark.unit
def test_filter_locations_filters_by_single_location():
    df = pd.DataFrame({"location": ["location1", "location2", "location3"]})
    filtered_df = spatial.filter_locations(df=df, locations=["location1"], columns=["location"])
    assert all(filtered_df["location"] == pd.Series(["location1"]))


@pytest.mark.unit
def test_filter_locations_filters_by_multiple_locations():
    df = pd.DataFrame({"location": ["location1", "location2", "location3"]})
    filtered_df = spatial.filter_locations(df, locations=["location1", "location3"], columns=["location"])
    assert all(filtered_df["location"] == pd.Series(["location1", "location3"]))


@pytest.mark.unit
def test_filter_locations_handles_no_matching_locations():
    df = pd.DataFrame({"location": ["location1", "location2", "location3"]})
    filtered_df = spatial.filter_locations(df, locations=["location4"], columns=["location"])
    assert filtered_df.empty


@pytest.mark.unit
def test_filter_locations_handles_empty_dataframe():
    df = pd.DataFrame({"location": []})
    filtered_df = spatial.filter_locations(df, locations=["location1"], columns=["location"])
    assert filtered_df.empty


@pytest.mark.unit
def test_filter_locations_handles_empty_locations_list():
    df = pd.DataFrame({"location": ["location1", "location2", "location3"]})
    filtered_df = spatial.filter_locations(df, locations=[], columns=["location"])
    assert filtered_df.empty


# location_path tests


@pytest.mark.unit
def test_location_path_creates_path_with_location():
    pattern = Path("/path/to/{location}/file.txt")
    location = "location1:location2"
    expected_path = Path("/path/to/location1/location2/file.txt")
    with patch("deepfacility.utils.spatial.util.make_dir") as mock_make_dir:
        actual_path = spatial.location_path(pattern, location)
    assert actual_path == expected_path
    mock_make_dir.assert_called_once_with(expected_path)


@pytest.mark.unit
def test_location_path_creates_path_without_location():
    pattern = Path("/path/to/file.txt")
    location = "location1:location2"
    expected_path = Path("/path/to/file.txt")
    with patch("deepfacility.utils.spatial.util.make_dir") as mock_make_dir:
        actual_path = spatial.location_path(pattern, location)
    assert actual_path == expected_path
    mock_make_dir.assert_called_once_with(expected_path)


@pytest.mark.unit
def test_location_path_creates_path_without_mkdir():
    pattern = Path("/path/to/{location}/file.txt")
    location = "location1:location2"
    expected_path = Path("/path/to/location1/location2/file.txt")
    with patch("deepfacility.utils.spatial.util.make_dir") as mock_make_dir:
        actual_path = spatial.location_path(pattern, location, mkdir=False)
    assert actual_path == expected_path
    mock_make_dir.assert_not_called()
    
    
# xy_to_gdf tests


@pytest.mark.unit
def test_xy_to_gdf_creates_geodataframe_from_dataframe():
    df = pd.DataFrame({"lon": [1, 2, 3], "lat": [4, 5, 6]})
    gdf = spatial.xy_to_gdf(df, ["lon", "lat"])
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert all(gdf.geometry == gpd.GeoSeries([Point(1, 4), Point(2, 5), Point(3, 6)]))
    assert gdf.crs == spatial.default_crs


@pytest.mark.unit
def test_xy_to_gdf_handles_empty_dataframe():
    df = pd.DataFrame({"lon": [], "lat": []})
    gdf = spatial.xy_to_gdf(df, ["lon", "lat"])
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert gdf.empty
    assert gdf.crs == spatial.default_crs


@pytest.mark.unit
def test_xy_to_gdf_handles_dataframe_with_nan_values():
    df = pd.DataFrame({"lon": [1, 2, None], "lat": [4, None, 6]})
    gdf = spatial.xy_to_gdf(df, ["lon", "lat"])
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert all(gdf.geometry == gpd.GeoSeries([Point(1, 4)]))
    assert gdf.crs == spatial.default_crs
