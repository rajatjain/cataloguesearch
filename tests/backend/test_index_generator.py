import os
import shutil
import tempfile
import traceback

import pytest

from backend.crawler.index_generator import IndexGenerator
from backend.crawler.paragraph_generator.factory import create_paragraph_generator
from backend.crawler.paragraph_generator.language_meta import get_language_meta
from backend.common.embedding_models import get_embedding_model_factory
from backend.common.opensearch import get_opensearch_client
from backend.common.opensearch import create_indices_if_not_exists
from tests.backend.base import *

log_handle = logging.getLogger(__name__)

@pytest.fixture(scope="module")
def setup():
    config = Config()
    temp_dir = tempfile.mkdtemp("indexing_module_test")
    # copy ocr files to this directory
    base_test_dir = get_test_base_dir()
    ocr_source_dir = os.path.join(base_test_dir, "data", "ocr", config.CHUNK_STRATEGY)
    ocr_dest_dir = os.path.join(temp_dir, "ocr")

    shutil.copytree(ocr_source_dir, ocr_dest_dir)

    config.settings()["crawler"]["base_ocr_path"] = ocr_dest_dir
    return temp_dir

@pytest.fixture(scope="function")
def indexing_module():
    """
    Provides an initialized IndexingEmbeddingModule instance for testing.
    """
    config = Config()
    opensearch_client = get_opensearch_client(config)
    try:
        if opensearch_client.indices.exists(config.OPENSEARCH_INDEX_NAME):
            response = opensearch_client.indices.delete(index=config.OPENSEARCH_INDEX_NAME)
            log_handle.info(f"Deleted index '{config.OPENSEARCH_INDEX_NAME}' before recreating: {response}")
        else:
            log_handle.warning(f"Index '{config.OPENSEARCH_INDEX_NAME}' does not exist, skipping deletion.")
    except Exception as e:
        traceback.print_exc()
        log_handle.error(f"Error deleting index '{config.OPENSEARCH_INDEX_NAME}': {e}")

    module = IndexGenerator(config, opensearch_client)
    create_indices_if_not_exists(config, opensearch_client)
    return module


# Helper functions for test_index_generator
def setup_document_paths(temp_dir, doc_name):
    """Set up OCR directory paths and get pages list for a document."""
    ocr_base_dir = os.path.join(temp_dir, "ocr")
    ocr_dir = os.path.join(ocr_base_dir, doc_name)
    pages_list = get_pages_list(ocr_dir)
    return ocr_dir, pages_list

def get_pages_list(ocr_dir):
    """Get sorted list of page numbers from OCR directory."""
    pages = []
    config = Config()
    extn = ".txt" if config.CHUNK_STRATEGY == "paragraph" else ".json"
    if os.path.exists(ocr_dir):
        for file in os.listdir(ocr_dir):
            if file.startswith("page_") and file.endswith(extn):
                page_num = int(file.replace("page_", "").replace(extn, ""))
                pages.append(page_num)
    return sorted(pages)

def get_expected_paragraph_count(ocr_dir, pages_list, language, indexing_module):
    """Calculate expected paragraph count by calling generate_paragraphs directly."""
    paragraphs = []
    scan_config = {}
    for page_num in pages_list:
        page_file = os.path.join(ocr_dir, f"page_{page_num:04d}.txt")
        if os.path.exists(page_file):
            with open(page_file, 'r', encoding='utf-8') as f:
                content = f.read()
            page_paragraphs = content.split("\n----\n") if content.strip() else []
            paragraphs.append((page_num, page_paragraphs))

    # Create paragraph generator with language-specific meta
    language_meta = get_language_meta(language, scan_config)
    paragraph_gen = create_paragraph_generator(indexing_module._config, language_meta)
    processed_paras = paragraph_gen.generate_paragraphs(paragraphs, scan_config)

    return len(processed_paras)

def count_paragraphs_in_output_dir(output_dir):
    """Count total paragraphs written to output text directory."""
    total_paragraphs = 0
    for file in os.listdir(output_dir):
        if file.endswith('.txt'):
            file_path = os.path.join(output_dir, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    paragraphs = content.split("\n----\n")
                    total_paragraphs += len(paragraphs)
    return total_paragraphs

def validate_dry_run_phase(config, temp_dir, doc_configs, indexing_module, opensearch_client):
    """Validate dry run phase: no documents indexed, but paragraphs generated."""
    log_handle.info("=== DRY RUN VALIDATION ===")

    # Refresh and verify no documents indexed
    opensearch_client.indices.refresh(index=indexing_module._index_name)
    all_docs_after_dry_run = get_documents(config, "match_all")
    log_handle.info(f"Documents after dry run: {len(all_docs_after_dry_run)}")
    assert len(all_docs_after_dry_run) == 0, "No documents should be indexed to OpenSearch during dry run"

    # Validate paragraph generation for each document
    for doc_config in doc_configs:
        output_dir = doc_config['output_dir']
        expected_count = doc_config['expected_count']
        doc_name = doc_config['doc_name']

        assert os.path.exists(output_dir), f"{doc_name} output directory should exist"

        text_files = [f for f in os.listdir(output_dir) if f.endswith('.txt')]
        log_handle.info(f"{doc_name} text files generated: {len(text_files)}")

        actual_paragraphs = count_paragraphs_in_output_dir(output_dir)
        log_handle.info(f"{doc_name} paragraphs in output files: {actual_paragraphs}")

        assert actual_paragraphs == expected_count, \
            f"{doc_name} paragraphs in files should match expected count: expected {expected_count}, got {actual_paragraphs}"

def validate_document_counts(config, doc_configs):
    """Validate that document counts match expected paragraph counts."""
    log_handle.info("=== DOCUMENT COUNT VALIDATION ===")

    # Get language-specific documents
    hindi_docs = get_documents(config, "field_exists", "text_content_hindi")
    gujarati_docs = get_documents(config, "field_exists", "text_content_gujarati")

    # Filter and validate each document set
    for doc_config in doc_configs:
        doc_id = doc_config['doc_id']
        expected_count = doc_config['expected_count']
        filename = doc_config['filename']
        language = doc_config['language']
        doc_name = doc_config['doc_name']

        if language == 'hi':
            docs = [doc for doc in hindi_docs if doc['_source']['document_id'] == doc_id]
        else:  # gujarati
            docs = [doc for doc in gujarati_docs if doc['_source']['document_id'] == doc_id]

        actual_count = len(docs)
        log_handle.info(f"Actual {doc_name} document count: {actual_count}")

        # Validate document properties
        for doc in docs:
            source = doc['_source']
            assert source['document_id'] == doc_id
            assert source['original_filename'] == filename
            assert source['metadata']['language'] == language

            if language == 'hi':
                assert 'text_content_hindi' in source
                assert source['text_content_hindi'].strip() != ""
                assert 'text_content_gujarati' not in source or source['text_content_gujarati'] == ''
            else:
                assert 'text_content_gujarati' in source
                assert source['text_content_gujarati'].strip() != ""
                assert 'text_content_hindi' not in source or source['text_content_hindi'] == ''

        # Validate counts match
        assert actual_count == expected_count, \
            f"{doc_name} document count mismatch: expected {expected_count}, got {actual_count}"

    return hindi_docs, gujarati_docs

def validate_vector_embeddings(config):
    """Validate that all documents have properly sized vector embeddings."""
    log_handle.info("=== VECTOR EMBEDDING VALIDATION ===")

    expected_embedding_dim = get_embedding_model_factory(config).get_embedding_dimension()
    all_indexed_docs = get_documents(config, "match_all")

    log_handle.info(f"Expected embedding dimension: {expected_embedding_dim}")
    log_handle.info(f"Validating vector embeddings for all {len(all_indexed_docs)} documents")

    for doc in all_indexed_docs:
        source = doc['_source']
        doc_id_for_logging = source.get('document_id', 'unknown')

        # Validate vector embedding exists and has correct properties
        assert 'vector_embedding' in source, f"Missing vector_embedding in document {doc['_id']} (doc_id: {doc_id_for_logging})"
        assert isinstance(source['vector_embedding'], list), f"vector_embedding should be a list in document {doc['_id']} (doc_id: {doc_id_for_logging})"
        assert len(source['vector_embedding']) == expected_embedding_dim, \
            f"vector_embedding dimension mismatch in document {doc['_id']} (doc_id: {doc_id_for_logging}): expected {expected_embedding_dim}, got {len(source['vector_embedding'])}"
        assert all(isinstance(x, (int, float)) for x in source['vector_embedding']), \
            f"vector_embedding should contain only numbers in document {doc['_id']} (doc_id: {doc_id_for_logging})"

    log_handle.info(f"✅ Vector embedding validation passed for all {len(all_indexed_docs)} documents!")

def get_documents(config, query_type="match_all", field=None, max_results: int = 1000) -> list:
    """
    Retrieves documents from the configured OpenSearch index based on query type.

    Args:
        config: The application configuration object, which contains OpenSearch settings.
        query_type: Type of query - "match_all", "field_exists", or "count_only"
        field: Field name for field_exists queries (required when query_type="field_exists")
        max_results: The maximum number of documents to return.

    Returns:
        A list of the documents found in the index for regular queries, or count for "count_only".
        Returns an empty list or 0 if an error occurs.
    """
    try:
        # Initialize the OpenSearch client and get the index name from the config
        opensearch_client = get_opensearch_client(config)
        index_name = config.OPENSEARCH_INDEX_NAME

        # Build query based on type
        if query_type == "match_all":
            query = {"match_all": {}}
        elif query_type == "field_exists":
            if not field:
                raise ValueError("field parameter required for field_exists query")
            query = {"exists": {"field": field}}
        else:
            raise ValueError(f"Unsupported query_type: {query_type}")

        # Define the search body
        search_body = {
            "size": max_results,
            "query": query
        }

        # Execute the search query
        response = opensearch_client.search(
            index=index_name,
            body=search_body
        )

        # Return results based on query type
        if query_type == "count_only":
            return response['hits']['total']['value']
        else:
            return response['hits']['hits']

    except Exception as e:
        print(f"An error occurred while querying OpenSearch: {e}")
        return [] if query_type != "count_only" else 0

# Keep the old function for backward compatibility
def get_all_documents(config, max_results: int = 1000) -> list:
    """Legacy function - use get_documents() instead."""
    return get_documents(config, "match_all", max_results=max_results)

def test_create_index_if_not_exists(indexing_module):
    """
    Tests that the index is created correctly with the specified mappings and settings.
    """
    config = Config()
    opensearch_client = get_opensearch_client(config)
    index_name = indexing_module._index_name
    assert opensearch_client.indices.exists(index_name)

    # Verify some settings and mappings
    index_info = opensearch_client.indices.get(index_name)
    assert index_info[index_name]['settings']['index']['knn'] == 'true'

    mappings = index_info[index_name]['mappings']['properties']
    assert 'document_id' in mappings and mappings['document_id']['type'] == 'keyword'
    assert 'vector_embedding' in mappings and mappings['vector_embedding']['type'] == 'knn_vector'
    assert mappings['vector_embedding']['dimension'] == \
           get_embedding_model_factory(config).get_embedding_dimension()
    assert 'text_content_hindi' in mappings and mappings['text_content_hindi']['analyzer'] == 'hindi_analyzer'
    assert 'text_content_gujarati' in mappings and mappings['text_content_gujarati']['analyzer'] == 'gujarati_analyzer'

def test_generate_embedding_empty_text(indexing_module):
    """
    Tests embedding generation for empty text.
    """
    config = Config()
    embedding_model = get_embedding_model_factory(config)
    embedding = embedding_model.get_embedding("")
    assert len(embedding) == embedding_model.get_embedding_dimension()

def test_index_generator(setup, indexing_module):
    """
    Tests comprehensive indexing workflow with incremental validation.
    Validates dry run, paragraph generation, live indexing, and vector embeddings.
    """
    config = Config()
    opensearch_client = get_opensearch_client(config)
    temp_dir = setup
    scan_config = {
        "header_regex": [
            "^.{0,20}इतिहास एवं लेख$",
            "^.{0,15}पर.{0,5}निबंध$",
            "^निबंध.{0,15}$",
            "^નિબંધ.{0,15}$",
            "^.{0,15}ઉપર.{0,15}નિબંધ$",
            "^.{0,20}ઇતિહાસ.{0,8}લેખ$",
            "^[0-9]{0,4}$"
        ],
        "crop": {
            "top": 8,
            "bottom": 8
        }
    }

    # Document configurations for testing
    document_configs = [
        # First test case: Bangalore documents
        {
            'doc_name': 'bangalore_hindi',
            'doc_id': 'bangalore_hindi_doc_id',
            'filename': 'bangalore_hindi.pdf',
            'language': 'hi',
            'metadata': {'language': 'hi'},
            'para_count_advanced': 20,
            'para_count_paragraph': 20
        },
        {
            'doc_name': 'bangalore_gujarati',
            'doc_id': 'bangalore_gujarati_doc_id',
            'filename': 'bangalore_gujarati.pdf',
            'language': 'gu',
            'metadata': {'language': 'gu'},
            'para_count_advanced': 21,
            'para_count_paragraph': 20
        },
        # Second test case: Thanjavur/Songadh documents
        {
            'doc_name': 'thanjavur_hindi',
            'doc_id': 'thanjavur_hindi_doc_id',
            'filename': 'thanjavur_hindi.pdf',
            'language': 'hi',
            'metadata': {'language': 'hi'},
            'para_count_advanced': 21,
            'para_count_paragraph': 20
        },
        {
            'doc_name': 'songadh_gujarati',
            'doc_id': 'songadh_gujarati_doc_id',
            'filename': 'songadh_gujarati.pdf',
            'language': 'gu',
            'metadata': {'language': 'gu'},
            'para_count_advanced': 21,
            'para_count_paragraph': 20
        }
    ]

    log_handle.info("=== SETUP PHASE ===")

    # Setup document paths and expected counts
    for doc_config in document_configs:
        doc_name = doc_config['doc_name']
        language = doc_config['language']

        # Setup paths
        ocr_dir, pages_list = setup_document_paths(temp_dir, doc_name)
        output_dir = os.path.join(temp_dir, "text", doc_name)
        os.makedirs(output_dir, exist_ok=True)

        # Calculate expected count
        para_count_key = "para_count_%s" % config.CHUNK_STRATEGY
        expected_count = doc_config[para_count_key]
        # expected_count = get_expected_paragraph_count(ocr_dir, pages_list, language, indexing_module)

        # Add to config
        doc_config.update({
            'ocr_dir': ocr_dir,
            'pages_list': pages_list,
            'output_dir': output_dir,
            'expected_count': expected_count
        })

        log_handle.info(f"{doc_name}: {len(pages_list)} pages, expected {expected_count} paragraphs")

    # Phase 1: Dry run indexing
    log_handle.info("=== PHASE 1: DRY RUN INDEXING ===")
    for doc_config in document_configs:
        indexing_module.index_document(
            doc_config['doc_id'], doc_config['filename'], doc_config['ocr_dir'],
            doc_config['output_dir'], doc_config['pages_list'], doc_config['metadata'],
            scan_config, {}, reindex_metadata_only=False, dry_run=True)

    # Validate dry run phase
    validate_dry_run_phase(config, temp_dir, document_configs, indexing_module, opensearch_client)

    # Phase 2: Live indexing (incremental)
    log_handle.info("=== PHASE 2: LIVE INDEXING ===")
    for i, doc_config in enumerate(document_configs):
        log_handle.info(f"Indexing document {i+1}/{len(document_configs)}: {doc_config['doc_name']}")

        indexing_module.index_document(
            doc_config['doc_id'], doc_config['filename'], doc_config['ocr_dir'],
            doc_config['output_dir'], doc_config['pages_list'], doc_config['metadata'],
            scan_config, {}, reindex_metadata_only=False, dry_run=False)

        opensearch_client.indices.refresh(index=indexing_module._index_name)

        # Log incremental progress
        total_docs = len(get_documents(config, "match_all"))
        log_handle.info(f"Total documents after indexing {doc_config['doc_name']}: {total_docs}")

    # Phase 3: Final validation
    log_handle.info("=== PHASE 3: FINAL VALIDATION ===")

    # Validate document counts and properties
    hindi_docs, gujarati_docs = validate_document_counts(config, document_configs)

    # Validate total counts match expectations
    total_expected_hindi = sum(d['expected_count'] for d in document_configs if d['language'] == 'hi')
    total_expected_gujarati = sum(d['expected_count'] for d in document_configs if d['language'] == 'gu')

    assert len(hindi_docs) == total_expected_hindi, \
        f"Total Hindi count mismatch: expected {total_expected_hindi}, got {len(hindi_docs)}"
    assert len(gujarati_docs) == total_expected_gujarati, \
        f"Total Gujarati count mismatch: expected {total_expected_gujarati}, got {len(gujarati_docs)}"

    log_handle.info(f"✅ Total validation passed - Hindi: {len(hindi_docs)}, Gujarati: {len(gujarati_docs)}")

    # Validate vector embeddings for all documents
    validate_vector_embeddings(config)

    log_handle.info("🎉 All phases completed successfully!")


def test_index_documents_with_bookmarks_validation(setup, indexing_module):
    """
    Tests bookmark indexing and validation with songadh_hindi and hampi_gujarati documents.
    Validates that bookmarks are properly indexed, searchable, and counts match expectations.
    """
    config = Config()
    opensearch_client = get_opensearch_client(config)
    temp_dir = setup
    scan_config = {}

    log_handle.info("=== BOOKMARK INDEXING TEST ===")

    # Document configurations with bookmarks
    document_configs = [
        {
            'doc_name': 'jaipur_hindi',
            'doc_id': 'jaipur_hindi_doc_id',
            'filename': 'jaipur_hindi.pdf',
            'para_count_advanced': 21,
            'para_count_paragraph': 20,
            'language': 'hi',
            'metadata': {'language': 'hi'},
            'bookmarks': {1: "प्रस्तावना", 2: "मुख्य विषय", 3: "निष्कर्ष",
                          4: "अध्याय एक", 5: "अध्याय दो", 6: "अध्याय तीन"}
        },
        {
            'doc_name': 'hampi_gujarati',
            'doc_id': 'hampi_gujarati_doc_id',
            'filename': 'hampi_gujarati.pdf',
            'para_count_advanced': 20,
            'para_count_paragraph': 19,
            'language': 'gu',
            'metadata': {'language': 'gu'},
            'bookmarks': {1: "પરિચય", 2: "મુખ્ય વિષય", 3: "સમાપન",
                          4: "પ્રકરણ એક", 5: "પ્રકરણ બે", 6: "પ્રકરણ ત્રણ"}
        }
    ]

    # Setup document paths and expected counts
    for doc_config in document_configs:
        doc_name = doc_config['doc_name']
        language = doc_config['language']

        # Setup paths
        ocr_dir, pages_list = setup_document_paths(temp_dir, doc_name)
        output_dir = os.path.join(temp_dir, "text", doc_name)
        os.makedirs(output_dir, exist_ok=True)

        # Calculate expected count
        para_count_key = "para_count_%s" % config.CHUNK_STRATEGY
        expected_count = doc_config[para_count_key]

        # Add to config
        doc_config.update({
            'ocr_dir': ocr_dir,
            'pages_list': pages_list,
            'output_dir': output_dir,
            'expected_count': expected_count
        })

        log_handle.info(f"{doc_name}: {len(pages_list)} pages, expected {expected_count} paragraphs")
        log_handle.info(f"{doc_name} bookmarks: {doc_config['bookmarks']}")

    # Index documents with bookmarks
    log_handle.info("=== INDEXING WITH BOOKMARKS ===")
    for doc_config in document_configs:
        log_handle.info(f"Indexing {doc_config['doc_name']} with bookmarks")

        indexing_module.index_document(
            doc_config['doc_id'], doc_config['filename'], doc_config['ocr_dir'],
            doc_config['output_dir'], doc_config['pages_list'], doc_config['metadata'],
            scan_config, doc_config['bookmarks'], reindex_metadata_only=False, dry_run=False)

    # Refresh index to make documents searchable
    opensearch_client.indices.refresh(index=indexing_module._index_name)

    log_handle.info("=== BOOKMARK VALIDATION ===")

    # Validate bookmark indexing for each document
    for doc_config in document_configs:
        doc_id = doc_config['doc_id']
        doc_name = doc_config['doc_name']
        bookmarks = doc_config['bookmarks']
        expected_count = doc_config['expected_count']
        language = doc_config['language']

        # Get all documents for this document ID
        search_body = {
            "size": 1000,
            "query": {
                "term": {"document_id": doc_id}
            }
        }

        response = opensearch_client.search(index=indexing_module._index_name, body=search_body)
        docs = response['hits']['hits']

        log_handle.info(f"{doc_name}: Found {len(docs)} indexed documents")
        assert len(docs) == expected_count, f"{doc_name} document count mismatch: expected {expected_count}, got {len(docs)}"

        # Validate each document has correct bookmark
        bookmark_counts = {}
        for doc in docs:
            source = doc['_source']
            page_number = source['page_number']
            bookmark = source.get('bookmarks', None)

            # Verify bookmark matches expected for this page
            expected_bookmark = bookmarks.get(page_number, None)
            assert bookmark == expected_bookmark, \
                f"{doc_name} page {page_number}: expected bookmark '{expected_bookmark}', got '{bookmark}'"

            # Count bookmarks
            if bookmark:
                bookmark_counts[bookmark] = bookmark_counts.get(bookmark, 0) + 1

            # Verify language-specific content exists
            if language == 'hi':
                assert 'text_content_hindi' in source, f"{doc_name} missing Hindi content"
                assert source['text_content_hindi'].strip() != "", f"{doc_name} empty Hindi content"
            else:
                assert 'text_content_gujarati' in source, f"{doc_name} missing Gujarati content"
                assert source['text_content_gujarati'].strip() != "", f"{doc_name} empty Gujarati content"

        log_handle.info(f"{doc_name} bookmark distribution: {bookmark_counts}")

    # Test bookmark searchability
    log_handle.info("=== BOOKMARK SEARCH VALIDATION ===")

    # Test specific bookmark searches
    test_searches = [
        ("प्रस्तावना", "jaipur_hindi", "Hindi"),
        ("મુખ્ય વિષય", "hampi_gujarati", "Gujarati"),
        ("निष्कर्ष", "jaipur_hindi", "Hindi"),
        ("સમાપન", "hampi_gujarati", "Gujarati")
    ]

    for bookmark_text, expected_doc, language in test_searches:
        # Search for documents with this bookmark
        search_body = {
            "size": 1000,
            "query": {
                "match": {"bookmarks": bookmark_text}
            }
        }

        response = opensearch_client.search(index=indexing_module._index_name, body=search_body)
        matching_docs = response['hits']['hits']

        log_handle.info(f"Bookmark search '{bookmark_text}': {len(matching_docs)} documents found")

        # Verify all matching documents belong to expected document
        for doc in matching_docs:
            source = doc['_source']
            doc_filename = source['original_filename']
            assert expected_doc in doc_filename, \
                f"Bookmark '{bookmark_text}' found in unexpected document: {doc_filename}"
            assert source['bookmarks'] == bookmark_text, \
                f"Document bookmark mismatch: expected '{bookmark_text}', got '{source['bookmarks']}'"

        # Verify no documents found for opposite language
        opposite_language_docs = []
        for doc in matching_docs:
            source = doc['_source']
            if language == "Hindi" and 'text_content_gujarati' in source and source['text_content_gujarati'].strip():
                opposite_language_docs.append(doc)
            elif language == "Gujarati" and 'text_content_hindi' in source and source['text_content_hindi'].strip():
                opposite_language_docs.append(doc)

        assert len(opposite_language_docs) == 0, \
            f"Bookmark '{bookmark_text}' incorrectly found in {len(opposite_language_docs)} opposite language documents"

    # Test wildcard bookmark searches
    log_handle.info("=== WILDCARD BOOKMARK SEARCH ===")

    wildcard_searches = [
        ("अध्याय*", "jaipur_hindi", 2),  # Should match "अध्याय एक" and "अध्याय दो"
        ("પ્રકરણ*", "hampi_gujarati", 2)   # Should match "પ્રકરણ એક" and "પ્રકરણ બે"
    ]

    for wildcard_pattern, expected_doc, expected_min_count in wildcard_searches:
        search_body = {
            "size": 1000,
            "query": {
                "wildcard": {"bookmarks": wildcard_pattern}
            }
        }

        response = opensearch_client.search(index=indexing_module._index_name, body=search_body)
        matching_docs = response['hits']['hits']

        log_handle.info(f"Wildcard search '{wildcard_pattern}': {len(matching_docs)} documents found")
        assert len(matching_docs) >= expected_min_count, \
            f"Wildcard search '{wildcard_pattern}' expected at least {expected_min_count} docs, got {len(matching_docs)}"

        # Verify all results belong to expected document
        for doc in matching_docs:
            source = doc['_source']
            doc_filename = source['original_filename']
            assert expected_doc in doc_filename, \
                f"Wildcard '{wildcard_pattern}' found in unexpected document: {doc_filename}"

    # Final comprehensive validation
    log_handle.info("=== FINAL BOOKMARK VALIDATION ===")

    all_docs = get_documents(config, "match_all")
    total_docs_with_bookmarks = 0
    bookmark_distribution = {}

    for doc in all_docs:
        source = doc['_source']
        bookmark = source.get('bookmarks', None)
        if bookmark:
            total_docs_with_bookmarks += 1
            bookmark_distribution[bookmark] = bookmark_distribution.get(bookmark, 0) + 1

    expected_total = sum(d['expected_count'] for d in document_configs)
    assert total_docs_with_bookmarks == expected_total, \
        f"Total documents with bookmarks mismatch: expected {expected_total}, got {total_docs_with_bookmarks}"

    log_handle.info(f"✅ Bookmark validation passed!")
    log_handle.info(f"Total documents with bookmarks: {total_docs_with_bookmarks}")
    log_handle.info(f"Bookmark distribution: {bookmark_distribution}")
    log_handle.info("🎉 Bookmark indexing test completed successfully!")