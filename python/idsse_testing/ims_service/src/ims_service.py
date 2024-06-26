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

from glob import glob
from os import path

from flask import Flask, request, jsonify

app = Flask(__name__)
app.config['GSL_KEY'] = '8209c979-e3de-402e-a1f5-556d650ab889'

# The joined profiles from the JSON examples...
ims_request = {'errors': [], 'profiles': []}


@app.route('/all-events', methods=['GET'])
def profiles():
    # First check for the key argument and that it matches the expected value...
    if request.headers.get("X-Api-Key") != app.config['GSL_KEY']:
        return jsonify({"message": "ERROR: Unauthorized"}), 401

    if len(request.args.keys()) != 1 or request.args.get('dataSource') != 'NBM':
        # add one more check for ANY (currently IMS Gateway Request is using 'ANY')
        if request.args.get('dataSource') != 'ANY':
            return jsonify({"message": "Bad Request : Invalid argument!"}), 400

    # Return the profiles...
    return jsonify(ims_request)


@app.route('/ims-response', methods=['POST'])
def response():
    # First check for the key argument and that it matches the expected value...
    if request.headers.get("X-Api-Key") != app.config['GSL_KEY']:
        return jsonify({"message": "ERROR: Unauthorized"}), 401

    data = request.get_json()  # Assumes the incoming data is in JSON format
    print("Received POST request with data:", data)

    # Process the data or perform any desired actions
    return jsonify({"message": "POST request received successfully!"})


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

    # host=0.0.0.0 is required for flask to work properly in docker and k8s env
    app.run(host='0.0.0.0', port=5000)
