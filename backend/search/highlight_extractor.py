import re
from typing import List, Dict, Any
import logging

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
        # Simple split, consider more advanced tokenization for multi-language if needed
        for word in re.findall(r'\b\w+\b', query_keywords.lower()):
            highlight_words.add(word)
        log_handle.verbose(f"Added query keywords to highlights: {list(highlight_words)}")

        # Add words from content snippets (especially those highlighted by OpenSearch)
        for result in search_results:
            snippet = result.get('content_snippet')
            if snippet:
                # Remove HTML tags (like <em>) and then extract words
                clean_snippet = re.sub(r'<[^>]+>', '', snippet)
                for word in re.findall(r'\b\w+\b', clean_snippet.lower()):
                    highlight_words.add(word)
        log_handle.verbose(f"Added snippet words to highlights. Total unique words: {len(highlight_words)}")

        return sorted(list(highlight_words))