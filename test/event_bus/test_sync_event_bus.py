import unittest

from loguru import logger

from flashboot_core.event_bus import sync_event_bus


class TestSyncEventBus(unittest.TestCase):

    def setUp(self) -> None:
        sync_event_bus.subscribe("test", self.self_on)
        sync_event_bus.subscribe("test", self.on)

    def self_on(self, data):
        logger.info(data)

    @staticmethod
    def on(data):
        logger.info(data)

    def test_emit(self):
        sync_event_bus.emit("test", data="something")
