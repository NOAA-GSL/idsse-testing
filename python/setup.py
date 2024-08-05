"""Setup to support installation as Python library"""
import glob
import os
from setuptools import setup

def package_files(directory):
    paths = []
    for (path, directories, filenames) in os.walk(directory):
        for filename in filenames:
            paths.append(os.path.join(path, filename))
    print(directory, paths)
    return paths

setup(name='idsse-testing',
      version='1.0',
      description='IDSSe Common Test Data and External Proxies',
      url='',
      author='WIDS',
      author_email='@noaa.gov',
      license='MIT',
      python_requires=">=3.11",
      packages=['idsse.testing.data_access',
                'idsse.testing.data_access.data_cache',
                'idsse.testing.data_access.mrms_aws_grib',
                'idsse.testing.data_access.nbm_aws_grib',
                'idsse.testing.event_portfolios',
                'idsse.testing.ims_request',
                'idsse.testing.ims_response',
                'idsse.testing.ims_service',
                'idsse.testing.risk_processor',
                'idsse.testing.risk_processor.binghamton',
                'idsse.testing.risk_processor.i87',
                'idsse.testing.risk_processor.simple',
                'idsse.testing.risk_processor.syracuse',
                'idsse.testing.utils'],
      data_files=[('idsse.testing.data_access.data_cache', package_files('idsse/testing/data_access/data_cache')),
                  ('idsse.testing.data_access.mrms_aws_grib', package_files('idsse/testing/data_access/mrms_aws_grib')),
                  ('idsse.testing.data_access.nbm_aws_grib', package_files('idsse/testing/data_access/nbm_aws_grib'))],
      include_package_data=True,
      package_data={'':['*.csv', '*.json', '*.nc', '*.grib2*'],
                    'idsse.testing.data_access.data_cache': package_files('idsse/testing/data_access/data_cache'),
                    'idsse.testing.data_access.mrms_aws_grib': package_files('idsse/testing/data_access/mrms_aws_grib'),
                    'idsse.testing.data_access.nbm_aws_grib': package_files('idsse/testing/data_access/nbm_aws_grib')},
      install_requires=[
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
