"""NWS Connect Dummy service simulating behaviors of NWS Connect core services"""
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

from flask import Flask, current_app, request, jsonify

from src.profile_store import ProfileStore

# constants
GSL_KEY = '8209c979-e3de-402e-a1f5-556d650ab889'


def to_iso(date_time: datetime) -> str:
    """Format a datetime instance to an ISO string. Borrowed from idsse.commons.utils for now"""
    return (f'{date_time.strftime("%Y-%m-%dT%H:%M")}:'
            f'{(date_time.second + date_time.microsecond / 1e6):06.3f}'
            'Z' if date_time.tzname() in [None, str(UTC)]
            else date_time.strftime("%Z")[3:])


# pylint: disable=too-few-public-methods
class HealthRoute:
    """Handle requests to /health endpoint"""
    def __init__(self):
        self._app_start_time = datetime.now(UTC)

    def handler(self):
        """Logic for requests to /health"""
        uptime = datetime.now(UTC) - self._app_start_time
        return jsonify({
            'startedAt': to_iso(self._app_start_time),
            'uptime': uptime.total_seconds()
        }), 200


class EventsRoute:
    """Handle requests to /all-events endpoint"""
    def __init__(self, base_dir: str):
        self.profile_store = ProfileStore(base_dir)

    # pylint: disable=too-many-return-statements
    def handler(self):
        """Logic for requests to /all-events"""
        # check that this request has proper key to get or add data
        if request.headers.get('X-Api-Key') != current_app.config['GSL_KEY']:
            return jsonify({'message': 'ERROR: Unauthorized'}), 401

        if request.method == 'POST':
            # request is saving new Support Profile event
            request_body: dict = request.json
            profile_id = self.profile_store.save(request_body)
            if not profile_id:
                return jsonify({'message': f'Profile {request_body.get("id")} already exists'}
                               ), 400

            return jsonify({'message': f'Profile {profile_id} saved'}), 201

        if request.method == 'DELETE':
            profile_id = request.args.get('uuid', default=None, type=str)
            is_deleted = self.profile_store.delete(profile_id)
            if not is_deleted:
                return jsonify({'message': f'Profile {profile_id} not found'}), 404
            return jsonify({'message': f'Profile {profile_id} deleted'}), 204

        # otherwise, must be 'GET' operation
        data_source = request.args.get('dataSource', None, type=str)
        if data_source != 'NBM':
            return jsonify({'profiles': [], 'errors': [f'Invalid dataSource: {data_source}']}), 400

        profile_status = request.args.get('status', default='existing', type=str)
        if profile_status == 'existing':
            profiles = self.profile_store.get_all()

        elif profile_status == 'new':
            profiles = self.profile_store.get_all(filter_new_profiles=True)
            # update ProfileStore to label all queried events as no longer "new";
            # they've now been returned to IDSS Engine clients at least once
            current_app.logger.info('Got all new profiles: %s', profiles)
            for profile in profiles:
                self.profile_store.move_to_existing(profile['id'])

        else:
            # status query param should have been 'existing' or 'new'
            return jsonify(
                {'profiles': [], 'errors': [f'Invalid profile status: {profile_status}']}
                ), 400

        return jsonify({'profiles': profiles, 'errors': []}), 200


class AppWrapper:
    """Web server class wrapping Flask operations"""
    def __init__(self, base_dir: str):
        """Build Flask app instance, mapping handler to each endpoint"""
        self.app = Flask(__name__, static_folder=None)  # no need for a static folder

        health_route = HealthRoute()
        events_route = EventsRoute(base_dir)

        self.app.add_url_rule('/health', 'health', view_func=health_route.handler,
                              methods=['GET'])
        self.app.add_url_rule('/all-events', 'events',
                              view_func=events_route.handler,
                              methods=['GET', 'POST', 'DELETE'])

    def run(self, **kwargs):
        """Start up web server"""
        self.app.run(**kwargs)


def create_app(args: Namespace = None) -> Flask:
    """Create a Flask instance"""
    base_dir = args.base_dir
    return AppWrapper(base_dir).app


if __name__ == '__main__':  # pragma: no cover
    parser = ArgumentParser()
    parser.add_argument('--port', dest='port', default=5000, type=int,
                        help='The port the web server will listen on.')
    parser.add_argument('--base_dir', dest='base_dir', required=True, type=str,
                        help='The base directory where Support Profile JSONs will be read/written')

    _args = parser.parse_args()

    app = create_app(_args)
    # host=0.0.0.0 is required for flask to work properly in docker and k8s env
    app.run(host='0.0.0.0', port=_args.port)

elif 'gunicorn' in os.getenv('SERVER_SOFTWARE', default=''):  # pragma: no cover
    # default to current directory
    _base_dir = os.getenv('BASE_DIR', os.getcwd())
    app = AppWrapper(_base_dir).app
