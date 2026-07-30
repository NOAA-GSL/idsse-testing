"""User store that does CRUD operations on in-memory users to simulate NWS Connect authorization"""

# ----------------------------------------------------------------------------------
# Created on Thu Jul 30 2026
#
# Copyright (c) 2026 Colorado State University. All rights reserved.             (1)
#
# Contributors:
#     Mackenzie Grimes (1)
#
# ----------------------------------------------------------------------------------

import os
import json
import logging
from uuid import uuid4

from copy import deepcopy
from datetime import datetime, UTC
from glob import glob

from dateutil.parser import parse as dt_parse

from src.utils import to_iso

logger = logging.getLogger(__name__)


class UserStore:
    """In-memory storage that simulates authorization: logged-in users based on client cookies,
    and per-user settings management.
    """

    def __init__(self):
        self._user_settings: dict[str, dict] = {}

        # track class instantiation time so placeholder user's createdTime is a meaningful value
        self._start_time = datetime.now(UTC)

    def get_user(self, session_id: str):
        """Fetch the 'logged-in user' for a particular JSESSIONID cookie. If no user exists,
        returns placeholder user data.
        """
        return self._user_settings.get(session_id, self._placeholder)

    def update_user_settings(
        self, session_id: str, active_office: str | None = None, settings: dict | None = None
    ):
        """Update a user's settings associated with a given JSESSIONID cookie"""
        user = self._user_settings.get(session_id)
        # user did not exist, so create a new one using the placeholder user as a template
        if not user:
            user = self._create_user()
            # just created user, so updatedTime ought to be same as createdTime
            user["updatedTime"] = user["createdTime"]
        else:
            user["updatedTime"] = to_iso(datetime.now(UTC))

        # update any settings that are useful to IDSS Engine, like theme, is24HourTime
        if settings:
            user["settings"] = settings
        if active_office:
            user["activeOfficeId"] = active_office

        # commit new user state to the in-memory cache
        self._user_settings[session_id] = user

        return user

    @property
    def _placeholder(self) -> dict:
        """A fake User response object that has placeholders for all values"""
        return {
            "userId": "b9b48808-bc5a-403c-8cac-9e5f783a743b",
            "nwsChatAccountId": "508d7dbb-c974-4d08-8c4d-4d3572f2c711",
            "primaryEmailAddress": "firstname.lastname@noaa.gov",
            "firstName": "FirstName",
            "lastName": "LastName",
            "forecasterSignature": "FLN",
            "jobTitle": {"id": "MIC", "title": "Meteorologist in Charge"},
            "primaryOfficeId": "BOI",
            "secondaryOfficeIds": [],
            "activeOfficeId": "BOI",
            "roles": [{"groupId": "BOI", "role": "USER"}],
            "isDeleted": False,
            "isRegistered": True,
            # placeholder user was created whenever this class was created
            "updatedTime": to_iso(self._start_time),
            "createdTime": to_iso(self._start_time),
            "settings": {"theme": "LIGHT", "is24HourTime": False},
        }

    def _create_user(self) -> dict:
        """Create a new user with mostly placeholder values (some unique values like userId)"""
        new_user = deepcopy(self._placeholder)
        new_user["createdTime"] = to_iso(datetime.now(UTC))

        # generate UUIDs just to look consistent. IDs actually persist only as long as session does
        new_user["userId"] = str(uuid4())
        new_user["nwsChatAccountid"] = str(uuid4())

        return new_user
