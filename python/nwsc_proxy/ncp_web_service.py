"""NWS Connect Proxy service simulating behaviors of NWS Connect core services"""

# ----------------------------------------------------------------------------------
# Created on Fri Apr 07 2023
#
# Copyright (c) 2023 Colorado State University. All rights reserved.             (1)
#
# Contributors:
#     Paul Hamer (1)
#     Mackenzie Grimes (1)
#
# ----------------------------------------------------------------------------------
import os
from datetime import datetime, UTC
from argparse import ArgumentParser, Namespace

from flask import Flask, Response, current_app, request, jsonify

from src.vulnerability_store import VulnerabilityStore

# constants
GSL_KEY = "8209c979-e3de-402e-a1f5-556d650ab889"


def to_iso(dt: datetime) -> str:
    """Format a datetime instance to an ISO string. Copied from `idss-engine-commons` for now"""
    # pylint: disable=invalid-name
    return (
        f'{dt.strftime("%Y-%m-%dT%H:%M")}:' f"{(dt.second + dt.microsecond / 1e6):06.3f}" "Z"
        if dt.tzname() in [None, str(UTC)]
        else dt.strftime("%Z")[3:]
    )


# pylint: disable=too-few-public-methods
class HealthRoute:
    """Handle requests to /health endpoint"""

    def __init__(self):
        self._app_start_time = datetime.now(UTC)

    def handler(self):
        """Logic for requests to /health"""
        uptime = datetime.now(UTC) - self._app_start_time
        return (
            jsonify({"startedAt": to_iso(self._app_start_time), "uptime": uptime.total_seconds()}),
            200,
        )


class VulnerabilitiesRoute:
    """Handle requests to /vulnerabilities endpoint"""

    def __init__(self, base_dir: str):
        self._profile_store = VulnerabilityStore(base_dir)

    def documents(self):
        """Logic for any HTTP request to /vulnerabilities."""
        # check that this request has proper key to get or add data
        if request.headers.get("X-Api-Key") != current_app.config["GSL_KEY"]:
            return jsonify({"message": "ERROR: Unauthorized"}), 401

        if request.method == "POST":
            return self._handle_create()

        # otherwise, must be 'GET' operation
        office = request.args.get("officeId")

        # let request control if `isDeleted: true` profiles are included in response.
        # Default to False if param not present (only return profiles where isDeleted: false)
        include_is_deleted = request.args.get("isDeleted", default=False, type=bool)

        profiles = self._profile_store.get_all(include_inactive=include_is_deleted, office=office)
        return jsonify(profiles), 200

    def document(self, profile_id: str):
        """Logic for HTTP requests to /vulnerabilities/:profile_id"""

        # pylint: disable=duplicate-code
        # check that this request has proper key to get or add data
        if request.headers.get("X-Api-Key") != current_app.config["GSL_KEY"]:
            return jsonify({"message": "ERROR: Unauthorized"}), 401
        # pylint: enable=duplicate-code

        if request.method == "DELETE":
            return self._handle_delete(profile_id)

        if request.method == "PATCH":
            return self._handle_update(profile_id)

        # otherwise, must be 'GET' operation
        if profile := self._profile_store.get(profile_id):
            return jsonify(profile), 200

        return jsonify({"message": f"Profile {profile_id} not found"}), 404

    def _handle_create(self) -> Response:
        """Logic for POST requests to /vulnerabilities. Returns Response with status_code: 201 on
        success, 400 otherwise."""
        profile_data: dict = request.json

        saved_profile = self._profile_store.save(profile_data)
        if not saved_profile:
            return jsonify({"message": "Error creating profile, may be malformed"}), 400

        return jsonify(saved_profile), 201

    def _handle_delete(self, profile_id: str) -> Response:
        """Logic for DELETE requests to /vulnerabilities/:id.
        Returns Response with status_code: 204 on success, 404 otherwise.
        """
        is_deleted = self._profile_store.delete(profile_id)
        if not is_deleted:
            return jsonify({"message": f"Profile {profile_id} not found"}), 404

        return jsonify({"message": f"Profile {profile_id} deleted"}), 204

    def _handle_update(self, profile_id: str) -> Response:
        if not request.data:
            return jsonify({"message": "PUT requires request body"}), 400

        request_body: dict = request.json
        try:
            updated_profile = self._profile_store.update(profile_id, request_body)
        except FileNotFoundError:
            return jsonify({"message": f"Profile {profile_id} not found"}), 404

        if not updated_profile:
            return jsonify({"message": "Internal Server Error"}), 500

        return jsonify(updated_profile), 200


class AppWrapper:
    """Web server class wrapping Flask operations"""

    def __init__(self, base_dir: str):
        """Build Flask app instance, mapping handler to each endpoint"""
        self.app = Flask(__name__, static_folder=None)  # no need for a static folder
        self.app.config["GSL_KEY"] = GSL_KEY

        health_route = HealthRoute()
        vulnerabilities_route = VulnerabilitiesRoute(base_dir)

        self.app.add_url_rule("/health", "health", view_func=health_route.handler, methods=["GET"])
        self.app.add_url_rule(
            "/vulnerabilities",
            "vulnerabilities",
            view_func=vulnerabilities_route.documents,
            methods=["GET", "POST"],
        )
        self.app.add_url_rule(
            "/vulnerabilities/<profile_id>",
            "vulnerability",
            view_func=vulnerabilities_route.document,
            methods=["GET", "PATCH", "DELETE"],
        )

    def run(self, **kwargs):
        """Start up web server"""
        self.app.run(**kwargs)


def create_app(args: Namespace = None) -> Flask:
    """Create a Flask instance"""
    base_dir = args.base_dir
    return AppWrapper(base_dir).app


if __name__ == "__main__":  # pragma: no cover
    parser = ArgumentParser()
    parser.add_argument(
        "--port",
        dest="port",
        default=5000,
        type=int,
        help="The port the web server will listen on.",
    )
    parser.add_argument(
        "--base_dir",
        dest="base_dir",
        required=True,
        help="The base directory where Support Profile JSONs will be read/written",
    )

    _args = parser.parse_args()

    app = create_app(_args)
    # host=0.0.0.0 is required for flask to work properly in docker and k8s env
    app.run(host="0.0.0.0", port=_args.port)

elif "gunicorn" in os.getenv("SERVER_SOFTWARE", default=""):  # pragma: no cover
    # default to current directory
    _base_dir = os.getenv("BASE_DIR", os.getcwd())
    app = AppWrapper(_base_dir).app
