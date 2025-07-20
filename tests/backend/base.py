import logging
import os
import pytest
import shutil
from dotenv import load_dotenv

from backend.config import Config
from backend.utils import json_dumps
from utils import logger

initialized = False

TEST_BASE_DIR = None
TEST_LOGS_DIR = None

def get_test_base_dir():
    """
    Returns the base directory for tests.
    This is set in the .env file.
    """
    if TEST_BASE_DIR is None:
        raise ValueError("TEST_BASE_DIR is not set. Please check your .env file.")
    return TEST_BASE_DIR

@pytest.fixture(scope="session", autouse=True)
def initialise():
    """
    Sample .env file content:
    ROOT_DIR=${HOME}/cataloguesearch # set the full directory path, not just the var
    TEST_BASE_DIR=${ROOT_DIR}/tests
    TEST_DATA_DIR=${TEST_BASE_DIR}/data
    """
    global initialized
    global TEST_BASE_DIR
    global TEST_LOGS_DIR

    if initialized:
        return

    load_dotenv(
        dotenv_path="%s/.env" % os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))),
        verbose=True)

    TEST_BASE_DIR = os.getenv("TEST_BASE_DIR")
    TEST_LOGS_DIR = "%s/test_logs" % TEST_BASE_DIR

    if TEST_BASE_DIR is None or TEST_LOGS_DIR is None:
        raise ValueError(
            f"TEST_BASE_DIR or TEST_LOGS_DIR is not set. "
            f"Please set these in your .env file."
            f".env file should be in the same directory from where you run the tests.")

    # initialize the config
    config = Config("%s/data/configs/test_config.yaml" % TEST_BASE_DIR)

    # Setup logging once for all tests
    logger.setup_logging(
        logs_dir=TEST_LOGS_DIR, console_level=logger.VERBOSE_LEVEL_NUM,
        file_level=logger.VERBOSE_LEVEL_NUM, console_only=True)

    logging.getLogger(__name__).info(
        f"Config initialised: {json_dumps(config._settings)}"
    )

    yield

    shutil.rmtree(TEST_LOGS_DIR, ignore_errors=True)