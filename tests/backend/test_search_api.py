import asyncio
import logging
import os
import shutil
import threading
import time
import uvicorn
import pytest
import requests
from backend.common import embedding_models
from backend.common.opensearch import get_opensearch_client
from backend.crawler.discovery import Discovery
from backend.crawler.index_state import IndexState
from backend.crawler.index_generator import IndexGenerator
from backend.crawler.pdf_processor import PDFProcessor
from backend.search.index_searcher import IndexSearcher
from tests.backend.common import setup, get_all_documents
from tests.backend.base import *

log_handle = logging.getLogger(__name__)

def run_api_server_in_thread(host, port, stop_event):
    """Function to run the API server in a thread."""
    # Initialize test environment in the API server thread
    # This ensures the same process context as the test
    import os
    from dotenv import load_dotenv
    from backend.config import Config
    
    # Load .env file (same logic as in tests.backend.base.initialise)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(dotenv_path=f"{project_root}/.env", verbose=True)
    
    # Set test environment variables
    test_base_dir = os.getenv("TEST_BASE_DIR")
    if not test_base_dir:
        raise ValueError("TEST_BASE_DIR not set in .env file")
    
    # Set environment variables for the API server
    os.environ["LOGS_DIR"] = "logs"
    os.environ["CONFIG_PATH"] = f"{test_base_dir}/data/configs/test_config.yaml"
    
    # Reset Config singleton to use the test config
    Config.reset()
    
    # Import the FastAPI app
    from backend.api.search_api import app
    
    # Create a custom server that can be stopped
    import uvicorn
    from uvicorn import Config as UvicornConfig
    
    config = UvicornConfig(
        app=app,
        host=host,
        port=port,
        log_level="error",
        access_log=False
    )
    server = uvicorn.Server(config)
    
    # Run server until stop event is set
    import asyncio
    
    async def serve():
        await server.serve()
    
    # Run the server
    try:
        asyncio.run(serve())
    except Exception as e:
        log_handle.error(f"API server error: {e}")


@pytest.fixture(scope="module", autouse=True)
def build_index(initialise):
    """
    Setup test data and build search index.
    Copy OCR data to base_ocr_path and call discovery with process=False, index=True.
    """
    # Setup test environment with scan_config files
    setup(copy_ocr_files=True, add_scan_config=True)
    config = Config()
    
    # Initialize OpenSearch client and ensure clean index state
    opensearch_client = get_opensearch_client(config)
    
    # Explicitly delete indices to ensure clean state and proper mapping creation
    log_handle.info("Deleting existing indices to ensure clean state for vector search")
    indices_to_delete = [config.OPENSEARCH_INDEX_NAME, config.OPENSEARCH_METADATA_INDEX_NAME]
    for index_name in indices_to_delete:
        if index_name and opensearch_client.indices.exists(index=index_name):
            opensearch_client.indices.delete(index=index_name)
            log_handle.info(f"Deleted existing index: {index_name}")
    
    # Create indices with proper mapping (including knn_vector for embeddings)
    from backend.common.opensearch import create_indices_if_not_exists
    create_indices_if_not_exists(config, opensearch_client)
    log_handle.info("Created indices with proper mapping for vector search")
    
    pdf_processor = PDFProcessor(config)  # We won't actually use this since process=False
    discovery = Discovery(
        config, 
        IndexGenerator(config, opensearch_client),
        pdf_processor, 
        IndexState(config.SQLITE_DB_PATH)
    )

    # Call discovery with process=False, index=True
    log_handle.info("Starting discovery with process=False, index=True")
    discovery.crawl(process=False, index=True)

    # Verify indexes are present
    os_all_docs = get_all_documents()
    doc_count = len(os_all_docs)
    log_handle.info(f"Indexed {doc_count} documents")

    yield

    # Cleanup - delete index
    opensearch_client.indices.delete(index=config.OPENSEARCH_INDEX_NAME, ignore=[400, 404])


class APIServerManager:
    """Manager class to handle API server startup and shutdown."""
    
    def __init__(self, host="127.0.0.1", port=8001):
        self.host = host
        self.port = port
        self.server_thread = None
        self.stop_event = None
        
    def start_server_in_thread(self):
        """Start the API server in a separate thread."""
        self.stop_event = threading.Event()
        
        # Start server in a separate thread
        self.server_thread = threading.Thread(
            target=run_api_server_in_thread, 
            args=(self.host, self.port, self.stop_event),
            daemon=True
        )
        self.server_thread.start()
        
        # Wait for server to start up
        self._wait_for_server_startup()
        
    def _wait_for_server_startup(self, timeout=30):
        """Wait for the server to start up by checking if it's responding."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"http://{self.host}:{self.port}/api/metadata", timeout=1)
                if response.status_code in [200, 404, 500]:  # Any response means server is up
                    log_handle.info(f"API server started successfully at http://{self.host}:{self.port}")
                    return True
            except requests.exceptions.RequestException:
                pass  # Server not ready yet
            
            time.sleep(0.5)
        
        raise TimeoutError(f"API server failed to start within {timeout} seconds")
        
    def stop_server(self):
        """Stop the API server."""
        if self.stop_event:
            self.stop_event.set()
        
        if self.server_thread and self.server_thread.is_alive():
            log_handle.info("Stopping API server thread...")
            self.server_thread.join(timeout=5)
            if self.server_thread.is_alive():
                log_handle.warning("API server thread did not stop gracefully")
        
        self.server_thread = None
        self.stop_event = None


@pytest.fixture(scope="module")
def api_server():
    """Fixture to start and stop the API server for tests."""
    server_manager = APIServerManager(host="127.0.0.1", port=8001)  # Use different port to avoid conflicts
    
    try:
        log_handle.info("Starting API server for tests...")
        server_manager.start_server_in_thread()
        yield server_manager
    finally:
        log_handle.info("Stopping API server...")
        server_manager.stop_server()


def test_api_server_startup(api_server):
    """Test that the API server starts up successfully."""
    # Test that the server is responding
    response = requests.get(f"http://{api_server.host}:{api_server.port}/api/metadata")
    assert response.status_code == 200
    log_handle.info("API server startup test passed")


def test_api_search_endpoint(api_server):
    """Test the /api/search endpoint."""
    # Test search endpoint with a simple query
    search_payload = {
        "query": "बेंगलुरु",
        "language": "hi",
        "exact_match": False,
        "exclude_words": [],
        "categories": {},
        "page_size": 10,
        "page_number": 1,
        "enable_reranking": True
    }
    
    response = requests.post(
        f"http://{api_server.host}:{api_server.port}/api/search",
        json=search_payload
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    validate_result_schema(data, True)
    log_handle.info(f"✓ API search test passed - found {data['total_results']} lexical results and {data.get('total_vector_results', 0)} vector results")


def test_api_metadata_endpoint(api_server):
    """Test the /api/metadata endpoint."""
    response = requests.get(f"http://{api_server.host}:{api_server.port}/api/metadata")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, dict)
    
    # Check new language-specific structure
    expected_language_keys = {"hindi", "gujarati"}
    actual_keys = set(data.keys())
    
    # Should have both language keys
    assert expected_language_keys.issubset(actual_keys), f"Expected language keys {expected_language_keys} in metadata, got {actual_keys}"
    
    # Each language should have its own metadata dictionary
    for language in expected_language_keys:
        lang_metadata = data[language]
        assert isinstance(lang_metadata, dict), f"Expected dict for {language} metadata"
        
        # Each language metadata can have various keys like Granth, Anuyog, Year, etc.
        # Just verify it's a dict structure - specific keys depend on indexed data
        log_handle.info(f"{language} metadata keys: {list(lang_metadata.keys())}")
    
    log_handle.info(f"API metadata test passed - received language-specific structure with keys: {list(data.keys())}")


def test_api_exact_phrase_search(api_server):
    """Test the /api/search endpoint with exact phrase matching."""
    test_cases = [
        {
            "query": "बृहदीश्वर मंदिर",
            "language": "hi",
            "expected_file": "thanjavur_hindi.pdf"
        },
        {
            "query": "વિધાધર ભટ્ટાયાર્યની",
            "language": "gu",
            "expected_file": "jaipur_gujarati.pdf"
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        search_payload = {
            "query": test_case["query"],
            "language": test_case["language"],
            "exact_match": True,
            "exclude_words": [],
            "categories": {},
            "page_size": 10,
            "page_number": 1,
            "enable_reranking": True
        }
        
        response = requests.post(
            f"http://{api_server.host}:{api_server.port}/api/search",
            json=search_payload
        )
        
        assert response.status_code == 200
        data = response.json()
        log_handle.info(f"response: {json_dumps(data, truncate_fields=['vector_embedding'])}")
        validate_result_schema(data, True)

        assert len(data["results"]) > 0
        for result in data["results"]:
            fname = result["filename"]
            assert fname == test_case["expected_file"]


def test_api_exclude_words(api_server):
    """Test the /api/search endpoint with exclude words functionality."""
    query = "हिंदू पौराणिक"
    language = "hi"
    
    # First test: regular search without exclude words - should return 2 results
    regular_search_payload = {
        "query": query,
        "language": language,
        "exact_match": False,
        "exclude_words": [],
        "categories": {},
        "page_size": 10,
        "page_number": 1,
        "enable_reranking": True
    }
    
    response = requests.post(
        f"http://{api_server.host}:{api_server.port}/api/search",
        json=regular_search_payload
    )
    
    assert response.status_code == 200
    data = response.json()
    log_handle.info(f"Regular search response: {json_dumps(data, truncate_fields=['vector_embedding'])}")
    
    # Check response structure
    validate_result_schema(data, True)

    # Should return 2 results
    regular_result_count = data["total_results"]
    assert regular_result_count == 3, f"Expected 2 results for regular search, got {regular_result_count}"
    
    # Second test: search with exclude words - should return only 1 result
    exclude_search_payload = {
        "query": query,
        "language": language,
        "exact_match": False,
        "exclude_words": ["हंपी"],
        "categories": {},
        "page_size": 10,
        "page_number": 1,
        "enable_reranking": True
    }
    
    response = requests.post(
        f"http://{api_server.host}:{api_server.port}/api/search",
        json=exclude_search_payload
    )
    
    assert response.status_code == 200
    data = response.json()
    log_handle.info(f"Exclude words search response: {json_dumps(data, truncate_fields=['vector_embedding'])}")
    
    # Check response structure
    validate_result_schema(data, True)

    # Should return only 1 result after excluding "हंपी"
    exclude_result_count = data["total_results"]
    assert exclude_result_count == 1, f"Expected 1 result after excluding 'हंपी', got {exclude_result_count}"
    
    log_handle.info(f"✓ Exclude words test passed - regular search: {regular_result_count} results, exclude search: {exclude_result_count} results")


def test_api_context_endpoint(api_server):
    """Test the /api/context/{chunk_id} endpoint."""
    # First, get some search results to get a valid chunk_id
    search_payload = {
        "query": "बेंगलुरु",
        "language": "hi",
        "exact_match": False,
        "exclude_words": [],
        "categories": {},
        "page_size": 1,
        "page_number": 1,
        "enable_reranking": True
    }
    
    search_response = requests.post(
        f"http://{api_server.host}:{api_server.port}/api/search",
        json=search_payload
    )
    
    assert search_response.status_code == 200
    search_data = search_response.json()
    
    if search_data["total_results"] > 0:
        # Get chunk_id from first result
        chunk_id = search_data["results"][0].get("id") or search_data["results"][0].get("_id")
        
        if chunk_id:
            # Test context endpoint
            context_response = requests.get(
                f"http://{api_server.host}:{api_server.port}/api/context/{chunk_id}?language=hi"
            )
            
            if context_response.status_code == 200:
                context_data = context_response.json()
                assert "current" in context_data
                log_handle.info("API context test passed")
            else:
                log_handle.info(f"Context endpoint returned {context_response.status_code}, may not be implemented or chunk not found")
        else:
            log_handle.info("No chunk_id found in search results, skipping context test")
    else:
        log_handle.info("No search results found, skipping context test")

def test_is_lexical_query(api_server):
    """Test is_lexical_query() logic with Hindi text searches."""
    # Test case 1: "इंदौर का इतिहास" - should trigger lexical search
    # (3 words, no punctuation, so is_lexical_query should return True)
    search_payload_1 = {
        "query": "इंदौर का इतिहास",
        "language": "hi",
        "exact_match": False,
        "exclude_words": [],
        "categories": {},
        "page_size": 10,
        "page_number": 1,
        "enable_reranking": True
    }
    
    response_1 = requests.post(
        f"http://{api_server.host}:{api_server.port}/api/search",
        json=search_payload_1
    )
    
    assert response_1.status_code == 200
    data_1 = response_1.json()
    log_handle.info(f"Response for 'इंदौर का इतिहास': {json_dumps(data_1, truncate_fields=['vector_embedding'])}")
    
    # Validate response structure for lexical search
    validate_result_schema(data_1, True)
    
    # Should have lexical results and specifically from indore_hindi.pdf
    assert data_1["total_results"] > 0, "Expected lexical results for 'इंदौर का इतिहास'"
    
    # Verify results are from indore_hindi.pdf
    found_indore_file = False
    for result in data_1["results"]:
        if "indore_hindi.pdf" in result["filename"]:
            found_indore_file = True
            break
    assert found_indore_file, "Expected to find results from indore_hindi.pdf"
    
    # Test case 2: "इंदौर का इतिहास?" - should trigger vector search  
    # (has punctuation '?', so is_lexical_query should return False)
    search_payload_2 = {
        "query": "इंदौर का इतिहास?",
        "language": "hi",
        "exact_match": False,
        "exclude_words": [],
        "categories": {},
        "page_size": 10,
        "page_number": 1,
        "enable_reranking": True
    }
    
    response_2 = requests.post(
        f"http://{api_server.host}:{api_server.port}/api/search",
        json=search_payload_2
    )
    
    assert response_2.status_code == 200
    data_2 = response_2.json()
    log_handle.info(f"Response for 'इंदौर का इतिहास?': {json_dumps(data_2, truncate_fields=['vector_embedding'])}")
    
    # Validate response structure for vector search
    validate_result_schema(data_2, False)
    
    # Should have vector results (can be from any file)
    assert data_2["total_vector_results"] > 0, "Expected vector results for 'इंदौर का इतिहास?'"
    
    # Test case 3: "સોનગઢ ઇતિહાસ" - should trigger lexical search
    # (2 words, no punctuation, so is_lexical_query should return True)
    search_payload_3 = {
        "query": "સોનગઢ ઇતિહાસ",
        "language": "gu",
        "exact_match": False,
        "exclude_words": [],
        "categories": {},
        "page_size": 10,
        "page_number": 1,
        "enable_reranking": True
    }
    
    response_3 = requests.post(
        f"http://{api_server.host}:{api_server.port}/api/search",
        json=search_payload_3
    )
    
    assert response_3.status_code == 200
    data_3 = response_3.json()
    log_handle.info(f"Response for 'સોનગઢ ઇતિહાસ': {json_dumps(data_3, truncate_fields=['vector_embedding'])}")
    
    # Validate response structure for lexical search
    validate_result_schema(data_3, True)
    
    # Should have lexical results
    assert data_3["total_results"] > 0, "Expected lexical results for 'સોનગઢ ઇતિહાસ'"
    
    # Test case 4: "સોનગઢનો ઇતિહાસ?" - should trigger vector search  
    # (has punctuation '?', so is_lexical_query should return False)
    search_payload_4 = {
        "query": "સોનગઢનો ઇતિહાસ?",
        "language": "gu",
        "exact_match": False,
        "exclude_words": [],
        "categories": {},
        "page_size": 10,
        "page_number": 1,
        "enable_reranking": True
    }
    
    response_4 = requests.post(
        f"http://{api_server.host}:{api_server.port}/api/search",
        json=search_payload_4
    )
    
    assert response_4.status_code == 200
    data_4 = response_4.json()
    log_handle.info(f"Response for 'સોનગઢનો ઇતિહાસ?': {json_dumps(data_4, truncate_fields=['vector_embedding'])}")
    
    # Validate response structure for vector search
    validate_result_schema(data_4, False)
    
    # Should have vector results
    assert data_4["total_vector_results"] > 0, "Expected vector results for 'સોનગઢનો ઇતિહાસ?'"
    
    # Test case 5: "हंपी के बारे में कुछ बताइए" - should trigger vector search
    # (has question phrase "कुछ बताइए", so is_lexical_query should return False)
    search_payload_5 = {
        "query": "हंपी के बारे में कुछ बताइए",
        "language": "hi",
        "exact_match": False,
        "exclude_words": [],
        "categories": {},
        "page_size": 10,
        "page_number": 1,
        "enable_reranking": True
    }
    
    response_5 = requests.post(
        f"http://{api_server.host}:{api_server.port}/api/search",
        json=search_payload_5
    )
    
    assert response_5.status_code == 200
    data_5 = response_5.json()
    log_handle.info(f"Response for 'हंपी के बारे में कुछ बताइए': {json_dumps(data_5, truncate_fields=['vector_embedding'])}")
    
    # Validate response structure for vector search
    validate_result_schema(data_5, False)
    
    # Should have vector results
    assert data_5["total_vector_results"] > 0, "Expected vector results for 'हंपी के बारे में कुछ बताइए'"
    
    log_handle.info(f"is_lexical_query test passed - Hindi lexical: {data_1['total_results']}, Hindi vector: {data_2['total_vector_results']}, Gujarati lexical: {data_3['total_results']}, Gujarati vector: {data_4['total_vector_results']}, Hindi question: {data_5['total_vector_results']} results")


def test_api_spell_suggestion_search(api_server):
    """Test search with spelling suggestion functionality."""
    test_cases = [
        {
            "misspelled_query": "सराफ",
            "language": "hi",
            "expected_suggestion": "सराफा",
            "expected_file": "indore_hindi.pdf"
        },
        {
            "misspelled_query": "સરાફ",
            "language": "gu",
            "expected_suggestion": "સરાફા",
            "expected_file": "indore_gujarati.pdf"
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        # Test case 1: Search for misspelled word - should return no results but suggest correct spelling
        search_payload_1 = {
            "query": test_case["misspelled_query"],
            "language": test_case["language"],
            "exact_match": False,
            "exclude_words": [],
            "categories": {},
            "page_size": 10,
            "page_number": 1,
            "enable_reranking": True
        }
        
        response_1 = requests.post(
            f"http://{api_server.host}:{api_server.port}/api/search",
            json=search_payload_1
        )
        
        assert response_1.status_code == 200
        data_1 = response_1.json()
        log_handle.info(f"Response for '{test_case['misspelled_query']}': {json_dumps(data_1, truncate_fields=['vector_embedding'])}")
        
        # Should have no results but contain suggestions
        assert data_1["total_results"] == 0, f"Expected no results for misspelled '{test_case['misspelled_query']}'"
        assert "suggestions" in data_1, "Expected suggestions in response"
        assert len(data_1["suggestions"]) > 0, "Expected at least one suggestion"
        
        # Check if expected suggestion is in suggestions
        suggested_words = data_1["suggestions"]
        assert test_case["expected_suggestion"] in suggested_words, f"Expected '{test_case['expected_suggestion']}' in suggestions"
        
        # Test case 2: Search for the suggested word - should return results from expected file
        search_payload_2 = {
            "query": test_case["expected_suggestion"],
            "language": test_case["language"],
            "exact_match": False,
            "exclude_words": [],
            "categories": {},
            "page_size": 10,
            "page_number": 1,
            "enable_reranking": True
        }
        
        response_2 = requests.post(
            f"http://{api_server.host}:{api_server.port}/api/search",
            json=search_payload_2
        )
        
        assert response_2.status_code == 200
        data_2 = response_2.json()
        log_handle.info(f"Response for '{test_case['expected_suggestion']}': {json_dumps(data_2, truncate_fields=['vector_embedding'])}")
        
        # Should have results for the correctly spelled word
        assert data_2["total_results"] > 0, f"Expected results for correctly spelled '{test_case['expected_suggestion']}'"
        
        # Validate response structure
        validate_result_schema(data_2, True)
        
        # Validate that results come from expected file
        found_expected_file = False
        for result in data_2["results"]:
            if test_case["expected_file"] in result["filename"]:
                found_expected_file = True
                break
        assert found_expected_file, f"Expected to find results from {test_case['expected_file']}"
        
        log_handle.info(f"✓ {test_case['language']} spell suggestion test passed - '{test_case['misspelled_query']}' returned {data_1['total_results']} results with {len(data_1.get('suggestions', []))} suggestions, '{test_case['expected_suggestion']}' returned {data_2['total_results']} results from {test_case['expected_file']}")
    
    log_handle.info("✓ All spell suggestion tests passed")


def test_get_context(api_server):
    """Test the /api/context/{document_id} endpoint with Gujarati and Hindi queries."""
    test_cases = [
        {
            "query": "અહમદનગર",
            "language": "gu", 
            "expected_file": "hampi_gujarati.pdf"
        },
        {
            "query": "गोलकोंडा",
            "language": "hi",
            "expected_file": "hampi_hindi.pdf"
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        # Step 1: Issue search query to get document_id
        search_payload = {
            "query": test_case["query"],
            "language": test_case["language"],
            "exact_match": False,
            "exclude_words": [],
            "categories": {},
            "page_size": 10,
            "page_number": 1,
            "enable_reranking": True
        }
        
        search_response = requests.post(
            f"http://{api_server.host}:{api_server.port}/api/search",
            json=search_payload
        )
        
        assert search_response.status_code == 200
        search_data = search_response.json()
        log_handle.info(f"Search response for '{test_case['query']}': {json_dumps(search_data, truncate_fields=['vector_embedding'])}")
        
        # Validate we have search results
        assert search_data["total_results"] > 0, f"Expected results for '{test_case['query']}'"
        
        # Validate results come from expected file
        first_result = search_data["results"][0]
        assert test_case["expected_file"] in first_result["filename"], f"Expected result from {test_case['expected_file']}"
        
        # Step 2: Get document_id from first result
        document_id = first_result.get("document_id") or first_result.get("id") or first_result.get("_id")
        assert document_id is not None, "Expected document_id in search result"
        
        # Step 3: Issue get_context API call
        context_response = requests.get(
            f"http://{api_server.host}:{api_server.port}/api/context/{document_id}?language={test_case['language']}"
        )
        
        assert context_response.status_code == 200, f"Context API should return 200 for document_id: {document_id}"
        context_data = context_response.json()
        log_handle.info(f"Context response for document_id '{document_id}': {json_dumps(context_data, truncate_fields=['vector_embedding'])}")
        
        # Step 4: Validate response structure - should have previous, current, next keys
        expected_keys = {"previous", "current", "next"}
        actual_keys = set(context_data.keys())
        assert expected_keys.issubset(actual_keys), f"Expected keys {expected_keys} in context response, got {actual_keys}"
        
        # Step 5: Validate consecutive paragraph_id values
        paragraphs = []
        for key in ["previous", "current", "next"]:
            if context_data[key] is not None:  # Some keys might be None at document boundaries
                paragraph_id = context_data[key].get("paragraph_id")
                if paragraph_id is not None:
                    paragraphs.append((key, paragraph_id))
        
        # Sort by paragraph_id to check if they are consecutive
        paragraphs.sort(key=lambda x: x[1])
        assert len(paragraphs) > 2
        
        # Check if paragraph_ids are consecutive
        for j in range(1, len(paragraphs)):
            current_id = paragraphs[j][1]
            previous_id = paragraphs[j-1][1]
            assert current_id == previous_id + 1, f"Expected consecutive paragraph_ids, got {previous_id} and {current_id}"
        
        log_handle.info(f"✓ {test_case['language']} context test passed - document_id: {document_id}, paragraph_ids: {[p[1] for p in paragraphs]}")
    
    log_handle.info("✓ All context tests passed")


def test_get_similar_documents(api_server):
    """Test the /api/similar/{document_id} endpoint with Gujarati and Hindi queries."""
    test_cases = [
        {
            "query": "સોનગઢનો ઇતિહાસ શું છે?",
            "language": "gu"
        },
        {
            "query": "सोनगढ़ का इतिहास क्या है?",
            "language": "hi"
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        # Step 1: Issue search query to get search results
        search_payload = {
            "query": test_case["query"],
            "language": test_case["language"],
            "exact_match": False,
            "exclude_words": [],
            "categories": {},
            "page_size": 10,
            "page_number": 1,
            "enable_reranking": True
        }
        
        search_response = requests.post(
            f"http://{api_server.host}:{api_server.port}/api/search",
            json=search_payload
        )
        
        assert search_response.status_code == 200
        search_data = search_response.json()
        log_handle.info(f"Search response for '{test_case['query']}': {json_dumps(search_data, truncate_fields=['vector_embedding'])}")
        
        # Validate we have enough search results to get the second one
        total_results = search_data.get("total_vector_results", 0)
        assert total_results >= 2, f"Expected at least 2 results for '{test_case['query']}', got {total_results}"
        
        # Step 2: Get document_id from second result
        one_result = search_data["vector_results"][1]

        assert one_result is not None, "Could not find search result"
        
        document_id = one_result.get("document_id")
        assert document_id is not None, "Expected document_id in second search result"
        
        log_handle.info(f"Using document_id '{document_id}' from second search result")
        
        # Step 3: Issue get similar documents API call
        similar_response = requests.get(
            f"http://{api_server.host}:{api_server.port}/api/similar-documents/{document_id}?language={test_case['language']}"
        )
        
        assert similar_response.status_code == 200, f"Similar documents API should return 200 for document_id: {document_id}"
        similar_data = similar_response.json()
        log_handle.info(f"Similar documents response for document_id '{document_id}': {json_dumps(similar_data, truncate_fields=['vector_embedding'])}")
        
        # Step 4: Validate response has non-zero results
        similar_results_count = similar_data.get("total_results", 0)
        assert similar_results_count > 0, f"Expected non-zero similar documents for document_id: {document_id}, got {similar_results_count}"
        
        # Step 5: Validate response structure
        # Validate each similar document has required fields
        for doc in similar_data["results"]:
            assert "document_id" in doc or "_id" in doc or "document_id" in doc, "Expected id field in similar document"
            assert "filename" in doc, "Expected filename field in similar document"
            assert "content_snippet" in doc
        
        log_handle.info(f"✓ {test_case['language']} similar documents test passed - document_id: {document_id}, found {similar_results_count} similar documents")
    
    log_handle.info("✓ All similar documents tests passed")


def test_cache_invalidation(api_server):
    """
    Tests cache invalidation by:
    1. Calling metadata to populate cache
    2. Invalidating cache
    3. Calling metadata again and comparing - should be no change in data
    """
    # First call to populate cache
    response1 = requests.get(f"http://{api_server.host}:{api_server.port}/api/metadata")
    assert response1.status_code == 200
    metadata_before = response1.json()
    log_handle.info(f"before: {json_dumps(metadata_before)}")
    
    # Invalidate cache
    invalidate_response = requests.post(f"http://{api_server.host}:{api_server.port}/api/cache/invalidate")
    assert invalidate_response.status_code == 200
    assert invalidate_response.json()["status"] == "success"
    assert "Cache invalidated successfully" in invalidate_response.json()["message"]
    
    # Second call after cache invalidation
    response2 = requests.get(f"http://{api_server.host}:{api_server.port}/api/metadata")
    assert response2.status_code == 200
    metadata_after = response2.json()
    log_handle.info(f"after: {json_dumps(metadata_after)}")
    
    # Data should be the same (no change in underlying OpenSearch data)
    assert metadata_before == metadata_after
    assert "hindi" in metadata_after
    assert "gujarati" in metadata_after
    
    log_handle.info("✓ Cache invalidation test passed - metadata consistent after cache invalidation")


def validate_result_schema(data, lexical_results):
    keys = ["results", "total_results", "vector_results", "total_vector_results"]
    for key in keys:
        assert key in data
    if lexical_results:
        assert data["vector_results"] == []
        assert data["total_vector_results"] == 0
    else:
        assert data["results"] == []
        assert data["total_results"] == 0
