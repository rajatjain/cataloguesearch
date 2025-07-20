import datetime

import pytest
import os
import shutil
import uuid
import tempfile
import fitz

from backend.crawler.discovery import SingleFileProcessor, Discovery
from backend.crawler.index_state import IndexState
from backend.index.embedding_module import IndexingEmbeddingModule
from backend.processor.pdf_processor import PDFProcessor, log_handle
from backend.utils import json_dump, json_dumps
from tests.backend.base import *
from tests.backend.test_config import config

"""
Test Setup:
  - Create a temporary directory for test data.
  - Copy the various PDF files from the test data directory to the temporary directory.
  - Build JSON config files for some directories.
  - Build JSON config files for some PDF files.
  
Test Suite 1: Test get_metadata function for various files
  - get metadata for all the files created
  - change the config file in one of those directories
    - get metadata for the changed files again and confirm
  - delete a config file and confirm that the metadata is updated accordingly
  
Test Suite 2: Check the state
  - Setup: index_document() and pdf_process() are no-ops.
  - Define mocks for them.
  - repeat the same exercise of scanning all documents
  - change one config file. ensure configs of all affected files are updated.
  - delete one config file. ensure configs of all affected files are updated.
  - delete a file. ensure its config is removed.
"""

class MockIndexingEmbeddingModule(IndexingEmbeddingModule):
    def __init__(self):
        pass

    def index_document(self, document_id: str, original_filename: str, page_text_paths: list[str],
                       metadata: dict, bookmarks: list[dict], reindex_metadata_only: bool = False):
        pass

    def create_index_if_not_exists(self):
        pass

class MockPDFProcessor(PDFProcessor):
    def __init__(self):
        pass

    def process_pdf(
            self, pdf_path: str, output_dir: str,
            images_dir: str,
    ) -> tuple[list[str], dict[int: str]]:
        return [], {}

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

def setup(base_dir):
    os.makedirs("%s/a/b/c" % base_dir, exist_ok=True)
    os.makedirs("%s/a/b/d" % base_dir, exist_ok=True)
    os.makedirs("%s/x/y/z" % base_dir, exist_ok=True)

    TEST_BASE_DIR = os.getenv("TEST_BASE_DIR")

    # copy files
    data_pdf_path = os.path.join(TEST_BASE_DIR, "data", "pdfs")
    bangalore_hindi = os.path.join(data_pdf_path, "bangalore_hindi.pdf")
    bangalore_gujarati = os.path.join(data_pdf_path, "bangalore_gujarati.pdf")
    bangalore_english = os.path.join(data_pdf_path, "bangalore_english.pdf")
    multi_language_document = os.path.join(data_pdf_path, "multi_language_document.pdf")

    abcbh = "%s/a/b/c/bangalore_hindi.pdf" % base_dir
    abcbg = "%s/a/b/c/bangalore_gujarati.pdf" % base_dir
    abbeng = "%s/a/b/bangalore_english.pdf" % base_dir
    xyzmld = "%s/x/y/z/multi_language_document.pdf" % base_dir
    abdmld = "%s/a/b/d/multi_language_document.pdf" % base_dir
    abh = "%s/a/bangalore_hindi.pdf" % base_dir
    xbg = "%s/x/bangalore_gujarati.pdf" % base_dir

    doc_ids = {
        "abcbh": [abcbh, get_doc_id(base_dir, abcbh)],
        "abcbg": [abcbg, get_doc_id(base_dir, abcbg)],
        "abbeng": [abbeng, get_doc_id(base_dir, abbeng)],
        "xyzmld": [xyzmld, get_doc_id(base_dir, xyzmld)],
        "abdmld": [abdmld, get_doc_id(base_dir, abdmld)],
        "abh": [abh, get_doc_id(base_dir, abh)],
        "xbg": [xbg, get_doc_id(base_dir, xbg)]
    }

    shutil.copy(bangalore_hindi, abcbh)
    shutil.copy(bangalore_gujarati, abcbg)
    shutil.copy(bangalore_english, abbeng)
    shutil.copy(multi_language_document, xyzmld)
    shutil.copy(multi_language_document, abdmld)
    shutil.copy(bangalore_hindi, abh)
    shutil.copy(bangalore_gujarati, xbg)

    # create config files
    a = { "category": "a", "type": "t" }
    b = { "category": "b", "type": "t1" }
    # dir c is empty
    bhc = { "type": "t2", "new": "c3" }

    # dir d is empty

    x = { "category": "x", "type": "tx" }
    z = { "category": "z", "type": "tz" }
    bgx = { "type": "t3", "new": "c4" }

    write_config_file("%s/a/config.json" % base_dir, a)
    write_config_file("%s/a/b/config.json" % base_dir, b)
    write_config_file("%s/a/b/c/bangalore_hindi_config.json" % base_dir, bhc)

    write_config_file("%s/x/config.json" % base_dir, x)
    write_config_file("%s/x/y/z/config.json" % base_dir, z)
    write_config_file("%s/x/bangalore_gujarati_config.json" % base_dir, bgx)

    return doc_ids

def test_get_metadata(initialise, config):
    # create temp dir
    tmp_dir = tempfile.mkdtemp(prefix="test_discovery_")
    pdf_dir = "%s/data/pdfs" % tmp_dir
    config.settings()["crawler"]["base_pdf_path"] = pdf_dir
    setup(pdf_dir)

    sfp = SingleFileProcessor(
        config, "%s/a/b/c/bangalore_hindi.pdf" % pdf_dir,
        None, None,
        MockPDFProcessor(),
        datetime.datetime.now().isoformat()
    )

    meta = sfp.get_metadata()
    assert meta == {'category': 'b', 'type': 't2', 'new': 'c3'}

    sfp = SingleFileProcessor(
        config, "%s/a/b/c/bangalore_gujarati.pdf" % pdf_dir,
        None, None,
        MockPDFProcessor(),
        datetime.datetime.now().isoformat()
    )
    meta = sfp.get_metadata()
    assert meta == {'category': 'b', 'type': 't1'}

    sfp = SingleFileProcessor(
        config, "%s/a/b/bangalore_english.pdf" % pdf_dir,
        None, None,
        MockPDFProcessor(),
        datetime.datetime.now().isoformat()
    )
    meta = sfp.get_metadata()
    assert meta == {'category': 'b', 'type': 't1'}

    abdmld = SingleFileProcessor(
        config, "%s/a/b/d/multi_language_document.pdf" % pdf_dir,
        None, None,
        MockPDFProcessor(),
        datetime.datetime.now().isoformat()
    )
    meta = abdmld.get_metadata()
    assert meta == {'category': 'b', 'type': 't1'}

    xbg = SingleFileProcessor(
        config, "%s/x/bangalore_gujarati.pdf" % pdf_dir,
        None, None,
        MockPDFProcessor(),
        datetime.datetime.now().isoformat()
    )
    meta = xbg.get_metadata()
    assert meta == {'category': 'x', 'type': 't3', 'new': 'c4'}

def test_crawl(initialise, config):
    # create temp dir
    tmp_dir = tempfile.mkdtemp(prefix="test_crawl_")
    pdf_dir = "%s/data/pdfs" % tmp_dir
    config.settings()["crawler"]["base_pdf_path"] = pdf_dir
    doc_ids = setup(pdf_dir)

    tmp_db_dir = tempfile.mkdtemp(prefix="test_crawl_db_")
    config.settings()["crawler"]["sqlite_db_path"] = "%s/crawl_state.db" % tmp_db_dir

    index_state = IndexState(config.SQLITE_DB_PATH)

    discovery = Discovery(
        config,
        MockIndexingEmbeddingModule(),
        MockPDFProcessor(),
        index_state)

    discovery.crawl()

    state1 = index_state.load_state()
    log_handle.info(f"state: {json_dumps(state1)}")
    assert len(state1) == 7

    # change the file "a/b/config.json"
    new_config = { "category": "c", "type": "t1", "new": "blah1" }
    write_config_file("%s/a/b/config.json" % pdf_dir, new_config)
    # re-crawl

    log_handle.info(f"Test 1: re-crawling after changing config file")
    discovery.crawl()

    changed_keys = [
        doc_ids["abcbh"][1],
        doc_ids["abcbg"][1],
        doc_ids["abbeng"][1],
        doc_ids["abdmld"][1]
    ]
    state2 = index_state.load_state()
    log_handle.info(f"state: {json_dumps(state2)}")
    log_handle.info(f"changed_keys: {changed_keys}")

    validate(state1, state2, changed_keys, check_file_changed=False, check_config_changed=True)

    log_handle.info(f"Test 2: re-crawling after changing config file again")
    # change the same config_json
    xbg = { "category": "c", "type": "t3", "new": "blah2" }
    fname = doc_ids["xbg"][0]
    config_fname = fname.replace(".pdf", "_config.json")
    write_config_file(config_fname, xbg)

    changed_keys = [doc_ids["xbg"][1]]
    discovery.crawl()
    state3 = index_state.load_state()
    validate(state2, state3, changed_keys, check_file_changed=False, check_config_changed=True)

    # change data in a file. should be full-reindex
    xyzmld = doc_ids["xyzmld"][0]
    add_bookmark_to_pdf(xyzmld, "new_bookmark", 1)
    log_handle.info(f"Test 3: re-crawling after changing file content")
    discovery.crawl()
    state4 = index_state.load_state()
    log_handle.info(f"state: {json_dumps(state4)}")
    changed_keys = [
        doc_ids["xyzmld"][1]
    ]
    validate(state3, state4, changed_keys, check_file_changed=True, check_config_changed=False)

    # delete a config file. should be removed from state
    log_handle.info(f"Test 4: re-crawling after deleting config file")
    fname = doc_ids["abh"][0]
    assert os.path.exists(fname)
    os.remove(fname)
    assert not os.path.exists(fname)
    discovery.crawl()
    state5 = index_state.load_state()
    log_handle.info(f"state: {json_dumps(state5)}")
    assert len(state5) == 6

    # it shouldn't have the fname in "state"
    assert doc_ids["abh"][1] not in state5
    validate(state4, state5, changed_keys=[], check_file_changed=False, check_config_changed=False)


def validate(old_state, new_state, changed_keys,
             check_file_changed=False, check_config_changed=True):
    for doc_id, vals in new_state.items():
        if doc_id in changed_keys:
            assert vals["last_indexed_timestamp"] != old_state[doc_id]["last_indexed_timestamp"]
            assert check_file_changed == (vals["file_checksum"] != old_state[doc_id]["file_checksum"])
            assert check_config_changed == (vals["config_hash"] != old_state[doc_id]["config_hash"])
        else:
            assert vals["last_indexed_timestamp"] == old_state[doc_id]["last_indexed_timestamp"]
            assert vals["file_checksum"] == old_state[doc_id]["file_checksum"]
            assert vals["config_hash"] == old_state[doc_id]["config_hash"]

def add_bookmark_to_pdf(pdf_path, bookmark_name, page_number):
    doc = None
    # Define a temporary path for the new file
    temp_pdf_path = tempfile.mkstemp(suffix=".temp.pdf")[1]

    try:
        doc = fitz.open(pdf_path)
        toc = doc.get_toc()

        # Add the new bookmark
        toc.append([1, bookmark_name, page_number])

        doc.set_toc(toc)

        # Save the changes to the temporary file (this is a full rewrite)
        doc.save(temp_pdf_path, garbage=4, deflate=True, clean=True)
    except Exception as e:
        log_handle.error(f"An error occurred during PDF modification: {e}")
        # If the temp file was created, clean it up
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        return  # Exit the function on error
    finally:
        if doc:
            doc.close()

    try:
        # If saving was successful, replace the original file with the new one
        os.replace(temp_pdf_path, pdf_path)
        log_handle.verbose(f"Successfully added bookmark '{bookmark_name}' to page {page_number}.")
        log_handle.verbose(f"The file '{pdf_path}' has been updated.")
    except Exception as e:
        log_handle.error(f"An error occurred during file replacement: {e}")
