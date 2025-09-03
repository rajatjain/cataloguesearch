import os
import logging
import random
import pytest

from backend.crawler.index_generator import IndexGenerator
from backend.crawler.index_state import IndexState
from backend.crawler.pdf_processor import PDFProcessor
from tests.backend.base import *
from tests.backend.common import setup
from backend.config import Config
from backend.common.opensearch import get_opensearch_client, delete_index, create_indices_if_not_exists
from backend.crawler.discovery import Discovery

log_handle = logging.getLogger(__name__)

@pytest.fixture(scope="module")
def init_integration_test():
    """
    Setup function for integration tests.
    Creates PDF files in temp directory using common setup and adds _ignore files to 3 random files.
    """
    # Call setup to create all PDF files in temp directory
    doc_ids = setup(copy_ocr_files=False, add_scan_config=True)
    
    # Get all PDF file paths and randomly select 3 directories
    all_files = list(doc_ids.items())
    random_files = random.sample(all_files, 3)
    ignored_directories = set()
    ignored_files = []
    
    # Get unique directories from the 3 random files
    for file_name, (file_path, doc_id) in random_files:
        directory = os.path.dirname(file_path)
        ignored_directories.add(directory)
    
    # Create _ignore files in the selected directories and find all PDFs in those directories
    for directory in ignored_directories:
        ignore_file_path = os.path.join(directory, "_ignore")
        
        with open(ignore_file_path, 'w') as f:
            f.write(f"Ignore file for directory: {directory}\n")
        
        log_handle.info(f"Created _ignore file at: {ignore_file_path}")
        
        # Find all PDF files in this directory that will be ignored
        for file_name, (file_path, doc_id) in doc_ids.items():
            if os.path.dirname(file_path) == directory:
                ignored_files.append(file_name)
    
    log_handle.info(f"Ignored files: {ignored_files}")
    return doc_ids, ignored_files, ignored_directories


def test_integration(init_integration_test):
    """
    Integration test that verifies _ignore files work correctly during crawling.
    """
    doc_ids, ignored_files, ignored_directories = init_integration_test
    
    config = Config()
    opensearch_client = get_opensearch_client(config)
    index_name = config.OPENSEARCH_INDEX_NAME
    
    # Delete and recreate OpenSearch index
    log_handle.info("Deleting and recreating OpenSearch index")
    delete_index(config)
    create_indices_if_not_exists(config, opensearch_client)
    
    # Run crawl with index=True and process=True
    log_handle.info("Running crawl with index=True, process=True")
    discovery = Discovery(
        config, IndexGenerator(config, opensearch_client),
        PDFProcessor(config), IndexState(config.SQLITE_DB_PATH))
    discovery.crawl(index=True, process=True)
    
    # Check base_ocr_dir - should not contain ignored files
    base_ocr_path = config.BASE_OCR_PATH
    log_handle.info(f"Checking base_ocr_path: {base_ocr_path}")
    
    for file_name in ignored_files:
        # Get relative path for the file
        file_path, _ = doc_ids[file_name]
        pdf_dir = config.BASE_PDF_PATH
        rel_path = os.path.relpath(file_path, pdf_dir)
        rel_path_no_ext = os.path.splitext(rel_path)[0]
        
        ocr_file_path = os.path.join(base_ocr_path, rel_path_no_ext)
        assert not os.path.exists(ocr_file_path), f"OCR file should not exist for ignored file: {ocr_file_path}"
        log_handle.info(f"Verified OCR file does not exist for ignored file: {file_name}")
    
    # Check base_text_path - should not contain ignored files
    base_text_path = config.BASE_TEXT_PATH
    log_handle.info(f"Checking base_text_path: {base_text_path}")
    
    for file_name in ignored_files:
        file_path, _ = doc_ids[file_name]
        pdf_dir = config.BASE_PDF_PATH
        rel_path = os.path.relpath(file_path, pdf_dir)
        rel_path_no_ext = os.path.splitext(rel_path)[0]
        text_file_path = os.path.join(base_text_path, rel_path_no_ext)
        
        assert not os.path.exists(text_file_path), f"Text file should not exist for ignored file: {text_file_path}"
        log_handle.info(f"Verified text file does not exist for ignored file: {file_name}")
    
    # Verify non-ignored files are present in OCR directory
    non_ignored_files = [name for name in doc_ids.keys() if name not in ignored_files]
    
    log_handle.info("Checking that non-ignored files exist in base_ocr_path")
    for file_name in non_ignored_files:
        file_path, _ = doc_ids[file_name]
        pdf_dir = config.BASE_PDF_PATH
        rel_path = os.path.relpath(file_path, pdf_dir)
        rel_path_no_ext = os.path.splitext(rel_path)[0]
        
        ocr_file_path = os.path.join(base_ocr_path, rel_path_no_ext)
        assert os.path.exists(ocr_file_path), f"OCR file should exist for non-ignored file: {ocr_file_path}"
        log_handle.info(f"Verified OCR file exists for non-ignored file: {file_name}")
    
    # Verify non-ignored files are present in text directory
    log_handle.info("Checking that non-ignored files exist in base_text_path")
    for file_name in non_ignored_files:
        file_path, _ = doc_ids[file_name]
        pdf_dir = config.BASE_PDF_PATH
        rel_path = os.path.relpath(file_path, pdf_dir)
        rel_path_no_ext = os.path.splitext(rel_path)[0]
        text_file_path = os.path.join(base_text_path, rel_path_no_ext)
        
        assert os.path.exists(text_file_path), f"Text file should exist for non-ignored file: {text_file_path}"
        log_handle.info(f"Verified text file exists for non-ignored file: {file_name}")
    
    # Check OpenSearch - should not contain ignored files
    log_handle.info("Checking OpenSearch index")
    
    # Refresh the index to make sure all documents are available for search
    opensearch_client.indices.refresh(index=index_name)
    
    # Get all documents from OpenSearch
    search_body = {
        "size": 1000,
        "query": {"match_all": {}}
    }
    
    response = opensearch_client.search(index=index_name, body=search_body)
    indexed_doc_ids = list(set([hit['_source']['document_id'] for hit in response['hits']['hits']]))
    
    for file_name in ignored_files:
        _, doc_id = doc_ids[file_name]
        assert doc_id not in indexed_doc_ids, f"Document should not be indexed for ignored file: {file_name} (doc_id: {doc_id})"
        log_handle.info(f"Verified document not indexed for ignored file: {file_name}")
    
    # Verify non-ignored files are present in OpenSearch
    for file_name in non_ignored_files:
        _, doc_id = doc_ids[file_name]
        assert doc_id in indexed_doc_ids, f"Document should be indexed for non-ignored file: {file_name} (doc_id: {doc_id})"
        log_handle.info(f"Verified document indexed for non-ignored file: {file_name}")
    
    log_handle.info(f"Integration test completed successfully. Ignored {len(ignored_files)} files, processed {len(non_ignored_files)} files.")
    
    # Test 2: Remove _ignore files and verify previously ignored files get processed
    log_handle.info("Starting Test 2: Remove _ignore files and process previously ignored files")
    
    # Step 1: Load IndexState as old_index_state
    index_state = IndexState(config.SQLITE_DB_PATH)
    old_index_state = index_state.load_state()
    log_handle.info(f"Loaded old index state with {len(old_index_state)} entries")
    
    # Step 2: Delete the _ignore files and map all the new files that should be indexed
    newly_processable_files = []
    
    for directory in ignored_directories:
        ignore_file_path = os.path.join(directory, "_ignore")
        if os.path.exists(ignore_file_path):
            os.remove(ignore_file_path)
            log_handle.info(f"Removed _ignore file: {ignore_file_path}")
    
    # Map the files that were previously ignored and should now be processed
    for file_name in ignored_files:
        newly_processable_files.append(file_name)
    
    log_handle.info(f"Files that should now be processed: {newly_processable_files}")
    
    # Step 3: Run crawl/process again
    log_handle.info("Running second crawl with index=True, process=True")
    discovery.crawl(index=True, process=True)
    
    # Step 4: Load new IndexState and compare timestamps
    new_index_state = index_state.load_state()
    log_handle.info(f"Loaded new index state with {len(new_index_state)} entries")
    
    # Step 4.1: Verify old files have the same last index timestamp
    for doc_id, old_state in old_index_state.items():
        if doc_id in new_index_state:
            old_timestamp = old_state["last_indexed_timestamp"]
            new_timestamp = new_index_state[doc_id]["last_indexed_timestamp"]
            assert old_timestamp == new_timestamp, f"Timestamp should not change for existing file with doc_id: {doc_id}"
            log_handle.info(f"Verified timestamp unchanged for existing doc_id: {doc_id}")
    
    # Step 4.2: Verify new files have last index timestamp
    newly_processed_doc_ids = []
    for file_name in newly_processable_files:
        _, doc_id = doc_ids[file_name]
        newly_processed_doc_ids.append(doc_id)
        assert doc_id in new_index_state, f"New file should be in index state: {file_name} (doc_id: {doc_id})"
        assert new_index_state[doc_id]["last_indexed_timestamp"] is not None, f"New file should have timestamp: {file_name}"
        log_handle.info(f"Verified new file has timestamp: {file_name}")
    
    # Step 5: Ensure that new files are present in OCR directory, base_text_path and OpenSearch
    
    # Check OCR directory
    log_handle.info("Verifying newly processed files exist in OCR directory")
    for file_name in newly_processable_files:
        file_path, _ = doc_ids[file_name]
        pdf_dir = config.BASE_PDF_PATH
        rel_path = os.path.relpath(file_path, pdf_dir)
        rel_path_no_ext = os.path.splitext(rel_path)[0]
        
        ocr_file_path = os.path.join(base_ocr_path, rel_path_no_ext)
        assert os.path.exists(ocr_file_path), f"OCR file should exist for newly processed file: {ocr_file_path}"
        log_handle.info(f"Verified OCR file exists for newly processed file: {file_name}")
    
    # Check text directory  
    log_handle.info("Verifying newly processed files exist in text directory")
    for file_name in newly_processable_files:
        file_path, _ = doc_ids[file_name]
        pdf_dir = config.BASE_PDF_PATH
        rel_path = os.path.relpath(file_path, pdf_dir)
        rel_path_no_ext = os.path.splitext(rel_path)[0]
        text_file_path = os.path.join(base_text_path, rel_path_no_ext)
        
        assert os.path.exists(text_file_path), f"Text file should exist for newly processed file: {text_file_path}"
        log_handle.info(f"Verified text file exists for newly processed file: {file_name}")
    
    # Check OpenSearch
    log_handle.info("Verifying newly processed files exist in OpenSearch")
    # Refresh the index to make sure all newly indexed documents are available for search
    opensearch_client.indices.refresh(index=index_name)
    response = opensearch_client.search(index=index_name, body=search_body)
    updated_indexed_doc_ids = list(set([hit['_source']['document_id'] for hit in response['hits']['hits']]))
    
    for file_name in newly_processable_files:
        _, doc_id = doc_ids[file_name]
        assert doc_id in updated_indexed_doc_ids, f"Document should be indexed for newly processed file: {file_name} (doc_id: {doc_id})"
        log_handle.info(f"Verified document indexed for newly processed file: {file_name}")
    
    log_handle.info(f"Test 2 completed successfully. Processed {len(newly_processable_files)} previously ignored files.")
