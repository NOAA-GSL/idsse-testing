"""Unit tests for ncp_web_service.py"""

# ----------------------------------------------------------------------------------
# Created on Wed Dec 18 2024
#
# Copyright (c) 2024 Colorado State University. All rights reserved.             (1)
#
# Contributors:
#     Mackenzie Grimes (1)
#
# ----------------------------------------------------------------------------------
# pylint: disable=missing-function-docstring,redefined-outer-name,unused-argument
import json
from datetime import timedelta
from unittest.mock import Mock

from flask import Request, Response
from pytest import fixture, MonkeyPatch
from werkzeug.datastructures import MultiDict

from python.nwsc_proxy.ncp_web_service import (
    AppWrapper,
    Flask,
    Namespace,
    SupportProfileStore,
    create_app,
    datetime,
    GSL_KEY,
)

# constants
EXAMPLE_DATETIME = datetime(2024, 1, 1, 12, 34)
EXAMPLE_UUID = "9835b194-74de-4321-aa6b-d769972dc7cb"


# fixtures
@fixture
def mock_datetime(monkeypatch: MonkeyPatch) -> Mock:
    mock_obj = Mock(name="MockDatetime")
    mock_obj.now.return_value = EXAMPLE_DATETIME
    monkeypatch.setattr("python.nwsc_proxy.ncp_web_service.datetime", mock_obj)

    return mock_obj


@fixture
def mock_profile_store(monkeypatch: MonkeyPatch) -> Mock:
    mock_obj = Mock(name="MockProfileStore", spec=SupportProfileStore)
    monkeypatch.setattr("python.nwsc_proxy.ncp_web_service.SupportProfileStore", mock_obj)
    return mock_obj


@fixture
def mock_jsonify(monkeypatch: MonkeyPatch) -> Mock:
    def mock_func(*args, **_kwargs):
        return Response(bytes(json.dumps(args[0]), "utf-8"), content_type="application/json")

    mock_obj = Mock(name="MockJsonify")
    mock_obj.side_effect = mock_func
    monkeypatch.setattr("python.nwsc_proxy.ncp_web_service.jsonify", mock_obj)
    return mock_obj


@fixture
def mock_current_app(monkeypatch: MonkeyPatch) -> Mock:
    mock_obj = Mock(name="MockCurrentApp", spec=Flask)
    mock_obj.logger.info.return_value = None
    mock_obj.logger.error.return_value = None
    mock_obj.config = MultiDict({"GSL_KEY": GSL_KEY})
    monkeypatch.setattr("python.nwsc_proxy.ncp_web_service.current_app", mock_obj)
    return mock_obj


@fixture
def mock_request(monkeypatch: MonkeyPatch, mock_current_app, mock_jsonify) -> Mock:
    mock_obj = Mock(name="MockFlaskRequest", spec=Request)
    mock_obj.origin = "http://example.com:5000"
    mock_obj.method = "GET"
    mock_obj.headers = MultiDict({"X-Api-Key": GSL_KEY})
    monkeypatch.setattr("python.nwsc_proxy.ncp_web_service.request", mock_obj)
    return mock_obj


@fixture
def wrapper(mock_profile_store, mock_datetime, mock_request) -> AppWrapper:
    return AppWrapper("/fake/base/dir")


def test_create_app(mock_profile_store: Mock):
    args = Namespace()
    args.base_dir = "/fake/base/dir"

    _app = create_app(args)

    assert isinstance(_app, Flask)
    endpoint_dict = _app.view_functions
    assert sorted(list(endpoint_dict.keys())) == ["events", "health", "vulnerabilities"]


def test_health_route(wrapper: AppWrapper, mock_datetime: Mock):
    # simulate that server has been running for 5 minutes
    mock_datetime.now.return_value = EXAMPLE_DATETIME + timedelta(minutes=5)

    result: tuple[Response, int] = wrapper.app.view_functions["health"]()

    response, status_code = result
    assert status_code == 200
    assert response.json == {"startedAt": "2024-01-01T12:34:00.000Z", "uptime": 5 * 60}


def test_events_bad_key(wrapper: AppWrapper, mock_request: Mock):
    mock_request.headers = MultiDict({"X-Api-Key": "A_BAD_KEY"})

    result: tuple[Response, int] = wrapper.app.view_functions["events"]()

    assert result[1] == 401


def test_get_existing_profiles(wrapper: AppWrapper, mock_request: Mock, mock_profile_store: Mock):
    mock_request.args = MultiDict({"dataSource": "NBM"})
    example_profile_list = [{"id": EXAMPLE_UUID, "name": "My Profile"}]
    mock_profile_store.return_value.get_all.return_value = example_profile_list

    result: tuple[Response, int] = wrapper.app.view_functions["events"]()

    response, status_code = result
    assert status_code == 200
    assert response.json == {"profiles": example_profile_list, "errors": []}
    # filter_new_profiles not set
    mock_profile_store.return_value.get_all.assert_called_with("NBM", include_inactive=False)


def test_create_profile_existing(
    wrapper: AppWrapper, mock_request: Mock, mock_profile_store: Mock
):
    mock_request.method = "POST"
    example_profile = {"id": EXAMPLE_UUID, "name": "My Profile"}
    mock_request.json = {"data": example_profile}
    mock_profile_store.return_value.save.return_value = EXAMPLE_UUID  # save() success

    result: tuple[Response, int] = wrapper.app.view_functions["events"]()

    assert result[1] == 201
    mock_profile_store.return_value.save.assert_called_once_with(example_profile)


def test_create_previous_profile_failure(
    wrapper: AppWrapper, mock_request: Mock, mock_profile_store: Mock
):
    mock_request.method = "POST"
    mock_request.json = {"id": EXAMPLE_UUID, "name": "My Profile"}
    mock_profile_store.return_value.save.return_value = None  # save() rejected, profile must exist

    result: tuple[Response, int] = wrapper.app.view_functions["events"]()

    assert result[1] == 400


def test_delete_profile_success(wrapper: AppWrapper, mock_request: Mock, mock_profile_store: Mock):
    mock_request.method = "DELETE"
    mock_request.args = MultiDict({"id": EXAMPLE_UUID})
    mock_profile_store.return_value.delete.return_value = True  # delete worked

    result: tuple[Response, int] = wrapper.app.view_functions["events"]()

    assert result[1] == 204


def test_delete_profile_failure(wrapper: AppWrapper, mock_request: Mock, mock_profile_store: Mock):
    mock_request.method = "DELETE"
    mock_request.args = MultiDict({"uuid": EXAMPLE_UUID})
    # delete() was rejected, profile must exist
    mock_profile_store.return_value.delete.return_value = False

    result: tuple[Response, int] = wrapper.app.view_functions["events"]()

    assert result[1] == 404


def test_update_profile_success(wrapper: AppWrapper, mock_request: Mock, mock_profile_store: Mock):
    mock_request.method = "PUT"
    mock_request.args = MultiDict({"id": EXAMPLE_UUID})
    expected_data = {"id": EXAMPLE_UUID, "name": "Some new name"}
    mock_request.json = expected_data
    mock_profile_store.return_value.update.return_value = expected_data

    result: tuple[Response, int] = wrapper.app.view_functions["events"]()

    assert result[1] == 200
    assert result[0].json["profile"] == expected_data


def test_update_no_body(wrapper: AppWrapper, mock_request: Mock, mock_profile_store: Mock):
    mock_request.method = "PUT"
    mock_request.args = MultiDict({"uuid": EXAMPLE_UUID})
    mock_request.data = None

    result: tuple[Response, int] = wrapper.app.view_functions["events"]()

    assert result[1] == 400


def test_update_profile_missing(wrapper: AppWrapper, mock_request: Mock, mock_profile_store: Mock):
    mock_request.method = "PUT"
    mock_request.args = MultiDict({"uuid": EXAMPLE_UUID})
    mock_profile_store.return_value.update.side_effect = FileNotFoundError

    result: tuple[Response, int] = wrapper.app.view_functions["events"]()

    assert result[1] == 404
