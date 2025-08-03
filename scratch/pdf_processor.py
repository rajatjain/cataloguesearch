# main.py
import datetime
import tempfile

import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from typing import List, Tuple
import os
import re

from backend.config import Config
from backend.crawler.discovery import Discovery, SingleFileProcessor
from backend.crawler.index_state import IndexState
from backend.crawler.pdf_processor import PDFProcessor
from scratch.prod_setup import prod_setup


def extract_paragraphs(
        pdf_file: str, start_page: int, end_page: int) -> List[Tuple[int, List[str]]]:
    """
    Extracts paragraphs from a specified range of pages in a PDF file.

    This function converts each page of the PDF into an image and then uses
    Optical Character Recognition (OCR) to extract text. It then splits the
    text into paragraphs.

    Args:
        pdf_file: The file path to the PDF document.
        start_page: The first page number to process (1-indexed).
        end_page: The last page number to process (inclusive).

    Returns:
        A list of tuples, where each tuple contains the page number
        and a list of paragraph strings extracted from that page.
        Example: [(1, ["Paragraph 1...", "Paragraph 2..."]), (2, [...])]

    Raises:
        FileNotFoundError: If the specified pdf_file does not exist.
        ValueError: If start_page or end_page are invalid.
    """
    if not os.path.exists(pdf_file):
        raise FileNotFoundError(f"Error: The file '{pdf_file}' was not found.")

    if start_page < 1 or end_page < start_page:
        raise ValueError("Error: Invalid page range provided.")

    print(f"Processing PDF '{os.path.basename(pdf_file)}' from page {start_page} to {end_page}...")

    # Convert the specified page range of the PDF to a list of PIL images
    # The first_page and last_page arguments are 1-based.
    try:
        images = convert_from_path(
            pdf_file,
            dpi=300,  # Use a higher DPI for better OCR accuracy
            first_page=start_page,
            last_page=end_page
        )
    except Exception as e:
        print(f"Error during PDF to image conversion: {e}")
        print("Please ensure Poppler is installed and in your system's PATH.")
        return []


    extracted_data = []

    # Enumerate through the images, starting from the specified start_page
    for i, image in enumerate(images, start=start_page):
        print(f"  - Processing page {i}...")
        try:
            # Use pytesseract to extract text from the image
            # We use a page segmentation mode (psm) that assumes a single uniform block of text.
            text = pytesseract.image_to_string(image, lang='hin', config='--psm 3')

            # A paragraph is often defined as a block of text separated by one or more
            # empty lines. We can split the text by double newlines.
            # We also filter out any empty strings that result from the split.
            raw_paragraphs = re.split(r'\n\s*\n', text)

            # Clean up paragraphs: strip leading/trailing whitespace and remove empty ones.
            paragraphs = [p.strip().replace('\n', ' ') for p in raw_paragraphs if p.strip()]

            extracted_data.append((i, paragraphs))
            print(f"    -> Found {len(paragraphs)} paragraphs.")

        except pytesseract.TesseractNotFoundError:
            print("Tesseract Error: The Tesseract executable was not found.")
            print("Please ensure Tesseract is installed and its path is configured correctly.")
            return []
        except Exception as e:
            print(f"An error occurred while processing page {i}: {e}")
            extracted_data.append((i, []))


    print("Extraction complete.")
    return extracted_data

def process_pdf():
    prod_setup(console_only=True)
    scan_config = {
        "default": {
            "header_regex": [
                "^.{0,5}गाथा.{0,30}$",
                "^.{0,5}कलश.{0,30}$",
                "^.{0,5}श्लोक.{0,30}$",
                "^प्रवचन\\s+नं\\.?.*$",
                "^प्रवच्चन\\s+नं\\.?.*$",
                "^[०-९\\s]*$",
            ]
        },
        "Karan_Karya_Niyam_Part_1_H": {
            "start_page": 19,
            "end_page": 617
        },
        "language": "hi"
    }

    pdf_file = "/Users/r0j08wt/cataloguesearch/pdf/Pravachans/hindi/Dravyanuyog/Niyamsaar/1979_Series/Karan_Karya_Niyam_Part_1_H.pdf"
    index_state = IndexState(tempfile.mktemp())
    processor = PDFProcessor(Config())
    single = SingleFileProcessor(
        Config(), pdf_file, None, index_state, processor, datetime.datetime.now().isoformat()
    )
    single.process()

# --- Example Usage ---
if __name__ == '__main__':
    process_pdf()
