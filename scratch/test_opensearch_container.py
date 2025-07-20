# test_opensearch_integration.py
from testcontainers.opensearch import OpenSearchContainer
from opensearchpy import OpenSearch, ConnectionError
import pytest
import time

@pytest.fixture(scope="module")
def opensearch_client():
    """
    Fixture to create an OpenSearch client connected to the container.
    """
    # Get the dynamically assigned host and port from the running container
    host = "localhost"
    port = "9200"

    try:
        # 2. Create the OpenSearch client with SSL and authentication
        client = OpenSearch(
            hosts=[{
                'scheme': 'https',  # Use 'https' because the security plugin is enabled
                'host': "localhost",
                'port': 9200
            }],
            http_auth=("admin", "Admin@Password123!"),

            # --- SSL Settings for Local Development ---
            # The Docker container uses a self-signed SSL certificate. These settings
            # are required to connect to it without the client raising security errors.
            use_ssl=True,
            verify_certs=False,        # Don't try to verify the server's certificate
            ssl_assert_hostname=False, # Don't verify the certificate's hostname
            ssl_show_warn=False        # Suppress warnings about self-signed certificates
        )
        return client
    except Exception as e:
        print(f"Error creating the OpenSearch client: {e}")
        return None

# test_opensearch_integration.py (continued)
def test_opensearch_index_and_search(opensearch_client):
    """
    Example test case: index a document and perform a search.
    """
    index_name = "test-index"
    document = {"title": "Test Document", "content": "This is a test document about testing."}
    doc_id = "1"

    print(f"\n--- Running test: {test_opensearch_index_and_search.__name__} ---")

    # 1. Create an index if it doesn't exist
    if not opensearch_client.indices.exists(index=index_name):
        print(f"Creating index: {index_name}")
        create_response = opensearch_client.indices.create(index=index_name)
        assert create_response["acknowledged"] is True
    else:
        print(f"Index {index_name} already exists. Skipping creation.")

    # 2. Index a document
    print(f"Indexing document with ID {doc_id} into {index_name}...")
    response = opensearch_client.index(index=index_name, id=doc_id, body=document, refresh=True)
    assert response["result"] == "created"
    print(f"Document indexed: {response}")

    # 3. Search for the document
    search_query = {"query": {"match": {"title": "Test"}}}
    print(f"Searching for documents with query: {search_query}")
    search_response = opensearch_client.search(index=index_name, body=search_query)

    assert search_response["hits"]["total"]["value"] == 1
    assert search_response["hits"]["hits"][0]["_source"]["title"] == "Test Document"
    print(f"Search successful. Found {search_response['hits']['total']['value']} hit(s).")
    print(f"Found document title: {search_response['hits']['hits'][0]['_source']['title']}")


    # 4. Clean up (optional, as the container will be torn down by the fixture,
    # but good practice for isolated tests within the same container lifecycle)
    print(f"Cleaning up document with ID {doc_id} from {index_name}...")
    opensearch_client.delete(index=index_name, id=doc_id)
    print(f"Deleting index: {index_name}")
    opensearch_client.indices.delete(index=index_name)
    print("Cleanup complete.")