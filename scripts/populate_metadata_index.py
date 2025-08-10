#!/usr/bin/env python3
"""
One-time script to populate the metadata index from the main document index.

This script scans all documents in the primary data index, aggregates all unique
metadata key-value pairs, and then populates the dedicated metadata index with
this information. This is intended to be run once after the metadata index has
been created to backfill historical data.
"""
import logging
import sys
import os

# Add the project root to the Python path to allow for module imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from opensearchpy import helpers
from tqdm import tqdm

from backend.common.opensearch import get_opensearch_client
from backend.config import Config
from utils.logger import setup_logging, VERBOSE_LEVEL_NUM

log_handle = logging.getLogger(__name__)

def populate_metadata(config: Config):
    """
    Scans the main document index, aggregates all metadata, and populates
    the dedicated metadata index.
    """
    client = get_opensearch_client(config)
    main_index = config.OPENSEARCH_INDEX_NAME
    metadata_index = config.OPENSEARCH_METADATA_INDEX_NAME

    log_handle.info(f"Starting metadata aggregation from index '{main_index}'...")

    # --- Step 1: Aggregate metadata from the main index ---
    query_body = {
        "size": 1000,  # Batch size for scroll
        "_source": ["metadata"],
        "query": {"match_all": {}}
    }

    # Use tqdm to show a progress bar for the scan operation
    total_docs = client.count(index=main_index, body={"query": {"match_all": {}}})['count']
    pbar = tqdm(total=total_docs, desc="Scanning documents")

    aggregated_metadata = {}

    # Use the helpers.scan utility, a generator that simplifies scrolling through all documents
    for hit in helpers.scan(client, index=main_index, query=query_body):
        document_metadata = hit.get('_source', {}).get('metadata', {})

        for key, value in document_metadata.items():
            if key not in aggregated_metadata:
                aggregated_metadata[key] = set()

            # Add value(s) to the set to ensure uniqueness
            if isinstance(value, list):
                for item in value:
                    aggregated_metadata[key].add(str(item))
            else:
                aggregated_metadata[key].add(str(value))
        pbar.update(1)

    pbar.close()
    log_handle.info(f"Finished aggregation. Found {len(aggregated_metadata)} unique metadata keys.")

    if not aggregated_metadata:
        log_handle.warning("No metadata found. Nothing to populate.")
        return

    # --- Step 2: Populate the metadata index using the bulk helper ---
    log_handle.info(f"Populating the '{metadata_index}' index...")

    actions = [
        {
            "_index": metadata_index,
            "_id": key,  # Use the metadata key (e.g., "author") as the document ID
            "_source": {"values": sorted(list(values))}
        }
        for key, values in aggregated_metadata.items()
    ]

    success, failed = helpers.bulk(client, actions, stats_only=True, raise_on_error=False)
    log_handle.info(f"Successfully indexed {success} metadata documents.")
    if failed > 0:
        log_handle.error(f"Failed to index {failed} metadata documents. Check OpenSearch logs for details.")

    log_handle.info("Metadata index population complete.")

def main():
    """Main entry point for the script."""
    logs_dir = os.path.join(os.getenv("HOME", "/tmp"), "cataloguesearch/logs/scripts")
    setup_logging(logs_dir, console_level=logging.INFO, file_level=VERBOSE_LEVEL_NUM, console_only=False)
    config = Config("configs/config.yaml")
    populate_metadata(config)

if __name__ == '__main__':
    main()