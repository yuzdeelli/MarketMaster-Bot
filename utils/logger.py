import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "market_master.log")

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(threadName)s | %(message)s"
)

_logger = logging.getLogger("MarketMaster")
_logger.setLevel(logging.INFO)

_file_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(formatter)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(formatter)

_logger.addHandler(_file_handler)
_logger.addHandler(_console_handler)


def get_logger():
    return _logger
