"""Test service for ims_gateway services"""
# ----------------------------------------------------------------------------------
# Created on Fri Apr 07 2023
#
# Copyright (c) 2023 Colorado State University. All rights reserved.             (1)
#
# Contributors:
#     Paul Hamer (1)
#
# ----------------------------------------------------------------------------------
# pylint: disable=missing-function-docstring,redefined-outer-name,protected-access
# pylint: disable=unused-argument, disable=duplicate-code
import json
import logging
import os

from glob import glob
from os import path

from flask import Flask, Response, request, jsonify, current_app
from flask_cors import CORS

# The joined profiles from the JSON examples...
ims_request = {'errors': [], 'profiles': []}

logger = logging.getLogger(__name__)

# URLs that webserver will tell browsers to allow requests from (CORS setting)
ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'https://sites.gsl.noaa.gov'
]

class IMSService:
    
    def profiles(self) -> Response:
        print('----DEBUG----')
        print('Received GET request for all events, with headers:', request.headers)
        print('    request.args.keys are:', request.args.keys())
        print('DEBUG: request.headers.get("X-Api-Key") =', request.headers.get("X-Api-Key"))
        print('DEBUG: app.config["GSL_KEY"] =', app.config['GSL_KEY'])
        print('DEBUG: request.args.get("dataSource") =', request.args.get('dataSource'))

        # logger doesn't get printed in the deployed version for some reason
        # since mock-ims is a temporary service, I'm not going to spend time debugging this
        # and will just use print statements instead
        #logger.info('Received GET request for all events, with headers: %s', request.headers)
        #logger.info('    request.args.keys are: %s', request.args.keys())

        # First check for the key argument and that it matches the expected value...
        if request.headers.get("X-Api-Key") != app.config['GSL_KEY']:
            return jsonify({"message": "ERROR: Unauthorized"}), 401

        if len(request.args.keys()) != 1 or request.args.get('dataSource') != 'NBM':
            # add one more check for ANY (currently IMS Gateway Request is using 'ANY')
            if request.args.get('dataSource') != 'ANY':
                return jsonify({"message": "Bad Request : Invalid argument!"}), 400

        # Return the profiles...
        return jsonify(ims_request)

    def response(self) -> Response:
        # First check for the key argument and that it matches the expected value...
        if request.headers.get("X-Api-Key") != app.config['GSL_KEY']:
            return jsonify({"message": "ERROR: Unauthorized"}), 401

        data = request.get_json()  # Assumes the incoming data is in JSON format
        print("Received POST request with data:", data)

        # Process the data or perform any desired actions
        return jsonify({"message": "POST request received successfully!"})

class AppWrapper:
    """Web server class wrapping Flask app operations"""
    # pylint: disable=too-few-public-methods
    def __init__(self):
        """Build web app instance, mapping handler to endpoint"""
        self.app: Flask = Flask(__name__)
        # set CORS policy to allow specific origins on all endpoints
        CORS(self.app, methods=['OPTIONS', 'GET', 'POST'], origins=ALLOWED_ORIGINS)

        self._service = IMSService()

        # register endpoints
        self.app.add_url_rule('/all-events', methods=['GET'], view_func=self._service.profiles)
        self.app.add_url_rule(
            '/ims-response', methods=['POST'], view_func=self._service.response)

    def run(self, **kwargs):
        """Start up web server"""
        self.app.run(**kwargs)

def create_app() -> tuple[Flask, int]:
    """Entry point for the Flask web server to start"""
    wrapper = AppWrapper()

    return wrapper.app

if __name__ == '__main__':
    # Load the canned profiles from the resources directory into a single dictionary to form
    # one JSON response when queried by the IMS_request service.
    profile_dir = path.join(path.dirname(__file__), '..', 'profiles')
    json_files = [
        path.join(profile_dir, file)
        for file in glob('*.json', root_dir=profile_dir)
    ]

    print('Loading canned support profiles from:', json_files)
    # json_files = sorted(glob('../profiles/*.json'))
    for json_file in json_files:
        with open(json_file, 'r', encoding="utf-8") as jf:
            profile = json.load(jf)
            # print(profile)
            for err in profile['errors']:
                ims_request['errors'].append(err)
            for pro in profile['profiles']:
                ims_request['profiles'].append(pro)
            # ims_request = ims_request | {os.path.basename(json_file).strip('.json') : profile}

    print('Loaded profiles:', ims_request)

    app = create_app()
    # host=0.0.0.0 is required for flask to work properly in docker and k8s env
    app.run(host='0.0.0.0', port=5000)

# set up container run time with gunicorn
elif 'gunicorn' in os.getenv('SERVER_SOFTWARE', default=''): # pragma: no cover
    app = Flask(__name__)
    app.config['GSL_KEY'] = '8209c979-e3de-402e-a1f5-556d650ab889'

    print('TEST: Running from gunicorn main block')
    print(app.config['GSL_KEY'])
    print('----DEBUG----')
