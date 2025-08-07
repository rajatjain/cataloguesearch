import logging
import os
import traceback

import yaml
from opensearchpy import OpenSearch, ConnectionError
from backend.config import Config  # Adjust the import path as needed
from backend.common.embedding_models import get_embedding_model_factory

# --- Module-level variables ---
# This variable will hold our single, cached client instance.
_client: OpenSearch | None = None
_opensearch_settings: dict | None = None

log_handle = logging.getLogger(__name__)

def get_opensearch_config(config: Config) -> dict:
    """
    Loads the OpenSearch configuration from the specified YAML file.
    If the file does not exist, raises a FileNotFoundError.

    Args:
        config: Config object containing OpenSearch settings

    Returns:
        A dictionary containing the OpenSearch configuration settings.
    """
    global _opensearch_settings
    opensearch_config_path = config.OPENSEARCH_CONFIG_PATH
    if not opensearch_config_path or not os.path.exists(opensearch_config_path):
        log_handle.critical(
            f"OpenSearch config file not found at {opensearch_config_path}. Exiting.")
        raise FileNotFoundError(
            f"OpenSearch config file not found: {opensearch_config_path}")

    if not _opensearch_settings:
        log_handle.info(f"Loading OpenSearch config from {opensearch_config_path}")
        with open(opensearch_config_path, 'r', encoding='utf-8') as f:
            _opensearch_settings = yaml.safe_load(f)
        log_handle.info(f"Loaded OpenSearch config from {opensearch_config_path}")
        log_handle.info(f"Open Search settings is {_opensearch_settings}")

    # Get embedding dimension from factory pattern
    embedding_model = get_embedding_model_factory(config)
    _opensearch_settings['mappings']['properties']['vector_embedding']['dimension'] = \
        embedding_model.get_embedding_dimension()

    return _opensearch_settings


def create_index_if_not_exists(config, opensearch_client):
    """
    Creates the OpenSearch index with a predefined mapping if it doesn't already exist.
    Includes settings for k-NN and analyzers for Hindi/Gujarati.
    """
    opensearch_config = get_opensearch_config(config)
    index_name = config.OPENSEARCH_INDEX_NAME
    settings = opensearch_config.get('settings', {})
    mappings = opensearch_config.get('mappings', {})

    try:
        if not opensearch_client.indices.exists(index_name):
            response = opensearch_client.indices.create(
                index=index_name, body = {
                    "settings": settings,
                    "mappings": mappings,
                })
            log_handle.info(f"Index '{index_name}' created: {response}")
    except Exception as e:
        log_handle.critical(f"Error creating index '{index_name}': {e}")
        raise

def delete_index(config: Config):
    """
    Deletes the specified OpenSearch index if it exists.

    Args:
        config: Config object containing OpenSearch settings
    """
    global _client
    if not config or not config.OPENSEARCH_INDEX_NAME:
        log_handle.error("Invalid config or missing index name")
        raise ValueError("Config and index name are required")

    client = _client
    index_name = config.OPENSEARCH_INDEX_NAME

    try:
        if client.indices.exists(index=index_name):
            response = client.indices.delete(index=index_name)
            log_handle.info(f"Index '{index_name}' deleted successfully: {response}")
        else:
            log_handle.warning(f"Index '{index_name}' does not exist, nothing to delete")
    except Exception as e:
        log_handle.error(f"Error deleting index '{index_name}': {e}")
        raise


def get_opensearch_client(config: Config, force_clean=False) -> OpenSearch:
    """
    Returns a singleton OpenSearch client instance.
    Args:
        config: A Config object with the OpenSearch connection details.
                This is only used on the very first call.
        force_clean: If True, deletes the existing index before creating a new one.
                     IMPORTANT: ONLY USE THIS PARAM WHILE RUNNING TESTS. OR IF YOU
                     KNOW WHAT YOU ARE DOING. THIS WILL DELETE ALL DATA IN THE INDEX.

    Returns:
        An initialized and connected OpenSearch client.

    Raises:
        ConnectionError: If a connection to OpenSearch cannot be established on the first call.
    """
    global _client
    if _client:
        if force_clean:
            delete_index(config)
        create_index_if_not_exists(config, _client)
        return _client

    log_handle.info("OpenSearch client not initialized. Creating a new instance...")
    try:
        # Create the OpenSearch client using the provided configuration
        client = OpenSearch(
            hosts=[{
                'scheme': 'http',
                'host': config.OPENSEARCH_HOST,
                'port': config.OPENSEARCH_PORT
            }],
            use_ssl=False
        )

        # Ping the server to confirm the connection and credentials are valid
        if not client.ping():
            raise ConnectionError(
                "Failed to ping OpenSearch. Please check your host, port, and credentials."
            )

        # Cache the successfully created client in our module-level variable
        _client = client
        log_handle.info("OpenSearch client initialized and cached successfully.")

        if force_clean:
            delete_index(config)

    except Exception as e:
        traceback.print_exc()
        log_handle.critical(f"Failed to initialize OpenSearch client: {e}")
        # Re-raise the exception to let the calling code handle the connection failure.
        raise

    create_index_if_not_exists(config, _client)
    return _client


def get_metadata(config: Config) -> dict[str, list[str]]:
    """
    Scans the metadata field in OpenSearch, extracts all key-value pairs,
    deduplicates them and returns as dict[str, list[str]].
    Uses scroll API to retrieve all documents without limit.

    Args:
        config: Config object containing OpenSearch settings

    Returns:
        dict[str, list[str]]: Dictionary with metadata keys and their unique values
    """
    client = get_opensearch_client(config)

    # Query to get all documents and extract metadata field using scroll API
    query_body = {
        "size": 10000,  # Batch size for scroll
        "_source": ["metadata"],
        "query": {
            "match_all": {}
        }
    }

    # Initialize scroll search
    response = client.search(
        index=config.OPENSEARCH_INDEX_NAME,
        body=query_body,
        scroll='2m'  # Keep scroll context alive for 2 minutes
    )

    # Extract and deduplicate metadata
    metadata_dict = {}
    total_processed = 0
    
    while True:
        hits = response.get('hits', {}).get('hits', [])
        
        if not hits:
            break
            
        # Process current batch
        for hit in hits:
            source = hit.get('_source', {})
            document_metadata = source.get('metadata', {})

            # Process each key-value pair in the metadata
            for key, value in document_metadata.items():
                if key not in metadata_dict:
                    metadata_dict[key] = set()

                # Handle different value types
                if isinstance(value, list):
                    for item in value:
                        metadata_dict[key].add(str(item))
                else:
                    metadata_dict[key].add(str(value))
        
        total_processed += len(hits)
        log_handle.debug(f"Processed {total_processed} documents so far...")
        
        # Get scroll ID for next batch
        scroll_id = response.get('_scroll_id')
        if not scroll_id:
            break
            
        # Get next batch
        response = client.scroll(
            scroll_id=scroll_id,
            scroll='2m'
        )

    # Convert sets to sorted lists for consistent output
    result = {key: sorted(list(values)) for key, values in metadata_dict.items()}

    log_handle.info(f"Metadata retrieved from {total_processed} documents: {len(result)} unique keys found")
    return result

def delete_documents_by_filename(config: Config, original_filename: str):
    """
    Deletes all documents from the OpenSearch index that match the given original_filename.

    Args:
        config: Config object containing OpenSearch settings.
        original_filename: The name of the file to delete documents for.
    """
    client = get_opensearch_client(config)
    index_name = config.OPENSEARCH_INDEX_NAME

    query_body = {
        "query": {
            "term": {
                # Use .keyword for an exact, non-analyzed match on the filename
                "original_filename": original_filename
            }
        }
    }

    try:
        log_handle.info(f"Attempting to delete documents with original_filename: {original_filename}")
        response = client.delete_by_query(
            index=index_name,
            body=query_body,
            wait_for_completion=True,  # Make the operation synchronous
            refresh=True  # Refresh the index to make changes visible immediately
        )
        deleted_count = response.get('deleted', 0)
        log_handle.info(f"Successfully deleted {deleted_count} documents for '{original_filename}'.")
    except Exception as e:
        log_handle.error(f"Error deleting documents for '{original_filename}': {e}", exc_info=True)
        raise
