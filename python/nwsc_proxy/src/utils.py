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
