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
                'idsse_testing.ims_response',
                'idsse_testing.ims_service',
                'idsse_testing.utilities'],
      data_files=[('idsse_testing/event_portfolios', glob.glob('event_portfolios/*.json')),
                  ('idsse_testing/ims_response', glob.glob('ims_response/*.json'))],
      include_package_data=True,
      package_data={'':['*.json']},
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
