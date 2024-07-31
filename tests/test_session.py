from requests import Request

from unittest.mock import Mock, MagicMock, patch

from deepfacility.ux.session import Session


def test_get_session_id_from_query_string():
    request: Request = MagicMock(query_params={'sid': 'test123'}, cookies={})
    assert Session.get_session_id(request) == 'test123'


def test_get_session_id_from_cookie():
    request: Request = MagicMock(query_params={}, cookies={'session_id': 'test123'})
    assert Session.get_session_id(request) == 'test123'


def test_generate_new_session_id_when_no_source_provided():
    request: Request = MagicMock(query_params={}, cookies={})
    assert Session.get_session_id(request) is not None
    assert len(Session.get_session_id(request)) == 12
