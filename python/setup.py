"""Setup to support installation as Python library"""
import glob
from setuptools import setup

setup(name='idsse-testing',
      version='1.0',
      description='IDSSe Common Test Data and External Proxies',
      url='',
      author='WIDS',
      author_email='@noaa.gov',
      license='MIT',
      python_requires=">=3.11",
      packages=['idsse_testing.event_portfolios',
                'idsse_testing.ims_request',
                'idsse_testing.ims_response',
                'idsse_testing.ims_service',
                'idsse_testing.risk_processor',
                'idsse_testing.risk_processor.binghamton',
                'idsse_testing.risk_processor.i87',
                'idsse_testing.risk_processor.simple',
		'idsse_testing.risk_processor.syracuse',
                'idsse_testing.utilities'],
      data_files=[('idsse_testing/event_portfolios', glob.glob('event_portfolios/*.json')),
                  ('idsse_testing/ims_response', glob.glob('ims_response/*.json')),
                  ('idsse_testing/ims_request', glob.glob('ims_request/*.json'))],
      include_package_data=True,
      package_data={'':['*.json', '*.nc']},
      install_requires=[
        'importlib',
        'pika',
        'jsonschema',
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
