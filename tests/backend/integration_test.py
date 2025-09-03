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
    return doc_ids, ignored_files


def test_integration(init_integration_test):
    """
    Integration test that verifies _ignore files work correctly during crawling.
    """
    doc_ids, ignored_files = init_integration_test
    
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
        text_file_path = os.path.join(base_text_path, rel_path.replace('.pdf', '.txt'))
        
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
    
    # Get all documents from OpenSearch
    search_body = {
        "size": 1000,
        "query": {"match_all": {}}
    }
    
    response = opensearch_client.search(index=index_name, body=search_body)
    log_handle.info(f"{json_dumps(response, truncate_fields=['vector_embedding', 'text_content_gujarati', 'text_content_hindi'])}")
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