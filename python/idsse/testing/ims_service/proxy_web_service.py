"""Proxy web service simulating behaviors of NWS Connect core services"""
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
# pylint: disable=too-few-public-methods
from datetime import datetime, UTC
from argparse import ArgumentParser, Namespace

from flask import Flask, request, jsonify, current_app

from src.event_store import EventStore

# constants
GSL_KEY = '8209c979-e3de-402e-a1f5-556d650ab889'


def to_iso(date_time: datetime) -> str:
    """Format a datetime instance to an ISO string. Borrowed from idsse.commons.utils for now"""
    return (f'{date_time.strftime("%Y-%m-%dT%H:%M")}:'
            f'{(date_time.second + date_time.microsecond / 1e6):06.3f}'
            'Z' if date_time.tzname() in [None, str(UTC)]
            else date_time.strftime("%Z")[3:])


class HealthRoute:
    """Handle requests to /health endpoint"""
    def __init__(self):
        self._app_start_time = datetime.now(UTC)

    def handler(self):
        """Logic for requests to /health"""
        uptime = datetime.now(UTC) - self._app_start_time
        return jsonify({
            'startedAt': to_iso(self._app_start_time),
            'uptime': uptime.total_seconds
        }), 200


class EventsRoute:
    """Handle requests to /events endpoint"""
    def __init__(self, base_dir: str):
        self.event_store = EventStore(base_dir)

    def handler(self):
        """Logic for requests to /events"""
        # check that this request has proper key to get or add data
        if request.headers.get('X-Api-Key') != GSL_KEY:
            return jsonify({'message': 'ERROR: Unauthorized'}), 401

        if request.method == 'POST':
            # request is saving new Support Profile event
            request_body: dict = request.json
            event_id = self.event_store.save(request_body)  # TODO: handle failure?

            return jsonify({'message': f'Event {event_id} saved'}), 201

        if request.method == 'DELETE':
            event_id = request.args.get('uuid', default=None, type=str)
            self.event_store.delete(event_id)  # TODO: handle failure?

            return jsonify({'message': f'Event {event_id} deleted'}), 204

        # otherwise, must be 'GET' operation
        event_status = request.args.get('status', default='existing', type=str)
        if event_status == 'existing':
            events = self.event_store.get_all()
            return jsonify({'events': events}), 200

        if event_status == 'new':
            new_events = self.event_store.get_all(filter_new_profiles=True)
            # update EventStore to label all queried events as no longer "new";
            # they've now been returned to IDSS Engine clients at least once
            for event in new_events:
                self.event_store.move_to_existing(event['id'])
            return jsonify({'events': events}), 200

        return jsonify({'message': f'Invalid event status: {event_status}'}), 400


class AppWrapper:
    """Web server class wrapping Flask operations"""
    def __init__(self, base_dir: str):
        """Build Flask app instance, mapping handler to each endpoint"""
        self.app = Flask(__name__)

        health_route = HealthRoute()
        events_route = EventsRoute(base_dir)

        self.app.add_url_rule('/health', 'health', view_func=health_route.handler,
                              methods=['GET'])
        self.app.add_url_rule('/events', 'events',
                              view_func=events_route.handler,
                              methods=['GET', 'POST', 'DELETE'])

    def run(self, **kwargs):
        """Start up web server"""
        self.app.run(**kwargs)


def create_app(args: Namespace = None) -> Flask:
    base_dir = args.base_dir
    _wrapper = AppWrapper(base_dir)
    return _wrapper.app


if __name__ == '__main__':
    # TODO: command line args

    # host=0.0.0.0 is required for flask to work properly in docker and k8s env
    app = create_app()
    app.run(host='0.0.0.0', port=5000)

# TODO: gunicorn runtime
