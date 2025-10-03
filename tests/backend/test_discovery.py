import datetime
import hashlib
import os
import shutil
import tempfile
import fitz
from opensearchpy import OpenSearch

from backend.crawler.discovery import SingleFileProcessor, Discovery
from backend.crawler.index_state import IndexState
from backend.crawler.index_generator import IndexGenerator
from backend.crawler.pdf_processor import PDFProcessor, log_handle
from tests.backend.base import *
from tests.backend.common import setup, write_config_file

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

class MockIndexGenerator(IndexGenerator):
    def __init__(self, config: Config, opensearch_client: OpenSearch):
        super().__init__(config, opensearch_client)

    def index_document(
        self, document_id: str, original_filename: str,
        ocr_dir: str, output_text_dir: str, pages_list: list[int], metadata: dict,
        scan_config: dict, bookmarks: dict[int, str],
        reindex_metadata_only: bool = False, dry_run: bool = True):
        pass

    def create_index_if_not_exists(self):
        pass

class MockPDFProcessor(PDFProcessor):
    def __init__(self, config: Config):
        super().__init__(config)

    def process_pdf(
        self, pdf_path: str, scan_config: dict,
        pages_list: list[int]):
        relative_pdf_path = os.path.relpath(pdf_path, self._base_pdf_folder)
        output_ocr_dir = f"{self._base_ocr_folder}/{os.path.splitext(relative_pdf_path)[0]}"
        
        if os.path.exists(output_ocr_dir):
            shutil.rmtree(output_ocr_dir)
        
        os.makedirs(output_ocr_dir, exist_ok=True)
        
        # Get the base filename without path and extension for source directory
        base_filename = os.path.splitext(os.path.basename(pdf_path))[0]
        source_ocr_dir = f"{get_test_base_dir()}/data/ocr/{base_filename}"
        
        # Copy the page files for the pages in pages_list
        if os.path.exists(source_ocr_dir):
            for page_num in pages_list:
                source_file = f"{source_ocr_dir}/page_{page_num:04d}.txt"
                dest_file = f"{output_ocr_dir}/page_{page_num:04d}.txt"
                if os.path.exists(source_file):
                    shutil.copy2(source_file, dest_file)
        
        return True

class MockIndexState(IndexState):
    def calculate_ocr_checksum(self, relative_file_path: str, ocr_pages: list[int]) -> str:
        # only use relative file path
        if not relative_file_path:
            return ""
        return hashlib.sha256(relative_file_path.encode('utf-8')).hexdigest()

def test_get_metadata():
    setup()
    config = Config()
    pdf_dir = config.BASE_PDF_PATH

    # Test bangalore_hindi.pdf in hindi/cities/metro/ - should get language, category, and type
    sfp = SingleFileProcessor(
        config, f"{pdf_dir}/hindi/cities/metro/bangalore_hindi.pdf",
        None, None,
        MockPDFProcessor(config),
        datetime.datetime.now().isoformat()
    )
    meta = sfp._get_metadata()
    assert meta == {'language': 'hi', 'category': 'Pravachan', 'Anuyog': 'city', 'type': 'metro'}

    # Test bangalore_gujarati.pdf in gujarati/cities/metro/ - should get language, category, and type
    sfp = SingleFileProcessor(
        config, f"{pdf_dir}/gujarati/cities/metro/bangalore_gujarati.pdf",
        None, None,
        MockPDFProcessor(config),
        datetime.datetime.now().isoformat()
    )
    meta = sfp._get_metadata()
    assert meta == {'language': 'gu', 'category': 'Pravachan', 'Anuyog': 'city', 'type': 'metro'}

    # Test hampi_hindi.pdf in hindi/history/ - should get language and category
    sfp = SingleFileProcessor(
        config, f"{pdf_dir}/hindi/history/hampi_hindi.pdf",
        None, None,
        MockPDFProcessor(config),
        datetime.datetime.now().isoformat()
    )
    meta = sfp._get_metadata()
    assert meta == {'language': 'hi', 'category': 'Pravachan', 'Anuyog': 'history'}

    # Test indore_hindi.pdf in hindi/cities/non_metro/ - should get language, category, and type
    sfp = SingleFileProcessor(
        config, f"{pdf_dir}/hindi/cities/non_metro/indore_hindi.pdf",
        None, None,
        MockPDFProcessor(config),
        datetime.datetime.now().isoformat()
    )
    meta = sfp._get_metadata()
    assert meta == {'language': 'hi', 'category': 'Pravachan', 'Anuyog': 'city', 'type': 'non_metro'}

    # Test songadh_gujarati.pdf in gujarati/spiritual/ - should get language and category
    sfp = SingleFileProcessor(
        config, f"{pdf_dir}/gujarati/spiritual/songadh_gujarati.pdf",
        None, None,
        MockPDFProcessor(config),
        datetime.datetime.now().isoformat()
    )
    meta = sfp._get_metadata()
    assert meta == {'language': 'gu', 'category': 'Pravachan', 'Anuyog': 'spiritual'}

def test_crawl(initialise):
    config = Config()
    # create temp dir
    doc_ids = setup()

    index_state = MockIndexState(config.SQLITE_DB_PATH)

    discovery = Discovery(
        config,
        MockIndexGenerator(config, None),
        MockPDFProcessor(config),
        index_state)

    discovery.crawl(process=True, index=True)

    state1 = index_state.load_state()
    log_handle.info(f"state: {json_dumps(state1)}")
    assert len(state1) == 12

    # change the hindi cities config file to affect all hindi city files
    new_config = {"Anuyog": "urban"}
    write_config_file(f"{config.BASE_PDF_PATH}/hindi/cities/config.json", new_config)
    # re-crawl

    log_handle.info(f"Test 1: re-crawling after changing config file")
    discovery.crawl(process=True, index=True)

    changed_keys = [
        doc_ids["bangalore_hindi"][1],
        doc_ids["indore_hindi"][1],
        doc_ids["jaipur_hindi"][1]
    ]
    state2 = index_state.load_state()
    log_handle.info(f"state: {json_dumps(state2)}")
    log_handle.info(f"changed_keys: {changed_keys}")

    validate(state1, state2, changed_keys, check_file_changed=False, check_config_changed=True)

    log_handle.info(f"Test 2: re-crawling after changing config file again")
    # change the config for jaipur_gujarati.pdf
    jgx = {"Anuyog": "special_city", "type": "heritage"}
    fname = doc_ids["jaipur_gujarati"][0]
    config_fname = fname.replace(".pdf", "_config.json")
    write_config_file(config_fname, jgx)

    changed_keys = [doc_ids["jaipur_gujarati"][1]]
    discovery.crawl(process=True, index=True)
    state3 = index_state.load_state()
    validate(state2, state3, changed_keys, check_file_changed=False, check_config_changed=True)

    # adding bookmarks doesn't change anything.
    hampi_gujarati = doc_ids["hampi_gujarati"][0]
    add_bookmark_to_pdf(hampi_gujarati, "new_bookmark", 1)
    log_handle.info(f"Test 3: re-crawling after changing file content")
    discovery.crawl(process=True, index=True)
    state4 = index_state.load_state()
    log_handle.info(f"state: {json_dumps(state4)}")
    changed_keys = []
    validate(state3, state4, changed_keys, check_file_changed=True, check_config_changed=False)

    # delete a config file. should be removed from state
    log_handle.info(f"Test 4: re-crawling after deleting config file")
    fname = doc_ids["jaipur_hindi"][0]
    assert os.path.exists(fname)
    os.remove(fname)
    assert not os.path.exists(fname)
    discovery.crawl(process=True, index=True)
    state5 = index_state.load_state()
    log_handle.info(f"state: {json_dumps(state5)}")
    assert len(state5) == 11

    # it shouldn't have the fname in "state"
    assert doc_ids["jaipur_hindi"][1] not in state5
    validate(state4, state5, changed_keys=[], check_file_changed=False, check_config_changed=False)

    # copy an existing file to another folder to test new file discovery
    log_handle.info(f"Test 5: copying file to new location and re-crawling")
    source_file = doc_ids["songadh_hindi"][0]  # hindi/spiritual/songadh_hindi.pdf
    dest_file = f"{config.BASE_PDF_PATH}/gujarati/history/songadh_copy.pdf"
    shutil.copy(source_file, dest_file)
    
    discovery.crawl(process=True, index=True)
    state6 = index_state.load_state()
    log_handle.info(f"state after copying file: {json_dumps(state6)}")
    assert len(state6) == 12  # should be back to 12 files (11 + 1 new copy)


def test_pages_crawl(initialise):
    config = Config()
    doc_ids = setup()

    index_state = MockIndexState(config.SQLITE_DB_PATH)

    discovery = Discovery(
        config,
        MockIndexGenerator(config, None),
        MockPDFProcessor(config),
        index_state)

    # Start with scan_config pages [1]
    config.SCAN_CONFIG = {"pages": [1]}
    discovery.crawl(process=True, index=True)

    state1 = index_state.load_state()
    log_handle.info(f"Initial state with pages [1]: {json_dumps(state1)}")
    assert len(state1) == 12

    # Change scan_config to pages [1, 2] for some specific files by updating their config files
    files_to_change = [
        (f"{config.BASE_PDF_PATH}/hindi/cities/metro/bangalore_hindi.pdf", doc_ids["bangalore_hindi"][1]),
        (f"{config.BASE_PDF_PATH}/gujarati/cities/metro/bangalore_gujarati.pdf", doc_ids["bangalore_gujarati"][1]),
        (f"{config.BASE_PDF_PATH}/hindi/history/hampi_hindi.pdf", doc_ids["hampi_hindi"][1])
    ]

    for file_path, doc_id in files_to_change:
        config_path = file_path.replace(".pdf", "_config.json")
        config_data = {"pages": [1, 2]}
        write_config_file(config_path, config_data)

    discovery.crawl(process=True, index=True)

    state2 = index_state.load_state()
    log_handle.info(f"State after changing pages config for some files: {json_dumps(state2)}")

    # Ensure that only the modified files have their config_checksum changed
    changed_files = [doc_ids["bangalore_hindi"][1], doc_ids["bangalore_gujarati"][1], doc_ids["hampi_hindi"][1]]
    
    validate(state1, state2, changed_files, check_file_changed=False, check_config_changed=True)

def test_ignore_file(initialise):
    config = Config()
    doc_ids = setup()

    index_state = MockIndexState(config.SQLITE_DB_PATH)

    discovery = Discovery(
        config,
        MockIndexGenerator(config, None),
        MockPDFProcessor(config),
        index_state)

    # Add _ignore files in 2 folders to ignore all files in those folders
    ignore_folders = [
        f"{config.BASE_PDF_PATH}/hindi/cities/metro",     # Will ignore bangalore_hindi.pdf
        f"{config.BASE_PDF_PATH}/gujarati/history"        # Will ignore hampi_gujarati.pdf, thanjavur_gujarati.pdf
    ]
    
    for folder in ignore_folders:
        ignore_file = f"{folder}/_ignore"
        with open(ignore_file, 'w') as f:
            f.write("")  # Empty file

    # First crawl - should ignore files in the 2 folders
    discovery.crawl(process=True, index=True)
    
    state1 = index_state.load_state()
    log_handle.info(f"Initial crawl with 2 ignored folders: {json_dumps(state1)}")
    # Should have fewer files (depends on how many files are in ignored folders)
    
    # Verify the ignored files are not in state
    ignored_doc_ids = [doc_ids["bangalore_hindi"][1], doc_ids["hampi_gujarati"][1],
                       doc_ids["thanjavur_gujarati"][1]]
    for ignored_id in ignored_doc_ids:
        assert ignored_id not in state1

    # Delete first ignore file
    first_ignore = f"{ignore_folders[0]}/_ignore"
    os.remove(first_ignore)
    
    discovery.crawl(process=True, index=True)
    state2 = index_state.load_state()
    log_handle.info(f"After removing first ignore file: {json_dumps(state2)}")
    assert doc_ids["bangalore_hindi"][1] in state2  # This file should now be indexed
    
    # Validate that only the newly unignored file is changed, others remain unchanged
    changed_keys = [doc_ids["bangalore_hindi"][1]]
    validate(state1, state2, changed_keys, check_file_changed=False, check_config_changed=True, new_file_added=True)

    # Delete second ignore file
    second_ignore = f"{ignore_folders[1]}/_ignore"
    os.remove(second_ignore)
    
    discovery.crawl(process=True, index=True)
    state3 = index_state.load_state()
    log_handle.info(f"After removing second ignore file: {json_dumps(state3)}")
    assert doc_ids["hampi_gujarati"][1] in state3  # This file should now be indexed
    assert doc_ids["thanjavur_gujarati"][1] in state3
    
    # Validate that only the newly unignored file is changed, others remain unchanged
    changed_keys = [doc_ids["hampi_gujarati"][1], doc_ids["thanjavur_gujarati"][1]]
    validate(state2, state3, changed_keys, check_file_changed=False, check_config_changed=True, new_file_added=True)
    
    # Final validation - should have all 10 files
    assert len(state3) == 12

def test_crawl_vs_crawl_and_index(initialise):
    config = Config()
    doc_ids = setup()

    index_state = MockIndexState(config.SQLITE_DB_PATH)

    discovery = Discovery(
        config,
        MockIndexGenerator(config, None),
        MockPDFProcessor(config),
        index_state)

    # First call crawl with only process=True (no indexing)
    discovery.crawl(process=True, index=False)
    
    state1 = index_state.load_state()
    log_handle.info(f"State after crawl(process=True, index=False): {json_dumps(state1)}")
    assert len(state1) == 12
    
    # Validate that ocr_checksum is present but config_hash should be empty (since no indexing was done)
    for doc_id, vals in state1.items():
        assert vals["ocr_checksum"] is not None  # OCR processing was done
        assert vals["config_hash"] == ""         # No indexing was done, so config_hash is empty

    # Now call crawl with both process=True and index=True
    discovery.crawl(process=True, index=True)
    
    state2 = index_state.load_state()
    log_handle.info(f"State after crawl(process=True, index=True): {json_dumps(state2)}")
    assert len(state2) == 12
    
    # Validate that both ocr_checksum and config_hash are present
    for doc_id, vals in state2.items():
        assert vals["ocr_checksum"] is not None  # OCR processing was done
        assert vals["config_hash"] != ""         # Indexing was done, so config_hash is set to non-empty
        # Timestamp should be updated since indexing happened
        assert vals["last_indexed_timestamp"] != state1[doc_id]["last_indexed_timestamp"]
        # OCR checksum should remain the same since files didn't change
        assert vals["ocr_checksum"] == state1[doc_id]["ocr_checksum"]

def validate(old_state, new_state, changed_keys,
             check_file_changed=False, check_config_changed=True, new_file_added=False):
    for doc_id, vals in new_state.items():
        if doc_id in changed_keys:
            if new_file_added:
                # For newly added files, they shouldn't exist in old_state
                assert doc_id not in old_state
                assert vals["ocr_checksum"] is not None
            else:
                # For existing files that changed
                assert vals["last_indexed_timestamp"] != old_state[doc_id]["last_indexed_timestamp"]
                assert check_config_changed == (vals["config_hash"] != old_state[doc_id]["config_hash"])
                assert vals["ocr_checksum"] == old_state[doc_id]["ocr_checksum"]
        else:
            # For unchanged files, they should exist in both states and be identical
            assert doc_id in old_state
            assert vals["last_indexed_timestamp"] == old_state[doc_id]["last_indexed_timestamp"]
            assert vals["config_hash"] == old_state[doc_id]["config_hash"]
            assert vals["ocr_checksum"] == old_state[doc_id]["ocr_checksum"]

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
