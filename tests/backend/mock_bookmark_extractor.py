"""
Mock Bookmark Extractor for tests.

This module provides a fast, in-memory bookmark extractor that returns
pre-defined parsed bookmarks without calling any LLM. This significantly
speeds up tests by avoiding slow LLM calls.

The bookmarks are based on the test data defined in tests/backend/common.py.
"""

import logging
from typing import List, Dict, Any, Optional

from backend.crawler.bookmark_extractor.base import BookmarkExtractor

log_handle = logging.getLogger(__name__)


class MockBookmarkExtractor(BookmarkExtractor):
    """
    Mock bookmark extractor that returns pre-defined parsed bookmarks.

    This avoids the slow LLM calls during testing and uses pre-defined
    bookmark strings and their expected extractions based on the test data
    in tests/backend/common.py.
    """

    # Pre-defined bookmark mappings based on tests/backend/common.py
    # Maps bookmark strings to their expected parsed results
    BOOKMARK_MAPPINGS = {
        # hampi_hindi bookmarks
        "prav number 248, 1985-10-23": {
            "pravachan_no": "248",
            "date": "23-10-1985"
        },
        "Prav 324. Date 24-05-1986": {
            "pravachan_no": "324",
            "date": "24-05-1986"
        },

        # jaipur_hindi bookmarks
        "Pravachan Num 10 on Date 03-05-1986": {
            "pravachan_no": "10",
            "date": "03-05-1986"
        },
        "Pravachan Num 12 on Date 04-06-1987": {
            "pravachan_no": "12",
            "date": "04-06-1987"
        },

        # indore_gujarati bookmarks
        "pr number 28, 1982-10-23": {
            "pravachan_no": "28",
            "date": "23-10-1982"
        },
        "Prav 324. Date 24-05-1982": {
            "pravachan_no": "324",
            "date": "24-05-1982"
        },

        # thanjavur_gujarati bookmarks
        "Pravachan Num 15 on Date 06-05-1980": {
            "pravachan_no": "15",
            "date": "06-05-1980"
        },
        "Pravachan Num 18 on Date 04-06-1983": {
            "pravachan_no": "18",
            "date": "04-06-1983"
        }
    }

    def call_llm(self, indexed_titles: List[Dict[str, Any]]) -> Optional[List[Dict[str, str]]]:
        """
        Mock LLM call that returns pre-defined parsed bookmark data.

        Instead of calling an actual LLM, this looks up the bookmark title
        in the BOOKMARK_MAPPINGS dictionary and returns the pre-defined result.

        Args:
            indexed_titles: List of dictionaries with 'index' and 'title' keys

        Returns:
            List of dictionaries with 'index', 'pravachan_no', and 'date' keys
        """
        log_handle.info(f"MockBookmarkExtractor: Processing {len(indexed_titles)} bookmarks")

        results = []
        for item in indexed_titles:
            index = item.get('index')
            title = item.get('title', '').strip()

            # Look up the bookmark in our pre-defined mappings
            if title in self.BOOKMARK_MAPPINGS:
                mapping = self.BOOKMARK_MAPPINGS[title]
                results.append({
                    "index": index,
                    "pravachan_no": mapping.get("pravachan_no"),
                    "date": mapping.get("date")
                })
                log_handle.debug(f"Matched bookmark '{title}' -> pravachan_no={mapping.get('pravachan_no')}, date={mapping.get('date')}")
            else:
                # If not found in mappings, return null values
                results.append({
                    "index": index,
                    "pravachan_no": None,
                    "date": None
                })
                log_handle.debug(f"No mapping found for bookmark '{title}', returning null values")

        log_handle.info(f"MockBookmarkExtractor: Processed {len(results)} bookmarks successfully")
        return results