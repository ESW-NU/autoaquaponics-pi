import pykka
from logs import register_logger

dummy_logger = register_logger("logs/dummy.log", "Dummy Logger")

class Dummy(pykka.ThreadingActor):
    def __init__(self, dummy_logger=dummy_logger):
        super().__init__()
        self.dummy_logger = dummy_logger
        self.dummy_logger.info("Dummy actor initialized")

    def on_start(self):
        self.dummy_logger.info("Starting dummy actor")

    def on_receive(self, message):
        self.dummy_logger.info(f"Received message: {message}")
        if message == "fail":
            raise Exception("Dummy actor failed")

    def on_failure(self, failure):
        self.dummy_logger.error(f"Dummy actor failed: {failure}")

    def on_stop(self):
        self.dummy_logger.info("Stopping dummy actor")

