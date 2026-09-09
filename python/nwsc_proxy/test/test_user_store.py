"""Tests for src/user_store.py"""

# ----------------------------------------------------------------------------------
# Created on Tue Aug 11 2026
#
# Copyright (c) 2026 Colorado State University. All rights reserved.             (1)
#
# Contributors:
#     Mackenzie Grimes (1)
#
# ----------------------------------------------------------------------------------
# pylint: disable=missing-function-docstring,redefined-outer-name,unused-argument,protected-access

from datetime import datetime, timedelta
from unittest.mock import Mock

from pytest import fixture, MonkeyPatch

from python.nwsc_proxy.src.user_store import UserSession, UserStore

# constants
EXAMPLE_SESSION_ID = "12345abcde"
EXAMPLE_DATETIME = datetime.now()


# fixtures
@fixture
def mock_datetime(monkeypatch: MonkeyPatch) -> Mock:
    mock_obj = Mock(name="MockDatetime")
    mock_obj.now.return_value = EXAMPLE_DATETIME
    monkeypatch.setattr("python.nwsc_proxy.src.user_store.datetime", mock_obj)
    return mock_obj


@fixture
def store(mock_datetime) -> UserStore:
    return UserStore()


# tests
def test_get_session_not_found(store: UserStore):
    expected_data = store._placeholder_data

    result = store.get_user(EXAMPLE_SESSION_ID)

    # remove dynamically created things, evaluate just placeholder
    result["userId"] = expected_data["userId"]
    result["nwsChatAccountId"] = expected_data["nwsChatAccountId"]
    result["createdTime"] = expected_data["createdTime"]
    assert result == expected_data


def test_get_session(store: UserStore, mock_datetime: Mock):
    now_plus_ten_minutes = mock_datetime.now.return_value + timedelta(minutes=10)
    expected_data = {**store._placeholder_data, "activeOfficeId": "BOU"}
    store._sessions[EXAMPLE_SESSION_ID] = UserSession(
        expected_data, expires_at=now_plus_ten_minutes.timestamp()
    )

    result = store.get_user(EXAMPLE_SESSION_ID)

    assert result == expected_data


def test_get_session_expired(store: UserStore, mock_datetime: Mock):
    # session exists but expired 10 minutes ago
    ten_minutes_ago = mock_datetime.now.return_value - timedelta(minutes=10)
    expired_data = {**store._placeholder_data, "activeOfficeId": "BOU"}
    store._sessions[EXAMPLE_SESSION_ID] = UserSession(
        expired_data, expires_at=ten_minutes_ago.timestamp()
    )

    result = store.get_user(EXAMPLE_SESSION_ID)

    assert result["activeOfficeId"] != expired_data["activeOfficeId"]


def test_delete_expired_sessions(store: UserStore, mock_datetime: Mock):
    expired_dt = mock_datetime.now.return_value - timedelta(minutes=10)
    unexpired_dt = mock_datetime.now.return_value + timedelta(minutes=10)
    store._sessions["expiredSession"] = UserSession(
        store._placeholder_data, expires_at=expired_dt.timestamp()
    )
    store._sessions["goodSession"] = UserSession(store._placeholder_data, unexpired_dt.timestamp())

    _ = store.get_user("doesNotMatter")

    # expiredSession was cleared out when someone queried for any session
    assert "expiredSession" not in store._sessions
    assert "goodSession" in store._sessions


def test_update_session(store: UserStore, mock_datetime: Mock):
    unexpired_dt = mock_datetime.now.return_value + timedelta(minutes=10)
    store._sessions[EXAMPLE_SESSION_ID] = UserSession(
        store._placeholder_data, expires_at=unexpired_dt.timestamp()
    )
    expected_office = "BOU"
    expected_theme = "DARK"
    settings = {"theme": expected_theme}

    result = store.update_user_settings(EXAMPLE_SESSION_ID, expected_office, settings)

    assert result["activeOfficeId"] == expected_office
    assert result["settings"]["theme"] == expected_theme
    # pre-existing settings not overwritten
    assert (
        result["settings"]["is24HourTime"] == store._placeholder_data["settings"]["is24HourTime"]
    )
