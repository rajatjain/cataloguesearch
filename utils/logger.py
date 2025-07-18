import logging
import os
from logging.handlers import RotatingFileHandler

VERBOSE_LEVEL_NUM = 15
logging.addLevelName(VERBOSE_LEVEL_NUM, "VERBOSE")

def verbose(self, message, *args, **kws):
    if self.isEnabledFor(VERBOSE_LEVEL_NUM):
        self._log(VERBOSE_LEVEL_NUM, message, args, **kws)

logging.Logger.verbose = verbose

def setup_logging(logs_dir="logs",
                  console_level=VERBOSE_LEVEL_NUM,
                  file_level=logging.DEBUG,
                  console_only=True):
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    log_format = '[%(asctime)s %(levelname)s - %(name)s : %(lineno)d] %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    root_logger = logging.getLogger()
    root_logger.setLevel(min(console_level, file_level))

    # Clear existing handlers
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    root_logger.addHandler(console_handler)

    # Module-specific loggers and file handlers
    modules = ["discovery_module", "indexing_embedding_module", "config_parser", "pdf_processor"]
    for module_name in modules:
        logger = logging.getLogger(module_name)
        logger.setLevel(min(console_level, file_level))

        if not console_only:
            log_file_path = os.path.join(logs_dir, f"{module_name}.log")
            file_handler = RotatingFileHandler(
                log_file_path,
                maxBytes=10*1024*1024,
                backupCount=5
            )
            file_handler.setLevel(file_level)
            file_handler.setFormatter(logging.Formatter(log_format, date_format))
            logger.addHandler(file_handler)