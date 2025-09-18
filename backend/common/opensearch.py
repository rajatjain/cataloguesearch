"""OpenSearch client and configuration management.

This module provides functions to manage OpenSearch connections, configurations,
and operations including index management, metadata retrieval, and document operations.
"""
import logging
import os
import traceback

import yaml
from opensearchpy import OpenSearch
from backend.config import Config
from backend.common.embedding_models import get_embedding_model_factory

# Module-level variables for singleton pattern
# These variables hold cached client instance and settings
_CLIENT = None
_OPENSEARCH_SETTINGS = None

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
    global _OPENSEARCH_SETTINGS  # pylint: disable=global-statement
    opensearch_config_path = config.OPENSEARCH_CONFIG_PATH
    if not opensearch_config_path or not os.path.exists(opensearch_config_path):
        log_handle.critical(
            f"OpenSearch config file not found at {opensearch_config_path}. Exiting.")
        raise FileNotFoundError(
            f"OpenSearch config file not found: {opensearch_config_path}")

    if not _OPENSEARCH_SETTINGS:
        log_handle.info(f"Loading OpenSearch config from {opensearch_config_path}")
        with open(opensearch_config_path, 'r', encoding='utf-8') as f:
            full_config = yaml.safe_load(f)

        # Extract the search_index configuration
        _OPENSEARCH_SETTINGS = full_config.get('search_index', {})
        if not _OPENSEARCH_SETTINGS:
            log_handle.critical(
                f"search_index configuration not found in {opensearch_config_path}")
            raise ValueError(
                f"search_index configuration not found in {opensearch_config_path}")

        log_handle.info(f"Loaded OpenSearch config from {opensearch_config_path}")
        log_handle.info(f"OpenSearch settings: {_OPENSEARCH_SETTINGS}")

    # Get embedding dimension from factory pattern
    embedding_model = get_embedding_model_factory(config)

    # Ensure mappings structure exists before setting dimension
    if ('mappings' in _OPENSEARCH_SETTINGS and
            'properties' in _OPENSEARCH_SETTINGS['mappings'] and
            'vector_embedding' in _OPENSEARCH_SETTINGS['mappings']['properties']):
        _OPENSEARCH_SETTINGS['mappings']['properties']['vector_embedding']['dimension'] = \
            embedding_model.get_embedding_dimension()
    else:
        log_handle.warning(
            "vector_embedding mapping not found in OpenSearch config, "
            "skipping dimension update")

    return _OPENSEARCH_SETTINGS

def get_metadata_index_config(config: Config) -> dict:
    """Loads the OpenSearch configuration for the metadata index."""
    opensearch_config_path = config.OPENSEARCH_CONFIG_PATH
    with open(opensearch_config_path, 'r', encoding='utf-8') as f:
        full_config = yaml.safe_load(f)

    metadata_config = full_config.get('metadata_index', {})

    if not metadata_config:
        log_handle.warning(f"metadata_index configuration not found in {opensearch_config_path}")
        return {}

    return metadata_config

def _create_index_if_not_exists(opensearch_client: OpenSearch, index_name: str, index_body: dict):
    """Helper to create a single index if it doesn't exist."""
    if not index_body:
        log_handle.error(f"Index configuration for '{index_name}' is empty. Skipping creation.")
        return
    try:
        if not opensearch_client.indices.exists(index_name):
            log_handle.info(f"Index '{index_name}' does not exist. Creating...")
            response = opensearch_client.indices.create(
                index=index_name, body=index_body
            )
            log_handle.info(f"Index '{index_name}' created: {response}")
    except Exception as e:
        log_handle.critical(f"Error creating index '{index_name}': {e}")
        raise

def create_indices_if_not_exists(config: Config, opensearch_client: OpenSearch):
    """
    Creates all required OpenSearch indices (main and metadata) if they don't exist.
    """
    # 1. Create main document index
    main_index_config = get_opensearch_config(config)
    main_index_name = config.OPENSEARCH_INDEX_NAME
    _create_index_if_not_exists(opensearch_client, main_index_name, main_index_config)

    # 2. Create metadata index
    metadata_index_config = get_metadata_index_config(config)
    metadata_index_name = config.OPENSEARCH_METADATA_INDEX_NAME
    _create_index_if_not_exists(opensearch_client, metadata_index_name, metadata_index_config)

def delete_index(config: Config):
    """
    Deletes the specified OpenSearch indices if they exist.

    Args:
        config: Config object containing OpenSearch settings
    """
    if not config:
        log_handle.error("Invalid config provided")
        raise ValueError("Config is required")

    client = _CLIENT
    if not client:
        log_handle.warning("No OpenSearch client available for index deletion")
        return
    indices_to_delete = [
        config.OPENSEARCH_INDEX_NAME,
        config.OPENSEARCH_METADATA_INDEX_NAME
    ]

    for index_name in indices_to_delete:
        if not index_name:
            continue
        try:
            if client.indices.exists(index=index_name):
                response = client.indices.delete(index=index_name)
                log_handle.info(f"Index '{index_name}' deleted successfully: {response}")
            else:
                log_handle.warning(f"Index '{index_name}' does not exist, nothing to delete")
        except (ConnectionError, ValueError, OSError) as e:
            log_handle.error(f"Error deleting index '{index_name}': {e}", exc_info=True)
            # Continue to try deleting other indices even if one fails
            continue

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
    global _CLIENT  # pylint: disable=global-statement
    if _CLIENT:
        if force_clean:
            delete_index(config)
        return _CLIENT

    log_handle.info("OpenSearch client not initialized. Creating a new instance...")
    try:
        # Create the OpenSearch client using the provided configuration
        client = OpenSearch(
            hosts=[{
                'scheme': 'http',
                'host': config.OPENSEARCH_HOST,
                'port': config.OPENSEARCH_PORT
            }],
            use_ssl=False,
            timeout=60
        )

        # Ping the server to confirm the connection and credentials are valid
        if not client.ping():
            raise ConnectionError(
                "Failed to ping OpenSearch. Please check your host, port, and credentials."
            )

        # Cache the successfully created client in our module-level variable
        _CLIENT = client
        log_handle.info("OpenSearch client initialized and cached successfully.")
    except Exception as e:
        traceback.print_exc()
        log_handle.critical(f"Failed to initialize OpenSearch client: {e}")
        # Re-raise the exception to let the calling code handle the connection failure.
        raise

    return _CLIENT


def get_metadata(config: Config) -> dict[str, dict[str, list[str]]]:
    """
    Retrieves all metadata from the dedicated metadata index grouped by language.
    This is much more efficient than scanning the main document index.

    Args:
        config: Config object containing OpenSearch settings

    Returns:
        dict[str, dict[str, list[str]]]: Dictionary with language keys, each containing
        metadata keys and their unique, sorted values.
        Format: {"hindi": {"author": ["value1", "value2"]}, "gujarati": {"author": ["value3"]}}
    """
    client = get_opensearch_client(config)
    metadata_index = config.OPENSEARCH_METADATA_INDEX_NAME

    if not client.indices.exists(metadata_index):
        log_handle.warning(
            f"Metadata index '{metadata_index}' does not exist. Returning empty metadata.")
        return {"hindi": {}, "gujarati": {}}

    # Query to get all documents from the metadata index.
    query_body = {
        "size": 1000,  # Assume there won't be more than 1000 unique metadata keys
        "query": {"match_all": {}}
    }

    try:
        response = client.search(
            index=metadata_index,
            body=query_body
        )

        # Initialize language-specific dictionaries
        result = {"hindi": {}, "gujarati": {}}
        
        for hit in response.get('hits', {}).get('hits', []):
            source = hit.get('_source', {})
            
            # Get key from source (new structure) or fall back to document ID (old structure)
            key = source.get('key')
            if not key:
                # Backward compatibility: extract key from document ID
                doc_id = hit.get('_id')
                if '_' in doc_id:
                    key = '_'.join(doc_id.split('_')[:-1])  # Remove language suffix
                else:
                    key = doc_id  # Old format without language
            
            # The values are stored in the 'values' field of the source
            values = source.get('values', [])
            # Get language, default to "hindi" for backward compatibility
            language = source.get('language', 'hindi')

            if key and values:
                # Ensure language key exists in result
                if language not in result:
                    result[language] = {}
                
                # The values should already be sorted from the indexing process
                result[language][key] = values

        log_handle.info(
            f"Metadata retrieved from '{metadata_index}': "
            f"Hindi: {len(result['hindi'])} keys, Gujarati: {len(result['gujarati'])} keys")
        return result
    except (ConnectionError, ValueError, OSError) as e:
        log_handle.error(
            f"Error retrieving metadata from index '{metadata_index}': {e}", exc_info=True)
        return {"hindi": {}, "gujarati": {}}

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
        log_handle.info(
            f"Attempting to delete documents with original_filename: {original_filename}")
        response = client.delete_by_query(
            index=index_name,
            body=query_body
        )
        # Refresh the index to make changes visible immediately
        client.indices.refresh(index=index_name)
        deleted_count = response.get('deleted', 0)
        log_handle.info(
            f"Successfully deleted {deleted_count} documents for '{original_filename}'.")
    except Exception as e:
        log_handle.error(
            f"Error deleting documents for '{original_filename}': {e}", exc_info=True)
        raise
