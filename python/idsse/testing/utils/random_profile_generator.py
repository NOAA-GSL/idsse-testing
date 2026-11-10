"""Generate random IDSS Engine Profiles with every supported variable, units, and domain.

## Install
- Python 3.11+
- requests (`pip install requests`)
- pyproj (`pip install pyproj`)

## Run
```
python3 random_profile_generator.py --office BOU
```

Required arguments:
- `--office`: the NWS office tag to associate each created Profile (e.g. `BOU`).

Optional arguments:
- `--base_url`:
    URL of the API where profiles should be saved. Default is the GSL Dev DSD web server
    (http://wids-idsse-1/idss/dsd/api).
- `--count`:
    The number of profiles to generate random variables + locations. Default is None (create enough
    profiles to cover every weather variable).
- `--region`:
    The NBM region where profiles should be created, e.g. CONUS or ALASKA. Defaults to CONUS.
- `--max_severity_levels`:
    The number of severity levels to create per weather threshold (up to 4). Defaults to 1 (created
    profiles will only have 1 threshold/severity level, e.g. "MINOR", for each variable).
- `--cookies`:
    Cookie string from browser logs of logged-in DSD user. May be required to create profiles in
    environments that require user authentication (e.g. NWS Connect).
"""

import argparse
import json
import logging
import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from typing import Iterable, Generator
from uuid import uuid4

from requests import Response, Session
from pyproj import CRS, Transformer

logger = logging.getLogger(__name__)

# constants
MILES_TO_METERS = 1609.344


class ProgressBar:
    """A simple Python console progress bar. Source: https://stackoverflow.com/a/36985003"""

    def __init__(self, size: int, width=40, symbol="=", output=sys.stderr):
        assert len(symbol) == 1

        self.size = size
        self.width = width
        self.symbol = symbol
        self.output = output
        self.current_step = 0

    def next(self):
        """Increment the progress bar by one"""
        self.current_step += 1

        percent = self.current_step / float(self.size) * 100
        size = int(self.width * (percent / 100))
        remaining = self.size - self.current_step
        progress_bar = "[" + self.symbol * size + " " * (self.width - size) + "]"

        print(
            (
                f"\r{progress_bar} {self.current_step}/{self.size} ({percent:.0f}%) "
                f"{remaining} to go"
            ),
            file=self.output,
            end="",
        )

    def done(self):
        """Mark progress bar as complete"""
        self.current_step = self.size - 1
        self.next()
        print("", file=self.output)


def _to_iso(datetime_: datetime) -> str:
    """Stringify a Python Datetime using the ISO-8601 format. Datetime assumed to be in UTC."""
    return datetime_.isoformat().replace("+00:00", "Z")


class ProfileGenerator:
    """Generate IDSS Engine Profiles a.k.a. Vulnerabilities with random locations and thresholds"""

    # pylint: disable=too-few-public-methods

    # Field names, hazardTypes, and units from the DSD's forecastVarConfig.js.
    # Ranges for each Field contol the min and max random magnitude that will be generated; ranges
    # are roughly plausible but not guaranteed to be "impactful" or even realistic conditions.
    # BUG: commented out fields are supported by backend, but not by DSD yet
    FIELD_SPECS = {
        "AppTemp": {
            "hazard_type": "extreme_heat",
            "units": {"Fahrenheit": (-40, 120), "Celsius": (-40, 49)},
            "unsupported_regions": ["GUAM"],
        },
        "Ceiling": {
            "hazard_type": "low_visibility",
            "units": {"KiloFeet": (0.1, 10)},
        },
        # "CloudCover": {
        #     "hazard_type": "air_quality",
        #     "units": {"Percent": (0, 100)},
        # },
        "DewPoint": {
            "hazard_type": "elevated_fire_danger",
            "units": {"Fahrenheit": (-20, 80), "Celsius": (-29, 27)},
        },
        "HeatIdx": {
            "hazard_type": "extreme_heat",
            "units": {"Fahrenheit": (70, 130), "Celsius": (21, 54)},
            "unsupported_regions": ["GUAM"],
        },
        # BUG: change this to FreezingRain:<x> once DAS supports it
        "Ice:1HR": {
            "hazard_type": "ice_freezing_rain",
            "units": {"Inches": (0.01, 1)},
            "unsupported_regions": ["HAWAII", "GUAM", "PUERTO_RICO"],
        },
        "Ice:6HR": {
            "hazard_type": "ice_freezing_rain",
            "units": {"Inches": (0.01, 1)},
            "unsupported_regions": ["HAWAII", "GUAM", "PUERTO_RICO"],
        },
        "Ice:24HR": {
            "hazard_type": "ice_freezing_rain",
            "units": {"Inches": (0.01, 1)},
            "unsupported_regions": ["HAWAII", "GUAM", "PUERTO_RICO"],
        },
        # "MaxTemp": {
        #     "hazard_type": "extreme_heat",
        #     "units": {"Fahrenheit": (-30, 120), "Celsius": (-34, 49)},
        # },
        # "MinTemp": {
        #     "hazard_type": "extreme_cold",
        #     "units": {"Fahrenheit": (-50, 100), "Celsius": (-46, 38)},
        # },
        # "MaxRh": {
        #     "hazard_type": "elevated_fire_danger",
        #     "units": {"Percent": (1, 100)},
        # },
        # "MinRh": {
        #     "hazard_type": "elevated_fire_danger",
        #     "units": {"Percent": (1, 100)},
        # },
        "ProbThdr:1HR": {
            "hazard_type": "thunderstorms",
            "units": {"Percent": (1, 75)},
        },
        "ProbThdr:3HR": {
            "hazard_type": "thunderstorms",
            "units": {"Percent": (1, 75)},
        },
        "ProbThdr:6HR": {
            "hazard_type": "thunderstorms",
            "units": {"Percent": (1, 75)},
        },
        # "ProbThdr:12HR": {
        #     "hazard_type": "thunderstorms",
        #     "units": {"Percent": (1, 100)},
        # },
        "Precip:1HR": {
            "hazard_type": "heavy_rain",
            "units": {"Inches": (0.01, 2), "Millimeters": (0.01, 51)},
        },
        "Precip:6HR": {
            "hazard_type": "heavy_rain",
            "units": {"Inches": (0.01, 6), "Millimeters": (0.01, 152)},
        },
        "Precip:24HR": {
            "hazard_type": "heavy_rain",
            "units": {"Inches": (0.01, 12), "Millimeters": (0.01, 305)},
            "unsupported_regions": ["GUAM"],
        },
        "RH": {
            "hazard_type": "elevated_fire_danger",
            "units": {"Percent": (1, 100)},
        },
        "Snow:1HR": {
            "hazard_type": "snow_accumulation",
            "units": {"Inches": (0.01, 4), "Feet": (0.01, 0.3)},
            "unsupported_regions": ["HAWAII", "GUAM", "PUERTO_RICO"],
        },
        "Snow:6HR": {
            "hazard_type": "snow_accumulation",
            "units": {"Inches": (0.01, 24), "Feet": (0.01, 2)},
            "unsupported_regions": ["HAWAII", "GUAM", "PUERTO_RICO"],
        },
        # "Snow:12HR": {
        #     "hazard_type": "snow_accumulation",
        #     "units": {"Inches": (0.01, 36), "Feet": (0.01, 3)},
        #     "unsupported_regions": ["HAWAII", "GUAM", "PUERTO_RICO"],
        # },
        "Snow:24HR": {
            "hazard_type": "snow_accumulation",
            "units": {"Inches": (0.01, 36), "Feet": (0.01, 3)},
            "unsupported_regions": ["HAWAII", "GUAM", "PUERTO_RICO"],
        },
        "Snow:48HR": {
            "hazard_type": "snow_accumulation",
            "units": {"Inches": (0.01, 36), "Feet": (0.01, 3)},
            "unsupported_regions": ["HAWAII", "GUAM", "PUERTO_RICO"],
        },
        "Temp": {
            "hazard_type": "extreme_heat",
            "units": {"Fahrenheit": (-40, 120), "Celsius": (-40, 49)},
        },
        "Visibility": {
            "hazard_type": "low_visibility",
            "units": {"Miles": (0.1, 10), "Kilometers": (0.1, 16)},
        },
        # "WaveHeight": {
        #     "hazard_type": "high_waves_surf",
        #     "units": {"Feet": (0.1, 40), "Meters": (0.1, 12)},
        # },
        "WBGT": {
            "hazard_type": "extreme_heat",
            "units": {"Fahrenheit": (40, 110), "Celsius": (4, 43)},
            "unsupported_regions": ["ALASKA"],
        },
        # "WindChill": {
        #     "hazard_type": "extreme_cold",
        #     "units": {"Fahrenheit": (-60, 60), "Celsius": (-51, 16)},
        #     "unsupported_regions": ["GUAM"],
        # },
        "WindGust": {
            "hazard_type": "high_winds",
            "units": {"MilesPerHour": (0, 100), "Knots": (0, 87)},
        },
        "WindSpeed": {
            "hazard_type": "high_winds",
            "units": {"MilesPerHour": (0, 80), "Knots": (0, 70)},
        },
    }
    # NBM Grid dimensions, spacing, first grid coordinate, and PROJ strings from the DSD's
    # projections.js. The firstLat/firstLon point is treated as grid's bottom left corner.
    NBM_PROJECTIONS = {
        "CONUS": {
            "nx": 2345,
            "ny": 1597,
            "dx": 2539.703,
            "dy": 2539.703,
            "firstLat": 19.229,
            "firstLon": -126.2766,
            "proj": "+proj=lcc +a=6371200.0 +b=6371200.0 +lon_0=265.0 "
            "+lat_0=25.0 +lat_1=25.0 +lat_2=25.0",
        },
        "ALASKA": {
            "nx": 1649,
            "ny": 1105,
            "dx": 2976.56,
            "dy": 2976.56,
            "firstLat": 40.53,
            "firstLon": -178.571,
            "proj": "+proj=stere +lat_ts=60.0 +lat_0=90.0 +lon_0=210.0 "
            "+a=6371200.0 +b=6371200.0",
        },
        "HAWAII": {
            "nx": 625,
            "ny": 561,
            "dx": 2500.0,
            "dy": 2500.0,
            "firstLat": 14.3515,
            "firstLon": -164.9695,
            "proj": "+proj=merc +lat_ts=20.0 +lon_0=202.49515 " "+a=6371200.0 +b=6371200.0",
        },
        "PUERTO_RICO": {
            "nx": 339,
            "ny": 225,
            "dx": 1250.0,
            "dy": 1250.0,
            "firstLat": 16.9775,
            "firstLon": -68.0278,
            "proj": "+proj=merc +lat_ts=20.0 +lon_0=293.939 " "+a=6371200.0 +b=6371200.0",
        },
        "GUAM": {
            "nx": 193,
            "ny": 193,
            "dx": 2500.0,
            "dy": 2500.0,
            "firstLat": 12.349884,
            "firstLon": 143.656538,
            "proj": "+proj=merc +lat_ts=20.0 +lon_0=145.983269 " "+a=6371200.0 +b=6371200.0",
        },
    }
    # when Profile region is random, use this region more than others (80% of the time)
    PREFERRED_REGION = "CONUS"
    PREFERRED_REGION_LIKELIHOOD = 0.8

    # number of digits in each geometry's lat/lon coordinates
    PRECISION = 6

    OPERATORS = ["GREATER THAN OR EQUAL", "LESS THAN OR EQUAL", "GREATER THAN", "LESS THAN"]

    def __init__(self, seed: int | None = None):
        self._rand = random.Random(seed)

    def generate_vulnerabilities(
        self,
        office: str,
        count: int | None = None,
        region: str | None = None,
        *,
        max_severity_levels: int = 1,
    ) -> list[dict]:
        """Generate `count` number of random vulnerability JSONs.

        Args:
            office (str): the NWS officeId where all Vulnerabilities will be created, e.g. "BOU".
            count (optional, int | None): number of Vulnerability JSONs to generate. Defaults to
                None (generate enough Vulnerabilities to cover all weather variables configured in
                `self.FIELD_SPECS`).
            region (optional, str | None): the geographic region where all Vulnerabilities will be
                located, e.g. `CONUS, ALASKA, HAWAII, GUAM`. If None, a random region will be used
                for each Vulnerability. Defaults to None (use a random region).
            max_severity_levels (optiona, int): the maximum number of severity levels (a.k.a.
                impact levels) to create for each weather threshold in each Vulnerability. Each
                Vulnerability will create 1-4 severity levels (randomly chosen) for each weather
                hazard. Defaults to 1 (all Vulnerabilities may only generate a single severity
                level/threshold for each weather hazard).
        """
        if region and region not in self.NBM_PROJECTIONS:
            raise ValueError(
                f"Unexpected region: {region}; must be one of {', '.join(self.NBM_PROJECTIONS)}"
            )
        hazard_list = self._generate_field_groups(count)

        # name each profile using a random, unique color (no replacement)
        remaining_names = self._COLORS
        self._rand.shuffle(remaining_names)

        vulnerabilities: list[dict] = []

        for selected_fields in hazard_list:
            # generate a random start time between now and 7 days from now,
            # and random end time between 1 and 30 days after that
            start = datetime.now(timezone.utc) + timedelta(
                seconds=self._rand.randint(0, 7 * 24 * 60 * 60)
            )
            start = start.replace(minute=0, second=0, microsecond=0)  # round to nearest hour
            end = start + timedelta(days=self._rand.randint(1, 30))

            # select a random region if no hard-coded region passed by function caller
            if not region:
                region = self._generate_region(required_fields=selected_fields)

            # generate random Profile name, like "GSL Test Profile Burgundy"
            name = f"GSL Test Profile {remaining_names.pop().capitalize()}"

            vulnerability = {
                "name": name,
                "description": "",
                "primaryOfficeId": office,
                "geometry": self._generate_geometry(region, name),
                "activeTime": {
                    "startTime": _to_iso(start),
                    "endTime": _to_iso(end),
                    "recurrenceRule": "",
                },
                "support": {
                    "briefings": [],
                    "summary": "",
                    "recipients": {"partners": [], "externals": []},
                    "notes": "",
                },
                "notes": "",
                "hazards": self._generate_hazards(selected_fields, max_severity_levels),
                "scheduledEventData": {
                    "url": "",
                    "dailyAttendance": 0,
                    "venueType": "OUTDOOR",
                    "venueAddress": None,
                    "isNsseEvent": False,
                    "isSearEvent": False,
                    "searEventLevel": None,
                    "evacuationTimeMinutes": None,
                    "timezone": None,
                    "originalRequestId": None,
                },
            }
            vulnerabilities.append(vulnerability)

        return vulnerabilities

    def _generate_region(self, required_fields: list[str] | None = None) -> str:
        """Select a random region key from NBM_PROJECTIONS, weighting towards PREFERRED_REGION
        more often than others.

        Args:
            required_fields (optional, list[str] | None): a list of variables names (e.g. Temp,
                WindGust) that must all be available/supported in the returned region

        Returns:
            str: the selected region
        """
        if unrecognized_fields := set(required_fields) - set(list(self.FIELD_SPECS.keys())):
            raise ValueError(
                f"Cannot find region that supports unrecognized fields: {unrecognized_fields}"
            )

        regions = list(self.NBM_PROJECTIONS.keys())

        # avoid returning a region that is missing some of the fields caller expects to exist
        if not required_fields:
            region_candidates = regions
        else:
            region_candidates = [
                region_
                for region_ in regions
                if not any(
                    region_ in self.FIELD_SPECS[field_].get("unsupported_regions", [])
                    for field_ in required_fields
                )
            ]

        # weight preferred region LIKELIHOOD%, all other regions equal share of what's left
        if self.PREFERRED_REGION not in region_candidates:
            raise ValueError(
                f"Region {self.PREFERRED_REGION} not found, cannot weight higher than other regions"
            )

        if len(region_candidates) == 1:
            # only 1 region that supported all of these fields; guess we use that one
            selected_region = region_candidates[0]

        else:
            lesser_weight = (1 - self.PREFERRED_REGION_LIKELIHOOD) / (len(region_candidates) - 1)
            region_weights = [
                (self.PREFERRED_REGION_LIKELIHOOD if r == self.PREFERRED_REGION else lesser_weight)
                for r in region_candidates
            ]
            selected_region = random.choices(region_candidates, weights=region_weights, k=1)[0]

        return selected_region

    def _generate_field_groups(self, count: int | None = None):
        """Generate list of lists of 1 or more Fields to be assigned as Hazards to each generated
        Vulnerability. This ensures that we generate a number of random Hazards to be used in
        `count` number of Vulnerabilities, or if count is None, as many Vulnerabilities as it takes
        to account for all Fields at least once.
        """

        if count is None:
            # caller did not set number of profiles; assign hazards randomly to number of profiles
            # in any fashion, as long as all Fields are assigned to at least 1 profile
            remaining_fields = list(self.FIELD_SPECS.keys())
            self._rand.shuffle(remaining_fields)

            field_groups: list[list[str]] = []
            while remaining_fields:
                size = self._rand.randint(1, min(6, len(remaining_fields)))
                field_groups.append(remaining_fields[:size])
                del remaining_fields[:size]

            return field_groups

        if count < 1:
            raise ValueError("Count of generated vulnerabilities must be positive")

        # caller requested exact profile count; select 1-7 hazards randomly for each profile
        field_groups = [
            self._rand.sample(sorted(self.FIELD_SPECS), k=self._rand.randint(1, 7))
            for _ in range(count)
        ]
        return field_groups

    def _generate_geometry(self, region: str, name: str, *, max_width_miles=50, min_width_miles=1):
        """Return a GeoJSON geometry (stringified JSON) whose vertices lie within domain of
        the provided `region`. Shape will be between `min_width_miles` and `max_width_miles` wide.
        """
        # pylint: disable=too-many-locals,invalid-name
        logger.info("Generating random geometry within NBM region %s", region)

        projection = self.NBM_PROJECTIONS[region]
        projected_crs = CRS.from_proj4(projection["proj"])
        to_xy = Transformer.from_crs("EPSG:4326", projected_crs, always_xy=True)
        to_lonlat = Transformer.from_crs(projected_crs, "EPSG:4326", always_xy=True)

        x0, y0 = to_xy.transform(projection["firstLon"], projection["firstLat"])
        x1 = x0 + (projection["nx"] - 1) * projection["dx"]
        y1 = y0 + (projection["ny"] - 1) * projection["dy"]

        # Keep each geometry local: its projected bounding square is at most 20 miles.
        width = self._rand.uniform(min_width_miles, max_width_miles) * MILES_TO_METERS
        if x1 - x0 < width or y1 - y0 < width:
            raise ValueError(
                f"{region} grid is too small for a {width / MILES_TO_METERS:.1f}-mile geometry"
            )

        center = (
            self._generate_center_coord(width, x0, x1, projection["dx"]),
            self._generate_center_coord(width, y0, y1, projection["dy"]),
        )

        shape_type = self._rand.choice(("Point", "LineString", "Polygon"))
        if shape_type == "Point":
            coordinates = list(to_lonlat.transform(*center))
        elif shape_type == "LineString":
            coordinates = self._generate_line_string_coords(center, width, to_lonlat)
        else:
            coordinates = self._generate_polygon_coords(center, width, to_lonlat)

        # coerce result's precision to be less than 5-6 decimals (DSD doesn't support more)
        coordinates = self._round_nested_list(coordinates)

        # wrap our generated Polygon/Point/LineString in a GeoJSON FeatureCollection
        feature = {
            "id": str(uuid4()),
            "type": "Feature",
            "geometry": {"type": shape_type, "coordinates": coordinates},
            "properties": {"name": name},
        }
        return json.dumps(
            {"type": "FeatureCollection", "features": [feature]},
            # need to transform Generators from rounding coordinates back into lists
            default=lambda obj: list(obj) if isinstance(obj, Iterable) else obj,
        )

    def _generate_center_coord(
        self,
        width: int,
        start: int,
        end: int,
        cell_size: int,
        *,
        min_interior_buffer=20,
        max_interior_buffer=40,
    ) -> float:
        # pylint: disable=too-many-arguments
        # WARNING: untested slop code
        span = end - start
        half_width = width / 2

        # Keep both the buffer and the geometry inside the grid.
        max_buffer = max(0, math.floor((span - 2 * half_width) / (2 * cell_size)))
        if max_buffer == 0 and span < 2 * half_width:
            raise ValueError("Region grid is too small for this geometry")

        lower_buffer = min(min_interior_buffer, max_buffer)
        upper_buffer = min(max_interior_buffer, max_buffer)
        buffer_m = self._rand.randint(lower_buffer, upper_buffer) * cell_size

        low = start + half_width + buffer_m
        high = end - half_width - buffer_m

        # beta(2, 2) weights toward the middle without excluding any valid area.
        return low + (high - low) * self._rand.betavariate(2, 2)

    def _generate_line_string_coords(
        self, center: tuple[float, float], length: int, transformer: Transformer
    ) -> list[tuple[float, float]]:
        # WARNING: untested slop code
        center_x, center_y = center
        half_length = length / 2

        # LineString: 5-30 ordered vertices, with modest sideways variation.
        count = self._rand.randint(5, 30)
        cross_half_width = half_length * self._rand.uniform(0.08, 0.2)
        line_points: list[tuple[float]] = []

        for i in range(count):
            along = -half_length + 2 * half_length * i / (count - 1)
            across = self._rand.uniform(-cross_half_width, cross_half_width)

            # randomly choose to make LineString progress in x direction or y direction
            if self._rand.choice((False, True)):
                line_points.append((center_x + across, center_y + along))
            else:
                line_points.append((center_x + along, center_y + across))

        return [list(transformer.transform(x, y)) for x, y in line_points]

    def _generate_polygon_coords(
        self, center: tuple[float, float], width: int, transformer: Transformer
    ):
        # WARNING: untested slop code
        # Polygon: clipped corners make a simple, non-circular outline.
        center_x, center_y = center

        half_x = width / 2
        half_y = width / 2 * self._rand.uniform(0.35, 0.75)
        cut_x = half_x * self._rand.uniform(0.12, 0.25)
        cut_y = half_y * self._rand.uniform(0.12, 0.25)

        outer_xy = [
            (center_x - half_x + cut_x, center_y - half_y),
            (center_x + half_x - cut_x, center_y - half_y),
            (center_x + half_x, center_y - half_y + cut_y),
            (center_x + half_x, center_y + half_y - cut_y),
            (center_x + half_x - cut_x, center_y + half_y),
            (center_x - half_x + cut_x, center_y + half_y),
            (center_x - half_x, center_y + half_y - cut_y),
            (center_x - half_x, center_y - half_y + cut_y),
        ]

        def close_ring(points: list[tuple[float, float]]) -> list[list[tuple[float, float]]]:
            ring = [list(transformer.transform(x, y)) for x, y in points]
            return ring + [ring[0]]

        rings = [close_ring(outer_xy)]

        # BUG: backend supports Polygons with holes, but DSD criteria builder does not
        # if self._rand.random() < 0.25:
        #     # A centered, smaller rectangle forms a valid interior ring.
        #     hole_half_x = half_x * self._rand.uniform(0.15, 0.3)
        #     hole_half_y = half_y * self._rand.uniform(0.15, 0.3)
        #     hole_xy = [
        #         (center_x - hole_half_x, center_y - hole_half_y),
        #         (center_x - hole_half_x, center_y + hole_half_y),
        #         (center_x + hole_half_x, center_y + hole_half_y),
        #         (center_x + hole_half_x, center_y - hole_half_y),
        #     ]
        #     rings.append(close_ring(hole_xy))

        return rings

    def _generate_hazards(self, field_list: list[str], max_severity_levels: int) -> list[dict]:
        """
        Args:
            field_list (list[str]): list of weather Fields (e.g. AppTemp, WindGust, etc.) to use
                in this Hazard. The hazard may have 1 or more severity levels for each Field used.
            max_severity_levels (int): the highest count of severity levels to permit for each
                Hazard created. E.g. 1 = every Hazard can only generate a single random severity
                level (and threshold) per Field. 4 = every Hazard can generate 1, 2, 3, or 4
                severity levels for each Field.

        Returns:
            list[dict]: list of Hazard JSON objects
        """
        hazards: list[dict] = []

        for field in field_list:
            # generate 1, 2, 3, or 4 random impact levels (impactLevelValue must be between 1-4)
            # physically cannot create more than 4 severities for each hazard
            max_severity_levels = min(max_severity_levels, 4)
            impact_values = sorted(
                self._rand.sample(range(1, 5), self._rand.randint(1, max_severity_levels))
            )

            field_spec = self.FIELD_SPECS[field]
            hazard_category = field_spec["hazard_type"]

            # select a random unit associated with this Field, which tells us the min and max
            # magnitude permitted (plausible) for this Field + unit
            unit = self._rand.choice(list(field_spec["units"].keys()))
            min_mag, max_mag = field_spec["units"][unit]
            magnitudes = [round(self._rand.uniform(min_mag, max_mag), 2) for _ in impact_values]

            operator = self._rand.choice(self.OPERATORS)
            # sort impact levels by higher magnitude = higher impact, or higher magnitude = lower
            # impact if we're evaluating LESS_THAN. This relationship isn't accurate
            # for all variables (e.g. RH, WindChill, etc.), but we don't care.
            magnitudes.sort(reverse=operator.startswith("LESS"))

            hazards.append(
                {
                    "id": str(uuid4()),
                    "type": hazard_category,
                    "impactLevels": [
                        {
                            "thresholdSet": [
                                {
                                    "weatherElement": field,
                                    "magnitude": magnitude,
                                    "operator": operator,
                                    "units": unit,
                                    "minDurationHours": 0,
                                    "source": "NBM",
                                }
                            ],
                            "impactLevelValue": impact_value,
                            "impactStatements": [],
                        }
                        for impact_value, magnitude in zip(impact_values, magnitudes)
                    ],
                }
            )

        return hazards

    @classmethod
    def _round_nested_list(
        cls, items: Iterable | Iterable[Iterable] | Iterable[Iterable[Iterable]]
    ) -> Generator:
        """Recursively round all coordinates (lat/lons) for a Point/LineString/Polygon geometry"""
        for item in items:
            if isinstance(item, Iterable):
                yield cls._round_nested_list(item)
            elif isinstance(item, float):
                yield round(item, cls.PRECISION)
            else:
                yield item

    # fmt: off
    # list of color to use like lorem ipsum text for Profile names
    _COLORS = [
        "almond", "amber", "amethyst", "apricot", "aqua", "aquamarine", "auburn", "azure", "beige",
        "bisque", "black", "blond", "blue", "blush", "bone", "brass", "bronze", "brown", "buff",
        "burgundy", "cardinal", "carmine", "carnation", "celadon", "cerise", "cerulean",
        "champagne", "charcoal", "chartreuse", "chestnut", "chocolate", "cinnamon", "citron",
        "claret", "cobalt", "coffee", "copper", "coral", "cornsilk", "crimson", "cyan", "denim",
        "drab", "ebony", "ecru", "eggplant", "eggshell", "emerald", "fallow", "fawn", "flax",
        "fuchsia", "garnet", "ginger", "gold", "goldenrod", "gray", "green", "grey", "harlequin",
        "heliotrope", "henna", "honeydew", "indigo", "iris", "ivory", "jade", "jasmine", "jet",
        "khaki", "lavender", "lemon", "lilac", "lime", "linen", "magenta", "mahogany", "maize",
        "malachite", "marigold", "maroon", "mauve", "melon", "mint", "mocha", "moss", "mulberry",
        "mustard", "myrtle", "navy", "ochre", "olive", "onyx", "orange", "orchid", "peach", "pear",
        "pearl", "periwinkle", "persimmon", "pewter", "pink", "pistachio", "platinum", "plum",
        "puce", "pumpkin", "purple", "quartz", "raspberry", "red", "rose", "ruby", "ruddy",
        "russet", "rust", "saffron", "sage", "salmon", "sand", "sapphire", "scarlet", "sepia",
        "sienna", "silver", "slate", "smoke", "snow", "steel", "straw", "tan", "tangerine",
        "taupe", "teal", "terracotta", "thistle", "titanium", "topaz", "turquoise", "umber",
        "vanilla", "vermilion", "violet", "viridian", "walnut", "wheat", "white", "wine",
        "wisteria", "yellow"
    ]
    # fmt: on


def _parse_cookie_string(cookie: str | None) -> dict[str, str]:
    """Read all key-value pairs from a Cookies string (copied from some user's browser)"""
    if not cookie:
        return {}

    cookies_dict: dict[str, str] = {}

    cookie_segments = cookie.split("; ")
    for cookie_segment in cookie_segments:
        key, val = cookie_segment.split("=", maxsplit=2)
        cookies_dict[key] = val
    return cookies_dict


def submit_vulnerabilities(
    vulnerabilities: list[dict], base_url: str, cookie: str | None = None
) -> tuple[Response, str | None]:
    """Send POST HTTP(s) requests for 1 or more Vulnerability objects to a DSD URL.

    Args:
        vulnerabilities (list[dict]): all the Vulnerability objects to be submitted to the API.
        base_url (str): The base URL of the DSD web server that will persist the Vulnerabilities.
        cookies (optional, str | None): Cookies string from the browser of a logged-in DSD user,
            if this DSD API requires authentication. Defaults to None (do not send any auth headers
            in requests).

    Returns:
        tuple[Response, str | None]: all requests.Response objects, with the created vulnerability
            ID from each API response (if success) or None on failure.
    """
    # parse the Cookie string, if any, to transform it into the auth header the API requires
    cookie_vals = _parse_cookie_string(cookie)

    headers = {**cookie_vals, "Content-Type": "application/json"}
    url = f"{base_url}/vulnerabilities"

    logger.info("Now creating %s vulnerabilities in API at %s", len(vulnerabilities), url)
    progress_bar = ProgressBar(size=len(vulnerabilities), width=100)
    responses: list[tuple[Response, str | None]] = []

    with Session() as session:
        for vuln in vulnerabilities:
            response = session.post(url, json=vuln, headers=headers, timeout=30)
            progress_bar.next()

            new_id = None
            if response.ok:
                try:
                    # extract the created Vuln's id from response body
                    new_id = response.json()["id"]
                except (json.JSONDecodeError, KeyError) as exc:
                    logger.warning(
                        "Could not parse API response, status unknown. Res: %s. Cause: %s",
                        response,
                        exc,
                    )

            responses.append((response, new_id))

    return responses


def main(args: argparse.Namespace):
    """Driver function"""
    generator = ProfileGenerator()

    vulns = generator.generate_vulnerabilities(
        args.office,
        count=args.count,
        region=args.region,
        max_severity_levels=args.max_severity_levels,
    )

    if not (output_file := args.out_file):
        # output Vulnerabilities to API
        logger.info(
            "Generated %s vulnerabilities, submitting to API at %s now.", len(vulns), args.base_url
        )

        responses_by_id = submit_vulnerabilities(vulns, args.base_url, args.cookies)
        for response, id_ in responses_by_id:
            if not response.ok:
                logger.warning(
                    "Could not create Vulnerability %s; API response: %s",
                    id_,
                    str(response.reason),
                )
            logger.debug(response.status_code, response.text)

        success_ids = [id_ for (_, id_) in responses_by_id if id_]

    else:
        # generate some IDs before saving to file (API would have created them for us)
        vulns = [{"id": str(uuid4()), **v} for v in vulns]
        logger.info(
            "Generated %s vulnerabilities, outputing to local path: %s", len(vulns), output_file
        )

        with open(os.path.abspath(output_file), "w", encoding="utf-8") as file:
            json.dump(vulns, file, indent=2)
        success_ids = [v["id"] for v in vulns]

    logger.info(
        "\nDone! Sucessfully created vulnerability IDs (%s): %s", len(success_ids), success_ids
    )


if __name__ == "__main__":
    # output all logging messages to console
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--office", required=True, help="The NWS officeId to assign each Profile to, e.g. `BOU`"
    )
    parser.add_argument(
        "--base_url",
        default="https://wids-idsse-1/idss/dsd/api",
        help="Base URL of DSD web server where Profiles should be created",
    )
    parser.add_argument(
        "--out_file",
        default=None,
        help=(
            "Local JSON path to dump generated Profiles to (instead of sending to API). Default "
            "is None (use --base_url to upload Profiles to DSD API)"
        ),
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help=(
            "Number of Profiles to create. Defaults to None (create as many profiles as it takes "
            "to use every weather variable)"
        ),
    )
    parser.add_argument(
        "--region",
        type=str,
        default=None,
        choices=list(ProfileGenerator.NBM_PROJECTIONS.keys()),
        help=(
            "Geographic region where profile locations should fall. Defaults to None (each"
            "profile will use random region)."
        ),
    )
    parser.add_argument(
        "--max_severity_levels",
        type=int,
        default=1,
        help=(
            "Most severity levels/thresholds to ever use in a single Hazard for the generated "
            "Vulnerabilities. Defaults to 1 (only create 1 threshold per weather var)."
        ),
    )
    parser.add_argument(
        "--cookies",
        default=None,
        help=(
            "Stringified Cookie (;-separated) from a logged in DSD user's browser to auth against"
            "Vulnerabilities API. Default is None (don't send any Xsrf-Token in API calls)."
        ),
    )

    _args = parser.parse_args()
    main(_args)
