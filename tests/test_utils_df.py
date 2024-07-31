import geopandas as gpd

import pandas as pd
import pytest

from deepfacility.utils import util

   
# clean_dataframe tests


@pytest.mark.unit
def test_clean_dataframe_removes_accents_and_spaces():
    df = pd.DataFrame({"name": ["Mëtàl ", " Rock "]})
    assert all(util.clean_dataframe(df, ["name"])["name"] == pd.Series(["Metal", "Rock"]))


@pytest.mark.unit
def test_clean_dataframe_removes_apostrophes():
    df = pd.DataFrame({"name": ["Metal's", "Rock's"]})
    assert all(util.clean_dataframe(df, ["name"])["name"] == pd.Series(["Metals", "Rocks"]))


@pytest.mark.unit
def test_clean_dataframe_handles_empty_string():
    df = pd.DataFrame({"name": [""]})
    assert all(util.clean_dataframe(df, ["name"])["name"] == pd.Series([""]))


@pytest.mark.unit
def test_clean_dataframe_handles_non_string_input():
    df = pd.DataFrame({"name": [123, 456]})
    assert all(util.clean_dataframe(df, ["name"])["name"] == pd.Series(["123", "456"]))


@pytest.mark.unit
def test_clean_dataframe_handles_mixed_input():
    df = pd.DataFrame({"name": ["Mëtàl's ", 123, " Rock's ", ""]})
    assert all(util.clean_dataframe(df, ["name"])["name"] == pd.Series(["Metals", "123", "Rocks", ""]))


@pytest.mark.unit
def test_clean_dataframe_keeps_raw_columns():
    df = pd.DataFrame({"name": ["Mëtàl's ", 123, " Rock's ", ""]})
    cleaned_df = util.clean_dataframe(df, ["name"], keep=True)
    assert all(cleaned_df["name_raw"] == pd.Series(["Mëtàl's ", 123, " Rock's ", ""]))
    assert all(cleaned_df["name"] == pd.Series(["Metals", "123", "Rocks", ""]))


@pytest.mark.unit
def test_clean_dataframe_handles_no_columns():
    df = pd.DataFrame({"name": ["Mëtàl's ", 123, " Rock's ", ""]})
    assert util.clean_dataframe(df, []).equals(df)
    

# rename_df_cols tests


@pytest.mark.unit
def test_rename_df_cols_renames_single_column():
    df = pd.DataFrame({"A": [1, 2, 3]})
    renamed_df = util.rename_df_cols(df, "A", "B")
    assert "B" in renamed_df.columns
    assert "A" not in renamed_df.columns


@pytest.mark.unit
def test_rename_df_cols_renames_multiple_cols():
    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    df_renamed = util.rename_df_cols(df, ["A", "B"], ["C", "D"])
    assert "C" in df_renamed.columns
    assert "D" in df_renamed.columns
    assert "A" not in df_renamed.columns
    assert "B" not in df_renamed.columns


@pytest.mark.unit
def test_rename_df_cols_handles_non_existent_cols():
    df = pd.DataFrame({"A": [1, 2, 3]})
    with pytest.raises(AssertionError):
        util.rename_df_cols(df, "B", "C")


@pytest.mark.unit
def test_rename_df_cols_handles_no_change_in_column_name():
    df = pd.DataFrame({"A": [1, 2, 3]})
    renamed_df = util.rename_df_cols(df, "A", "A")
    assert "A" in renamed_df.columns


@pytest.mark.unit
def test_rename_df_cols_handles_geodataframe():
    df = gpd.GeoDataFrame({"A": [1, 2, 3]})
    renamed_df = util.rename_df_cols(df, "A", "B")
    assert "B" in renamed_df.columns
    assert "A" not in renamed_df.columns