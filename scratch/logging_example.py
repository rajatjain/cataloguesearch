import logging
import os
import tempfile
from utils.logger import setup_logging, VERBOSE_LEVEL_NUM

# Example Usage:
if __name__ == "__main__":
    HOME = os.getenv("HOME")
    log_dir = "%s/tmp" % HOME
    # To see VERBOSE messages on the console
    setup_logging(logs_dir=log_dir, console_level=VERBOSE_LEVEL_NUM)

    test_logger = logging.getLogger(__name__)

    test_logger.critical("This is a critical message.")
    test_logger.error("This is an error message.")
    test_logger.warning("This is a warning message (using 'warning').")
    test_logger.info("This is an info message.")
    test_logger.verbose("This is a verbose message.") # Custom verbose level
    test_logger.debug("This is a debug message.")

    print("\nCheck 'logs/test_module.log' for all messages.")
    print("Console output will now show VERBOSE and higher messages by default.")

    # To set the console level to INFO instead
    # setup_logging(console_level=logging.INFO)
    # test_logger.info("This is another info message after reconfiguring.")
    # test_logger.verbose("This verbose message will NOT appear on the console now.")

