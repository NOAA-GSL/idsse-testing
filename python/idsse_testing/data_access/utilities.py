"""Utilities for using test resources from this directory in unit tests"""
# --------------------------------------------------------------------------------
# Created on Wed Jul 19 2023
#
# Copyright (c) 2023 Colorado State University. All rights reserved. (1)
# Copyright (c) 2023 Regents of the University of Colorado. All rights reserved. (2)
#
# Contributors:
#     Mackenzie Grimes (1)
#
# --------------------------------------------------------------------------------

import json
import csv
from importlib import resources
from os import path
from collections.abc import Sequence
from typing import TextIO, Any


def get_resource_from_file(filename: str) -> dict | Sequence[Sequence[Any]]:
    """Load test resource/data from file into python object

    Args:
        filename (str): name of test resource to load from the /test/resources directory

    Raises:
        ValueError: if file extension is not supported

    Returns:
        dict | Sequence[Sequence[Any]]: Appropriate data type based on resource file type.
        For example, .json returns a dict, .csv returns a list of lists
    """
    file_stream = resources.files(__package__).joinpath(filename).open('r')
    _, file_extension = path.splitext(filename)

    if file_extension == '.json':
        return _load_json_resource(file_stream)
    if file_extension == '.csv':
        return _load_csv_resource(file_stream)
    raise ValueError(f'Unable to load test data from unsupported extension {file_extension}')


def _load_json_resource(stream: TextIO) -> dict:
    """utility to load JSON file from test/resources directory into dict object"""
    return json.load(stream)


def _load_csv_resource(stream: TextIO) -> Sequence[Sequence[Any]]:
    """utility to load CSV file from test/resources directory into 2D array of floats"""
    file_reader = csv.reader(stream)
    return [list(map(float, row)) for row in file_reader]
