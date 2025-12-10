#!/usr/bin/env python3
"""
Test script for bookmark extraction with different Ollama models.

Usage:
    python scratch/test_bookmark_extractor.py

Edit the main() function to set:
    - pdf_path: Path to your PDF file
    - model_name: Ollama model to use

Available models to try:
    - gpt-oss:20b (default, slow but accurate)
    - qwen2.5:7b (good at structured tasks)
    - llama3.2:3b (fast)
    - phi3.5:3.8b (solid)
    - phi4:14b (accurate)
    - gemma2:9b (good)
    - ministral:8b (efficient)
"""

import logging
import os
import json
import time

from backend.crawler.bookmark_extractor.ollama import OllamaBookmarkExtractor
from scratch.prod_setup import prod_setup

log_handle = logging.getLogger(__name__)


def main():
    # ========================================================================
    # CONFIGURE YOUR TEST HERE
    # ========================================================================

    # Path to the PDF file to test
    pdf_path = "/Users/r0j08wt/github/swalakshya/cataloguesearch-configs/Pravachans/hindi/Dravyanuyog/Parmatma Prakash/1976/ParmatmaPrakash_Pravachan_Part-1_H.pdf"

    # Ollama model to use
    model_name = "gpt-oss:20b"

    # ========================================================================
    # END CONFIGURATION
    # ========================================================================

    # Validate PDF exists
    if not os.path.exists(pdf_path):
        log_handle.error(f"PDF file not found: {pdf_path}")
        log_handle.error(f"Current working directory: {os.getcwd()}")
        return

    log_handle.info("=" * 80)
    log_handle.info(f"Testing Bookmark Extraction")
    log_handle.info("=" * 80)
    log_handle.info(f"PDF Path:  {pdf_path}")
    log_handle.info(f"PDF Name:  {os.path.basename(pdf_path)}")
    log_handle.info(f"Model:     {model_name}")
    log_handle.info("=" * 80)

    # Create extractor
    log_handle.info(f"Initializing OllamaBookmarkExtractor with model: {model_name}")
    extractor = OllamaBookmarkExtractor(model=model_name)

    # Extract bookmarks
    log_handle.info("Extracting and parsing bookmarks...")
    log_handle.info("-" * 80)

    start_time = time.time()
    try:
        results = extractor.parse_bookmarks(pdf_path)
        end_time = time.time()
        elapsed_time = end_time - start_time

        if not results:
            log_handle.warning("No bookmarks found or extraction failed")
            log_handle.info(f"Time taken: {elapsed_time:.2f} seconds")
            return

        log_handle.info(f"✓ Successfully extracted {len(results)} bookmarks")
        log_handle.info(f"Time taken: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")

        # Print results in a nice table format
        log_handle.info("Results:")
        log_handle.info("-" * 80)
        log_handle.info(f"{'Page':<6} {'Title':<50} {'Pravachan':<12} {'Date':<12}")
        log_handle.info("-" * 80)

        for bookmark in results:
            page = bookmark.get('page', 'N/A')
            title = bookmark.get('title', 'N/A')
            pravachan_no = bookmark.get('pravachan_no') or 'null'
            date = bookmark.get('date') or 'null'

            # Truncate title if too long
            if len(title) > 47:
                title = title[:44] + "..."

            log_handle.info(f"{page:<6} {title:<50} {pravachan_no:<12} {date:<12}")

        log_handle.info("-" * 80)

        # Print JSON output for detailed inspection
        log_handle.info("Full JSON Output:")
        log_handle.info("-" * 80)
        log_handle.info(json.dumps(results, indent=2, ensure_ascii=False))

        # Print statistics
        extracted_count = sum(1 for b in results if b.get('pravachan_no') or b.get('date'))
        log_handle.info("Statistics:")
        log_handle.info("-" * 80)
        log_handle.info(f"Total bookmarks:      {len(results)}")
        log_handle.info(f"Successfully parsed:  {extracted_count}")
        log_handle.info(f"Failed to parse:      {len(results) - extracted_count}")
        log_handle.info(f"Success rate:         {extracted_count/len(results)*100:.1f}%")

    except Exception as e:
        log_handle.error(f"Error during extraction: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    prod_setup()
    main()