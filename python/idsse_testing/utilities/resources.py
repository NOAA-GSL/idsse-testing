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

from collections.abc import Sequence
from importlib import resources
from os import path
from typing import TextIO

from idsse.common.sci.netcdf_io import read_netcdf

import numpy as np

# pylint: disable=protected-access
def get_package_path(package: str) -> str:
    """Get file path from package/filename

     Args:
         package (str): name of test package

     Returns:
         str: The package path from the installed package
    """
    return str(resources.files(package)._paths[0])

def get_filepath(package: str, filename: str) -> str:
    """Get file path from package/filename

     Args:
         package (str): name of test package containing the file
         filename (str): name of test resource to load from the package directory

     Returns:
         str: The filepath from the installed package
    """
    return str(resources.files(package).joinpath(filename))

def get_resource_from_file(package: str, filename: str) -> dict | Sequence[Sequence[any]]:
    """Load test resource/data from file into python object

    Args:
        package (str): name of test package containing the file
        filename (str): name of test resource to load from the package directory

    Raises:
        ValueError: if file extension is not supported

    Returns:
        dict | Sequence[Sequence[any]]: Appropriate data type based on resource file type.
        For example, .json returns a dict, .csv returns a list of lists
    """
    _, file_extension = path.splitext(filename)
    if file_extension == '.nc':
        return _load_netcdf_resource(resources.files(package).joinpath(filename))
    print(filename, file_extension)
    file_stream = resources.files(package).joinpath(filename).open('r')
    if file_extension == '.json':
        return _load_json_resource(file_stream)
    if file_extension == '.csv':
        return _load_csv_resource(file_stream)
    raise ValueError(f'Unable to load test data from unsupported extension {file_extension}')


def _load_json_resource(stream: TextIO) -> dict:
    """utility to load JSON file from package into dict object"""
    return json.load(stream)


def _load_csv_resource(stream: TextIO) -> Sequence[Sequence[any]]:
    """utility to load CSV file from package into 2D array of floats"""
    file_reader = csv.reader(stream)
    return [list(map(float, row)) for row in file_reader]


def _load_netcdf_resource(filename: str) -> tuple[dict, np.ndarray]:
    """utility to load NetCDF file from package"""
    return read_netcdf(filename)
