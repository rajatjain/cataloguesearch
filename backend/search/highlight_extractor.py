import re
from typing import List, Dict, Any, Set
import logging

log_handle = logging.getLogger(__name__)

class HighlightExtractor:
    @staticmethod
    def extract_highlights(results: List[str], proximity_distance: int = None) -> List[str]:
        """
        Extracts highlighted words/phrases from a list of result strings.

        Args:
            results: List of result strings containing highlighted terms.
            proximity_distance: If 0 (exact phrase), keep phrases intact. Otherwise split into words.

        Returns:
            A list of unique highlighted words or phrases.
        """
        highlighted_items: Set[str] = set()
        highlight_regex = re.compile(r'<em>(.*?)</em>', re.IGNORECASE)

        for result in results:
            log_handle.info(f"Processing highlight result for proximity_distance={proximity_distance}: {result}")
            matches = highlight_regex.findall(result)
            log_handle.info(f"Found regex matches: {matches}")
            
            for match in matches:
                if proximity_distance == 0:  # exact phrase search
                    # Keep the entire phrase intact
                    cleaned_phrase = match.strip()
                    if cleaned_phrase:
                        highlighted_items.add(cleaned_phrase)
                else:
                    # Split into individual words for proximity/fuzzy searches
                    words = match.split()
                    for word in words:
                        cleaned_word = word.strip()
                        if cleaned_word:
                            highlighted_items.add(cleaned_word)

        log_handle.info(f"Extracted unique highlight items: {list(highlighted_items)}")
        return list(highlighted_items)
