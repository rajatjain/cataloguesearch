"""
Factory for creating paragraph generators based on configuration.
"""
import logging

from backend.config import Config
from backend.crawler.paragraph_generator.base import BaseParagraphGenerator
from backend.crawler.paragraph_generator.advanced import AdvancedParagraphGenerator
from backend.crawler.paragraph_generator.language_meta import LanguageMeta

log_handle = logging.getLogger(__name__)


def create_paragraph_generator(config: Config, language_meta: LanguageMeta):
    """
    Factory function to create the appropriate ParagraphGenerator based on CHUNK_STRATEGY.

    Args:
        config: Configuration object
        language_meta: LanguageMeta instance for language-specific behavior

    Returns:
        BaseParagraphGenerator or AdvancedParagraphGenerator instance based on CHUNK_STRATEGY
    """
    if config.CHUNK_STRATEGY == "advanced":
        log_handle.info("Creating AdvancedParagraphGenerator based on CHUNK_STRATEGY=advanced")
        return AdvancedParagraphGenerator(config, language_meta)
    else:
        log_handle.info(f"Creating BaseParagraphGenerator based on CHUNK_STRATEGY={config.CHUNK_STRATEGY}")
        return BaseParagraphGenerator(config, language_meta)