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

import logging
from uuid import uuid4
from datetime import datetime, timedelta, UTC
from dataclasses import dataclass

from src.utils import to_iso

logger = logging.getLogger(__name__)


@dataclass
class UserSession:
    """Data class to track a User Session, settings, etc. Can delete once `is_expired` is True"""

    data: dict
    expires_at: float

    @property
    def is_expired(self) -> bool:
        """Returns True if UserSession has expired (can be ignored)"""
        return datetime.now(UTC).timestamp() > self.expires_at


class UserStore:
    """In-memory storage that simulates authorization: logged-in users based on client cookies,
    and per-user settings management.
    """

    MAX_AGE = 8 * 60 * 60  # time (seconds) after creation when User Session will auto-delete

    def __init__(self):
        self._sessions: dict[str, UserSession] = {}

        # track class instantiation time so placeholder user's createdTime is a meaningful value
        self._start_time = datetime.now(UTC)

    def get_user(self, session_id: str | None):
        """Fetch the 'logged-in user' for a particular JSESSIONID cookie. If no user exists,
        returns placeholder user data.
        """
        self._delete_expired_sessions()  # trigger cleanup of any expired sessions

        if existing_session := self._sessions.get(session_id):
            return existing_session.data

        # create new Session so we can start tracking officeId, settings
        session = self._create_session(session_id)
        return session.data

    def update_user_settings(
        self, session_id: str, active_office: str | None = None, settings: dict | None = None
    ):
        """Update a user's settings associated with a given JSESSIONID cookie"""
        self._delete_expired_sessions()  #  trigger cleanup of any expired sessions
        user = self._sessions.get(session_id)

        # user did not exist (or was expired); create new UserSession with placeholder as template
        if not user or user.is_expired:
            user = self._create_session(session_id)
            # just created user, so updatedTime ought to be same as createdTime
            user.data["updatedTime"] = user.data["createdTime"]
        else:
            user.data["updatedTime"] = to_iso(datetime.now(UTC))

        # update any settings that are useful to IDSS Engine, like theme, is24HourTime
        if settings:
            user.data["settings"] = {**user.data["settings"], **settings}
        if active_office:
            user.data["activeOfficeId"] = active_office

        # commit new UserSession to the in-memory cache
        self._sessions[session_id] = user

        return user.data

    @property
    def _placeholder_data(self) -> dict:
        """A fake User response object that has placeholders for all values"""
        return {
            "userId": "b9b48808-bc5a-403c-8cac-9e5f783a743b",
            "nwsChatAccountId": "508d7dbb-c974-4d08-8c4d-4d3572f2c711",
            "primaryEmailAddress": "firstname.lastname@noaa.gov",
            "firstName": "GSL",
            "lastName": "User",
            "forecasterSignature": "GUS",
            "jobTitle": {"id": "MIC", "title": "Meteorologist in Charge"},
            "primaryOfficeId": "GSL",
            "secondaryOfficeIds": [],
            "activeOfficeId": "GSL",
            "roles": [{"groupId": "GSL", "role": "IDSS_USER"}],
            "isDeleted": False,
            "isRegistered": True,
            # placeholder user was created whenever this class was created
            "updatedTime": to_iso(self._start_time),
            "createdTime": to_iso(self._start_time),
            "settings": {"theme": "LIGHT", "is24HourTime": False},
        }

    def _create_session(self, session_id: str) -> UserSession:
        """Create a new UserSession with mostly placeholder values (some unique values like userId)
        and expiration date of `ttl` seconds.
        """
        created_at = datetime.now(UTC)
        expires_at = created_at + timedelta(seconds=self.MAX_AGE)
        new_user = UserSession(self._placeholder_data, expires_at=expires_at.timestamp())
        new_user.data["createdTime"] = to_iso(created_at)

        # generate UUIDs just to look consistent. IDs actually persist only as long as session does
        new_user.data["userId"] = str(uuid4())
        new_user.data["nwsChatAccountId"] = str(uuid4())

        # commit new UserSession to the in-memory cache
        self._sessions[session_id] = new_user

        return new_user

    def _delete_expired_sessions(self):
        """Find and delete any sessions past expiration."""
        expired_session_ids = list({k for (k, v) in self._sessions.items() if v.is_expired})
        for session_id in expired_session_ids:
            self._sessions.pop(session_id)
