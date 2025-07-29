import sys

from dotenv import load_dotenv

from backend.common import embedding_models, opensearch
from backend.crawler.discovery import Discovery
from backend.crawler.index_state import IndexState
from backend.index.embedding_module import IndexingEmbeddingModule
from backend.crawler.pdf_processor import PDFProcessor
from backend.search.index_searcher import IndexSearcher
from tests.backend.common import setup
from backend.common.opensearch import get_opensearch_client
from backend.config import Config
from utils import logger
import logging
from backend.utils import json_dumps

import os

from utils.logger import setup_logging, VERBOSE_LEVEL_NUM

log_handle = logging.getLogger(__name__)

class MockPDFProcessor(PDFProcessor):
    def __init__(self, config: Config):
        """
        Initializes the MockPDFProcessor with a given configuration.
        """
        super().__init__(config)

    def process_pdf(self, pdf_path: str, output_dir: str, images_dir: str):
        """
        1. Return the page_text_paths from the BASE_TEXT_PATH
        2. Return the bookmarks of the PDF file
        Returns the repsonse.
        """
        relpath = os.path.relpath(pdf_path, Config().BASE_PDF_PATH)
        relpath = os.path.splitext(relpath)[0]
        log_handle.info(f"relpath: {relpath}")
        output_text_folder = os.path.join(
            self._output_text_folder, relpath)
        log_handle.info(f"output_text_folder: {output_text_folder}")

        # get the sorted list of text files in the output_text_folder
        page_text_paths = sorted([
            os.path.join(output_text_folder, f) for f in os.listdir(output_text_folder)
            if f.endswith('.txt')
        ])

        # fetch bookmarks from the PDF file
        bookmarks = self.fetch_bookmarks(pdf_path)

        return page_text_paths, bookmarks

def init():
    # Reset Config singleton for each test module
    Config.reset()
    """
    Sample .env file content:
    ROOT_DIR=${HOME}/cataloguesearch # set the full directory path, not just the var
    TEST_BASE_DIR=${ROOT_DIR}/tests
    TEST_DATA_DIR=${TEST_BASE_DIR}/data
    """
    global initialized
    global TEST_BASE_DIR
    global TEST_LOGS_DIR
    global TEST_DATA_DIR

    load_dotenv(
        dotenv_path="/Users/r0j08wt/github/rajatjain/cataloguesearch/tests/.env",
        verbose=True)

    TEST_BASE_DIR = os.getenv("TEST_BASE_DIR")
    TEST_LOGS_DIR = "%s/test_logs" % TEST_BASE_DIR
    TEST_DATA_DIR = "%s/data" % TEST_BASE_DIR

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

def build_index():
    setup(copy_text_files=True)
    config = Config()
    pdf_processor = MockPDFProcessor(config)
    opensearch_client = get_opensearch_client(config, force_clean=True)
    discovery = Discovery(
        config, IndexingEmbeddingModule(config, opensearch_client),
        pdf_processor, IndexState(config.SQLITE_DB_PATH)
    )

    # Crawl
    log_handle.info("Starting crawling")
    discovery.crawl()

def vector_search(query):
    config = Config()
    index_searcher = IndexSearcher(config)

    embedding = embedding_models.get_embedding(config.EMBEDDING_MODEL_NAME, query)
    if embedding is None:
        log_handle.error("Embedding for the query could not be generated.")
        return
    log_handle.info(f"Running basic vector query: {query}")
    results, _ = index_searcher.perform_vector_search(
        embedding, {}, 10, 1, "hi")
    log_handle.info(f"Results: {json_dumps(results)}")

def lexical_search(query, categories={}):
    config = Config()
    index_searcher = IndexSearcher(config)
    log_handle.info(f"Index Name: {config.OPENSEARCH_INDEX_NAME}")

    log_handle.info(f"Running basic lexical query: {query}")
    results, _ = index_searcher.perform_lexical_search(
        query, 50, categories, "hi", 10, 1)
    log_handle.info(f"Results: {json_dumps(results)}")

def prod_setup():
    # setup logging
    logs_dir = os.getenv("HOME", "") + "/cataloguesearch/logs/discovery"
    setup_logging(logs_dir, console_level=logging.INFO,
                  file_level=VERBOSE_LEVEL_NUM, console_only=False)

    try:
        config = Config("configs/config.yaml")
    except Exception as e:
        logging.error(f"Failed to load config: {e}")
        sys.exit(1)


def main():
    prod_setup()
    query = "मुनिराज चश्मा"
    # lexical_search(query)
    vector_search(query)

def are_dicts_same(dict1: dict[str, list[str]], dict2: dict[str, list[str]]) -> bool:
    """
    Compares two dictionaries of the format {str: list[str]} to ensure they are the same,
    regardless of key order or element order within the lists.

    Args:
        dict1: The first dictionary.
        dict2: The second dictionary.

    Returns:
        True if the dictionaries are considered the same, False otherwise.
    """

    # 1. Check if the sets of keys are identical
    if set(dict1.keys()) != set(dict2.keys()):
        return False

    # 2. Iterate through keys and compare their corresponding lists
    for key in dict1:
        list1 = dict1[key]
        list2 = dict2[key]

        # Check if the lengths of the lists are the same
        if len(list1) != len(list2):
            return False

        # Convert lists to sets for order-independent comparison of elements
        if set(list1) != set(list2):
            return False

    return True

def get_documents_tags():
    prod_setup()
    config = Config()
    metadata = opensearch.get_metadata(config)

    log_handle.info(f"Metadata: {json_dumps(metadata)}")

    index_state = IndexState(config.SQLITE_DB_PATH)
    index_state.update_metadata_cache(metadata)

    met = index_state.get_metadata_cache()
    log_handle.info(f"Metadata from IndexState: {json_dumps(met)}")

    log_handle.info(f"Are two dicts same? {are_dicts_same(metadata, met)}")

    # compare the two dicts and ensure they are the same


get_documents_tags()