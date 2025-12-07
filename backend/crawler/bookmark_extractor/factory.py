"""
Factory for creating bookmark extractors based on configuration.
"""
import logging
import os

from backend.config import Config
from backend.crawler.bookmark_extractor.base import BookmarkExtractor
from backend.crawler.bookmark_extractor.gemini import GeminiBookmarkExtractor
from backend.crawler.bookmark_extractor.groq import GroqBookmarkExtractor

log_handle = logging.getLogger(__name__)


def create_bookmark_extractor_by_name(llm_type: str) -> BookmarkExtractor:
    """
    Factory function to create a BookmarkExtractor by LLM provider name.

    Args:
        llm_type: LLM provider name ("groq" or "gemini")

    Returns:
        BookmarkExtractor instance (GeminiBookmarkExtractor or GroqBookmarkExtractor)

    Raises:
        ValueError: If the LLM type is not supported or API key is missing
    """
    llm_type_lower = llm_type.lower()

    if llm_type_lower == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")
        log_handle.info("Creating GroqBookmarkExtractor for llm_type=groq")
        return GroqBookmarkExtractor(api_key=api_key)

    elif llm_type_lower == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        log_handle.info("Creating GeminiBookmarkExtractor for llm_type=gemini")
        return GeminiBookmarkExtractor(api_key=api_key)

    else:
        raise ValueError(
            f"Unsupported bookmark extractor LLM: {llm_type}. "
            f"Supported values: 'groq', 'gemini'"
        )


def create_bookmark_extractor(config: Config) -> BookmarkExtractor:
    """
    Factory function to create the appropriate BookmarkExtractor based on BOOKMARK_EXTRACTOR_LLM config.

    Args:
        config: Configuration object

    Returns:
        BookmarkExtractor instance (GeminiBookmarkExtractor or GroqBookmarkExtractor)
        based on BOOKMARK_EXTRACTOR_LLM config

    Raises:
        ValueError: If the configured LLM is not supported or API key is missing
    """
    llm_type = config.BOOKMARK_EXTRACTOR_LLM
    log_handle.info(f"Creating bookmark extractor from config: {llm_type}")
    return create_bookmark_extractor_by_name(llm_type)