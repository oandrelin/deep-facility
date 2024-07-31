# DO NOT MODIFY

import pytest


@pytest.fixture(autouse=True)
def change_test_dir(request, monkeypatch):
    """Ensure the correct working directory is set."""
    monkeypatch.chdir(request.fspath.dirname)