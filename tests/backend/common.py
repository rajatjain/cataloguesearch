import logging
import os
import shutil
import tempfile
import uuid

from backend.common import opensearch
from backend.common.opensearch import get_opensearch_client
from backend.config import Config
from backend.crawler.index_state import IndexState
from backend.utils import json_dump, json_dumps

log_handle = logging.getLogger(__name__)

def write_config_file(file_name, config_data):
    """
    Write the given config data to a JSON file.
    """
    with open(file_name, 'w') as f:
        json_dump(config_data, f)
    log_handle.info(f"Config file written: {file_name}")

def get_doc_id(base_dir, file_path):
    relative_path = os.path.relpath(file_path, base_dir)
    doc_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, relative_path))
    return doc_id

def setup(copy_text_files=False):
    config = Config()
    base_dir = tempfile.mkdtemp(prefix="test_")
    pdf_dir = "%s/data/pdfs" % base_dir
    log_handle.info(f"Using base dir: {base_dir}, pdf dir: {pdf_dir}")
    config.settings()["crawler"]["base_pdf_path"] = pdf_dir
    config.settings()["crawler"]["base_text_path"] = "%s/data/texts" % base_dir
    config.settings()["crawler"]["tmp_images_path"] = "%s/data/tmp_images" % base_dir
    config.settings()["crawler"]["sqlite_db_path"] = "%s/crawl_state.db" % base_dir

    os.makedirs("%s/a/b/c" % pdf_dir, exist_ok=True)
    os.makedirs("%s/a/b/d" % pdf_dir, exist_ok=True)
    os.makedirs("%s/x/y/z" % pdf_dir, exist_ok=True)

    TEST_BASE_DIR = os.getenv("TEST_BASE_DIR")

    # copy files - using all new test files
    data_pdf_path = os.path.join(TEST_BASE_DIR, "data", "pdfs")
    bangalore_hindi = os.path.join(data_pdf_path, "bangalore_hindi.pdf")
    bangalore_gujarati = os.path.join(data_pdf_path, "bangalore_gujarati.pdf")
    hampi_hindi = os.path.join(data_pdf_path, "hampi_hindi.pdf")
    hampi_gujarati = os.path.join(data_pdf_path, "hampi_gujarati.pdf")
    indore_hindi = os.path.join(data_pdf_path, "indore_hindi.pdf")
    indore_gujarati = os.path.join(data_pdf_path, "indore_gujarati.pdf")
    jaipur_hindi = os.path.join(data_pdf_path, "jaipur_hindi.pdf")
    jaipur_gujarati = os.path.join(data_pdf_path, "jaipur_gujarati.pdf")
    songadh_hindi = os.path.join(data_pdf_path, "songadh_hindi.pdf")
    songadh_gujarati = os.path.join(data_pdf_path, "songadh_gujarati.pdf")

    abcbh = "%s/a/b/c/bangalore_hindi.pdf" % pdf_dir
    abcbg = "%s/a/b/c/bangalore_gujarati.pdf" % pdf_dir
    abhampi = "%s/a/b/hampi_hindi.pdf" % pdf_dir
    xyzhampi = "%s/x/y/z/hampi_gujarati.pdf" % pdf_dir
    abdindore = "%s/a/b/d/indore_hindi.pdf" % pdf_dir
    abjaipur = "%s/a/bangalore_hindi.pdf" % pdf_dir
    xjaipur = "%s/x/jaipur_gujarati.pdf" % pdf_dir
    xysongadh = "%s/x/y/songadh_hindi.pdf" % pdf_dir
    absongadh = "%s/a/b/songadh_gujarati.pdf" % pdf_dir
    xindore = "%s/x/indore_gujarati.pdf" % pdf_dir

    doc_ids = {
        "abcbh": [abcbh, get_doc_id(pdf_dir, abcbh)],
        "abcbg": [abcbg, get_doc_id(pdf_dir, abcbg)],
        "abhampi": [abhampi, get_doc_id(pdf_dir, abhampi)],
        "xyzhampi": [xyzhampi, get_doc_id(pdf_dir, xyzhampi)],
        "abdindore": [abdindore, get_doc_id(pdf_dir, abdindore)],
        "abjaipur": [abjaipur, get_doc_id(pdf_dir, abjaipur)],
        "xjaipur": [xjaipur, get_doc_id(pdf_dir, xjaipur)],
        "xysongadh": [xysongadh, get_doc_id(pdf_dir, xysongadh)],
        "absongadh": [absongadh, get_doc_id(pdf_dir, absongadh)],
        "xindore": [xindore, get_doc_id(pdf_dir, xindore)]
    }

    shutil.copy(bangalore_hindi, abcbh)
    shutil.copy(bangalore_gujarati, abcbg)
    shutil.copy(hampi_hindi, abhampi)
    shutil.copy(hampi_gujarati, xyzhampi)
    shutil.copy(indore_hindi, abdindore)
    shutil.copy(bangalore_hindi, abjaipur)
    shutil.copy(jaipur_gujarati, xjaipur)
    shutil.copy(songadh_hindi, xysongadh)
    shutil.copy(songadh_gujarati, absongadh)
    shutil.copy(indore_gujarati, xindore)

    # create config files with language metadata
    a = { "category": "a", "type": "t" }
    b = { "category": "b", "type": "t1" }
    # dir c is empty
    bhc = { "type": "t2", "new": "c3", "language": "hindi" }

    # dir d is empty

    x = { "category": "x", "type": "tx" }
    y = { "category": "y", "type": "ty" }
    z = { "category": "z", "type": "tz" }
    jgx = { "type": "t3", "new": "c4", "language": "gujarati" }

    write_config_file("%s/a/config.json" % pdf_dir, a)
    write_config_file("%s/a/b/config.json" % pdf_dir, b)
    write_config_file("%s/a/b/c/bangalore_hindi_config.json" % pdf_dir, bhc)

    write_config_file("%s/x/config.json" % pdf_dir, x)
    write_config_file("%s/x/y/config.json" % pdf_dir, y)
    write_config_file("%s/x/y/z/config.json" % pdf_dir, z)
    write_config_file("%s/x/jaipur_gujarati_config.json" % pdf_dir, jgx)

    if copy_text_files:
        # This is to simulate the text files that would be generated
        # by the PDF processor. This option is useful for speeding
        # up the tests by avoiding the need to process PDFs.
        for file_path, _ in doc_ids.values():
            log_handle.info(f"Processing file: {file_path}")
            relpath = os.path.relpath(file_path, pdf_dir) # a/b/c/bangalore_hindi.pdf
            relpath = os.path.splitext(relpath)[0] # a/b/c/bangalore_hindi
            log_handle.info(f"Relative path: {relpath}")

            src_folder = os.path.join(
                TEST_BASE_DIR, "data", "text",
                os.path.basename(relpath))
            dest_folder = os.path.join(
                config.BASE_TEXT_PATH,
                relpath
            )
            log_handle.info(f"Copying text files from {src_folder} to {dest_folder}")
            shutil.copytree(src_folder, dest_folder)

    return doc_ids

def get_all_documents(max_results: int = 1000) -> list:
    """
    Retrieves all documents from the configured OpenSearch index.

    Args:
        max_results: The maximum number of documents to return. Be aware that
                     very large numbers can impact performance. For retrieving
                     all documents from a large index, consider implementing
                     the OpenSearch Scroll API.

    Returns:
        A list of the documents found in the index. Each document is a dictionary.
        Returns an empty list if an error occurs.
    """
    try:
        # Initialize the OpenSearch client and get the index name from the config
        config = Config()
        opensearch_client = get_opensearch_client(config)
        index_name = config.OPENSEARCH_INDEX_NAME

        # Define the search query to match all documents
        search_body = {
            "size": max_results,
            "query": {
                "match_all": {}
            }
        }

        # Execute the search query
        response = opensearch_client.search(
            index=index_name,
            body=search_body
        )

        # The search results are in the 'hits' field of the response
        return response['hits']['hits']

    except Exception as e:
        print(f"An error occurred while querying OpenSearch: {e}")
        return []

def update_index_state_metadata():
    """
    Updates the index state metadata in the OpenSearch index.
    This is a placeholder function that can be implemented to update
    the index state metadata as needed.
    """
    config = Config()
    opensearch_client = get_opensearch_client(config)
    index_name = config.OPENSEARCH_INDEX_NAME
    index_state = IndexState(config.SQLITE_DB_PATH)

    metadata = opensearch.get_metadata(config)
    index_state.update_metadata_cache(metadata)

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