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
    VulnerabilityStore,
    create_app,
    datetime,
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
def mock_store(monkeypatch: MonkeyPatch) -> Mock:
    mock_obj = Mock(name="MockProfileStore", spec=VulnerabilityStore)
    monkeypatch.setattr("python.nwsc_proxy.ncp_web_service.VulnerabilityStore", mock_obj)
    return mock_obj


@fixture
def mock_jsonify(monkeypatch: MonkeyPatch) -> Mock:
    def mock_func(*args, **_kwargs):
        return Response(bytes(json.dumps(args[0]), "utf-8"), content_type="application/json")

    mock_obj = Mock(name="MockJsonify")
    mock_obj.side_effect = mock_func
    monkeypatch.setattr("python.nwsc_proxy.ncp_web_service.jsonify", mock_obj)
    return mock_obj


# @fixture
# def mock_current_app(monkeypatch: MonkeyPatch) -> Mock:
#     mock_obj = Mock(name="MockCurrentApp", spec=Flask)
#     mock_obj.logger.info.return_value = None
#     mock_obj.logger.error.return_value = None
#     # mock_obj.config = MultiDict({"GSL_KEY": GSL_KEY})
#     monkeypatch.setattr("python.nwsc_proxy.ncp_web_service.current_app", mock_obj)
#     return mock_obj


@fixture
def mock_request(monkeypatch: MonkeyPatch, mock_jsonify) -> Mock:
    mock_obj = Mock(name="MockFlaskRequest", spec=Request)
    mock_obj.origin = "http://example.com:5000"
    mock_obj.method = "GET"
    # mock_obj.headers = MultiDict({"X-Api-Key": GSL_KEY})
    monkeypatch.setattr("python.nwsc_proxy.ncp_web_service.request", mock_obj)
    return mock_obj


@fixture
def wrapper(mock_store, mock_datetime, mock_request) -> AppWrapper:
    return AppWrapper("/fake/base/dir")


def test_create_app(mock_store):
    args = Namespace()
    args.base_dir = "/fake/base/dir"
    expected_endpoints = ["health", "vulnerabilities", "vulnerability"]

    _app = create_app(args)

    assert isinstance(_app, Flask)
    endpoint_dict = _app.view_functions
    assert sorted(list(endpoint_dict.keys())) == expected_endpoints


def test_health_route(wrapper: AppWrapper, mock_datetime: Mock):
    # simulate that server has been running for 5 minutes
    mock_datetime.now.return_value = EXAMPLE_DATETIME + timedelta(minutes=5)

    result: tuple[Response, int] = wrapper.app.view_functions["health"]()

    response, status_code = result
    assert status_code == 200
    assert response.json == {"startedAt": "2024-01-01T12:34:00.000Z", "uptime": 5 * 60}


# def test_events_bad_key(wrapper: AppWrapper, mock_request: Mock):
#     mock_request.headers = MultiDict({"X-Api-Key": "A_BAD_KEY"})
#     result: tuple[Response, int] = wrapper.app.view_functions["vulnerabilities"]()
#     assert result[1] == 401


# test /vulnerabilities and /vulnerabilities/:profile_id endpoints
def test_get_vulnerabilities(wrapper: AppWrapper, mock_store: Mock):
    example_profile_list = [{"id": EXAMPLE_UUID, "name": "My Profile"}]
    mock_store.return_value.get_all.return_value = example_profile_list

    result: tuple[Response, int] = wrapper.app.view_functions["vulnerabilities"]()

    response, status = result
    assert status == 200
    actual_profile_list = response.json
    assert len(actual_profile_list) == 1
    assert actual_profile_list[0]["id"] == EXAMPLE_UUID
    mock_store.return_value.get_all.assert_called_once()


def test_get_vulnerabilities_office(wrapper: AppWrapper, mock_store: Mock, mock_request: Mock):
    expected_office = "BOU"
    example_profile_list = [{"id": EXAMPLE_UUID, "name": "My Profile", "primaryOfficeId": "BOU"}]
    mock_store.return_value.get_all.return_value = example_profile_list
    mock_request.args = MultiDict({"officeId": expected_office})

    result: tuple[Response, int] = wrapper.app.view_functions["vulnerabilities"]()

    assert result[1] == 200
    mock_store.return_value.get_all.assert_called_once_with(
        include_inactive=False, office=expected_office
    )


def test_post_vulnerabilities(wrapper: AppWrapper, mock_store: Mock, mock_request: Mock):
    example_profile = {"id": EXAMPLE_UUID, "name": "My Profile", "hazards": []}
    mock_request.json = example_profile
    mock_request.method = "POST"
    mock_store.return_value.save.return_value = EXAMPLE_UUID  # save() success

    result: tuple[Response, int] = wrapper.app.view_functions["vulnerabilities"]()

    _, status = result
    assert status == 201
    # request body JSON should have been passed in full to store's save() method
    mock_store.return_value.save.assert_called_with(example_profile)


def test_get_vulnerability(wrapper: AppWrapper, mock_store: Mock, mock_request: Mock):
    expected_id = EXAMPLE_UUID
    mock_store.return_value.get.return_value = {"id": expected_id, "name": "My Vulnerability"}

    result: tuple[Response, int] = wrapper.app.view_functions["vulnerability"](expected_id)

    assert result[1] == 200


def test_delete_vulnerability(wrapper: AppWrapper, mock_store: Mock, mock_request: Mock):
    expected_id = EXAMPLE_UUID
    mock_request.method = "DELETE"
    mock_store.return_value.delete.return_value = True  # delete() succeeds

    result: tuple[Response, int] = wrapper.app.view_functions["vulnerability"](expected_id)

    _, status = result
    assert status == 204


def test_delete_vulnerability_missing(wrapper: AppWrapper, mock_store: Mock, mock_request: Mock):
    expected_id = EXAMPLE_UUID
    mock_request.method = "DELETE"
    mock_store.return_value.delete.return_value = False  # delete() fails

    result: tuple[Response, int] = wrapper.app.view_functions["vulnerability"](expected_id)

    _, status = result
    assert status == 404


def test_patch_vulnerability(wrapper: AppWrapper, mock_store: Mock, mock_request: Mock):
    expected_id = EXAMPLE_UUID
    expected_request_body = {"name": "A different name", "hazards": []}
    updated_profile = {**expected_request_body, "activeTime": {"startDate": "2026-01-01T12:00Z"}}
    mock_request.method = "PATCH"
    mock_request.json = expected_request_body
    # update() succeeds
    mock_store.return_value.update.return_value = updated_profile

    result: tuple[Response, int] = wrapper.app.view_functions["vulnerability"](expected_id)

    assert result[1] == 200
    assert result[0].json == updated_profile
    mock_store.return_value.update.assert_called_with(expected_id, expected_request_body)


def test_patch_vulnerability_not_found(wrapper: AppWrapper, mock_store: Mock, mock_request: Mock):
    expected_id = EXAMPLE_UUID
    mock_request.method = "PATCH"
    mock_request.json = {"name": "A different name", "hazards": []}
    mock_store.return_value.update.side_effect = FileNotFoundError  # profile_id doesn't exist

    result: tuple[Response, int] = wrapper.app.view_functions["vulnerability"](expected_id)

    assert result[1] == 404


def test_patch_vulnerability_fails(wrapper: AppWrapper, mock_store: Mock, mock_request: Mock):
    expected_id = EXAMPLE_UUID
    mock_request.method = "PATCH"
    mock_request.json = {"name": "A different name", "hazards": []}
    mock_store.return_value.update.return_value = None  # update() fails

    result: tuple[Response, int] = wrapper.app.view_functions["vulnerability"](expected_id)

    assert result[1] == 500
