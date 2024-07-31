import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch
from deepfacility.tasks.clustering import cluster_points
from deepfacility.utils import spatial


@pytest.fixture
def df_points():
    return pd.DataFrame({
        'x': [1, 2, 3, 4, 5],
        'y': [1, 2, 3, 4, 5]
    })


@pytest.fixture
def df_centers():
    return pd.DataFrame({
        'x': [1, 5],
        'y': [1, 5]
    })


@pytest.fixture
def xy_cols():
    return ['x', 'y']


def validate(df1, df2):
    assert all(df1['cluster'] == pd.Series([0, 0, 1, 1, 1]))
    assert all(df2['cluster_lon'] == pd.Series([1, 5]))
    assert all(df2['cluster_lat'] == pd.Series([1, 5]))


@pytest.mark.unit
def test_cluster_points_converges(df_points, df_centers, xy_cols):

    with patch.object(spatial, 'kmeans_fit') as mock_kmeans_fit:
        mock_kmeans_fit.return_value.labels_ = np.array([0, 0, 1, 1, 1])
        mock_kmeans_fit.return_value.cluster_centers_ = np.array([[1, 1], [5, 5]])
        mock_kmeans_fit.return_value.n_iter_ = 9
        mock_kmeans_fit.return_value.max_iter = 10

        converged = cluster_points(df_points, df_centers, xy_cols)

    assert converged
    validate(df_points, df_centers)


@pytest.mark.unit
def test_cluster_points_does_not_converge(df_points, df_centers, xy_cols):
    
    with patch.object(spatial, 'kmeans_fit') as mock_kmeans_fit:
        mock_kmeans_fit.return_value.labels_ = np.array([0, 0, 1, 1, 1])
        mock_kmeans_fit.return_value.cluster_centers_ = np.array([[1, 1], [5, 5]])
        mock_kmeans_fit.return_value.n_iter_ = 10
        mock_kmeans_fit.return_value.max_iter = 10

        converged = cluster_points(df_points, df_centers, xy_cols)

    assert not converged
    validate(df_points, df_centers)