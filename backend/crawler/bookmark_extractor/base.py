import logging
import fitz
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

log_handle = logging.getLogger(__name__)


class BookmarkExtractor(ABC):
    """
    Base class for extracting and parsing PDF bookmarks using LLMs.

    This class handles PDF bookmark extraction and delegates LLM-specific
    processing to subclasses.
    """

    def __init__(self):
        self.system_prompt = """
You are a data extraction assistant. Extract the Pravachan Number and Date from bookmark titles.

Return a JSON array where each object has:
- index: the position number from the input
- pravachan_no: the extracted pravachan number, or null if not found
- date: the extracted date in DD-MM-YYYY format, or null if not found

EXAMPLES:
Input: {"index": 4, "title": "Prav. no. 244-A on Kalash 219, Date: 07-11-1965"}
Output: {"index": 4, "pravachan_no": "244-A", "date": "07-11-1965"}

Input: {"index": 5, "title": "Pravachan No.112, Date : 19-10-1978"}
Output: {"index": 5, "pravachan_no": "112", "date": "19-10-1978"}

Input: {"index": 6, "title": "Prav 45, 26th Sep 1978"}
Output: {"index": 6, "pravachan_no": "45", "date": "26-09-1978"}

Input: {"index": 9, "title": "Gatha 65 & 66"}
Output: {"index": 9, "pravachan_no": null, "date": null}

Note: Convert dates from various formats (like "26th Sep 1978") to DD-MM-YYYY format.

Return ONLY the JSON array, nothing else.
"""

    def parse_bookmarks(self, pdf_file: str, batch_size: int = 100) -> List[Dict[str, str]]:
        """
        Main function to extract bookmarks from PDF and parse them using LLM.

        Args:
            pdf_file: Path to the PDF file
            batch_size: Number of bookmarks to process per LLM call (default: 100)

        Returns:
            List of dictionaries with parsed bookmark data including:
            - page: Page number
            - level: Bookmark hierarchy level
            - title: Original bookmark title
            - pravachan_no: Extracted pravachan number
            - date: Extracted date
        """
        log_handle.info("Starting bookmark extraction for PDF: %s", pdf_file)

        # Step 1: Extract bookmarks from PDF
        bookmark_json = self._extract_bookmarks_from_pdf(pdf_file)

        if not bookmark_json.get('bookmarks'):
            log_handle.warning("No bookmarks found in PDF: %s", pdf_file)
            return []

        log_handle.info("Found %s bookmarks in PDF", bookmark_json['total'])

        # Step 2: Prepare indexed titles for LLM
        bookmarks = bookmark_json['bookmarks']
        indexed_titles = [
            {"index": i, "title": item.get('title', '')}
            for i, item in enumerate(bookmarks)
        ]

        # Step 3: Process in batches to avoid timeouts
        all_extracted_data = []
        total_batches = (len(indexed_titles) + batch_size - 1) // batch_size

        log_handle.info("Processing %s bookmarks in %s batches of %s", len(indexed_titles), total_batches, batch_size)

        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min((batch_num + 1) * batch_size, len(indexed_titles))
            batch = indexed_titles[start_idx:end_idx]

            log_handle.info("Processing batch %s/%s (%s bookmarks)", batch_num + 1, total_batches, len(batch))

            # Call LLM for this batch
            extracted_data = self.call_llm(batch)

            if not extracted_data:
                log_handle.error("Failed to extract data from LLM for batch %s/%s", batch_num + 1, total_batches)
                return []

            all_extracted_data.extend(extracted_data)
            log_handle.info("Successfully processed batch %s/%s", batch_num + 1, total_batches)

        log_handle.info("Successfully extracted data from all %s batches", total_batches)

        # Step 4: Merge extracted data back with original page numbers
        result = self._merge_results(bookmarks, all_extracted_data)
        log_handle.info("Bookmark extraction completed. Processed %s bookmarks", len(result))
        return result

    def _extract_bookmarks_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract bookmarks from a PDF file and return as JSON.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Dictionary with 'bookmarks' list and 'total' count
        """
        doc = fitz.open(pdf_path)
        toc = doc.get_toc(simple=True)  # Format: [level, title, page_number]
        doc.close()

        bookmarks = [
            {"level": level, "title": title, "page": page}
            for level, title, page in toc
        ]

        return {
            "bookmarks": bookmarks,
            "total": len(bookmarks)
        }

    def _merge_results(
        self,
        bookmarks: List[Dict[str, Any]],
        extracted_data: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Merge extracted LLM data with original bookmark information.

        Args:
            bookmarks: Original bookmark data from PDF
            extracted_data: Data extracted by LLM

        Returns:
            List of merged bookmark data
        """
        final_output = []

        # Create a dictionary for quick lookup of extracted data using the index
        extracted_map = {item.get('index'): item for item in extracted_data}

        for i, original_item in enumerate(bookmarks):
            extracted_item = extracted_map.get(i)

            if extracted_item:
                final_output.append({
                    "page": original_item['page'],
                    "level": original_item['level'],
                    "title": original_item['title'],
                    "pravachan_no": extracted_item.get('pravachan_no'),
                    "date": extracted_item.get('date'),
                })

        return final_output

    @abstractmethod
    def call_llm(self, indexed_titles: List[Dict[str, Any]]) -> Optional[List[Dict[str, str]]]:
        """
        Call LLM to extract pravachan number and date from bookmark titles.

        This method must be implemented by subclasses.

        Args:
            indexed_titles: List of dictionaries with 'index' and 'title' keys

        Returns:
            List of dictionaries with 'index', 'pravachan_no', and 'date' keys
            Returns None if extraction fails
        """
        pass