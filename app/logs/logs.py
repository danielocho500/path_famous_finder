import logging
from enum import Enum
from pathlib import Path

LOG_FORMAT_DEBUG = "%(levelname)s | %(asctime)s | %(message)s | %(pathname)s:%(funcName)s:%(lineno)d"
LOG_FORMAT_SIMPLE = "%(levelname)s | %(message)s"

class LogLevels(Enum):
    """Enum for log levels."""
    info = logging.INFO
    warn = logging.WARN
    error = logging.ERROR
    debug = logging.DEBUG

def configure_logging(log_level: LogLevels = LogLevels.info):
    """Configure logging with auto-format selection based on level."""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    level_value = log_level.value

    log_format = LOG_FORMAT_DEBUG if log_level == LogLevels.debug else LOG_FORMAT_SIMPLE

    logging.basicConfig(
        level=level_value,
        format=log_format,
        handlers=[
            logging.FileHandler(logs_dir / "app.log"),
            logging.StreamHandler()
        ]
    )

    if log_level == LogLevels.debug:
        logging.basicConfig(level=level_value, format=LOG_FORMAT_DEBUG)
    else:
        logging.basicConfig(level=level_value, format=LOG_FORMAT_SIMPLE)
