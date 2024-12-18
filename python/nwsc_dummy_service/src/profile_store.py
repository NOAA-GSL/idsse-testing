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
from glob import glob

# constants controlling the subdirectory where new vs. existing Profiles are saved
NEW_SUBDIR = 'new'
EXISTING_SUBDIR = 'existing'

logger = logging.getLogger(__name__)



@dataclass
class CachedProfile:
    """Data class to hold Support Profile's data and metadata ("new" vs "existing" status)

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
        return self.data.get('id')


class ProfileStore:
    """Data storage using JSON files on filesystem that simulates CRUD operations"""
    def __init__(self, base_dir: str):
        self._base_dir = base_dir
        self._new_dir = os.path.join(self._base_dir, NEW_SUBDIR)
        self._existing_dir = os.path.join(self._base_dir, EXISTING_SUBDIR)

        # ensure that base directory and all expected subdirectories exist
        for _dir in [self._base_dir, self._new_dir, self._existing_dir]:
            os.makedirs(_dir, exist_ok=True)

        # load any NWS Connect response files dumped into the base_dir
        for response_filename in glob('*.json', root_dir=self._base_dir):
            response_filepath = os.path.join(self._base_dir, response_filename)
            logger.warning('Loading profiles from raw API response file: %s', response_filepath)

            with open(response_filepath, 'r', encoding='utf-8') as infile:
                data: dict = json.load(infile)

                # loop through all profiles in this file,
                # save them to "existing" directory as individual profiles
                for profile in data.get('profiles', []):
                    profile_filepath = os.path.join(self._existing_dir, f'{profile["id"]}.json')
                    logger.info('Saving existing profile to file: %s', profile_filepath)

                    with open(profile_filepath, 'w', encoding='utf-8') as outfile:
                        json.dump(profile, outfile)

        # populate cache of JSON data of all Support Profiles, marked as new vs. existing
        existing_profiles = [CachedProfile(profile, is_new=False)
                             for profile in self._load_profiles_from_filesystem(self._existing_dir)]
        new_profiles = [CachedProfile(profile, is_new=True)
                        for profile in self._load_profiles_from_filesystem(self._new_dir)]

        self.profile_cache = existing_profiles + new_profiles

    def get_all(self, filter_new_profiles = False) -> list[dict]:
        """Get all Support Profile JSONs persisted in this API, filtering by status='new'
        (if Support Profile has never been returned in an API request before) or status='existing'
        otherwise.

        Args:
            filter_new_profiles (bool): if True, get only Support Profiles that have never been
                returned to IDSS Engine on previous requests (never processed). Default is False:
                return all existing profiles.
        """
        return [cached_profile.data for cached_profile in self.profile_cache
                if cached_profile.is_new == filter_new_profiles]

    def save(self, profile: dict) -> str | None:
        """Persist a new Support Profile Profile to this API

        Returns:
            str | None: UUID of saved Support Profile on success, otherwise None
        """
        logger.debug('Now saving new profile: %s', profile)

        # if profile ID is already in the cache, reject this save
        existing_profile = next(((cached_obj for cached_obj in self.profile_cache
                                if cached_obj.id == profile.get('id'))), None)
        if existing_profile:
            logger.warning('Cannot save profile; already exists %s', existing_profile.id)
            return None

        cached_profile = CachedProfile(profile, is_new=True)

        # save Profile JSON to filesystem
        filepath = os.path.join(self._new_dir, f'{cached_profile.id}.json')
        logger.info('Now saving profile to path: %s', filepath)
        with open(filepath, 'w', encoding='utf-8') as file:
            json.dump(profile, file)

        # add profile to in-memory cache
        self.profile_cache.append(cached_profile)
        return cached_profile.id

    def move_to_existing(self, profile_id: str) -> bool:
        """Mark a formerly "new" Support Profile as "existing", a.k.a. has been returned in
        API response at least once and should no longer be processed as "new"

        Returns:
            bool: True on success. False if JSON with this profile_id not found on filesystem
        """
        # find the profile data from the new_profiles cache and move it to existing_profiles
        cached_profile = next((profile for profile in self.profile_cache
                               if profile.id == profile_id), None)
        if not cached_profile:
            # profile is not in cache; it must not exist
            logger.warning('Support Profile %s expected in profile_cache but not found',
                           profile_id)
            return False

        new_filepath = os.path.join(self._new_dir, f'{profile_id}.json')
        if not os.path.exists(new_filepath):
            logger.warning('Attempt to mark as "existing" profile that is not found: %s',
                           new_filepath)
            return False

        # move the JSON file from the "new" to the "existing" directory and update cache
        existing_filepath = os.path.join(self._existing_dir, f'{profile_id}.json')
        os.rename(new_filepath, existing_filepath)

        # update this profile's is_new flag in in-memory cache
        profile_index = self.profile_cache.index(cached_profile)
        self.profile_cache[profile_index].is_new = False

        return True

    def delete(self, profile_id: str) -> bool:
        """Delete a Support Profile profile from storage, based on its UUID.

        Returns:
            bool: True on success
        """
        logger.info('Deleting profile_id %s', profile_id)

        filepath = os.path.join(self._existing_dir, f'{profile_id}.json')
        if not os.path.exists(filepath):
            # profile does not in exist in "existing" subdirectory, maybe its in "new"
            filepath = os.path.join(self._new_dir, f'{profile_id}.json')

            if not os.path.exists(filepath):
                logger.warning('Cannot delete profile %s; JSON file not found in %s or %s',
                               profile_id, self._existing_dir, self._new_dir)
                return False

        logger.debug('Attempting to delete profile at path: %s', filepath)
        os.remove(filepath)

        # drop profile from cache
        self.profile_cache = [cached_profile for cached_profile in self.profile_cache
                              if cached_profile.id != profile_id]
        return True

    def _load_profiles_from_filesystem(self, dir_: str) -> list[dict]:
        """Read all JSON files from one of this ProfileStore's subdirectories, and return list of
        the discovered files' json data.

        Args:
            dir_ (str): path to scan for Support Profile or NWS Connect API response JSON files
        """
        logger.info('Loading Support Profiles JSON files from path: %s', dir_)

        profile_list: list[dict] = []
        for filename in glob('*.json', root_dir=dir_):
            with open(os.path.join(dir_, filename), 'r', encoding='utf-8') as file:
                json_data: dict = json.load(file)
                # if this is a pure NWS Connect response, profile data is nested inside `profiles`
                if profiles := json_data.get('profiles', None) and isinstance(profiles, list):
                    profile_list.extend(profiles)
                else:
                    # this file is assumed to be just a Support Profile
                    profile_list.append(json_data)

        return profile_list
