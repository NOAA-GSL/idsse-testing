"""Tests for src/support_profile_store.py"""

# ----------------------------------------------------------------------------------
# Created on Wed Dec 18 2024
#
# Copyright (c) 2024 Colorado State University. All rights reserved.             (1)
#
# Contributors:
#     Mackenzie Grimes (1)
#
# ----------------------------------------------------------------------------------
# pylint: disable=missing-function-docstring,redefined-outer-name
import json
import os
import shutil
from copy import deepcopy
from datetime import datetime, UTC
from glob import glob

from pytest import fixture, raises

from python.nwsc_proxy.src.support_profile_store import SupportProfileStore, PROFILE_DIR, dt_parse

# constants
RAW_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "profiles")
EXAMPLE_UUID = "9835b194-74de-4321-aa6b-d769972dc7cb"

with open(os.path.join(RAW_JSON_PATH, "nwsc_test_response_1.json"), "r", encoding="utf-8") as file:
    EXAMPLE_SUPPORT_PROFILE: dict = json.load(file)["profiles"][0]


# fixtures
@fixture
def base_dir(tmpdir_factory) -> str:
    return tmpdir_factory.mktemp("temp")


@fixture(autouse=True)
def startup(base_dir: str):
    """Runs before each test is executed. Create test resource file structure"""
    # copy all JSON files from ../src/profiles/ to the ProfileStore's base dir
    for response_file in glob("*.json", root_dir=RAW_JSON_PATH):
        shutil.copy(os.path.join(RAW_JSON_PATH, response_file), base_dir)

    yield  # run test


@fixture
def store(base_dir: str):
    return SupportProfileStore(base_dir)


# tests
def test_profile_store_loads_api_responses(store: SupportProfileStore, base_dir: str):
    assert sorted(list(store.profile_cache.keys())) == [
        "a08370c6-ab87-4808-bd51-a8597e58410d",
        "e1033860-f198-4c6a-a91b-beaec905132f",
        "fd35adec-d2a0-49a9-a320-df20a7b6d681",
    ]

    for cache_id in store.profile_cache:
        # should have loaded all profiles, file should exist in known profile subdir
        filepath = os.path.join(base_dir, PROFILE_DIR, f"{cache_id}.json")
        assert os.path.exists(filepath)


def test_get_all_profiles(store: SupportProfileStore):
    result = store.get_all()
    assert len(result) == 3


def test_save_adds_to_profiles(store: SupportProfileStore, base_dir: str):
    new_profile = deepcopy(EXAMPLE_SUPPORT_PROFILE)
    new_profile["id"] = EXAMPLE_UUID

    new_profile_id = store.save(new_profile)

    assert new_profile_id == EXAMPLE_UUID
    # profile should now be returned by get() request
    new_profile_list = store.get_all()
    assert EXAMPLE_UUID in [p.get("id") for p in new_profile_list]
    # file should exist in profile subdirectory
    assert os.path.exists(os.path.join(base_dir, PROFILE_DIR, f"{new_profile_id}.json"))


def test_save_rejects_existing_profile(store: SupportProfileStore):
    new_profile = deepcopy(EXAMPLE_SUPPORT_PROFILE)  # use Support Profile that already exists
    expected_ids = sorted(p["id"] for p in store.get_all())

    new_profile_id = store.save(new_profile)

    assert not new_profile_id
    # no new profile should have been added
    new_profile_list = store.get_all()
    assert sorted([p["id"] for p in new_profile_list]) == expected_ids


def test_delete_profile(store: SupportProfileStore, base_dir: str):
    existing_profile_list = store.get_all()
    profile_id = existing_profile_list[0]["id"]

    success = store.delete(profile_id)

    # after delete, profile should not be returned to get() request, and JSON file should be gone
    assert success
    existing_profile_list = store.get_all()
    assert profile_id not in [p["id"] for p in existing_profile_list]
    assert not os.path.exists(os.path.join(base_dir, PROFILE_DIR, f"{profile_id}.json"))


def test_delete_profile_failure(store: SupportProfileStore):
    profile_id = "11111111-2222-3333-444444444444"  # fake ID does not exist in ProfileStore

    success = store.delete(profile_id)
    assert not success


def test_update_profile_success(store: SupportProfileStore):
    profile_id = EXAMPLE_SUPPORT_PROFILE["id"]
    new_start_dt = "2026-01-01T12:00:00Z"
    new_name = "A different name"
    new_profile = deepcopy(EXAMPLE_SUPPORT_PROFILE)
    new_profile["name"] = new_name
    new_profile["setting"] = {"timing": {"start": new_start_dt}}

    updated_profile = store.update(profile_id, new_profile)

    # data returned should have updated attributes
    assert updated_profile["name"] == new_name
    assert updated_profile["setting"]["timing"]["start"] == new_start_dt
    # profile in cache should have indeed been changed
    refetched_profile = store.profile_cache.get(profile_id)
    assert refetched_profile.name == new_name
    assert datetime.fromtimestamp(refetched_profile.start_timestamp, UTC) == dt_parse(new_start_dt)


def test_update_profile_error_rollback(store: SupportProfileStore):
    profile_id = EXAMPLE_SUPPORT_PROFILE["id"]
    new_name = "A different name"
    new_profile = deepcopy(EXAMPLE_SUPPORT_PROFILE)
    new_profile["name"] = new_name
    # inject unhashable content into JSON data, will cause save() to fail and return None
    new_profile["unhashable"] = set(["foo", "bar"])

    updated_profile = store.update(profile_id, new_profile)

    assert updated_profile is None
    # profile in cache is still there, no changes were made to data
    refetched_profile = store.profile_cache.get(profile_id)
    assert refetched_profile.name != new_name


def test_update_profile_not_found(store: SupportProfileStore):
    profile_id = "11111111-2222-3333-444444444444"  # fake ID does not exist in ProfileStore
    new_profile_data = {"name": "A different name"}

    with raises(FileNotFoundError) as exc:
        _ = store.update(profile_id, new_profile_data)

    assert exc is not None
