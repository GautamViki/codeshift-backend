import logging
import os
from pathlib import Path
from logging.handlers import WatchedFileHandler

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"


def setup_logger(name: str = "transpiler") -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:  # avoid duplicate helpers on reload
        return logger

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Only write to file (and echo to console) in local/dev
    if os.getenv("ENVIRONMENT", "development") == "development":
        file_handler = WatchedFileHandler(LOG_FILE, mode="a", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

    return logger


logger = setup_logger()