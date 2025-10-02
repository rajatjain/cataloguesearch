#!/usr/bin/env python3
"""
CLI script to index a Granth markdown file into OpenSearch.

This script:
1. Parses a markdown file into a Granth object
2. Indexes it into OpenSearch (both granth_index and search_index)

Usage:
    python scripts/index_granth.py <file_path> [--dry-run]

Arguments:
    file_path: Path to the markdown file to index (relative to BASE_PDF_PATH or absolute)
    --dry-run: If specified, performs a dry run without actually indexing

Examples:
    # Index a granth file (actual indexing)
    python scripts/index_granth.py tests/data/md/hindi/simple_granth.md

    # Dry run to see what would be indexed
    python scripts/index_granth.py tests/data/md/hindi/simple_granth.md --dry-run

    # Index using absolute path
    python scripts/index_granth.py /path/to/granth.md
"""
import argparse
import logging
import os
import sys

from backend.common.opensearch import get_opensearch_client, create_indices_if_not_exists
from backend.config import Config
from backend.crawler.granth_index import GranthIndexer
from backend.crawler.markdown_parser import MarkdownParser
from utils.logger import setup_logging, VERBOSE_LEVEL_NUM

log_handle = logging.getLogger(__name__)


def get_base_directory(config: Config) -> str:
    """
    Get the base directory for markdown files from Config.BASE_PDF_PATH.

    This is used for finding config.json files for metadata merging.

    Args:
        config: Config object

    Returns:
        Base directory path
    """
    base_dir = config.BASE_PDF_PATH

    if not base_dir or not os.path.exists(base_dir):
        log_handle.error(f"BASE_PDF_PATH not found or doesn't exist: {base_dir}")
        log_handle.error("Please configure 'crawler.base_pdf_path' in configs/config.yaml")
        sys.exit(1)

    log_handle.info(f"Using base directory: {base_dir}")
    return base_dir

def index_granth(file_path: str, dry_run: bool = False):
    """
    Parse and index a Granth markdown file.

    Args:
        file_path: Path to the markdown file
        dry_run: If True, performs a dry run without actually indexing
    """
    # Setup configuration
    config = Config("configs/config.yaml")

    # Get base directory for config.json merging (from BASE_PDF_PATH)
    base_dir = get_base_directory(config)

    # Verify file is a markdown file
    if not file_path.endswith('.md'):
        log_handle.error(f"File must be a markdown file (.md): {file_path}")
        sys.exit(1)

    # Initialize parser with base_folder for config merging
    parser = MarkdownParser(base_folder=base_dir)

    # Parse the markdown file using the resolved path
    log_handle.info(f"Parsing markdown file: {file_path}")
    try:
        granth = parser.parse_file(file_path)
        log_handle.info(f"Successfully parsed Granth: {granth._name}")
        log_handle.info(f"  - Verses: {len(granth._verses)}")
        log_handle.info(f"  - Language: {granth._metadata._language}")
        log_handle.info(f"  - Author: {granth._metadata._author}")
        log_handle.info(f"  - Teekakar: {granth._metadata._teekakar}")
        log_handle.info(f"  - Anuyog: {granth._metadata._anuyog}")
    except Exception as e:
        log_handle.error(f"Failed to parse markdown file: {e}", exc_info=True)
        sys.exit(1)

    if dry_run:
        log_handle.info("DRY RUN MODE - No actual indexing will be performed")
        return

    # Get OpenSearch client and ensure indices exist
    opensearch_client = get_opensearch_client(config)

    log_handle.info("Ensuring OpenSearch indices exist...")
    create_indices_if_not_exists(config, opensearch_client)

    # Initialize indexer
    indexer = GranthIndexer(config, opensearch_client)

    # Index the granth
    log_handle.info(f"{'[DRY RUN] ' if dry_run else ''}Indexing Granth into OpenSearch...")
    try:
        indexer.index_granth(granth, dry_run=dry_run)

        log_handle.info("=" * 80)
        log_handle.info("DRY RUN COMPLETE - No data was indexed")
        log_handle.info("To actually index, run without --dry-run flag")
        log_handle.info("=" * 80)
    except Exception as e:
        log_handle.error(f"Failed to index Granth: {e}", exc_info=True)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Index a Granth markdown file into OpenSearch',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        'file_path',
        help='Path to the markdown file to index (relative to BASE_PDF_PATH or absolute)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Perform a dry run without actually indexing'
    )

    parser.add_argument(
        '--no-dry-run',
        action='store_true',
        help='Explicitly disable dry run and perform actual indexing'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Setup logging
    console_level = VERBOSE_LEVEL_NUM if args.verbose else logging.INFO
    setup_logging(console_level=console_level, file_level=VERBOSE_LEVEL_NUM, console_only=True)

    # Determine dry_run value: --no-dry-run takes precedence
    dry_run = args.dry_run and not args.no_dry_run

    # Run indexing
    index_granth(args.file_path, dry_run=dry_run)


if __name__ == '__main__':
    main()