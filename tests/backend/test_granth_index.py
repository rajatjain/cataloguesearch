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
    
    # Phase 2: Parse all markdown files with config merging (skip prose granth files)
    log_handle.info("=== Phase 2: Parsing markdown files with config merging ===")
    for granth_name, file_info in granth_files.items():
        # Skip prose granth files (tested separately in test_granth_prose_indexing)
        if "prose_granth" in granth_name:
            continue

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
        body={"query": {"match_all": {}}, "size": 1000}
    )
    
    granth_docs = granth_search_result["hits"]["hits"]
    assert len(granth_docs) == 6, f"Expected 3 documents in granth_index, found {len(granth_docs)}"
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
            assert "type_start_num" in verse, "type_start_num missing from verse"
            assert "type_end_num" in verse, "type_end_num missing from verse"
            
            # Count verse types
            verse_type = verse["type"]
            verse_type_counts[verse_type] = verse_type_counts.get(verse_type, 0) + 1
        
        # Store verse data for detailed validation
        file_verse_data[original_filename] = {
            "total_verses": len(verses),
            "verse_types": verse_type_counts
        }
    
    assert len(original_filenames) == 6, f"Expected 3 unique filenames, found {len(original_filenames)}"
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
        body={"query": {"match_all": {}}, "size": 1000}
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
        assert "metadata" in source, "metadata missing from search_index document"

        # Get verse content type and language
        verse_content_type = source["metadata"].get("verse_content_type")
        language = source["metadata"].get("language")

        # Validate language-specific text content field
        if language == "hi":
            assert "text_content_hindi" in source, f"text_content_hindi missing for Hindi document"
            assert source["text_content_hindi"], "text_content_hindi should not be empty"
        elif language == "gu":
            assert "text_content_gujarati" in source, f"text_content_gujarati missing for Gujarati document"
            assert source["text_content_gujarati"], "text_content_gujarati should not be empty"

        # Fields WITH embeddings: teeka, bhavarth
        # Fields WITHOUT embeddings: verse, translation, meaning
        if verse_content_type in ["teeka", "bhavarth"]:
            # Should have vector_embedding
            assert "vector_embedding" in source, f"vector_embedding missing from {verse_content_type} document"
            embedding = source["vector_embedding"]
            assert isinstance(embedding, list), "vector_embedding should be a list"
            assert len(embedding) > 0, "vector_embedding should not be empty"
            assert all(isinstance(x, (int, float)) for x in embedding), "vector_embedding should contain numbers"
            embedding_count += 1
        else:
            # Should NOT have vector_embedding for verse, translation, meaning
            assert "vector_embedding" not in source, f"vector_embedding should not be present in {verse_content_type} document"

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
        body={"query": {"term": {"metadata.anuyog.keyword": "Simple Anuyog"}}}
    )
    assert simple_anuyog_query["hits"]["total"]["value"] == 2, "Should find 2 document with Simple Anuyog"
    log_handle.info("✓ Query by Anuyog 'Simple Anuyog': 2 document found")
    
    charitra_anuyog_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.anuyog.keyword": "Charitra Anuyog"}}}
    )
    assert charitra_anuyog_query["hits"]["total"]["value"] == 2, "Should find 2 document with Charitra Anuyog"
    log_handle.info("✓ Query by Anuyog 'Charitra Anuyog': 2 document found")
    
    dravya_anuyog_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.anuyog.keyword": "Dravya Anuyog"}}}
    )
    assert dravya_anuyog_query["hits"]["total"]["value"] == 2, "Should find 2 document with Dravya Anuyog"
    log_handle.info("✓ Query by Anuyog 'Dravya Anuyog': 2 document found")
    
    # Test querying by Author
    log_handle.info("Testing queries by Author...")
    simple_author_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.author.keyword": "Simple Author"}}}
    )
    assert simple_author_query["hits"]["total"]["value"] == 2, "Should find 2 document with Simple Author"
    log_handle.info("✓ Query by Author 'Simple Author': 2 document found")
    
    kundkund_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.author.keyword": "Acharya Kundkund"}}}
    )
    assert kundkund_query["hits"]["total"]["value"] == 2, "Should find 2 document with Acharya Kundkund"
    log_handle.info("✓ Query by Author 'Acharya Kundkund': 2 document found")
    
    haribhadra_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.author.keyword": "Acharya Haribhadra"}}}
    )
    assert haribhadra_query["hits"]["total"]["value"] == 2, "Should find 2 document with Acharya Haribhadra"
    log_handle.info("✓ Query by Author 'Acharya Haribhadra': 2 document found")
    
    # Test querying by Teekakar
    log_handle.info("Testing queries by Teekakar...")
    simple_teekakar_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.teekakar.keyword": "Simple Teekakar"}}}
    )
    assert simple_teekakar_query["hits"]["total"]["value"] == 2, "Should find 2 document with Simple Teekakar"
    log_handle.info("✓ Query by Teekakar 'Simple Teekakar': 2 document found")
    
    amritchandra_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.teekakar.keyword": "Acharya Nemichandra"}}}
    )
    assert amritchandra_query["hits"]["total"]["value"] == 2, "Should find 2 document with Acharya Nemichandra"
    log_handle.info("✓ Query by Teekakar 'Acharya Nemichandra': 2 document found")
    
    todarmal_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.teekakar.keyword": "Pandit Todarmal"}}}
    )
    assert todarmal_query["hits"]["total"]["value"] == 2, "Should find 2 document with Pandit Todarmal"
    log_handle.info("✓ Query by Teekakar 'Pandit Todarmal': 2 document found")
    
    # Test querying by Language
    log_handle.info("Testing queries by Language...")
    hindi_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.language.keyword": "hi"}}}
    )
    assert hindi_query["hits"]["total"]["value"] == 3, "Should find 3 documents with Hindi language"
    log_handle.info("✓ Query by Language 'hi': 3 documents found")
    
    gujarati_query = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.language.keyword": "gu"}}}
    )
    assert gujarati_query["hits"]["total"]["value"] == 3, "Should find 3 document with Gujarati language"
    log_handle.info("✓ Query by Language 'gu': 3 document found")
    
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
        body={"query": {"match": {"metadata.anuyog.keyword": "Simple Anuyog"}}}
    )
    assert search_anuyog_query["hits"]["total"]["value"] > 0, f"Should find paragraph chunks with Simple Anuyog. Found: {search_anuyog_query['hits']['total']['value']}"
    log_handle.info(f"✓ Search index query by Anuyog: {search_anuyog_query['hits']['total']['value']} chunks found")
    
    search_author_query = opensearch_client.search(
        index=config.OPENSEARCH_INDEX_NAME,
        body={"query": {"match": {"metadata.author.keyword": "Acharya Kundkund"}}}
    )
    assert search_author_query["hits"]["total"]["value"] > 0, f"Should find paragraph chunks with Acharya Kundkund. Found: {search_author_query['hits']['total']['value']}"
    log_handle.info(f"✓ Search index query by Author: {search_author_query['hits']['total']['value']} chunks found")
    
    # Test complex queries
    for lang in ["hi", "gu"]:
        log_handle.info("Testing complex metadata queries...")
        complex_query = opensearch_client.search(
            index=config.OPENSEARCH_GRANTH_INDEX_NAME,
            body={
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"metadata.language.keyword": lang}},
                            {"term": {"metadata.anuyog.keyword": "Simple Anuyog"}}
                        ]
                    }
                }
            }
        )
        assert complex_query["hits"]["total"]["value"] == 1, f"Should find 1 document matching both language={lang} and anuyog=Simple Anuyog"
        log_handle.info(f"✓ Complex query (language={lang} AND anuyog=Simple Anuyog): 1 document found")


def test_granth_prose_indexing():
    """
    Test indexing of prose sections with hierarchical subsections.

    Tests:
    1. Parse adhikar_prose_granth.md files with verses and prose sections
    2. Index and verify prose_sections in granth_index
    3. Verify prose paragraphs are indexed in search_index with embeddings
    4. Validate subsection hierarchy and seq_num continuity
    """
    config = Config()
    opensearch_client = get_opensearch_client(config)
    indexer = GranthIndexer(config, opensearch_client)

    # Setup directory structure with prose granth files
    log_handle.info("=== Phase 1: Setting up prose granth files ===")
    granth_setup = setup_granth()
    base_dir = granth_setup["base_dir"]
    granth_files = granth_setup["granth_files"]

    # Create parser with base_folder
    parser = MarkdownParser(base_folder=base_dir)

    # Parse only the prose granth files (Hindi and Gujarati)
    log_handle.info("=== Phase 2: Parsing prose granth files ===")
    prose_granths = []
    for granth_name, file_info in granth_files.items():
        if "prose_granth" not in granth_name:
            continue

        file_path = file_info["file_path"]
        log_handle.info(f"Parsing prose granth: {file_path}")

        granth = parser.parse_file(file_path)
        prose_granths.append((granth_name, granth, file_info["config"]))

        # Basic validation
        assert granth is not None, f"Failed to parse {file_path}"
        assert len(granth._verses) == 2, f"Expected 2 verses in {file_path}"
        assert len(granth._prose_sections) == 4, f"Expected 4 prose sections in {file_path}"

        log_handle.info(f"✓ Parsed {file_path}: {len(granth._verses)} verses, {len(granth._prose_sections)} prose sections")

    # Phase 3: Index prose granths
    log_handle.info("=== Phase 3: Indexing prose granths ===")
    for granth_name, granth, expected_config in prose_granths:
        log_handle.info(f"Indexing: {granth_name}")
        indexer.index_granth(granth, dry_run=False)
        log_handle.info(f"✓ Indexed: {granth_name}")

    # Refresh indices
    opensearch_client.indices.refresh(index=config.OPENSEARCH_GRANTH_INDEX_NAME)
    opensearch_client.indices.refresh(index=config.OPENSEARCH_INDEX_NAME)

    # Phase 4: Validate granth_index - prose_sections structure
    log_handle.info("=== Phase 4: Validating prose_sections in granth_index ===")

    granth_search = opensearch_client.search(
        index=config.OPENSEARCH_GRANTH_INDEX_NAME,
        body={"query": {"term": {"metadata.anuyog.keyword": "Prose Anuyog"}}, "size": 100}
    )

    granth_docs = granth_search["hits"]["hits"]
    assert len(granth_docs) == 2, f"Expected 2 prose granth documents (hi & gu), found {len(granth_docs)}"
    log_handle.info(f"✓ Found {len(granth_docs)} prose granth documents")

    for doc in granth_docs:
        source = doc["_source"]

        # Validate prose_sections field exists
        assert "prose_sections" in source, "prose_sections field missing from granth_index"
        prose_sections = source["prose_sections"]
        assert len(prose_sections) == 4, f"Expected 4 prose sections, found {len(prose_sections)}"

        # Validate seq_num continuity: Verse(1), Prose(2), Prose(5), Verse(8), Prose(9), Prose(12)
        assert source["verses"][0]["seq_num"] == 1, "First verse should be seq_num 1"
        assert prose_sections[0]["seq_num"] == 2, "First prose should be seq_num 2"
        assert prose_sections[1]["seq_num"] == 5, "Second prose should be seq_num 5"
        assert source["verses"][1]["seq_num"] == 8, "Second verse should be seq_num 8"
        assert prose_sections[2]["seq_num"] == 9, "Third prose should be seq_num 9"
        assert prose_sections[3]["seq_num"] == 12, "Fourth prose should be seq_num 12"

        log_handle.info(f"✓ Validated seq_num continuity for {source['original_filename']}")

        # Validate prose subsections
        for prose in prose_sections:
            assert "subsections" in prose, "subsections field missing from prose_section"
            assert len(prose["subsections"]) == 2, f"Expected 2 subsections in prose {prose['seq_num']}"

            # Validate subsection structure
            for subsection in prose["subsections"]:
                assert "seq_num" in subsection, "seq_num missing from subsection"
                assert "heading" in subsection, "heading missing from subsection"
                assert "content" in subsection, "content missing from subsection"
                assert isinstance(subsection["content"], list), "subsection content should be a list"
                assert len(subsection["content"]) == 2, "Each subsection should have 2 paragraphs"

        log_handle.info(f"✓ Validated prose subsections for {source['original_filename']}")

    # Phase 5: Validate search_index - prose paragraphs with embeddings
    log_handle.info("=== Phase 5: Validating prose paragraphs in search_index ===")

    # Query for prose content
    prose_search = opensearch_client.search(
        index=config.OPENSEARCH_INDEX_NAME,
        body={
            "query": {
                "bool": {
                    "must": [
                        {"exists": {"field": "metadata.prose_seq_num"}},
                        {"term": {"metadata.anuyog.keyword": "Prose Anuyog"}}
                    ]
                }
            },
            "size": 1000
        }
    )

    prose_docs = prose_search["hits"]["hits"]
    assert len(prose_docs) > 0, "No prose paragraphs found in search_index"
    log_handle.info(f"✓ Found {len(prose_docs)} prose paragraph documents in search_index")

    # Expected count: 2 languages × 4 prose sections × (1 main para + 2 subsections × 2 paras) = 2 × 4 × 5 = 40
    expected_prose_docs = 2 * 4 * (1 + 2 * 2)  # 40 prose paragraph documents
    assert len(prose_docs) == expected_prose_docs, f"Expected {expected_prose_docs} prose paragraphs, found {len(prose_docs)}"

    # Validate prose document structure
    prose_content_types = set()
    chunk_ids_checked = set()

    for doc in prose_docs:
        source = doc["_source"]

        # Validate required fields
        assert "chunk_id" in source, "chunk_id missing from prose document"
        assert "metadata" in source, "metadata missing from prose document"
        assert "vector_embedding" in source, "vector_embedding missing from prose document (should have embeddings)"

        metadata = source["metadata"]
        assert "prose_seq_num" in metadata, "prose_seq_num missing from metadata"
        assert "prose_heading" in metadata, "prose_heading missing from metadata"
        assert "prose_content_type" in metadata, "prose_content_type missing from metadata"

        prose_content_types.add(metadata["prose_content_type"])

        # Validate embedding
        embedding = source["vector_embedding"]
        assert isinstance(embedding, list), "vector_embedding should be a list"
        assert len(embedding) > 0, "vector_embedding should not be empty"

        # Validate chunk_id format
        chunk_id = source["chunk_id"]
        chunk_ids_checked.add(chunk_id)

        # Chunk IDs should be either:
        # - Main prose: {granth_id}_p{seq_num}_content_{index}
        # - Subsection: {granth_id}_p{parent_seq}_sub{seq_num}_content_{index}
        if metadata["prose_content_type"] == "main":
            assert "_p" in chunk_id and "_content_" in chunk_id, f"Invalid main prose chunk_id: {chunk_id}"
            assert "_sub" not in chunk_id, f"Main prose chunk_id should not have _sub: {chunk_id}"
        elif metadata["prose_content_type"] == "subsection":
            assert "_p" in chunk_id and "_sub" in chunk_id and "_content_" in chunk_id, f"Invalid subsection chunk_id: {chunk_id}"

        # Validate language-specific text content
        language = metadata.get("language")
        if language == "hi":
            assert "text_content_hindi" in source, "text_content_hindi missing for Hindi prose"
            assert source["text_content_hindi"], "text_content_hindi should not be empty"
        elif language == "gu":
            assert "text_content_gujarati" in source, "text_content_gujarati missing for Gujarati prose"
            assert source["text_content_gujarati"], "text_content_gujarati should not be empty"

    log_handle.info(f"✓ Validated {len(prose_docs)} prose paragraph documents with embeddings")
    log_handle.info(f"✓ Prose content types found: {prose_content_types}")

    # Verify both main and subsection types exist
    assert "main" in prose_content_types, "Expected 'main' prose content type"
    assert "subsection" in prose_content_types, "Expected 'subsection' prose content type"

    log_handle.info("=== Phase 6: Cross-validation ===")

    # Verify chunk_id uniqueness
    assert len(chunk_ids_checked) == len(prose_docs), "Duplicate chunk_ids found in prose documents"
    log_handle.info(f"✓ All {len(chunk_ids_checked)} prose chunk_ids are unique")

    log_handle.info("✅ Prose indexing test completed successfully")