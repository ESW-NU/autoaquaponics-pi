import logging
import logging.handlers
import atexit

"""
This module sets up logging for the AutoAquaponics system.

# Function
    `register_logger(log_file, subsystem_name)`
        Configures and returns a logger for a given subsystem.

# Variables
    - `global_logger: logging.Logger`: The global logger instance for the
    AutoAquaponics system. This is instantiated when this module is first
    imported, and other modules can import this logger and use it to log
    messages.
"""

formatter = logging.Formatter(
    "%(asctime)s %(levelname)s in module `%(module)s`: %(message)s",
)

def register_logger(log_file, subsystem_name):
    logger = logging.getLogger(subsystem_name)
    logger.setLevel(logging.DEBUG)

    handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when="midnight",
        backupCount=30,
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # indicate start and end of logging
    logger.info("======================= START LOGGING =======================")
    atexit.register(lambda: logger.info("======================= END LOGGING ======================="))

    return logger

global_logger = register_logger("logs/global.log", "AutoAquaponics System")
pykka_logger = register_logger("logs/pykka.log", "pykka") # pykka uses the `pykka` logger name
global_logger.info("logger setup complete")
