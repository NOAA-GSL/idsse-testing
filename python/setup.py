"""Setup to support installation as Python library"""
import glob
import os
from setuptools import setup

def package_files(directory):
    paths = []
    for (path, directories, filenames) in os.walk(directory):
        for filename in filenames:
            paths.append(os.path.join(path, filename))
    print(paths)
    return paths


print(package_files('idsse_testing/data_access/data_cache'))

setup(name='idsse-testing',
      version='1.0',
      description='IDSSe Common Test Data and External Proxies',
      url='',
      author='WIDS',
      author_email='@noaa.gov',
      license='MIT',
      python_requires=">=3.11",
      packages=['idsse_testing.data_access',
                'idsse_testing.data_access.data_cache',
                'idsse_testing.data_access.mrms_aws_grib',
                'idsse_testing.data_access.nbm_aws_grib',
                'idsse_testing.event_portfolios',
                'idsse_testing.ims_request',
                'idsse_testing.ims_response',
                'idsse_testing.ims_service',
                'idsse_testing.risk_processor',
                'idsse_testing.risk_processor.binghamton',
                'idsse_testing.risk_processor.i87',
                'idsse_testing.risk_processor.simple',
		'idsse_testing.risk_processor.syracuse',
                'idsse_testing.utilities'],
      data_files=[('idsse_testing.data_access.data_cache', package_files('idsse_testing/data_access/data_cache')),
                  ('idsse_testing.data_access.mrms_aws_grib', package_files('idsse_testing/data_access/mrms_aws_grib')),
                  ('idsse_testing.data_access.nbm_aws_grib', package_files('idsse_testing/data_access/nbm_aws_grib'))],
      include_package_data=True,
      package_data={'':['*.csv', '*.json', '*.nc', '*.grib2*'],},
      install_requires=[
        'importlib',
        'pika',
        'jsonschema',
	'netcdf4',
	'h5netcdf',
        'python-logging-rabbitmq'
      ],
      extras_require={
        'develop': [
          'pytest',
          'pytest-cov',
        ]
      },
      zip_safe=False,
)
