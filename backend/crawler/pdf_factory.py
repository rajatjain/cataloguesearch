"""
Factory for creating PDF processors based on configuration.
"""
import logging

from backend.config import Config
from backend.crawler.pdf_processor import PDFProcessor
from backend.crawler.advanced_pdf_processor import AdvancedPDFProcessor

log_handle = logging.getLogger(__name__)


def create_pdf_processor(config: Config):
    """
    Factory function to create the appropriate PDFProcessor based on CHUNK_STRATEGY.

    Args:
        config: Configuration object

    Returns:
        PDFProcessor or AdvancedPDFProcessor instance based on CHUNK_STRATEGY
    """
    if config.CHUNK_STRATEGY == "advanced":
        log_handle.info("Creating AdvancedPDFProcessor based on CHUNK_STRATEGY=advanced")
        return AdvancedPDFProcessor(config)
    else:
        log_handle.info(f"Creating PDFProcessor based on CHUNK_STRATEGY={config.CHUNK_STRATEGY}")
        return PDFProcessor(config)