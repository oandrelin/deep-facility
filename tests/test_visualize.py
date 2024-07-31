import pytest

import os
import tempfile
import geopandas as gpd

from pathlib import Path

from deepfacility.utils import spatial
from deepfacility.viz import visualize
from deepfacility.lang.translator import BaseTranslator


result_dir = Path(os.path.dirname(__file__), "test_data", "results")


@pytest.mark.unit
def test_create_from_shape():
    with tempfile.TemporaryDirectory() as temp_dir:
        spatial.create_geojson(Path(result_dir, 'village_shapes.shp'), "village_shapes", Path(temp_dir), None, None)
        expected_file_path = Path(temp_dir, "village_shapes.geojson")
        assert os.path.exists(expected_file_path)
        gdf = gpd.read_file(expected_file_path)
        assert len(gdf) == 3


@pytest.mark.unit
def test_create_from_csv():
    with tempfile.TemporaryDirectory() as temp_dir:
        spatial.create_geojson(Path(result_dir, 'optimal_facilities.csv'), "optimal_facilities", Path(temp_dir), 'lon', 'lat')
        expected_file_path = Path(temp_dir, "optimal_facilities.geojson")
        assert os.path.exists(expected_file_path)
        gdf = gpd.read_file(expected_file_path)
        assert len(gdf) == 9


@pytest.mark.unit
def test_translate_html_text(mocker):
    # Define the test input and expected output
    content = 'Hello, {{ _("world") }}!'
    expected_output = 'Hello, le monde!'
    translator = BaseTranslator()
    # Mock the replace_word function within translate_html_template
    mocker.patch('deepfacility.lang.translator.BaseTranslator.translate', return_value="le monde")
    # Call the function
    result = visualize.translate_html_template(translator, content)
    # Assert the expected result
    assert result == expected_output