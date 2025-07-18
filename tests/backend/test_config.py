import logging
import os
import pytest

from backend.config import Config
from tests.backend.base import *

log_handle = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def config(initialise):
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
    TEST_DATA_DIR = os.getenv("TEST_DATA_DIR")

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