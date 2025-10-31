"""Utilities for using test resources from named packages in unit tests"""

# --------------------------------------------------------------------------------
# Created on Wed Jul 19 2023
#
# Copyright (c) 2023 Colorado State University. All rights reserved. (1)
# Copyright (c) 2023 Regents of the University of Colorado. All rights reserved. (2)
#
# Contributors:
#     Mackenzie Grimes (1)
#     Paul Hamer (1)
#
# --------------------------------------------------------------------------------

import csv
import json
import pathlib

from collections.abc import Sequence
from importlib import resources
from os import path
from typing import Any, TextIO, Callable


# pylint: disable=protected-access
def get_package_path(package: str) -> str:
    """Get file path from package/filename

    Args:
        package (str): name of test package

    Returns:
        str: The package path from the installed package
    """
    package_path = resources.files(package)
    if isinstance(package_path, pathlib.PosixPath):
        return str(package_path)
    return str(package_path._paths[0])


def get_filepath(package: str, filename: str) -> str:
    """Get file path from package/filename

    Args:
        package (str): name of test package containing the file
        filename (str): name of test resource to load from the package directory

    Returns:
        str: The filepath from the installed package
    """
    return str(resources.files(package).joinpath(filename))


def get_resource_from_file(
    package: str, filename: str, load_func: Callable[[str], Any] | None = None
) -> dict | Sequence[Sequence[Any]]:
    """Load test resource/data from file into python object

    Args:
        package (str): name of test package containing the file
        filename (str): name of test resource to load from the package directory
        load_func (optional, Callable | None): custom function to read content from the provided
            filename and package. Required if file extension is not one of: `[.json, .csv. .html]`.
            Defaults to None (use built-in file readers).

    Raises:
        ValueError: if file extension is not supported

    Returns:
        dict | Sequence[Sequence[Any]]: Appropriate data type based on resource file type.
        For example, .json returns a dict, .csv returns a list of lists
    """
    traversable = resources.files(package).joinpath(filename)
    if load_func:
        return load_func(traversable)

    _, file_extension = path.splitext(filename)
    file_stream = traversable.open("r")
    if file_extension == ".json":
        return _load_json_resource(file_stream)
    if file_extension == ".csv":
        return _load_csv_resource(file_stream)
    if file_extension == ".html":
        return _load_html_resource(file_stream)
    raise ValueError(f"Unable to load test data from unsupported extension {file_extension}")


def _load_json_resource(stream: TextIO) -> dict:
    """utility to load JSON file from package into dict object"""
    return json.load(stream)


def _load_csv_resource(stream: TextIO) -> Sequence[Sequence[Any]]:
    """utility to load CSV file from package into 2D array of floats"""
    file_reader = csv.reader(stream)
    return [list(map(float, row)) for row in file_reader]


def _load_html_resource(filestream: TextIO) -> str:
    """utility to load NetCDF file from package"""
    return filestream.read()
