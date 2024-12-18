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
from glob import glob

# constants controlling the subdirectory where new vs. existing Profiles are saved
NEW_SUBDIR = 'new'
EXISTING_SUBDIR = 'existing'

logger = logging.getLogger(__name__)


class ProfileStore:
    """Data storage using JSON files on filesystem that simulates CRUD operations"""
    def __init__(self, base_dir: str):
        self._base_dir = base_dir
        self._new_dir = os.path.join(self._base_dir, NEW_SUBDIR)
        self._existing_dir = os.path.join(self._base_dir, EXISTING_SUBDIR)

        # ensure that base directory and all expected subdirectories exist
        for _dir in [self._base_dir, self._new_dir, self._existing_dir]:
            if not os.path.exists(_dir):
                os.mkdir(_dir)

        # cache of JSON data of all Support Profiles, divided into new vs. existing Profiles
        self.new_profiles = []
        self.existing_profiles = []

        logger.info('Loading existing Support Profiles from path: %s', self._existing_dir)
        self.existing_profiles = self._read_existing_profiles()

    def get_all(self, filter_new_profiles = False) -> list[dict]:
        """Get all Support Profile JSONs persisted in this API, filtering by status='new'
        (if Support Profile has never been returned in an API request before) or status='existing'
        otherwise.

        Args:
            filter_new_profiles (bool): if True, get only Support Profiles that have never been
                returned to IDSS Engine on previous requests (never processed). Default is False
                (return all existing profiles).
        """
        if filter_new_profiles:
            return self.new_profiles
        return self.existing_profiles

    def save(self, profile: dict) -> str | None:
        """Persist a new Support Profile Profile to this API

        Returns:
            str | None: UUID of saved Support Profile on success, otherwise None
        """
        logger.debug('Now saving new profile: %s', profile)
        # save to JSON file and add to in-memory cache
        return self._save_profile(profile, is_new=True)

    def move_to_existing(self, profile_id: str) -> bool:
        """Mark a formerly "new" Support Profile as "existing", a.k.a. has been returned in
        API response at least once and should no longer be processed as "new"

        Returns:
            bool: True on success. False if JSON with this profile_id not found on filesystem
        """
        new_filepath = os.path.join(self._new_dir, profile_id + '.json')

        if not os.path.exists(new_filepath):
            # TODO: why is this thrown when requesting /profiles?status=new ?
            logger.warning('Attempt to mark as "existing" profile that is not found: %s',
                           new_filepath)
            return False

        # move the JSON file from the "new" to the "existing" directory and update cache
        existing_filepath = os.path.join(self._existing_dir, profile_id + '.json')
        os.rename(new_filepath, existing_filepath)

        # find the profile data from the new_profiles cache and move it to existing_profiles
        profile_data = next((profile for profile in self.new_profiles
                             if profile['id'] == profile_id), None)
        if not profile_data:
            logger.warning('Support Profile %s expected in new_profiles cache but not found',
                           profile_id)

            # unexpectedly, profile is not in new_profiles cache;
            # recover from this by re-reading the JSON from file, because file did exist
            profile_data = self._read_existing_profile(profile_id)

        # add Profile/Profile to existing_profiles cache, and scrub from new_profiles cache
        self.existing_profiles.append(profile_data)
        self.new_profiles = [profile for profile in self.existing_profiles
                             if profile['id'] != profile_id]

        return True

    def delete(self, profile_id: str) -> bool:
        """Delete a Support Profile profile from storage, based on its UUID.

        Returns:
            bool: True on success
        """
        logger.debug('Attempting to delete profile_id %s', profile_id)
        is_deleted = self._delete_profile(profile_id)
        if not is_deleted:
            return False

        # drop profile from new or existing cache (could be in either)
        self.new_profiles = [profile for profile in self.new_profiles
                             if profile['id'] != profile_id]
        self.existing_profiles = [profile for profile in self.existing_profiles
                                  if profile['id'] != profile_id]

        return True

    # private methods that do the actual disk read/write operations
    def _save_profile(self, profile: dict, is_new: bool) -> str:
        """Writes profile JSON to disk and adds the JSON to appropriate in-memory cache:
        `self.new_profiles` if `is_new`, otherwise `self.existing_profiles`.

        Args:
            profile (dict): full JSON data to be saved
            is_new (bool): if True, profile will be saved in subdirectory and in-memory cache for
                "new" profiles. Otherwise will be stored in "existing" profiles subdir/cache.
        Returns:
            str: the profile_id, if save was successful
        """
        profile_id = profile.get('id')

        # determine the right filepath where JSON data will be written
        dir_path = self._new_dir if is_new else self._existing_dir
        filepath = os.path.join(dir_path, profile_id + '.json')

        # will be saved to the appropriate in-memory list of profile data
        profile_cache = self.new_profiles if is_new else self.existing_profiles

        logger.info('Now saving profile to path: %s', filepath)
        with open(filepath, 'w', encoding='utf-8') as file:
            json.dump(profile, file)  # save JSON to filesystem

        profile_cache.append(profile)
        return profile_id

    def _read_existing_profiles(self) -> list[dict]:
        """Read all JSON files from this ProfileStore's `existing` subdirectory"""
        profile_list: list[dict] = []
        for filename in glob('*.json', root_dir=self._existing_dir):
            with open(os.path.join(self._existing_dir, filename), 'r', encoding='utf-8') as file:
                json_data: dict = json.load(file)
                # if this is a pure NWS Connect response, profile will be nested inside `profiles`
                if profiles := json_data.get('profiles', None) and isinstance(profiles, list):
                    for profile in profiles:
                        profile_list.append(profile)
                else:
                    # this file is assumed to be just a Support Profile
                    profile_list.append(json_data)

        return profile_list

    def _read_existing_profile(self, profile_id: str) -> dict:
        """Get an existing profile from disk based on the profile ID.
        Reads from NEW subdirectory should almost never be necessary.
        """
        filename = os.path.join(self._existing_dir, profile_id + '.json')
        logger.debug('Attempting to read existing profile from path: %s', filename)
        with open(filename, 'r', encoding='utf-8') as file:
            return json.load(file)

    def _write_new_profile(self, data: dict):
        """Write a new Support Profile Profile to disk using `self._new_dir`"""
        profile_id = data['id']
        with open(os.path.join(self._new_dir, profile_id + '.json'), 'w', encoding='utf-8') as file:
            os.write(file, data)

    def _delete_profile(self, profile_id: str) -> bool:
        """Delete profile from disk by profile_id.
        Returns:
            bool: True on success, False if JSON file not found
        """
        filepath = os.path.join(self._existing_dir, profile_id + '.json')
        if not os.path.exists(filepath):
            # profile does not in exist in existing subdirectory, maybe its in the new one
            filepath = os.path.join(self._existing_dir, profile_id + '.json')

            if not os.path.exists(filepath):
                logger.warning('Cannot delete profile %s; JSON file not found in %s or %s',
                               profile_id, self._existing_dir, self._new_dir)
                return False

        logger.debug('Attempting to delete profile at path: %s', filepath)
        os.remove(filepath)
        return True
