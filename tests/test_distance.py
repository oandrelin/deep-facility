import pytest
import math
import pandas as pd
import numpy as np

from unittest.mock import MagicMock, patch

from deepfacility.config.config import Config
from deepfacility.tasks import distance


@pytest.fixture
def mock_config():
    return MagicMock(spec=Config)


rel = 1e-9
    
    
def test_convert_to_cartesian():
    # Test case 1: lon = 0, lat = 0, elevation = 0
    # This is the prime meridian, equator, and sea level
    x, y, z = distance.convert_to_cartesian(0, 0, 0)
    
    assert x == pytest.approx(6378137.0, rel=rel)
    assert y + 1 == pytest.approx(1, rel=rel)
    assert z + 1 == pytest.approx(1, rel=rel)
    
    # Note, when approx comparison with 0
    # +1 is added to both sides to work around the
    # pytest.approx limitation
    
    # Test case 2: lon = 90, lat = 0, elevation = 500
    # this is equator, 90 degree east of Greenwich with 500 elevation
    x, y, z = distance.convert_to_cartesian(90, 0, 500)
    
    assert x + 1 == pytest.approx(1, rel=rel)
    assert y == pytest.approx(6378637.0, rel=rel)
    assert z + 1 == pytest.approx(1, rel=rel)
       
    # Test case 3: Andre's example
    f = (-1.5189055063720351, 12.372283125598909, 297)
    x1, y1, z1 = distance.convert_to_cartesian(f[0], f[1], f[2])
    
    assert round(x1) == 6228112
    assert round(y1) == -165145
    assert round(z1) == 1366661
    

def test_calculate_minkowski_from_cartesian():
    # Test with sample data
    df_loc = pd.DataFrame(
        {'id': ['a', 'b', 'c'], 'f_id': ['q', 'q', 'q'], 'x': [0, 1, 2], 'y': [0, 1, 2], 'z': [0, 1, 2]})
    df_facility = pd.DataFrame({'facility_id': ['q', 'r', 's'], 'x': [1, 2, 3], 'y': [1, 2, 3], 'z': [1, 2, 3]})
    left_on = 'f_id'
    right_on = 'facility_id'
    p = 1.54
    # manually calculate distance.minkowski([0,0,0], [1,1,1], p=1.54) = 2.0408871750129656
    result = distance.calculate_minkowski_from_cartesian(df_loc, df_facility, left_on, right_on, p)

    assert result['minkowski'][0] == pytest.approx(2.040887175012965, rel=rel)
    assert result['minkowski'][1] == 0
    assert result['minkowski'][2] == pytest.approx(2.0408871750129656, rel=rel)


def test_find_nearest_facility():
    # generate two data frame with id and x, y columns
    df_loc = pd.DataFrame({'id': ['a', 'b', 'c'], 'x': [0, 1, 2], 'y': [0, 1, 2]})
    df_facility = pd.DataFrame({'facility_id': ['q', 'r', 's'], 'x': [1, 2, 3], 'y': [1, 2, 3]})

    xy_ser = df_loc[['x', 'y']].values
    xy_ser2 = df_facility[['x', 'y']].values

    nearest_facility_indices, shortest_distances = distance.find_nearest_facility(xy_ser, xy_ser2)

    expected_indices = ['q', 'q', 'r']
    expected_distances = [math.sqrt(2), 0, 0]

    df_loc['distance'] = shortest_distances
    df_loc['facility_id'] = df_facility['facility_id'][nearest_facility_indices].values

    assert df_loc['facility_id'].tolist() == expected_indices
    assert df_loc['distance'].tolist() == pytest.approx(expected_distances, rel=4)


def test_calculate_distance_df():
    # Create sample data
    df = pd.DataFrame({'id': ['a', 'b', 'c'], 'lon': [0, 1, 2], 'lat': [0, 1, 2]})
    facilities = pd.DataFrame({'facility_id': ['q', 'r', 's'], 'lon': [1, 2, 3], 'lat': [1, 2, 3]})
    df_xy = ['lon', 'lat']
    facilities_xy = ['lon', 'lat']
    column_prefix = 'distance'

    # Define expected result
    def cal_dist(a, b, p): return [np.power(np.sum(np.abs(a - b) ** p), 1 / p), 0, 0]

    a = np.array(distance.convert_to_cartesian(0, 0))
    b = np.array(distance.convert_to_cartesian(1, 1))
    expected_distances_euclidean = cal_dist(a, b, 2)
    expected_distances_minkowski = cal_dist(a, b, 1.54)

    # Call the function
    result = distance.calculate_distance_df(df, df_xy, facilities, facilities_xy, column_prefix)

    # Assert the output
    msg = f"expected: {expected_distances_euclidean} actual {result['distance_euclidean'].values}"
    assert all(abs(result['distance_euclidean'].values - expected_distances_euclidean) == 0), msg
    
    msg = f"expected: {expected_distances_minkowski} actual {result['distance_minkowski'].values}"
    assert all(abs(result['distance_minkowski'].values - expected_distances_minkowski) == 0), msg
                    

def test_plot_ecdf_distance(mock_config):
    # Create sample data
    df = pd.DataFrame({'minkowski': [1.5, 2.0, 1.8, 1.2, 1.6]})
    distance_col = 'minkowski'
    scale = 1.0
    prop = {'color': 'yellow'}

    result = distance.plot_ecdf_distance(
        cfg=mock_config,
        df=df,
        distance_col=distance_col,
        scale=scale,
        plot_properties=prop)
    
    assert result is not None

