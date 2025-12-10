"""
Factory for creating PDF processors based on configuration.
"""
import logging

from backend.config import Config
from backend.crawler.pdf_processor import PDFProcessor
from backend.crawler.advanced_pdf_processor import AdvancedPDFProcessor

log_handle = logging.getLogger(__name__)


def create_pdf_processor(config: Config, chunk_strategy: str = None):
    """
    Factory function to create the appropriate PDFProcessor based on CHUNK_STRATEGY.

    Args:
        config: Configuration object
        chunk_strategy: Optional chunk strategy override. If not provided, uses config.CHUNK_STRATEGY

    Returns:
        PDFProcessor or AdvancedPDFProcessor instance based on chunk_strategy
    """
    # Use provided chunk_strategy if available, otherwise fall back to config
    strategy = chunk_strategy if chunk_strategy is not None else config.CHUNK_STRATEGY

    if strategy == "advanced":
        log_handle.info(f"Creating AdvancedPDFProcessor based on chunk_strategy={strategy}")
        return AdvancedPDFProcessor(config)
    else:
        log_handle.info(f"Creating PDFProcessor based on chunk_strategy={strategy}")
        return PDFProcessor(config)