import logging
import logging.handlers
from datetime import datetime
import time

def setup_logger(log_file, subsystem_name):
    logger = logging.getLogger(subsystem_name)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(module)s: %(message)s",
    )

    handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when="midnight",
        backupCount=30,
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger

_global_log_file = "autoaquaponics.log"
global_logger = setup_logger(_global_log_file, "AutoAquaponics System")
global_logger.info("logger setup complete")
