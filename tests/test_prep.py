import pytest
import geopandas as gpd
import pandas as pd

from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import MagicMock, patch

from deepfacility.data.inputs import DataInputs
from deepfacility.config.config import Config, AdmPointsFile


@pytest.fixture
def mock_config():
    return MagicMock(spec=Config)


@pytest.fixture
def mock_data_inputs(mock_config):
    return DataInputs(mock_config)


# prepare_country_shapes tests

@pytest.mark.unit
def test_prepare_country_shapes_when_shape_files_exist(mock_data_inputs):
    mock_data_inputs.cfg.inputs.shape_files = [Path('shape1.shp'), Path('shape2.shp')]
    with patch('pathlib.Path.is_file', return_value=True):
        result = mock_data_inputs.prepare_country_shapes(Path('zipfile.zip'))
    assert result == mock_data_inputs.cfg.inputs.shape_files


@pytest.mark.unit
def test_prepare_country_shapes_when_shape_files_do_not_exist(mock_data_inputs):
    mock_data_inputs.cfg.inputs.shape_files = [Path('shape1.shp'), Path('shape2.shp')]
    with patch.object(Path, 'is_file') as mock_is_file:
        mock_is_file.return_value = True
    
        zip_file = Path('zipfile.zip')
        with patch('geopandas.read_file', return_value=MagicMock()), \
             patch('deepfacility.utils.util.clean_dataframe', return_value=MagicMock()), \
             patch('deepfacility.utils.util.make_dir'), \
             patch('geopandas.GeoDataFrame.to_file'):
            
            result = mock_data_inputs.prepare_country_shapes(zip_file)
            assert result == mock_data_inputs.cfg.inputs.shape_files


@pytest.mark.unit
def test_prepare_country_shapes_when_zip_file_does_not_exist(mock_data_inputs):
    with pytest.raises(AssertionError, match="Raw shape file not found."):
        mock_data_inputs.prepare_country_shapes(Path('nonexistent.zip'))
        
        
# prepare_households tests


@pytest.mark.unit
def test_households_preparation_when_file_exists(mock_data_inputs):
    mock_data_inputs.cfg.inputs.households.file = Path('existing_file.csv')
    with patch.object(Path, 'is_file', return_value=True):
        result = mock_data_inputs.prepare_households(Path('buildings_file.feather'), ['lon', 'lat'], Path('shapes_file.shp'), ['adm1', 'adm2'])
    assert result == mock_data_inputs.cfg.inputs.households.file


@pytest.mark.unit
def test_households_preparation_when_file_does_not_exist(mock_data_inputs):
    mock_data_inputs.cfg.inputs.households.file = Path(mkdtemp()) / Path('nonexistent_file.csv')
    with patch.object(Path, 'is_file', return_value=False), \
         patch('geopandas.read_file', return_value=MagicMock()), \
         patch('pandas.read_feather', return_value=MagicMock()), \
         patch('deepfacility.data.inputs.DataInputs.process_buildings', return_value=MagicMock()), \
         patch('pandas.DataFrame.to_csv'):
        result = mock_data_inputs.prepare_households(Path('buildings_file.feather'), ['lon', 'lat'], Path('shapes_file.shp'), ['adm1', 'adm2'])
    assert result == mock_data_inputs.cfg.inputs.households.file


# process_buildings tests


@pytest.fixture
def mock_gdf_shapes():
    return gpd.GeoDataFrame({
        'x': [1, 2, 3, 4, 5],
        'y': [1, 2, 3, 4, 5]
    })


@pytest.fixture
def mock_df_xy():
    return pd.DataFrame({
        'x': [1, 2, 3, 4, 5],
        'y': [1, 2, 3, 4, 5]
    })


@pytest.mark.unit
def test_buildings_processing_happy_path(mock_data_inputs, mock_gdf_shapes, mock_df_xy):
    with patch('deepfacility.data.inputs.process_google_buildings', return_value=mock_df_xy):
        result = mock_data_inputs.process_buildings(mock_gdf_shapes, ['x', 'y'], mock_df_xy, ['x', 'y'])
    assert result.equals(mock_df_xy)


@pytest.mark.unit
def test_buildings_processing_with_empty_dataframe(mock_data_inputs, mock_gdf_shapes):
    with patch('deepfacility.data.inputs.process_google_buildings', return_value=pd.DataFrame()):
        result = mock_data_inputs.process_buildings(mock_gdf_shapes, ['x', 'y'], pd.DataFrame(), ['x', 'y'])
    assert result.empty
    
    
# prepare_village_locality tests


@pytest.fixture
def mock_village_locality():
    return AdmPointsFile(file=Path('village_locality.csv'), adm_cols=['adm1', 'adm2'], xy_cols=['lon', 'lat'])


@pytest.fixture
def mock_shape_files():
    return [Path('shape1.shp'), Path('shape2.shp')]


@pytest.mark.unit
def test_village_locality_preparation(mock_data_inputs, mock_village_locality, mock_shape_files):
    mock_data_inputs.cfg.inputs.village_centers.file = Path(mkdtemp()) / Path('nonexistent_file.csv')
    with patch('pandas.read_csv', return_value=MagicMock()), \
         patch('geopandas.read_file', return_value=MagicMock()), \
         patch('deepfacility.data.inputs.DataInputs.prepare_village_centers', return_value=MagicMock()), \
         patch('pandas.DataFrame.to_csv'):
        result = mock_data_inputs.prepare_village_locality(mock_village_locality, mock_shape_files)
    assert result == mock_data_inputs.cfg.inputs.village_centers.file


@pytest.fixture
def mock_shape_file():
    return Path('shape.shp')


@pytest.fixture
def mock_df():
    return pd.DataFrame({
        'x': [1.1, 2.1, 3.1, 4.1, 5.1],
        'y': [1.2, 2.2, 3.2, 4.2, 5.2],
        'name': ['a4', 'b4', 'c4', 'd4', 'e4'],
        'info1': ['i11', 'i12', 'i13', 'i14', 'i15'],
        'info2': ['i21', 'i22', 'i23', 'i24', 'i25']
    })


@pytest.fixture
def mock_gdf(mock_df):
    return gpd.GeoDataFrame({
        'NAME2': ['a2', 'b2', 'c2', 'd2', 'e2'],
        'NAME3': ['a3', 'b3', 'c3', 'd3', 'e3'],
        'geometry': gpd.points_from_xy(mock_df.x, mock_df.y, crs="EPSG:4326"),
    })


@pytest.fixture
def mock_baseline_file():
    return Path('baseline.csv')


@pytest.mark.unit
def test_village_centers_preparation_happy_path(
        mock_data_inputs,
        mock_village_locality,
        mock_shape_file,
        mock_df,
        mock_gdf):
    
    # Mock baseline facilities config
    vc = mock_data_inputs.cfg.inputs.village_centers
    vc.file = Path('existing_file.csv')
    vc.xy_cols = ['lon', 'lat']
    vc.adm_cols = ['adm2', 'adm3', 'village']
    
    exp_cols = vc.adm_cols + vc.xy_cols
    
    with patch('pandas.read_csv', return_value=mock_df), \
         patch('geopandas.read_file', return_value=mock_gdf), \
         patch('pandas.DataFrame.to_csv'):
        df_res = mock_data_inputs.prepare_village_centers(village_locality_file=mock_village_locality.file,
                                                          xy_cols=['x', 'y'],
                                                          village_col='name',
                                                          shape_file=mock_shape_file,
                                                          adm_cols=['NAME2', 'NAME3'])
        
    df_exp = pd.DataFrame({
        'adm2': ['a2', 'b2', 'c2', 'd2', 'e2'],
        'adm3': ['a3', 'b3', 'c3', 'd3', 'e3'],
        'village': ['a4', 'b4', 'c4', 'd4', 'e4'],
        'lon': [1.1, 2.1, 3.1, 4.1, 5.1],
        'lat': [1.2, 2.2, 3.2, 4.2, 5.2]
    })

    assert df_res.equals(df_exp)
    
    
# prepare_baseline_facilities tests


@pytest.mark.unit
def test_baseline_facilities_preparation(
        mock_data_inputs,
        mock_baseline_file,
        mock_shape_file,
        mock_df,
        mock_gdf):
    import tempfile
    # Mock baseline facilities config
    bs = mock_data_inputs.cfg.inputs.baseline_facilities
    bs.file = Path(tempfile.mkdtemp()) / 'baseline_facilities.csv'
    bs.xy_cols = ['lon', 'lat']
    bs.adm_cols = ['adm2', 'adm3']
    #          #patch('pandas.DataFrame.to_csv'), \
    with patch.object(Path, 'is_file', return_value=True), \
         patch('pandas.read_csv', return_value=mock_df), \
         patch('geopandas.read_file', return_value=mock_gdf), \
         patch('deepfacility.utils.spatial.get_plus_code', return_value='g'), \
         patch('deepfacility.utils.spatial.create_geojson'):
        bs_file = mock_data_inputs.prepare_baseline_facilities(
            baseline_file=mock_baseline_file,
            baseline_xy_cols=['x', 'y'],
            shape_file=mock_shape_file,
            shape_adm_cols=['NAME2', 'NAME3'],
            info_cols=['info1', 'info2'],
            id_col='id')
    
    df_exp = pd.DataFrame({
        'adm2': ['a2', 'b2', 'c2', 'd2', 'e2'],
        'adm3': ['a3', 'b3', 'c3', 'd3', 'e3'],
        'lon': [1.1, 2.1, 3.1, 4.1, 5.1],
        'lat': [1.2, 2.2, 3.2, 4.2, 5.2],
        'id': [1, 2, 3, 4, 5],
        'plus': ['g', 'g', 'g', 'g', 'g']
    })
        
    assert bs_file == bs.file
    
    # Load the baseline facilities file.
    # Expected columns: adm2,adm3,lon,lat,facility_id,info_col,plus
    df_bs = pd.read_csv(bs_file)
    
    assert 'info_col' in df_bs.columns.values
    assert df_exp.equals(df_bs[df_exp.columns.values])
