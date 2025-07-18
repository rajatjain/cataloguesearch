import pytest
import os

from dotenv import load_dotenv

from backend.config import Config
import logging
from utils import logger

load_dotenv(
    dotenv_path="%s/.env" % os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))),
    verbose=True)

"""
Sample .env file content:
ROOT_DIR=${HOME}/cataloguesearch # set the full directory path, not just the var
TEST_BASE_DIR=${ROOT_DIR}/tests
TEST_DATA_DIR=${TEST_BASE_DIR}/data
"""

TEST_BASE_DIR = os.getenv("TEST_BASE_DIR")
TEST_DATA_DIR = os.getenv("TEST_DATA_DIR")

TEST_LOGS_DIR = "%s/test_logs" % TEST_BASE_DIR

# Setup logging once for all tests
logger.setup_logging(
    logs_dir=TEST_LOGS_DIR, console_level=logger.VERBOSE_LEVEL_NUM,
    file_level=logger.VERBOSE_LEVEL_NUM)

log_handle = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def config():
    """
    Fixture to provide a Config instance for tests.
    This will load the configuration from the specified file.
    """

    TEST_BASE_DIR = os.getenv("TEST_BASE_DIR")
    TEST_DATA_DIR = os.getenv("TEST_DATA_DIR")
    log_handle.info(f"TEST_BASE_DIR: {TEST_BASE_DIR}")
    log_handle.info(f"TEST_DATA_DIR: {TEST_DATA_DIR}")


    config_file_path = "%s/test_config.yaml" % TEST_DATA_DIR
    if not os.path.exists(config_file_path):
        raise FileNotFoundError(f"Config file not found: {config_file_path}")

    return Config(config_file_path)

def test_config_instance(config):
    """
    Tests that the Config instance is created correctly and has expected attributes.
    """
    assert isinstance(config, Config)
    assert config.BASE_PDF_PATH == "%s/cataloguesearch/pdfs" % TEST_DATA_DIR
    assert config.BASE_TEXT_PATH == "%s/cataloguesearch/text" % TEST_DATA_DIR
    assert config.CHUNK_SIZE == 500
    assert config.CHUNK_OVERLAP == 50
    assert config.OPENSEARCH_HOST == "localhost"
    assert config.OPENSEARCH_PORT == 9200
    assert config.OPENSEARCH_USERNAME == "admin"
    assert config.OPENSEARCH_PASSWORD == "password"
    assert config.OPENSEARCH_INDEX_NAME == "document_chunks_unit_test"
    assert config.EMBEDDING_MODEL_NAME == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    assert config.LLM_MODEL_NAME == "gemini-2.0-flash"