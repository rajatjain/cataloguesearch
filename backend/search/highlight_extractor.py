import re
from typing import List, Dict, Any, Set
import logging

log_handle = logging.getLogger(__name__)

class HighlightExtractor:
    @staticmethod
    def extract_highlights(results: List[str]) -> List[str]:
        """
        Extracts highlighted words from a list of result strings.

        Args:
            results: List of result strings containing highlighted terms.

        Returns:
            A list of unique highlighted words.
        """
        highlighted_words: Set[str] = set()
        highlight_regex = re.compile(r'<em>(.*?)</em>', re.IGNORECASE)

        for result in results:
            matches = highlight_regex.findall(result)
            for match in matches:
                words = match.split()
                for word in words:
                    cleaned_word = word.strip()
                    if cleaned_word:
                        highlighted_words.add(cleaned_word)

        log_handle.info(f"Extracted unique highlight words: {list(highlighted_words)}")
        return list(highlighted_words)
