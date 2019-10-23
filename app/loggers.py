import logging
import sys

import app.consts as consts


def setup_logger(name: str, level: int, fmt: str, datefmt: str) -> logging.Logger:
    """
    Setup a logger with the specified configuration and return it.

    Args:
        name (str): The name of the logger.
        level (int): The logging level.
        fmt (str): The format of the log message.
        datefmt (str): The format of the log date and time.

    Returns:
        logging.Logger: The configured logger.
    """
    # Create a logger with the specified name
    logger = logging.getLogger(name)

    # Create a stream handler to output log messages to stdout
    handler = logging.StreamHandler(sys.stdout)

    # Set the format of the log messages
    handler.setFormatter(logging.Formatter(fmt, datefmt))

    # Add the handler to the logger
    logger.addHandler(handler)

    # Set the logging level of the logger
    logger.setLevel(level)

    # Return the configured logger
    return logger


# Setting up the 'log' logger
log_format = "%(asctime)s | %(levelname)s | %(message)s"
log_datefmt = "%Y-%m-%d %H:%M:%S"

log = setup_logger(__name__, getattr(consts, "LOG_LEVEL", "INFO"), log_format, log_datefmt)
