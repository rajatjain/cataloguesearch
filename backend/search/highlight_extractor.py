import logging
from typing import List, Any, Dict

from indicnlp.tokenize import indic_tokenize

log_handle = logging.getLogger(__name__)

class HighlightExtractor:
    """
    A utility class to extract and clean words for UI highlighting.
    """

    @staticmethod
    def extract_highlights(query_keywords: str, search_results: List[Dict[str, Any]]) -> List[str]:
        """
        Extracts important words from the original query and content snippets
        of the search results for UI highlighting.

        Args:
            query_keywords (str): The original search query string.
            search_results (List[Dict[str, Any]]): A list of search result dictionaries.

        Returns:
            List[str]: A deduplicated list of words to highlight.
        """
        highlight_words = set()

        # Add words from the original query
        # Use Unicode-aware pattern for multi-language support (Hindi, Gujarati, etc.)
        query_tokens = indic_tokenize.trivial_tokenize(query_keywords)
        log_handle.verbose(f"Original query tokens: {query_tokens}")
        for word in query_tokens:
            highlight_words.add(word)
        log_handle.verbose(f"Added query keywords to highlights: {list(highlight_words)}")

        # The snippet extraction code is already commented out
        return sorted(list(highlight_words))

    @staticmethod
    def extract_phrase_highlights(query_keywords: str) -> List[str]:
        """
        Extract highlights for exact phrase search.
        
        Args:
            query_keywords (str): The exact phrase to highlight.
            
        Returns:
            List[str]: A list containing the full phrase as a single highlight unit.
        """
        return [query_keywords.strip()]