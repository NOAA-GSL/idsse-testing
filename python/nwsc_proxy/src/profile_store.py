"""Profile store that does CRUD operations on filesystem to simulate NWS Connect storage"""

# ----------------------------------------------------------------------------------
# Created on Tues Dec 17 2024
#
# Copyright (c) 2024 Colorado State University. All rights reserved.             (1)
#
# Contributors:
#     Mackenzie Grimes (1)
#
# ----------------------------------------------------------------------------------
import os
import json
import logging
from dataclasses import dataclass
from datetime import datetime, UTC
from glob import glob
from math import inf

from dateutil.parser import parse as dt_parse

from src.utils import deep_update

# constants controlling the subdirectory where new vs. existing Profiles are saved
NEW_SUBDIR = "new"
EXISTING_SUBDIR = "existing"
DEFAULT_DATA_SOURCE = "NBM"

logger = logging.getLogger(__name__)


@dataclass
class CachedProfile:
    """Data class to hold Support Profile's data and metadata ("new" vs "existing" status),
    as well as some derived properties extracted from the `data` JSON (e.g.
    `CachedProfile.is_active` or `CachedProfile.start_timestamp`) that make it easier to query
    and filter the Profiles.

    Args:
        data (dict): full JSON data of this Support Profile
        is_new (bool): track if Support Profile has ever been processed. Ought to start as True
    """

    # pylint: disable=invalid-name
    data: dict
    is_new: bool

    @property
    def id(self) -> str:
        """The Support Profile UUID"""
        return self.data.get("id")

    @property
    def name(self) -> str:
        """The Support Profile name"""
        return self.data.get("name")

    @property
    def is_active(self) -> bool:
        """The Support Profile's active state (can be marked as inactive to halt processing)"""
        return self.data.get("isLive")

    @property
    def start_timestamp(self) -> float:
        """The Support Profile event's start in Unix time (milliseconds since the epoch).
        math.inf if Support Profile is never-ending
        """
        profile_start: str | None = self.data["setting"]["timing"].get("start")
        return dt_parse(profile_start).timestamp() if profile_start else inf

    @property
    def end_timestamp(self) -> float:
        """The Support Profile event's end in Unix time (milliseconds since the epoch).
        math.inf if Support Profile is never-ending
        """
        if self.start_timestamp == inf:
            return inf  # infinite start time, so infinite end time as well
        timing: dict[str, int] = self.data["setting"]["timing"]
        # look up durationInMinutes, or deprecated duration, or None
        profile_duration = timing.get("durationInMinutes", timing.get("duration", inf))
        return self.start_timestamp + profile_duration * 60 * 1000  # convert mins to ms

    @property
    def data_sources(self) -> list[str]:
        """The weather products used by any parts of this Support Profile (e.g. NBM, HRRR, MRMS)"""
        try:
            return [
                # treat any profiles with empty string dataSource as default 'NBM'
                _map["dataSource"] if _map["dataSource"] != "" else DEFAULT_DATA_SOURCE
                for phrase in self.data["nonImpactThresholds"]["phrasesForAllSeverities"].values()
                for _map in phrase["map"].values()
            ]
        except KeyError:
            return [DEFAULT_DATA_SOURCE]  # couldn't lookup dataSources, so just default to NBM

    def __str__(self):
        return (
            f"{self.__class__.__name__}(id='{self.id}', name='{self.name}', is_new={self.is_new}, "
            f"is_active={self.is_active}, start_timestamp={self.start_timestamp}, "
            f"end_timestamp={self.end_timestamp}, data_sources={self.data_sources})"
        )


class ProfileStore:
    """Data storage using JSON files on filesystem that simulates CRUD operations"""

    def __init__(self, base_dir: str):
        self._new_dir = os.path.join(base_dir, NEW_SUBDIR)
        self._existing_dir = os.path.join(base_dir, EXISTING_SUBDIR)

        # ensure that base directory and all expected subdirectories exist
        for _dir in [self._new_dir, self._existing_dir]:
            os.makedirs(_dir, exist_ok=True)

        # load any NWS Connect response files dumped into the base_dir
        logger.info("Scanning base directory for raw NWS Connect API response files: %s", base_dir)
        for response_filename in glob("*.json", root_dir=base_dir):
            response_filepath = os.path.join(base_dir, response_filename)
            logger.warning("Loading profiles from raw API response file: %s", response_filepath)

            with open(response_filepath, "r", encoding="utf-8") as infile:
                data: dict = json.load(infile)

                # loop through all profiles in this file,
                # save them to "existing" directory as individual profiles
                for profile in data.get("profiles", []):
                    profile_filepath = os.path.join(self._existing_dir, f'{profile["id"]}.json')
                    logger.info("Saving existing profile to file: %s", profile_filepath)

                    with open(profile_filepath, "w", encoding="utf-8") as outfile:
                        json.dump(profile, outfile)

        # populate cache of JSON data of all Support Profiles, marked as new vs. existing
        existing_profiles = [
            CachedProfile(profile, is_new=False)
            for profile in self._load_profiles_from_filesystem(self._existing_dir)
        ]
        new_profiles = [
            CachedProfile(profile, is_new=True)
            for profile in self._load_profiles_from_filesystem(self._new_dir)
        ]

        self.profile_cache = existing_profiles + new_profiles

    def get_all(self, data_source="ANY", is_new=False, include_inactive=False) -> list[dict]:
        """Get all Support Profile JSONs persisted in this API, filtering by status='new'
        (if Support Profile has never been returned in an API request before) or status='existing'
        otherwise.

        Args:
            is_new (bool): if True, get only Support Profiles that have never been
                returned to IDSS Engine on previous requests (never processed). Default is False:
                return all existing profiles.
        """
        profiles_by_status = [
            cached_profile
            for cached_profile in self.profile_cache
            if (
                # is new, if client requested new profiles, or is existing
                cached_profile.is_new == is_new
                # is "active", meaning no one has intentional disabled/deactivated it
                and (include_inactive or cached_profile.is_active)
                # the end_dt has not yet passed (or profile is never-ending)
                and datetime.now(UTC).timestamp() <= cached_profile.end_timestamp
            )
        ]
        if data_source == "ANY":
            # all data sources requested, so do not filter by products used
            return [profile.data for profile in profiles_by_status]
        return [
            profile.data for profile in profiles_by_status if data_source in profile.data_sources
        ]

    def save(self, profile: dict, is_new=True) -> str | None:
        """Persist a new Support Profile Profile to this API

        Args:
            profile (dict): the JSON data of the Support Profile to store.
            is_new (optional, bool): whether to store the Profile as "new" or "existing". This
                will only control whether this SupportProfile will be returned to calls to the
                `get_all()` method (if it is classified as new vs. existing). Defaults to True.

        Returns:
            str | None: UUID of saved Support Profile on success, otherwise None
        """
        logger.debug("Now saving new profile: %s", profile)

        # if profile ID is already in the cache, reject this save
        existing_profile = next(
            (
                (
                    cached_obj
                    for cached_obj in self.profile_cache
                    if cached_obj.id == profile.get("id")
                )
            ),
            None,
        )
        if existing_profile:
            logger.warning("Cannot save profile; already exists %s", existing_profile.id)
            return None

        cached_profile = CachedProfile(profile, is_new=is_new)

        # save Profile JSON to filesystem
        file_dir = self._new_dir if is_new else self._existing_dir
        filepath = os.path.join(file_dir, f"{cached_profile.id}.json")
        logger.debug("Now saving profile to path: %s", filepath)
        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(profile, file)

        # add profile to in-memory cache
        self.profile_cache.append(cached_profile)
        logger.info("Saved profile to cache, file location: %s", filepath)
        return cached_profile.id

    def mark_as_existing(self, profile_id: str) -> bool:
        """Mark a formerly "new" Support Profile as "existing", a.k.a. has been returned in
        API response at least once and should no longer be processed as "new"

        Returns:
            bool: True on success. False if JSON with this profile_id not found on filesystem
        """
        # find the profile data from the new_profiles cache and move it to existing_profiles
        cached_profile = next(
            (profile for profile in self.profile_cache if profile.id == profile_id), None
        )
        if not cached_profile:
            # profile is not in cache; it must not exist
            logger.warning(
                "Support Profile %s expected in profile_cache but not found", profile_id
            )
            return False

        new_filepath = os.path.join(self._new_dir, f"{profile_id}.json")
        if not os.path.exists(new_filepath):
            logger.warning(
                'Attempt to mark as "existing" profile that is not found: %s', new_filepath
            )
            return False

        # move the JSON file from the "new" to the "existing" directory and update cache
        existing_filepath = os.path.join(self._existing_dir, f"{profile_id}.json")
        os.rename(new_filepath, existing_filepath)
        cached_profile.is_new = False

        return True

    def update(self, profile_id: str, data: dict) -> dict:
        """Update a Support Profile in storage based on its id.

        Args:
            profile_id (str): The UUID of the Support Profile to update
            data (dict): The JSON attributes to apply. Can be partial Support Profile

        Returns:
            dict: the latest version of the Profile, with all attribute changes applied

        Raises:
            FileNotFoundError: if no Support Profile exists with the provided id
        """
        logger.info("Updating profile_id %s with new attributes: %s", profile_id, data)

        # find the profile data from the new_profiles cache, then apply updates and save over it
        cached_profile = next(
            (profile for profile in self.profile_cache if profile.id == profile_id), None
        )
        if not cached_profile:
            raise FileNotFoundError  # Profile with this ID does not exist in cache

        # Apply dict of edits on top of existing cached profile (combining any nested attributes)
        new_profile_data = deep_update(cached_profile.data, data)
        is_new_profile = cached_profile.is_new

        # a bit hacky, but the fastest and least duplicative way to update a Profile
        # in cache + disk is to delete the existing profile and re-save with modified JSON data
        self.delete(profile_id)
        update_success = self.save(new_profile_data, is_new_profile)

        if not update_success:
            logger.warning("Unable to update Profile ID %s for some reason", profile_id)
            return None

        return new_profile_data

    def delete(self, profile_id: str) -> bool:
        """Delete a Support Profile profile from storage, based on its UUID.

        Returns:
            bool: True on success
        """
        logger.info("Deleting profile_id %s", profile_id)

        filepath = os.path.join(self._existing_dir, f"{profile_id}.json")
        if not os.path.exists(filepath):
            # profile does not in exist in "existing" subdirectory, maybe its in "new"
            filepath = os.path.join(self._new_dir, f"{profile_id}.json")

            if not os.path.exists(filepath):
                logger.warning(
                    "Cannot delete profile %s; JSON file not found in %s or %s",
                    profile_id,
                    self._existing_dir,
                    self._new_dir,
                )
                return False

        logger.debug("Attempting to delete profile at path: %s", filepath)
        os.remove(filepath)

        # drop profile from cache
        self.profile_cache = [
            cached_profile
            for cached_profile in self.profile_cache
            if cached_profile.id != profile_id
        ]
        return True

    def _load_profiles_from_filesystem(self, dir_: str) -> list[dict]:
        """Read all JSON files from one of this ProfileStore's subdirectories, and return list of
        the discovered files' json data.

        Args:
            dir_ (str): path to scan for Support Profile or NWS Connect API response JSON files
        """
        logger.info("Loading Support Profiles JSON files from path: %s", dir_)

        profile_list: list[dict] = []
        for filename in glob("*.json", root_dir=dir_):
            with open(os.path.join(dir_, filename), "r", encoding="utf-8") as file:
                json_data: dict = json.load(file)
                # if this is a pure NWS Connect response, profile data is nested inside `profiles`
                if profiles := json_data.get("profiles", None) and isinstance(profiles, list):
                    profile_list.extend(profiles)
                else:
                    # this file is assumed to be just a Support Profile
                    profile_list.append(json_data)

        return profile_list
