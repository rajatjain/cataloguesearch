import logging
import os
from logging.handlers import RotatingFileHandler

VERBOSE_LEVEL_NUM = 15
logging.addLevelName(VERBOSE_LEVEL_NUM, "VERBOSE")

def verbose(self, message, *args, **kws):
    if self.isEnabledFor(VERBOSE_LEVEL_NUM):
        # Call self.log with stacklevel=2. This tells the logging module to go
        # two frames up the call stack (past this function) to find the
        # original call site for getting the correct filename and line number.
        self.log(VERBOSE_LEVEL_NUM, message, *args, stacklevel=2, **kws)

logging.Logger.verbose = verbose

def setup_logging(logs_dir="logs",
                  console_level=VERBOSE_LEVEL_NUM,
                  file_level=logging.DEBUG,
                  console_only=True):
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    # Added %(filename)s to show the source file and %(funcName)s for the function.
    # Replaced %(name)s with the more informative filename.
    log_format = '[%(asctime)s %(levelname)s - %(filename)s:%(funcName)s : %(lineno)d] %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    root_logger = logging.getLogger()
    root_logger.setLevel(min(console_level, file_level, VERBOSE_LEVEL_NUM))

    # Clear existing handlers
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    root_logger.addHandler(console_handler)

    if not console_only:
        # Set up two file handlers: one for INFO+, one for VERBOSE+
        info_log_path = os.path.join(logs_dir, "info.log")
        verbose_log_path = os.path.join(logs_dir, "verbose.log")

        info_handler = RotatingFileHandler(
            info_log_path, maxBytes=5*1024*1024, backupCount=5
        )
        info_handler.setLevel(logging.INFO)
        info_handler.setFormatter(logging.Formatter(log_format, date_format))
        root_logger.addHandler(info_handler)

        verbose_handler = RotatingFileHandler(
            verbose_log_path, maxBytes=5*1024*1024, backupCount=5
        )
        verbose_handler.setLevel(VERBOSE_LEVEL_NUM)
        verbose_handler.setFormatter(logging.Formatter(log_format, date_format))
        root_logger.addHandler(verbose_handler)