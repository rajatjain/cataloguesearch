import re
from typing import List, Dict, Any
import logging
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
            search_results (List[Dict[str, Any]]): A list of search result dictionaries,
                                                    expected to contain 'content_snippet'.

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

        # Add words from content snippets (especially those highlighted by OpenSearch)
        """
        for result in search_results:
            snippet = result.get('content_snippet')
            if snippet:
                snippet_tokens = indic_tokenize.trivial_tokenize(snippet)
                log_handle.verbose(f"Snippet tokens: {snippet_tokens}")
                for word in snippet_tokens:
                    highlight_words.add(word)
        log_handle.verbose(f"Added snippet words to highlights. Total unique words: {len(highlight_words)}")
        """
        return sorted(list(highlight_words))