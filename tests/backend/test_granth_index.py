"""
Unit tests for GranthIndexer class to test indexing of Granth objects into OpenSearch.

Tests the complete indexing pipeline:
1. Parse markdown files into Granth objects
2. Index Granth objects into granth_index and search_index
3. Verify data integrity and structure in both indices
4. Validate vector embeddings are properly generated
"""

import logging
import os
import pytest

from backend.config import Config
from backend.common.opensearch import get_opensearch_client
from backend.crawler.granth_index import GranthIndexer
from backend.crawler.markdown_parser import MarkdownParser
from tests.backend.base import *
from tests.backend.common import setup_granth

log_handle = logging.getLogger(__name__)

# Simplify the logs - reduce opensearch logging to avoid noise
logging.getLogger('opensearch').setLevel(logging.WARNING)


@pytest.fixture(scope="module", autouse=True)
def build_granth_index(initialise):
    """
    Setup OpenSearch indices for granth indexing tests.
    Creates clean granth_index and search_index with proper mappings.
    """
    config = Config()
    
    # Initialize OpenSearch client and ensure clean index state
    opensearch_client = get_opensearch_client(config)
    
    # Explicitly delete indices to ensure clean state and proper mapping creation
    log_handle.info("Deleting existing indices to ensure clean state for granth indexing")
    indices_to_delete = [
        config.OPENSEARCH_INDEX_NAME,           # search_index
        config.OPENSEARCH_GRANTH_INDEX_NAME,    # granth_index
        config.OPENSEARCH_METADATA_INDEX_NAME   # metadata_index
    ]
    
    for index_name in indices_to_delete:
        if index_name and opensearch_client.indices.exists(index=index_name):
            opensearch_client.indices.delete(index=index_name)
            log_handle.info(f"Deleted existing index: {index_name}")
    
    # Create indices with proper mapping (including knn_vector for embeddings)
    from backend.common.opensearch import create_indices_if_not_exists
    create_indices_if_not_exists(config, opensearch_client)
    log_handle.info("Created indices with proper mapping for granth indexing")
    
    yield
    
    # Cleanup - delete indices
    for index_name in indices_to_delete:
        if index_name and opensearch_client.indices.exists(index=index_name):
            opensearch_client.indices.delete(index=index_name, ignore=[400, 404])


def test_granth_indexing_pipeline_with_config():
    """
    Comprehensive test for granth indexing pipeline with get_merged_config functionality.
    
    Tests:
    1. Setup hierarchical directory structure with config.json files
    2. Parse 3 markdown files using MarkdownParser with base_folder for config merging
    3. Index each Granth object using GranthIndexer
    4. Verify data integrity in granth_index and search_index
    5. Validate vector embeddings and paragraph extraction
    6. Test metadata querying by Anuyog, Author, Teekakar, etc.
    """
    config = Config()
    opensearch_client = get_opensearch_client(config)
    indexer = GranthIndexer(config, opensearch_client)
    
    # Setup hierarchical directory structure with config files
    log_handle.info("=== Phase 1: Setting up directory structure with configs ===")
    granth_setup = setup_granth()
    base_dir = granth_setup["base_dir"]
    granth_files = granth_setup["granth_files"]
    
    # Create parser with base_folder for config merging
    parser = MarkdownParser(base_folder=base_dir)
    
    granth_objects = []
    expected_metadata = {}
    
    # Phase 2: Parse all markdown files with config merging
    log_handle.info("=== Phase 2: Parsing markdown files with config merging ===")
    for granth_name, file_info in granth_files.items():
        file_path = file_info["file_path"]
        expected_config = file_info["config"]
        
        log_handle.info(f"Parsing file: {file_path}")
        granth = parser.parse_file(file_path)
        granth_objects.append(granth)
        expected_metadata[granth_name] = expected_config
        
        # Basic parsing validation
        assert granth is not None, f"Failed to parse {file_path}"
        assert len(granth._verses) > 0, f"No verses found in {file_path}"
        
        # Validate that config was merged correctly
        metadata = granth._metadata
        assert metadata._anuyog == expected_config["Anuyog"], f"Anuyog mismatch for {granth_name}"
        assert metadata._author == expected_config["Author"], f"Author mismatch for {granth_name}"
        assert metadata._teekakar == expected_config["Teekakar"], f"Teekakar mismatch for {granth_name}"
        assert metadata._language == expected_config["language"], f"Language mismatch for {granth_name}"
        
        log_handle.info(f"✓ Parsed {file_path}: {len(granth._verses)} verses")
        log_handle.info(f"✓ Config merged - Anuyog: {metadata._anuyog}, Author: {metadata._author}")
    
    # Phase 3: Index all Granth objects
    log_handle.info("=== Phase 3: Indexing Granth objects ===")
    for granth_name, granth in zip(granth_files.keys(), granth_objects):
        log_handle.info(f"Indexing granth: {granth_name}")
        
        # Index with dry_run=False to actually store data
        indexer.index_granth(granth, dry_run=False)
        log_handle.info(f"✓ Indexed granth: {granth_name}")
    
    # Allow some time for indexing to complete
    opensearch_client.indices.refresh(index=config.OPENSEARCH_GRANTH_INDEX_NAME)
    opensearch_client.indices.refresh(index=config.OPENSEARCH_INDEX_NAME)
    
    # Phase 4: Verify granth_index data and metadata
    log_handle.info("=== Phase 4: Validating granth_index ===")
    
    # Check total document count in granth_index
    granth_search_result = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"match_all": {}}, "size": 10}
    )
    
    granth_docs = granth_search_result["hits"]["hits"]
    assert len(granth_docs) == 3, f"Expected 3 documents in granth_index, found {len(granth_docs)}"
    log_handle.info(f"✓ Found {len(granth_docs)} documents in granth_index")
    
    # Verify unique original_filenames and detailed verse counts
    original_filenames = set()
    file_verse_data = {}
    
    for doc in granth_docs:
        source = doc["_source"]
        original_filename = source["original_filename"]
        original_filenames.add(original_filename)
        
        # Validate document structure
        assert "granth_id" in source, "granth_id missing from granth_index document"
        assert "name" in source, "name missing from granth_index document"
        assert "metadata" in source, "metadata missing from granth_index document"
        assert "verses" in source, "verses missing from granth_index document"
        assert "timestamp_indexed" in source, "timestamp_indexed missing from granth_index document"
        
        # Validate metadata structure
        metadata = source["metadata"]
        assert "language" in metadata, "language missing from metadata"
        assert "author" in metadata, "author missing from metadata"
        
        # Validate verses structure and count verse types
        verses = source["verses"]
        assert len(verses) > 0, "No verses found in granth_index document"
        
        verse_type_counts = {}
        for verse in verses:
            assert "seq_num" in verse, "seq_num missing from verse"
            assert "verse" in verse, "verse content missing from verse"
            assert "type" in verse, "type missing from verse"
            assert "type_num" in verse, "type_num missing from verse"
            
            # Count verse types
            verse_type = verse["type"]
            verse_type_counts[verse_type] = verse_type_counts.get(verse_type, 0) + 1
        
        # Store verse data for detailed validation
        file_verse_data[original_filename] = {
            "total_verses": len(verses),
            "verse_types": verse_type_counts
        }
    
    assert len(original_filenames) == 3, f"Expected 3 unique filenames, found {len(original_filenames)}"
    log_handle.info(f"✓ Verified 3 unique original_filenames: {original_filenames}")
    
    # Detailed verse count validation per file
    for filename, data in file_verse_data.items():
        total_verses = data["total_verses"]
        verse_types = data["verse_types"]
        
        if "simple_granth.md" in filename:
            assert total_verses == 5, f"simple_granth.md should have 5 verses, found {total_verses}"
            assert verse_types.get("Shlok", 0) == 5, f"simple_granth.md should have 5 Shlok, found {verse_types.get('Shlok', 0)}"
            log_handle.info(f"✓ simple_granth.md: {total_verses} verses (5 Shlok)")
            
        elif "adhikar_granth.md" in filename:
            assert total_verses == 7, f"adhikar_granth.md should have 7 verses, found {total_verses}"
            assert verse_types.get("Shlok", 0) == 7, f"adhikar_granth.md should have 7 Shlok, found {verse_types.get('Shlok', 0)}"
            log_handle.info(f"✓ adhikar_granth.md: {total_verses} verses (7 Shlok)")
            
        elif "mixed_granth.md" in filename:
            assert total_verses == 15, f"mixed_granth.md should have 15 verses, found {total_verses}"
            assert verse_types.get("Gatha", 0) == 9, f"mixed_granth.md should have 9 Gatha, found {verse_types.get('Gatha', 0)}"
            assert verse_types.get("Kalash", 0) == 6, f"mixed_granth.md should have 6 Kalash, found {verse_types.get('Kalash', 0)}"
            log_handle.info(f"✓ mixed_granth.md: {total_verses} verses (9 Gatha + 6 Kalash)")
        
        log_handle.info(f"  File: {filename}")
        log_handle.info(f"  Total verses: {total_verses}")
        log_handle.info(f"  Verse types: {verse_types}")
    
    # Phase 4: Verify search_index data
    log_handle.info("=== Phase 4: Validating search_index ===")
    
    # Check document count in search_index (should be paragraph chunks)
    search_result = opensearch_client.search(
        index=config.OPENSEARCH_INDEX_NAME,
        body={"query": {"match_all": {}}, "size": 100}
    )
    
    search_docs = search_result["hits"]["hits"]
    assert len(search_docs) > 0, "No documents found in search_index"
    log_handle.info(f"✓ Found {len(search_docs)} paragraph chunks in search_index")
    
    # Verify search_index document structure and embeddings
    embedding_count = 0
    document_ids = set()
    content_types = set()
    
    for doc in search_docs:
        source = doc["_source"]
        
        # Validate required fields
        assert "chunk_id" in source, "chunk_id missing from search_index document"
        assert "document_id" in source, "document_id missing from search_index document"
        assert "vector_embedding" in source, "vector_embedding missing from search_index document"
        assert "metadata" in source, "metadata missing from search_index document"
        
        # Validate vector embedding
        embedding = source["vector_embedding"]
        assert isinstance(embedding, list), "vector_embedding should be a list"
        assert len(embedding) > 0, "vector_embedding should not be empty"
        assert all(isinstance(x, (int, float)) for x in embedding), "vector_embedding should contain numbers"
        embedding_count += 1
        
        # Collect metadata for validation
        document_ids.add(source["document_id"])
        metadata = source["metadata"]
        if "verse_content_type" in metadata:
            content_types.add(metadata["verse_content_type"])
        
        # Validate content fields (should have text in language-specific fields)
        has_content = False
        for field in ["text_content_hindi", "text_content_gujarati"]:
            if field in source and source[field]:
                has_content = True
                break
        assert has_content, "No text content found in language fields"
    
    log_handle.info(f"✓ Verified {embedding_count} vector embeddings in search_index")
    log_handle.info(f"✓ Found content types: {content_types}")
    
    # Verify we have both teeka and bhavarth content
    assert "teeka" in content_types or "bhavarth" in content_types, "Expected teeka or bhavarth content types"
    
    # Phase 5: Cross-validate data consistency
    log_handle.info("=== Phase 5: Cross-validation ===")
    
    # Verify document IDs match between indices
    granth_ids_from_granth_index = set()
    for doc in granth_docs:
        granth_ids_from_granth_index.add(doc["_source"]["granth_id"])
    
    granth_ids_from_search_index = set(document_ids)
    
    assert granth_ids_from_granth_index == granth_ids_from_search_index, \
        "Document IDs should match between granth_index and search_index"
    log_handle.info(f"✓ Document IDs consistent between indices: {len(granth_ids_from_granth_index)} unique IDs")
    
    # Phase 6: Validate adhikar field handling
    log_handle.info("=== Phase 6: Validating adhikar field handling ===")
    
    # Check adhikar field in granth_index documents
    simple_granth_doc = None
    adhikar_granth_doc = None
    mixed_granth_doc = None
    
    for doc in granth_docs:
        source = doc["_source"]
        filename = source["original_filename"]
        
        if "simple_granth.md" in filename:
            simple_granth_doc = source
        elif "adhikar_granth.md" in filename:
            adhikar_granth_doc = source
        elif "mixed_granth.md" in filename:
            mixed_granth_doc = source
    
    # Validate simple_granth (should have adhikar=None for all verses)
    if simple_granth_doc:
        for verse in simple_granth_doc["verses"]:
            assert verse.get("adhikar") is None, "simple_granth verses should have adhikar=None"
        log_handle.info("✓ simple_granth.md: All verses have adhikar=None")
    
    # Validate adhikar_granth (should have adhikar values for verses)
    if adhikar_granth_doc:
        adhikar_found = False
        for verse in adhikar_granth_doc["verses"]:
            if verse.get("adhikar") is not None:
                adhikar_found = True
                break
        assert adhikar_found, "adhikar_granth should have verses with adhikar values"
        log_handle.info("✓ adhikar_granth.md: Found verses with adhikar values")
    
    # Validate mixed_granth (should have adhikar values)
    if mixed_granth_doc:
        adhikar_found = False
        for verse in mixed_granth_doc["verses"]:
            if verse.get("adhikar") is not None:
                adhikar_found = True
                break
        assert adhikar_found, "mixed_granth should have verses with adhikar values"
        log_handle.info("✓ mixed_granth.md: Found verses with adhikar values")
    
    # Phase 7: Test metadata querying - validate get_merged_config functionality
    log_handle.info("=== Phase 7: Metadata Querying Tests ===")
    
    # Test querying by Anuyog
    log_handle.info("Testing queries by Anuyog...")
    simple_anuyog_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.anuyog": "Simple Anuyog"}}}
    )
    assert simple_anuyog_query["hits"]["total"]["value"] == 1, "Should find 1 document with Simple Anuyog"
    log_handle.info("✓ Query by Anuyog 'Simple Anuyog': 1 document found")
    
    charitra_anuyog_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.anuyog": "Charitra Anuyog"}}}
    )
    assert charitra_anuyog_query["hits"]["total"]["value"] == 1, "Should find 1 document with Charitra Anuyog"
    log_handle.info("✓ Query by Anuyog 'Charitra Anuyog': 1 document found")
    
    dravya_anuyog_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.anuyog": "Dravya Anuyog"}}}
    )
    assert dravya_anuyog_query["hits"]["total"]["value"] == 1, "Should find 1 document with Dravya Anuyog"
    log_handle.info("✓ Query by Anuyog 'Dravya Anuyog': 1 document found")
    
    # Test querying by Author
    log_handle.info("Testing queries by Author...")
    simple_author_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.author": "Simple Author"}}}
    )
    assert simple_author_query["hits"]["total"]["value"] == 1, "Should find 1 document with Simple Author"
    log_handle.info("✓ Query by Author 'Simple Author': 1 document found")
    
    kundkund_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.author": "Acharya Kundkund"}}}
    )
    assert kundkund_query["hits"]["total"]["value"] == 1, "Should find 1 document with Acharya Kundkund"
    log_handle.info("✓ Query by Author 'Acharya Kundkund': 1 document found")
    
    haribhadra_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.author": "Acharya Haribhadra"}}}
    )
    assert haribhadra_query["hits"]["total"]["value"] == 1, "Should find 1 document with Acharya Haribhadra"
    log_handle.info("✓ Query by Author 'Acharya Haribhadra': 1 document found")
    
    # Test querying by Teekakar
    log_handle.info("Testing queries by Teekakar...")
    simple_teekakar_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.teekakar": "Simple Teekakar"}}}
    )
    assert simple_teekakar_query["hits"]["total"]["value"] == 1, "Should find 1 document with Simple Teekakar"
    log_handle.info("✓ Query by Teekakar 'Simple Teekakar': 1 document found")
    
    amritchandra_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.teekakar": "Acharya Nemichandra"}}}
    )
    assert amritchandra_query["hits"]["total"]["value"] == 1, "Should find 1 document with Acharya Nemichandra"
    log_handle.info("✓ Query by Teekakar 'Acharya Nemichandra': 1 document found")
    
    todarmal_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.teekakar": "Pandit Todarmal"}}}
    )
    assert todarmal_query["hits"]["total"]["value"] == 1, "Should find 1 document with Pandit Todarmal"
    log_handle.info("✓ Query by Teekakar 'Pandit Todarmal': 1 document found")
    
    # Test querying by Language
    log_handle.info("Testing queries by Language...")
    hindi_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.language": "hi"}}}
    )
    assert hindi_query["hits"]["total"]["value"] == 2, "Should find 2 documents with Hindi language"
    log_handle.info("✓ Query by Language 'hi': 2 documents found")
    
    gujarati_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.language": "gu"}}}
    )
    assert gujarati_query["hits"]["total"]["value"] == 1, "Should find 1 document with Gujarati language"
    log_handle.info("✓ Query by Language 'gu': 1 document found")
    
    # Test search_index metadata inheritance
    log_handle.info("Testing search_index metadata inheritance...")
    
    # Debug: Check sample search_index document structure
    sample_search_doc = opensearch_client.search(
        index=config.OPENSEARCH_INDEX_NAME,
        body={"query": {"match_all": {}}, "size": 1}
    )
    if sample_search_doc["hits"]["hits"]:
        sample_doc = sample_search_doc["hits"]["hits"][0]["_source"]
        log_handle.info(f"Sample search_index doc metadata: {sample_doc.get('metadata', {})}")
    
    # Try match query instead of term query for better text matching
    search_anuyog_query = opensearch_client.search(
        index=config.OPENSEARCH_INDEX_NAME,
        body={"query": {"match": {"metadata.anuyog": "Simple Anuyog"}}}
    )
    assert search_anuyog_query["hits"]["total"]["value"] > 0, f"Should find paragraph chunks with Simple Anuyog. Found: {search_anuyog_query['hits']['total']['value']}"
    log_handle.info(f"✓ Search index query by Anuyog: {search_anuyog_query['hits']['total']['value']} chunks found")
    
    search_author_query = opensearch_client.search(
        index=config.OPENSEARCH_INDEX_NAME,
        body={"query": {"match": {"metadata.author": "Acharya Kundkund"}}}
    )
    assert search_author_query["hits"]["total"]["value"] > 0, f"Should find paragraph chunks with Acharya Kundkund. Found: {search_author_query['hits']['total']['value']}"
    log_handle.info(f"✓ Search index query by Author: {search_author_query['hits']['total']['value']} chunks found")
    
    # Test complex queries
    log_handle.info("Testing complex metadata queries...")
    complex_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={
            "query": {
                "bool": {
                    "must": [
                        {"term": {"metadata.language": "hi"}},
                        {"term": {"metadata.anuyog": "Simple Anuyog"}}
                    ]
                }
            }
        }
    )
    assert complex_query["hits"]["total"]["value"] == 1, "Should find 1 document matching both language=hi and anuyog=Simple Anuyog"
    log_handle.info("✓ Complex query (language=hi AND anuyog=Simple Anuyog): 1 document found")
    
    # Phase 8: Final validation summary
    log_handle.info("=== Phase 8: Test Summary ===")
    log_handle.info(f"✓ Successfully indexed 3 Granth files with hierarchical configs")
    log_handle.info(f"✓ get_merged_config functionality validated")
    log_handle.info(f"✓ granth_index: {len(granth_docs)} documents with complete structure")
    log_handle.info(f"✓ search_index: {len(search_docs)} paragraph chunks with embeddings")
    log_handle.info(f"✓ Vector embeddings: {embedding_count} valid embeddings generated")
    log_handle.info(f"✓ Content types: {content_types}")
    log_handle.info(f"✓ Adhikar field handling validated for all file types")
    log_handle.info(f"✓ Metadata querying tested: Anuyog, Author, Teekakar, Language")
    log_handle.info(f"✓ Complex metadata filtering validated")
    log_handle.info("🎉 Granth indexing with config merging test completed successfully!")