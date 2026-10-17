"""User Service RabbitMQ topology tests."""

from app.messaging import (
    EXCHANGE,
)
from app.worker import declare_topology


class FakeChannel:
    def __init__(self):
        self.exchanges = []
        self.queues = []
        self.bindings = []

    def exchange_declare(self, **kwargs):
        self.exchanges.append(kwargs)

    def queue_declare(self, **kwargs):
        self.queues.append(kwargs)

    def queue_bind(self, queue, exchange, routing_key):
        self.bindings.append((queue, exchange, routing_key))


def test_user_producer_declares_only_the_shared_exchange() -> None:
    channel = FakeChannel()

    declare_topology(channel)

    assert channel.exchanges == [
        {"exchange": EXCHANGE, "exchange_type": "topic", "durable": True}
    ]
    assert channel.queues == []
    assert channel.bindings == []
