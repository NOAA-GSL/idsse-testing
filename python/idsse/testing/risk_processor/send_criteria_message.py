"""Standalone python script useful for emitting an example criteria message to RabbitMQ

Every command line argument has a sane default; you should only need to change --path:

python3 python/risk_processor/test/resources/send_criteria_message.py \
    --path python/risk_processor/test/resources/simple/criteria_single_temp.json \
    --host rabbitmq_host \
    --username rabbitmq_user \
    --password rabbitmq_password \
    --port rabbitmq_port \
    --criteria_exchange some_exchange_name \
    --criteria_exch_type some_exch_type \
    --criteria_queue some_queue_name
"""
# ------------------------------------------------------------------------------
# Created on Mon Nov 6 2023
#
# Copyright (c) 2023 Colorado State University. All rights reserved.             (1)
# Copyright (c) 2023 Regents of the University of Colorado                       (2)
#
# Contributors:
#     Mackenzie Grimes (1)
#
# ------------------------------------------------------------------------------
# pylint: disable=duplicate-code

import argparse
import json
import logging.config
import logging
import sys

from pika import BasicProperties

from idsse.common.log_util import get_default_log_config
from idsse.common.rabbitmq_utils import Conn, Queue, Exch, RabbitMqParams

logger = logging.getLogger(__name__)


class CriteriaPublisher:
    """Simple RabbitMQ message publisher for sending criteria using JSON file"""
    def __init__(self, conn: Conn, rabbitmq_params: RabbitMqParams):
        """
        Args:
            connection (Conn): connection parameters for RabbitMQ host
            rabbitmq_params (RabbitMqParams): parameters for RabbitMQ exchange and queue
        """
        self._params = rabbitmq_params
        logger.debug('Making connection to host %s with queue_name %s',
                     conn.host, self._params.queue.name)
        self._connection = conn.to_connection()
        self._channel = self._connection.channel()

    def send_criteria(self, criteria_path: str) -> bool:
        """Execute sending criteria message to RabbitMQ queue

        Args:
            criteria_path (str): Path of criteria JSON file to send as message

        Returns:
            True on message published successfully
        """
        if self._channel is None or self._channel.is_closed:
            logger.warning('RabbitMQ channel unavailable or not open, cannot publish message')
            return False

        # build message and publish
        try:
            with open(criteria_path, 'r', encoding='utf-8') as file_data:
                message = json.load(file_data)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.error('Did not find valid JSON file at path %s', criteria_path)
            return False

        logger.debug('Publishing message: %s', message)
        try:
            self._channel.basic_publish(
                exchange=self._params.exchange.name,
                routing_key=self._params.queue.route_key,
                properties=BasicProperties(content_type='application/json'),
                body=json.dumps(message)
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error(exc)
            return False

        logger.info('Message publish succeeded')
        return True

    def shutdown(self):
        """Graceful shutdown of RabbitMQ connection"""
        logger.debug('Closing RabbitMQ connection')
        if self._channel is not None:
            self._channel.close()
        if self._connection is not None:
            self._connection.close()


def main(args: argparse.Namespace | None = None):
    """Entry point for script to send criteria message to queue"""
    conn = Conn(args.host, args.v_host, args.port, args.username, args.password)
    exch = Exch(name=args.criteria_exchange, type=args.criteria_exch_type)
    queue = Queue(
        name=args.criteria_queue,
        route_key='',
        durable=args.durable,
        auto_delete=args.auto_del,
        exclusive=args.exclusive
    )

    logger.info('Args: %s', args)
    criteria_path = args.path

    try:
        publisher = CriteriaPublisher(conn, RabbitMqParams(exch, queue))
        success = publisher.send_criteria(criteria_path)
        logger.warning('Criteria from %s, status: %s', criteria_path,
                       'PUBLISHED' if success else 'FAILED_TO_PUBLISH')
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error(exc)
        success = False
    finally:
        publisher.shutdown()

    sys.exit(0 if success else 1)


if __name__ == '__main__':  # pragma: no cover
    logging.config.dictConfig(get_default_log_config('WARN'))

    # parse command line arguments
    parser = argparse.ArgumentParser()

    # RabbitMQ host parameters
    parser.add_argument('--host', dest='host', default='localhost',
                        help='The host name or address of the RabbitMQ server to connect to.')
    parser.add_argument('--vhost', dest='v_host', default='/',
                        help='The virtual host name or address of the RabbitMQ server.')
    parser.add_argument('--port', dest='port', default=5672,
                        help='The port of the RabbitMQ server.')
    parser.add_argument('--username', dest='username', default="guest",
                        help='The RabbitMQ server username to use to establish a connection')
    parser.add_argument('--password', dest='password', default="guest",
                        help='The RabbitMQ server password to use to establish a connection')

    parser.add_argument('--durable', dest='durable', default=True,
                        action=argparse.BooleanOptionalAction,
                        help='If the queue should be durable')
    parser.add_argument('--exclusive', dest='exclusive', default=False,
                        action=argparse.BooleanOptionalAction,
                        help='If the queue should be exclusive')
    parser.add_argument('--autodelete', dest='auto_del', default=False,
                        action=argparse.BooleanOptionalAction,
                        help='If the queue should auto delete')

    # Criteria RabbitMQ parameters
    parser.add_argument('--criteria_exchange', dest='criteria_exchange', default='criteria_data',
                        help='The exchange name to which this service will publish Criteria data.')
    parser.add_argument('--criteria_exch_type', dest='criteria_exch_type', default='direct',
                        help='The exchange type for Criteria data.')
    parser.add_argument('--criteria_queue', dest='criteria_queue', default='criteria_data',
                        help='The queue where Criteria data will be published.')

    parser.add_argument('--path', dest='path',
                        default=('python/risk_processor/test/resources/simple'
                                 '/criteria_single_temp.json'),
                        help='Path to criteria JSON file.')
    main(parser.parse_args())
