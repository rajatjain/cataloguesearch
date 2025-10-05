#!/usr/bin/env python3
"""
Script to repopulate the metadata index from existing documents in the main index.
Reuses the existing update_metadata_index() logic for consistency.
"""

import logging
import sys
import os

from utils.logger import setup_logging

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.config import Config
from backend.common.opensearch import get_opensearch_client, create_indices_if_not_exists, update_metadata_index

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log_handle = logging.getLogger(__name__)

def repopulate_metadata_index():
    """
    Repopulates the metadata index by extracting metadata from all documents
    in the main search index and calling update_metadata_index() for each unique metadata set.
    """
    # Load configuration
    config = Config()

    # Get OpenSearch client
    client = get_opensearch_client(config)

    # Delete metadata index if it exists
    metadata_index_name = config.OPENSEARCH_METADATA_INDEX_NAME
    if client.indices.exists(metadata_index_name):
        log_handle.info(f"Deleting existing metadata index: {metadata_index_name}")
        client.indices.delete(index=metadata_index_name)
        log_handle.info(f"Metadata index deleted successfully")

    # Ensure indices exist (will recreate the metadata index)
    create_indices_if_not_exists(config, client)

    main_index = config.OPENSEARCH_INDEX_NAME

    log_handle.info(f"Extracting metadata from main index: {main_index}")
    log_handle.info(f"Populating metadata index: {metadata_index_name}")

    # Keep track of processed metadata to avoid duplicates
    processed_metadata = set()

    # Scroll through all documents
    query_body = {
        "size": 1000,
        "query": {"match_all": {}},
        "_source": ["metadata", "language"]
    }

    try:
        # Initial search
        response = client.search(
            index=main_index,
            body=query_body,
            scroll='5m'
        )

        scroll_id = response.get('_scroll_id')
        hits = response['hits']['hits']
        total_docs = response['hits']['total']['value']
        processed_docs = 0

        log_handle.info(f"Found {total_docs} documents to process")

        while hits:
            for hit in hits:
                source = hit.get('_source', {})
                metadata = source.get('metadata', {})
                language = source.get('language', 'hi')

                # Add language to metadata for update_metadata_index
                metadata_with_language = metadata.copy()
                metadata_with_language['language'] = language

                # Create a hash of this metadata to avoid processing duplicates
                metadata_hash = str(sorted(metadata_with_language.items()))

                if metadata_hash not in processed_metadata:
                    processed_metadata.add(metadata_hash)

                    # Call update_metadata_index with config, client, and metadata
                    update_metadata_index(config, client, metadata_with_language)
                
                processed_docs += 1
            
            if processed_docs % 1000 == 0:
                log_handle.info(f"Processed {processed_docs}/{total_docs} documents...")
            
            # Get next batch
            try:
                response = client.scroll(scroll_id=scroll_id, scroll='5m')
                hits = response['hits']['hits']
            except Exception as e:
                log_handle.warning(f"Error during scroll: {e}")
                break
        
        # Clear scroll
        try:
            client.clear_scroll(scroll_id=scroll_id)
        except:
            pass
            
        log_handle.info(f"Finished processing {processed_docs} documents")
        log_handle.info(f"Processed {len(processed_metadata)} unique metadata combinations")
        log_handle.info("Metadata index repopulation completed successfully!")
        
    except Exception as e:
        log_handle.error(f"Error during metadata extraction: {e}")
        raise

if __name__ == "__main__":
    setup_logging(console_only=True)
    config = Config("configs/config.yaml")
    repopulate_metadata_index()