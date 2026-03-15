import json

import pika

from .config import settings


def _credentials() -> pika.PlainCredentials:
    return pika.PlainCredentials(settings.rabbitmq_user, settings.rabbitmq_password)


def _connection() -> pika.BlockingConnection:
    parameters = pika.ConnectionParameters(
        host=settings.rabbitmq_host,
        port=settings.rabbitmq_port,
        credentials=_credentials(),
        heartbeat=30,
    )
    return pika.BlockingConnection(parameters)


def ensure_queue() -> None:
    connection = _connection()
    channel = connection.channel()
    channel.queue_declare(queue=settings.rabbitmq_queue, durable=True)
    connection.close()


def publish_job(job_id: str) -> None:
    connection = _connection()
    channel = connection.channel()
    channel.queue_declare(queue=settings.rabbitmq_queue, durable=True)
    channel.basic_publish(
        exchange="",
        routing_key=settings.rabbitmq_queue,
        body=json.dumps({"job_id": job_id}),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    connection.close()

