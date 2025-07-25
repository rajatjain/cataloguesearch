import tempfile
import traceback
import uuid

from pathlib import Path
import pytest
import os
import logging

from backend.common.embedding_models import get_embedding_model, get_embedding
from backend.index.embedding_module import IndexingEmbeddingModule

from backend.common.opensearch import get_opensearch_client
from backend.utils import json_dumps
from tests.backend.base import *

log_handle = logging.getLogger(__name__)

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

    module = IndexingEmbeddingModule(config, opensearch_client)
    return module

def dummy_text_files(tmp_path):
    """
    Creates dummy page-wise text files for a document.
    """
    doc_id = "test_doc_1"
    doc_dir = os.path.join(tmp_path, doc_id)
    os.makedirs(doc_dir, exist_ok=True)

    page1_path = Path(doc_dir) / "page_0001.txt"
    page2_path = Path(doc_dir) / "page_0002.txt"
    page3_path = Path(doc_dir) / "page_0003.txt"

    page1_content = "This is page one content. It has some English text."
    page2_content = "यह पृष्ठ दो की सामग्री है। इसमें कुछ हिंदी पाठ है।" # Hindi
    page3_content = "આ પાના ત્રણની સામગ્રી છે. તેમાં કેટલીક ગુજરાતી લખાણ છે." # Gujarati

    page1_path.write_text(page1_content, encoding="utf-8")
    page2_path.write_text(page2_content, encoding="utf-8")
    page3_path.write_text(page3_content, encoding="utf-8")

    return doc_id, "original_test_file.pdf", [str(page1_path), str(page2_path), str(page3_path)]

def get_all_documents(config, max_results: int = 1000) -> list:
    """
    Retrieves all documents from the configured OpenSearch index.

    Args:
        config: The application configuration object, which contains OpenSearch settings.
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


def test_index_document_full_indexing(indexing_module):
    """
    Tests full indexing of a document, including text, embeddings, and metadata.
    """
    # Re-use the client from above
    config = Config()
    opensearch_client = get_opensearch_client(config, force_clean=True)
    tmp_path = tempfile.mkdtemp()
    doc_id, filename, page_paths = dummy_text_files(tmp_path)
    metadata = {"title": "Test Document", "author": "John Doe"}
    bookmarks = {1: "Introduction", 2: "Some Bookmark", 3: "Other Bookmark"}

    indexing_module.index_document(
        doc_id, filename, page_paths, metadata, bookmarks, reindex_metadata_only=False)

    # Verify documents are indexed
    opensearch_client.indices.refresh(index=indexing_module._index_name) # Ensure docs are searchable

    # Perform a single search to get all documents in the test index
    response = opensearch_client.search(
        index=indexing_module._index_name,
        body={"size": 100, "query": {"match_all": {}}}
    )
    all_docs = response['hits']['hits']
    log_handle.info(
        f"Found {len(all_docs)} total documents in index: {json_dumps(all_docs, truncate_fields=['vector_embedding'])}")

    # Filter the results in Python to get the hits for the specific document
    hits = [hit for hit in all_docs if hit['_source'].get('document_id') == doc_id]
    log_handle.info(
        f"Found {len(hits)} hits for document {doc_id}: {json_dumps(hits, truncate_fields=['vector_embedding'])}")

    assert len(hits) > 0 # Should have chunks indexed
    # Check that we found hits and the first one has content before trying to access it
    if not hits:
        # Fail the test explicitly if no hits were found for the doc_id
        pytest.fail(f"No documents found for doc_id '{doc_id}' after indexing.")

    log_handle.info(f"Document metadata: {hits[0]}")

    assert all('vector_embedding' in hit['_source'] for hit in hits)
    assert all(isinstance(hit['_source']['vector_embedding'], list) for hit in hits)
    assert all(len(hit['_source']['vector_embedding']) == \
               get_embedding_model(config.EMBEDDING_MODEL_NAME).get_sentence_embedding_dimension() for hit in hits)

    # Check metadata and text content
    found_page_one = False
    found_page_two = False
    found_page_three = False
    for hit in hits:
        source = hit['_source']
        assert source['document_id'] == doc_id
        assert source['original_filename'] == filename
        assert source['metadata'] == metadata
        assert bookmarks[source["page_number"]] == source['bookmarks']
        assert 'timestamp_indexed' in source

        if "page one content" in source['text_content']:
            found_page_one = True
        if "यह पृष्ठ दो की सामग्री है।" in source['text_content'] or "हिंदी पाठ" in source['text_content']:
            found_page_two = True
        if "આ પાના ત્રણની સામગ્રી છે." in source['text_content'] or "ગુજરાતી લખાણ" in source['text_content']:
            found_page_three = True

    assert found_page_one
    assert found_page_two
    assert found_page_three

def test_index_document_metadata_only_reindex(indexing_module):
    """
    Tests metadata-only re-indexing for an existing document.
    """
    config = Config()
    opensearch_client = get_opensearch_client(config, force_clean=True)
    tmp_path = tempfile.mkdtemp()
    doc_id, filename, page_paths = dummy_text_files(tmp_path)
    initial_metadata = {"title": "Old Title", "version": "1.0"}
    initial_bookmarks = {1: "Bookmark_1", 2: "Bookmark_2", 3: "Bookmark_3"}

    # First, perform a full index
    indexing_module.index_document(doc_id, filename, page_paths,
                                   initial_metadata, initial_bookmarks, reindex_metadata_only=False)
    opensearch_client.indices.refresh(index=indexing_module._index_name)

    # get all documents and log it.
    all_docs = get_all_documents(config)
    log_handle.info(f"All documents: {json_dumps(all_docs, truncate_fields=['vector_embedding'])}")


    # Get initial timestamps to ensure they don't change during metadata-only update
    response_initial = opensearch_client.search(
        index=indexing_module._index_name, body={"query": {"term": {"document_id": doc_id}}})
    initial_hits = response_initial['hits']['hits']
    log_handle.info(f"Initial hits: {json_dumps(initial_hits, truncate_fields=['vector_embedding'])}")
    assert len(initial_hits) > 0
    initial_timestamps = {hit['_id']: hit['_source']['timestamp_indexed'] for hit in initial_hits}
    initial_vector_embeddings = {hit['_id']: hit['_source']['vector_embedding'] for hit in initial_hits}
    initial_text_contents = {hit['_id']: hit['_source']['text_content'] for hit in initial_hits}


    # Now, perform metadata-only re-index
    updated_metadata = {"title": "New Title", "version": "2.0", "new_field": "test"}
    updated_bookmarks = {1: "New_1", 2: "Bookmark_2", 3: "New_3"}
    indexing_module.index_document(
        doc_id, filename, [], updated_metadata, updated_bookmarks, reindex_metadata_only=True)
    opensearch_client.indices.refresh(index=indexing_module._index_name)

    # Verify metadata is updated and other fields are unchanged
    response_updated = opensearch_client.search(
        index=indexing_module._index_name, body={"query": {"term": {"document_id": doc_id}}})
    updated_hits = response_updated['hits']['hits']

    assert len(updated_hits) == len(initial_hits) # Number of chunks should remain the same

    for hit in updated_hits:
        source = hit['_source']
        chunk_id = hit['_id']
        assert source['metadata'] == updated_metadata
        assert source["bookmarks"] == updated_bookmarks[source["page_number"]]
        assert source['timestamp_indexed'] != initial_timestamps[chunk_id] # Timestamp should be updated
        assert source['vector_embedding'] == initial_vector_embeddings[chunk_id] # Embedding should NOT change
        assert source['text_content'] == initial_text_contents[chunk_id] # Text content should NOT change

    # Search by metadata and ensure that we receive the docs.
    query = {
        "query": {
            "term": {
                "metadata.new_field": "test"
            }
        },
        "size": 10
    }
    response = opensearch_client.search(index=indexing_module._index_name, body=query)
    updated_hits = response['hits']['hits']
    assert len(updated_hits) == len(initial_hits)

    query = {
        "query": {
            "wildcard": {
                "bookmarks": "new_*"
            }
        },
        "size": 10
    }
    response = opensearch_client.search(index=indexing_module._index_name, body=query)
    updated_hits = response['hits']['hits']
    assert len(updated_hits) == 2

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
           get_embedding_model(config.EMBEDDING_MODEL_NAME).get_sentence_embedding_dimension()
    assert 'text_content_hindi' in mappings and mappings['text_content_hindi']['analyzer'] == 'hindi_analyzer'
    assert 'text_content_gujarati' in mappings and mappings['text_content_gujarati']['analyzer'] == 'gujarati_analyzer'

def test_generate_embedding_empty_text(indexing_module):
    """
    Tests embedding generation for empty text.
    """
    config = Config()
    embedding = get_embedding(config.EMBEDDING_MODEL_NAME, "")
    assert len(embedding) == \
           get_embedding_model(config.EMBEDDING_MODEL_NAME).get_sentence_embedding_dimension()

def test_chunk_text_basic(indexing_module):
    """
    Tests basic text chunking.
    """
    long_text = "a " * 800 # 1600 characters (800 'a ' pairs)
    chunks = indexing_module._text_splitter._chunk_text(long_text)
    # With chunk_size=100, chunk_overlap=20, and "a " being 2 chars
    # Expected chunks: (100-20) = 80 chars per effective chunk.
    # Total chars = 1000. 1000 / 80 = 12.5. So 13 chunks.
    # The first chunk will be 100 chars. Subsequent chunks will start 80 chars after previous.
    # Let's verify that chunks are created and have reasonable lengths.
    assert len(chunks) > 1
    assert all(len(chunk) <= indexing_module._text_splitter._chunk_size for chunk in chunks)
    assert chunks[0].startswith("a a a a a")
    assert chunks[1].startswith("a a a a a") # Should have overlap


def test_index_with_language_metadata(indexing_module):
    # clean index
    config = Config()
    opensearch_client = get_opensearch_client(config, force_clean=True)
    text_data_dir = config.BASE_TEXT_PATH
    bangalore_hindi = os.path.join(text_data_dir, "bangalore_hindi")
    bangalore_gujarati = os.path.join(text_data_dir, "bangalore_gujarati")
    log_handle.info(f"text_data_dir: {text_data_dir}")
    log_handle.info(f"bangalore_hindi: {bangalore_hindi}")
    log_handle.info(f"bangalore_gujarati: {bangalore_gujarati}")

    # iterate through the text files in the directory
    bangalore_hindi_files = []
    for root, dirs, files in os.walk(bangalore_hindi):
        for file in files:
            if file.endswith(".txt"):
                bangalore_hindi_files.append(os.path.join(root, file))

    bangalore_gujarati_files = []
    for root, dirs, files in os.walk(bangalore_gujarati):
        for file in files:
            if file.endswith(".txt"):
                bangalore_gujarati_files.append(os.path.join(root, file))

    # Index Hindi document
    doc_id_hindi = str(uuid.uuid5(uuid.NAMESPACE_DNS, "bangalore_hindi.pdf"))
    doc_id_gujarati = str(uuid.uuid5(uuid.NAMESPACE_DNS, "bangalore_gujarati.pdf"))

    log_handle.info(f"bangalore_hindi_files: {bangalore_hindi_files}")
    log_handle.info(f"bangalore_gujarati_files: {bangalore_gujarati_files}")
    # index documents
    indexing_module.index_document(
        doc_id_hindi, "bangalore_hindi.pdf", bangalore_hindi_files,
        {"language": "hi"}, {}, reindex_metadata_only=False)

    indexing_module.index_document(
        doc_id_gujarati, "bangalore_gujarati.pdf", bangalore_gujarati_files,
        {"language": "gu"}, {}, reindex_metadata_only=False)

    # get all docs
    all_docs = get_all_documents(config)

    for doc in all_docs:
        log_handle.info(f"Document: {json_dumps(doc, truncate_fields=['vector_embedding'])}")
        source = doc['_source']
        if source['document_id'] == doc_id_hindi:
            assert source['metadata']['language'] == 'hi'
            assert 'text_content_hindi' in source
            assert 'text_content_gujarati' not in source
        elif source['document_id'] == doc_id_gujarati:
            assert source['metadata']['language'] == 'gu'
            assert 'text_content_gujarati' in source
            assert 'text_content_hindi' not in source
        else:
            pytest.fail(f"Unexpected document ID: {source['document_id']}")


def test_index_with_language_detection(indexing_module):
    # clean index
    config = Config()
    opensearch_client = get_opensearch_client(config, force_clean=True)
    text_data_dir = config.BASE_TEXT_PATH
    bangalore_hindi = os.path.join(text_data_dir, "bangalore_hindi")
    bangalore_gujarati = os.path.join(text_data_dir, "bangalore_gujarati")
    log_handle.info(f"text_data_dir: {text_data_dir}")
    log_handle.info(f"bangalore_hindi: {bangalore_hindi}")
    log_handle.info(f"bangalore_gujarati: {bangalore_gujarati}")

    # iterate through the text files in the directory
    bangalore_hindi_files = []
    for root, dirs, files in os.walk(bangalore_hindi):
        for file in files:
            if file.endswith(".txt"):
                bangalore_hindi_files.append(os.path.join(root, file))

    bangalore_gujarati_files = []
    for root, dirs, files in os.walk(bangalore_gujarati):
        for file in files:
            if file.endswith(".txt"):
                bangalore_gujarati_files.append(os.path.join(root, file))

    # Index Hindi document
    doc_id_hindi = str(uuid.uuid5(uuid.NAMESPACE_DNS, "bangalore_hindi.pdf"))
    doc_id_gujarati = str(uuid.uuid5(uuid.NAMESPACE_DNS, "bangalore_gujarati.pdf"))

    log_handle.info(f"bangalore_hindi_files: {bangalore_hindi_files}")
    log_handle.info(f"bangalore_gujarati_files: {bangalore_gujarati_files}")
    # index documents
    indexing_module.index_document(
        doc_id_hindi, "bangalore_hindi.pdf", bangalore_hindi_files,
        {}, {}, reindex_metadata_only=False)

    indexing_module.index_document(
        doc_id_gujarati, "bangalore_gujarati.pdf", bangalore_gujarati_files,
        {}, {}, reindex_metadata_only=False)

    # get all docs
    all_docs = get_all_documents(config)

    for doc in all_docs:
        log_handle.info(f"Document: {json_dumps(doc, truncate_fields=['vector_embedding'])}")
        source = doc['_source']
        if source['document_id'] == doc_id_hindi:
            assert 'text_content_hindi' in source
            assert 'text_content_gujarati' not in source
        elif source['document_id'] == doc_id_gujarati:
            assert 'text_content_gujarati' in source
            assert 'text_content_hindi' not in source
        else:
            pytest.fail(f"Unexpected document ID: {source['document_id']}")
