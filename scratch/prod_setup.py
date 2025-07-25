import logging
import os
import sys

from backend.config import Config
from utils.logger import setup_logging, VERBOSE_LEVEL_NUM

def prod_setup(console_only=False, logs_dir="logs"):
    # setup logging
    setup_logging(logs_dir, console_level=logging.INFO,
                  file_level=VERBOSE_LEVEL_NUM, console_only=console_only)

    try:
        config = Config("configs/config.yaml")
    except Exception as e:
        logging.error(f"Failed to load config: {e}")
        sys.exit(1)
