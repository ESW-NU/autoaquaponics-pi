import logging
import logging.handlers

"""
This module sets up logging for the AutoAquaponics system.

# Function
    `setup_logger(log_file, subsystem_name)`
        Configures and returns a logger for a given subsystem.

# Variables
    - `_global_log_file: str`: The default log file name for the global logger.
    - `global_logger: logging.Logger`: The global logger instance for the
    AutoAquaponics system. This is instantiated when this module is first
    imported, and other modules can import this logger and use it to log
    messages.
"""

def setup_logger(log_file, subsystem_name):
    logger = logging.getLogger(subsystem_name)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s in module `%(module)s`: %(message)s",
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
