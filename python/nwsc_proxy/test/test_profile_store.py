"""Tests for src/profile_store.py"""

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
from unittest.mock import Mock

from pytest import fixture, raises

from python.nwsc_proxy.src.profile_store import ProfileStore, NEW_SUBDIR, EXISTING_SUBDIR, dt_parse

# constants
STORE_BASE_DIR = os.path.join(os.path.dirname(__file__), "temp")
RAW_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "profiles")

EXAMPLE_UUID = "9835b194-74de-4321-aa6b-d769972dc7cb"

with open(os.path.join(RAW_JSON_PATH, "nwsc_test_response_1.json"), "r", encoding="utf-8") as f:
    EXAMPLE_SUPPORT_PROFILE: dict = json.load(f)["profiles"][0]


def _empty_directory(dir_path: str):
    for filename in os.listdir(dir_path):
        filepath = os.path.join(dir_path, filename)
        if os.path.isdir(filepath):
            if len(os.listdir(filepath)) > 0:
                _empty_directory(filepath)  # recursively delete child directories
            os.rmdir(filepath)
        else:
            os.remove(filepath)


# fixtures
def startup():
    """Runs before each test is executed. Create test resource file structure"""
    os.makedirs(STORE_BASE_DIR, exist_ok=True)
    _empty_directory(STORE_BASE_DIR)  # delete any existing files/directories

    # copy all JSON files from ../src/profiles/ to the ProfileStore's base dir
    for response_file in glob("*.json", root_dir=RAW_JSON_PATH):
        shutil.copy(os.path.join(RAW_JSON_PATH, response_file), STORE_BASE_DIR)


def teardown():
    """Clean up any files/directories created during test"""
    _empty_directory(STORE_BASE_DIR)
    os.rmdir(STORE_BASE_DIR)


@fixture(autouse=True)
def startup_and_teardown():
    startup()
    yield  # run test
    teardown()


@fixture
def store():
    return ProfileStore(STORE_BASE_DIR)


# tests
def test_profile_store_loads_api_responses(store: ProfileStore):
    assert sorted([c.id for c in store.profile_cache]) == [
        "a08370c6-ab87-4808-bd51-a8597e58410d",
        "e1033860-f198-4c6a-a91b-beaec905132f",
        "fd35adec-d2a0-49a9-a320-df20a7b6d681",
    ]

    for cache_obj in store.profile_cache:
        # should have loaded all profiles as status "existing", file should exist in that subdir
        assert not cache_obj.is_new
        filepath = os.path.join(STORE_BASE_DIR, EXISTING_SUBDIR, f"{cache_obj.id}.json")
        assert os.path.exists(filepath)

    # new directory should be empty to begin with
    assert os.listdir(os.path.join(STORE_BASE_DIR, NEW_SUBDIR)) == []


def test_store_loads_jsons_from_new(store: ProfileStore):
    # create a pre-existing "new" profile as well as the 3 "existing" profiles
    profile = deepcopy(store.get_all()[0])
    profile["id"] = EXAMPLE_UUID  # give copied profile a unique identifier
    store.save(profile)

    # simulate starting ProfileStore process fresh, with existing JSONs on filesystem
    new_store = ProfileStore(STORE_BASE_DIR)

    # newly created ProfileStore should have correctly loaded and labeled "new" Profile
    new_profile_list = new_store.get_all(is_new=True)
    assert len(new_profile_list) == 1
    assert len(new_store.profile_cache) == 4  # 3 existing, 1 new


def test_get_all_profiles(store: ProfileStore):
    result = store.get_all()
    assert len(result) == 3

    result = store.get_all(is_new=True)
    assert len(result) == 0


def test_save_adds_to_new_profiles(store: ProfileStore):
    new_profile = deepcopy(EXAMPLE_SUPPORT_PROFILE)
    new_profile["id"] = EXAMPLE_UUID

    new_profile_id = store.save(new_profile)

    assert new_profile_id == EXAMPLE_UUID
    # profile should now be returned by get() request for new profiles
    new_profile_list = store.get_all(is_new=True)
    assert [p.get("id") for p in new_profile_list] == [EXAMPLE_UUID]

    # profile should not be returned by get() request for existing profiles
    existing_profile_list = store.get_all()
    assert EXAMPLE_UUID not in [p.get("id") for p in existing_profile_list]

    # file should exist in the "new" subdirectory
    assert os.path.exists(os.path.join(STORE_BASE_DIR, NEW_SUBDIR, f"{new_profile_id}.json"))


def test_save_rejects_existing_profile(store: ProfileStore):
    new_profile = deepcopy(EXAMPLE_SUPPORT_PROFILE)  # use Support Profile that already exists

    new_profile_id = store.save(new_profile)

    assert not new_profile_id
    # no new profile should have been added
    new_profile_list = store.get_all(is_new=True)
    assert new_profile_list == []
    # file should not exist in the "new" subdirectory
    assert not os.path.exists(
        os.path.join(STORE_BASE_DIR, NEW_SUBDIR, f'{new_profile["id"]}.json')
    )


def test_move_to_existing_success(store: ProfileStore):
    new_profile = deepcopy(EXAMPLE_SUPPORT_PROFILE)
    new_profile["id"] = EXAMPLE_UUID
    store.save(new_profile)

    new_profiles = store.get_all(is_new=True)
    assert [p["id"] for p in new_profiles] == [EXAMPLE_UUID]

    store.mark_as_existing(EXAMPLE_UUID)

    new_profiles = store.get_all(is_new=True)
    assert new_profiles == []  # Support Profile has vanished from list of new
    existing_profiles = store.get_all()
    assert EXAMPLE_UUID in [p["id"] for p in existing_profiles]  # now Profile is in existing list


def test_delete_profile(store: ProfileStore):
    existing_profile_list = store.get_all()
    profile_id = existing_profile_list[0]["id"]

    success = store.delete(profile_id)

    # after delete, profile should not be returned to get() request, and JSON file should be gone
    assert success
    existing_profile_list = store.get_all()
    assert profile_id not in [p["id"] for p in existing_profile_list]
    assert not os.path.exists(os.path.join(STORE_BASE_DIR, EXISTING_SUBDIR, f"{profile_id}.json"))


def test_delete_profile_failure(store: ProfileStore):
    profile_id = "11111111-2222-3333-444444444444"  # fake ID does not exist in ProfileStore

    success = store.delete(profile_id)
    assert not success


def test_update_profile_success(store: ProfileStore):
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
    refetched_profile = next((p for p in store.profile_cache if p.id == profile_id), None)
    assert refetched_profile.name == new_name
    assert datetime.fromtimestamp(refetched_profile.start_timestamp, UTC) == dt_parse(new_start_dt)


def test_update_profile_error_rollback(store: ProfileStore):
    profile_id = EXAMPLE_SUPPORT_PROFILE["id"]
    new_name = "A different name"
    new_profile = deepcopy(EXAMPLE_SUPPORT_PROFILE)
    new_profile["name"] = new_name
    # HACK: mocks out the class under test (BAD)
    store.delete = Mock(name="mock_delete")  # test fails if we really delete existing Profile
    store.save = Mock(name="mock_save", side_effect=[None, profile_id])  # fails first save

    updated_profile = store.update(profile_id, new_profile)

    assert updated_profile is None
    # profile in cache is still there, no changes were made to data
    refetched_profile = next((p for p in store.profile_cache if p.id == profile_id), None)
    assert refetched_profile.name == EXAMPLE_SUPPORT_PROFILE["name"]


def test_update_profile_not_found(store: ProfileStore):
    profile_id = "11111111-2222-3333-444444444444"  # fake ID does not exist in ProfileStore
    new_profile_data = {"name": "A different name"}

    with raises(FileNotFoundError) as exc:
        _ = store.update(profile_id, new_profile_data)

    assert exc is not None
