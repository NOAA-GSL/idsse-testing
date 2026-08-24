"""Misc Python utilities"""

# ----------------------------------------------------------------------------------
# Created on Wed Jun 18 2025
#
# Copyright (c) 2025 Colorado State University. All rights reserved.             (1)
#
# Contributors:
#     Mackenzie Grimes (1)
#
# ----------------------------------------------------------------------------------

from copy import deepcopy
from datetime import datetime, UTC


def deep_update(original: dict, updates: dict) -> dict:
    """Recursively combine two dictionaries such that attributes in `changes` only
    overwrite the original dict's values at the deepest level (a.k.a. leaf node). Returns
    the original dictionary with changes updated (dictionaries not changed in place).

    E.g.
    ```
    deepupdate({'foo': {'bar': 'x', 'baz': 'x'}}, {'foo': {'bar': 'y'}})
    ```
    Will result in a combined dictionary where only foo.bar was overwritten, not foo.baz:
    ```
    {'foo': {'bar': 'y', 'baz': 'x'}}
    ```
    """
    updated_dict = deepcopy(original)
    for key, value in updates.items():
        if isinstance(original.get(key), dict) and isinstance(value, dict):
            updated_dict[key] = deep_update(original.get(key), value)  # recurse down one level
        else:
            updated_dict[key] = value
    return updated_dict


def to_iso(dt: datetime) -> str:
    """Format a datetime instance to an ISO string. Copied from `idss-engine-commons` for now"""
    # pylint: disable=invalid-name
    return (
        f'{dt.strftime("%Y-%m-%dT%H:%M")}:' f"{(dt.second + dt.microsecond / 1e6):06.3f}" "Z"
        if dt.tzname() in [None, str(UTC)]
        else dt.strftime("%Z")[3:]
    )


# a Vulnerability from real NWSC Vulnerabilities API; dynamic objects should extend this format
VULNERABILITY_TEMPLATE = {
    "vulnerabilityType": "EVENT",
    "name": None,
    "description": None,
    "primaryOfficeId": "GSL",
    "geometry": "",
    "activeTime": {
        "startTime": None,
        "endTime": None,
        "recurrenceRule": None,
    },
    "support": {
        "summary": None,
        "notes": "",
        "briefings": [
            {
                "type": "email_briefing",
                "schedule": {"startTime": None, "endTime": None, "recurrenceRule": None},
            }
        ],
        "recipients": {"partners": [], "externals": []},
    },
    "notes": "",
    "hazards": [],
    "url": "",
    "dailyAttendance": None,
    "venueType": "OUTDOOR",
    "venueAddress": {
        "vulnerabilityId": None,
        "streetLine1": None,
        "streetLine2": None,
        "city": "",
        "state": "",
        "postalCode": None,
        "countryCode": None,
    },
    "isNsseEvent": False,
    "isSearEvent": False,
    "searEventLevel": None,
    "evacuationTimeMinutes": 0,
    "timezone": "UTC",
    "originalRequestId": None,
    "incidentName": None,
    "scheduledEventData": None,
    "hazmatResponseData": None,
    "searchRescueData": None,
    "wildfireData": None,
}
