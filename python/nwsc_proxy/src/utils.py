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


def deep_update(a: dict, b: dict) -> dict:
    """Recursively combine two dictionaries such that dictionary `b`'s attributes only
    overwrite dictionary a's values at the deepest (leaf node) level. Returns the combined
    dictionary (dictionaries not changed in place).

    E.g.
    ```
    deepupdate({'foo': {'bar': 'x', 'baz': 'x'}}, {'foo': {'bar': 'y'}})
    ```
    Will result in a combined dictionary where only foo.bar was overwritten, not foo.baz:
    ```
    {'foo': {'bar': 'y', 'baz': 'x'}}
    ```
    """
    combined_dict = deepcopy(a)
    for k, v in b.items():
        if isinstance(a.get(k), dict) and isinstance(v, dict):
            combined_dict[k] = deep_update(a.get(k), v)  # recurse down one level
        else:
            combined_dict[k] = v
    return combined_dict
