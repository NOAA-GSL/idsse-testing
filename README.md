# idsse-testing
[![Lint with pylint](https://github.com/NOAA-GSL/idsse-testing/actions/workflows/linter.yml/badge.svg)](https://github.com/NOAA-GSL/idsse-testing/actions/workflows/linter.yml)

## Overview
The `idsse-testing` module is responsible for defining all implicit common data that are used by the apps that make up the IDSS Engine Project distributed system. This
repository should be used to house elements that are common across multiple projects to encourage reuse.

# Twelve-Factors
The complete twelve-factors methodologies that the IDSS Engine Project adheres to can be found in the umbrella [idss-engine](https://github.com/NOAA-GSL/idss-engine) repository. The subset of the twelve factors that follows are specifics to this app only.

## Logging
To support some standardization and best practices for IDSS Engine, developers should following the logging guide found under the docs directory [here](https://github.com/NOAA-GSL/idss-engine-commons)

## Build, Release, and Install
The subsections below outline how to build the package within this project.

#### Build
From the IDSS Engine Testing project python directory `idsse-testing/python/`:

`$ pip install .`
