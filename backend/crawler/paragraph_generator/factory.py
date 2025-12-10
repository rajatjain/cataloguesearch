"""
Factory for creating paragraph generators based on configuration.
"""
import logging

from backend.config import Config
from backend.crawler.paragraph_generator.base import BaseParagraphGenerator
from backend.crawler.paragraph_generator.advanced import AdvancedParagraphGenerator
from backend.crawler.paragraph_generator.language_meta import LanguageMeta

log_handle = logging.getLogger(__name__)


def create_paragraph_generator(config: Config, language_meta: LanguageMeta, chunk_strategy: str = None):
    """
    Factory function to create the appropriate ParagraphGenerator based on CHUNK_STRATEGY.

    Args:
        config: Configuration object
        language_meta: LanguageMeta instance for language-specific behavior
        chunk_strategy: Optional chunk strategy override. If not provided, uses config.CHUNK_STRATEGY

    Returns:
        BaseParagraphGenerator or AdvancedParagraphGenerator instance based on CHUNK_STRATEGY
    """
    # Use provided chunk_strategy if available, otherwise fall back to config
    strategy = chunk_strategy if chunk_strategy is not None else config.CHUNK_STRATEGY

    if strategy == "advanced":
        log_handle.info(f"Creating AdvancedParagraphGenerator based on chunk_strategy={strategy}")
        return AdvancedParagraphGenerator(config, language_meta)
    else:
        log_handle.info(f"Creating BaseParagraphGenerator based on chunk_strategy={strategy}")
        return BaseParagraphGenerator(config, language_meta)