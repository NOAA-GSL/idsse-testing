# idsse-testing
[![Lint with pylint](https://github.com/NOAA-GSL/idsse-testing/actions/workflows/linter.yml/badge.svg)](https://github.com/NOAA-GSL/idsse-testing/actions/workflows/linter.yml)

## Overview
The `idsse-testing` module is responsible for defining all implicit common data that are used by the apps that make up the IDSS Engine Project distributed system. This
repository should be used to house elements that are common across multiple projects to encourage reuse.

## Twelve-Factors
The complete twelve-factors methodologies that the IDSS Engine Project adheres to can be found in the umbrella [idss-engine](https://github.com/NOAA-GSL/idss-engine) repository. The subset of the twelve factors that follows are specifics to this app only.

## Contributing
Clone this repository.

Create a Python pip environment and activate it:
```sh
python3 -m venv .venv && source .venv/bin/activate
```

Install all Python dependencies based on what is installed in any of the GitHub Actions in `.github/workflows`, e.g. `linter.yml`.
```sh
pip install <libs_from_.github/workflows/linter.yml>
```

### Formatting
Python code is formatted according to the [black](https://black.readthedocs.io/) style guide, and any Pull Requests will be checked against this styling to ensure the new code has been auto-formatted.

To have `black` reformat all Python code every time you create a git commit, install the [pre-commit](https://pre-commit.com/) library:
```sh
pip install pre-commit
```

And run this to have any Git pre-commit hooks installed for you according to `.pre-commit.config.yaml`:
```sh
pre-commit install
```

If you prefer, you can install the `black` library and run it yourself manually (not on `git commit`):
```sh
pip install black
```

This will reformat all your Python files for you:
```sh
black . --line-length 100
```

## Logging
To support some standardization and best practices for IDSS Engine, developers should following the logging guide found under the docs directory [here](https://github.com/NOAA-GSL/idss-engine-commons)

## Build, Release, and Install
The subsections below outline how to build the package within this project.

#### Build
From the IDSS Engine Testing project python directory `idsse-testing/python/`:

`$ pip install .`
