import logging
import os
import pytest

from backend.config import Config
from tests.backend.base import *

log_handle = logging.getLogger(__name__)


def test_config_instance():
    """
    Tests that the Config instance is created correctly and has expected attributes.
    """
    config = Config()
    index_name = os.getenv("INDEX_NAME")

    assert isinstance(config, Config)
    assert config.BASE_PDF_PATH == "%s/cataloguesearch/pdfs" % get_test_data_dir()
    assert config.BASE_TEXT_PATH == "%s/cataloguesearch/text" % get_test_data_dir()
    assert config.CHUNK_SIZE == 100
    assert config.CHUNK_OVERLAP == 20
    assert config.OPENSEARCH_HOST == "localhost"
    assert config.OPENSEARCH_PORT == 19200
    assert config.OPENSEARCH_USERNAME == "admin"
    assert config.OPENSEARCH_PASSWORD == "Admin@Password123!"
    assert config.OPENSEARCH_INDEX_NAME == index_name
    assert config.EMBEDDING_MODEL_NAME == "sentence-transformers/all-MiniLM-L6-v2"
    assert config.LLM_MODEL_NAME == "gemini-2.0-flash"
    log_handle.info(f"END TEST_CONFIG_INSTANCE")
