import tempfile
import traceback
import uuid

from pathlib import Path

from backend.crawler.index_generator import IndexGenerator
from backend.common.embedding_models import get_embedding_model_factory
from backend.common.opensearch import get_opensearch_client
from backend.common.opensearch import create_indices_if_not_exists
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

    module = IndexGenerator(config, opensearch_client)
    create_indices_if_not_exists(config, opensearch_client)
    return module

def dummy_text_files(tmp_path):
    """
    Creates dummy page-wise text files for a document.
    """
    doc_id_hindi = "test_doc_hindi"
    doc_id_gujarati = "test_doc_gujarati"
    
    # Create Hindi document directory and files
    hindi_doc_dir = os.path.join(tmp_path, doc_id_hindi)
    os.makedirs(hindi_doc_dir, exist_ok=True)
    
    hindi_page1_path = Path(hindi_doc_dir) / "page_0001.txt"
    hindi_page2_path = Path(hindi_doc_dir) / "page_0002.txt"
    hindi_page3_path = Path(hindi_doc_dir) / "page_0003.txt"
    
    hindi_page1_content = "यह पहला पृष्ठ है। इसमें केवल हिंदी पाठ है।"
    hindi_page2_content = "यह दूसरा पृष्ठ है। इसमें भी केवल हिंदी भाषा का उपयोग है।"
    hindi_page3_content = "यह तीसरा पृष्ठ है। यहाँ पर भी हिंदी सामग्री ही है।"
    
    hindi_page1_path.write_text(hindi_page1_content, encoding="utf-8")
    hindi_page2_path.write_text(hindi_page2_content, encoding="utf-8")
    hindi_page3_path.write_text(hindi_page3_content, encoding="utf-8")
    
    # Create Gujarati document directory and files
    gujarati_doc_dir = os.path.join(tmp_path, doc_id_gujarati)
    os.makedirs(gujarati_doc_dir, exist_ok=True)
    
    gujarati_page1_path = Path(gujarati_doc_dir) / "page_0001.txt"
    gujarati_page2_path = Path(gujarati_doc_dir) / "page_0002.txt"
    gujarati_page3_path = Path(gujarati_doc_dir) / "page_0003.txt"
    
    gujarati_page1_content = "આ પહેલું પાનું છે. તેમાં માત્ર ગુજરાતી લખાણ છે."
    gujarati_page2_content = "આ બીજું પાનું છે. તેમાં પણ માત્ર ગુજરાતી ભાષાનો ઉપયોગ છે."
    gujarati_page3_content = "આ ત્રીજું પાનું છે. અહીં પણ ગુજરાતી સામગ્રી જ છે."
    
    gujarati_page1_path.write_text(gujarati_page1_content, encoding="utf-8")
    gujarati_page2_path.write_text(gujarati_page2_content, encoding="utf-8")
    gujarati_page3_path.write_text(gujarati_page3_content, encoding="utf-8")

    return (doc_id_hindi, [str(hindi_page1_path), str(hindi_page2_path), str(hindi_page3_path)], 
            doc_id_gujarati, [str(gujarati_page1_path), str(gujarati_page2_path), str(gujarati_page3_path)])

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
    doc_id_hindi, hindi_page_paths, doc_id_gujarati, gujarati_page_paths = dummy_text_files(tmp_path)
    metadata = {"title": "Test Document", "author": "John Doe"}
    bookmarks = {1: "Introduction", 2: "Some Bookmark", 3: "Other Bookmark"}

    # Index Hindi document
    hindi_metadata = dict(metadata)
    hindi_metadata["language"] = "hi"
    indexing_module.index_document(
        doc_id_hindi, "test_hindi.pdf", hindi_page_paths, hindi_metadata, bookmarks, reindex_metadata_only=False)
    
    # Index Gujarati document
    gujarati_metadata = dict(metadata)
    gujarati_metadata["language"] = "gu"
    indexing_module.index_document(
        doc_id_gujarati, "test_gujarati.pdf", gujarati_page_paths, gujarati_metadata, bookmarks, reindex_metadata_only=False)

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

    # Filter the results for Hindi document
    hindi_hits = [hit for hit in all_docs if hit['_source'].get('document_id') == doc_id_hindi]
    log_handle.info(
        f"Found {len(hindi_hits)} hits for Hindi document {doc_id_hindi}: {json_dumps(hindi_hits, truncate_fields=['vector_embedding'])}")

    # Filter the results for Gujarati document
    gujarati_hits = [hit for hit in all_docs if hit['_source'].get('document_id') == doc_id_gujarati]
    log_handle.info(
        f"Found {len(gujarati_hits)} hits for Gujarati document {doc_id_gujarati}: {json_dumps(gujarati_hits, truncate_fields=['vector_embedding'])}")

    assert len(hindi_hits) > 0 # Should have Hindi chunks indexed
    assert len(gujarati_hits) > 0 # Should have Gujarati chunks indexed
    
    # Check that we found hits for both documents
    if not hindi_hits:
        pytest.fail(f"No documents found for Hindi doc_id '{doc_id_hindi}' after indexing.")
    if not gujarati_hits:
        pytest.fail(f"No documents found for Gujarati doc_id '{doc_id_gujarati}' after indexing.")

    log_handle.info(f"Hindi document metadata: {json_dumps(hindi_hits[0], truncate_fields=['vector_embedding'])}")
    log_handle.info(f"Gujarati document metadata: {json_dumps(gujarati_hits[0], truncate_fields=['vector_embedding'])}")

    # Check embeddings for both documents
    all_hits = hindi_hits + gujarati_hits
    assert all('vector_embedding' in hit['_source'] for hit in all_hits)
    assert all(isinstance(hit['_source']['vector_embedding'], list) for hit in all_hits)
    assert all(len(hit['_source']['vector_embedding']) == \
               get_embedding_model_factory(config).get_embedding_dimension() for hit in all_hits)

    # Check Hindi document content
    for hit in hindi_hits:
        source = hit['_source']
        assert source['document_id'] == doc_id_hindi
        assert source['original_filename'] == "test_hindi.pdf"
        assert source['metadata'] == hindi_metadata
        assert bookmarks[source["page_number"]] == source['bookmarks']
        assert 'timestamp_indexed' in source
        
        # Hindi document should only have text_content_hindi
        assert 'text_content_hindi' in source
        assert 'text_content_gujarati' not in source or source['text_content_gujarati'] == ''
        
        hindi_content = source.get('text_content_hindi', '')
        assert hindi_content != '', "Hindi content should not be empty"
        assert "हिंदी" in hindi_content, "Should contain Hindi text"

    # Check Gujarati document content
    for hit in gujarati_hits:
        source = hit['_source']
        assert source['document_id'] == doc_id_gujarati
        assert source['original_filename'] == "test_gujarati.pdf"
        assert source['metadata'] == gujarati_metadata
        assert bookmarks[source["page_number"]] == source['bookmarks']
        assert 'timestamp_indexed' in source
        
        # Gujarati document should only have text_content_gujarati
        assert 'text_content_gujarati' in source
        assert 'text_content_hindi' not in source or source['text_content_hindi'] == ''
        
        gujarati_content = source.get('text_content_gujarati', '')
        assert gujarati_content != '', "Gujarati content should not be empty"
        assert "ગુજરાતી" in gujarati_content, "Should contain Gujarati text"

def test_index_document_metadata_only_reindex(indexing_module):
    """
    Tests metadata-only re-indexing for an existing document.
    """
    config = Config()
    opensearch_client = get_opensearch_client(config, force_clean=True)
    tmp_path = tempfile.mkdtemp()
    doc_id_hindi, hindi_page_paths, doc_id_gujarati, gujarati_page_paths = dummy_text_files(tmp_path)
    # Use only the Hindi document for this test
    doc_id, filename, page_paths = doc_id_hindi, "test_hindi.pdf", hindi_page_paths
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
    initial_text_contents = {hit['_id']: {
        'hindi': hit['_source'].get('text_content_hindi', ''),
        'gujarati': hit['_source'].get('text_content_gujarati', '')
    } for hit in initial_hits}


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
        # Text content should NOT change
        assert source.get('text_content_hindi', '') == initial_text_contents[chunk_id]['hindi']
        assert source.get('text_content_gujarati', '') == initial_text_contents[chunk_id]['gujarati']

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
