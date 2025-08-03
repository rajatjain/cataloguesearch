import re
import shutil
import traceback
from concurrent.futures import ProcessPoolExecutor

import fitz
import pytesseract
import os
import logging

from PIL import Image
from pdf2image import convert_from_path
from tqdm import tqdm

from backend.crawler.paragraph_generator.hindi import HindiParagraphGenerator
from backend.utils import json_dumps

# Disable tokenizers parallelism to avoid fork conflicts
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from backend.config import Config

# Setup logging for this module
log_handle = logging.getLogger(__name__)


class PDFProcessor:
    """
    Handles PDF processing, including OCR, text extraction, and bookmark extraction.
    """

    def __init__(self, config: Config):
        """
        Initializes the PDFProcessor.
        """
        if shutil.which("pdftoppm") is None:
            raise RuntimeError(
                "Poppler is not installed or not in PATH. Please configure it for this module to work."
            )
        self._output_text_folder = config.BASE_TEXT_PATH
        self._pytesseract_language_map = {
            "hi": "hin",
            "gu": "guj"
        }
        self._config = config
        self._paragraph_gen = HindiParagraphGenerator(self._config)

    def _write_paragraphs(self, output_dir, paragraphs):
        page_paras = dict()
        for page_num, para in paragraphs:
            if page_num not in page_paras:
                page_paras[page_num] = []
            page_paras[page_num].append(para)

        page_nums = sorted(page_paras.keys())
        for page_num in page_nums:
            para_list = page_paras[page_num]
            fname = f"{output_dir}/page_{page_num:04d}.txt"
            content = "\n----\n".join(para_list)
            try:
                with open(fname, 'w', encoding='utf-8') as fh:
                    fh.write(content)
            except IOError as e:
                traceback.print_exc()
                log_handle.error(f"Failed to write {fname}")

    def _generate_paragraphs(self, pdf_file: str, page_list: list[int], language: str) -> list[tuple[int, list[str]]]:
        """
        Extracts paragraphs from a specified list of pages in a PDF file.

        This function converts each page of the PDF into an image and then uses
        OCR to extract text.

        Args:
            pdf_file: The file path to the PDF document.
            page_list: A list of 1-based page numbers to process.
            language: The language code for OCR (e.g., 'hi', 'gu').

        Returns:
            A list of tuples, where each tuple contains the page number
            and a list of paragraph strings extracted from that page.
            Example: [(1, ["Para 1...", "Para 2..."]), (5, [...])]
        """
        if not os.path.exists(pdf_file):
            raise FileNotFoundError(f"Error: File {pdf_file} not found.")

        if not page_list:
            return []

        images = []
        # Keep track of the page numbers for the images we successfully create
        page_numbers_for_images = []
        try:
            doc = fitz.open(pdf_file)
            total_pages = len(doc)

            for page_num in page_list:
                # Validate page number (1-based) against total pages
                if not (1 <= page_num <= total_pages):
                    log_handle.warning(
                        f"Page number {page_num} is out of bounds for PDF {pdf_file} "
                        f"which has {total_pages} pages. Skipping."
                    )
                    continue

                # PyMuPDF uses 0-based indexing for pages, so we subtract 1
                page = doc.load_page(page_num - 1)

                pix = page.get_pixmap(dpi=350)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)
                page_numbers_for_images.append(page_num)

            doc.close()

        except Exception as e:
            log_handle.error(f"Error during PDF to image conversion with PyMuPDF: {e}")
            traceback.print_exc()
            return []

        pyt_lang = self._pytesseract_language_map.get(language)
        log_handle.info(f"Scanning total pages: {len(page_list)}")

        # This is the corrected version of the original line.
        # It correctly pairs each image with its actual page number using zip().
        tasks = [(page_num, image, pyt_lang) for page_num, image in zip(page_numbers_for_images, images)]

        if not tasks:
            return []

        extracted_data = []
        with ProcessPoolExecutor() as executor:
            results = list(tqdm(executor.map(
                PDFProcessor._process_single_page, tasks), total=len(tasks), desc="Processing Pages"))
            extracted_data = results

        # Sort results by page number to guarantee order
        extracted_data.sort(key=lambda x: x[0])

        return extracted_data

    def fetch_bookmarks(self, pdf_file: str) -> dict[int, str]:
        doc = fitz.open(pdf_file)
        toc = doc.get_toc(simple=True)  # Format: [level, title, page_number]

        # Step 1: Build full hierarchical titles with pages
        bookmarks = []
        stack = []

        for level, title, page in toc:
            while len(stack) >= level:
                stack.pop()
            stack.append(title)
            full_title = " / ".join(stack)
            bookmarks.append((page, full_title))

        # Step 2: Map every page to the last applicable bookmark
        page_to_bookmark = {}
        current_title = None
        bookmark_index = 0
        total_pages = doc.page_count

        for page_num in range(1, total_pages + 1):
            # Advance bookmark if next one starts on this page
            while bookmark_index < len(bookmarks) and bookmarks[bookmark_index][0] <= page_num:
                current_title = bookmarks[bookmark_index][1].strip()
                bookmark_index += 1
            page_to_bookmark[page_num] = current_title

        return page_to_bookmark

    def process_pdf(
            self, pdf_path: str, output_dir: str,
            scan_config: dict):
        """
        Processes a PDF file, extracts text page by page, saves them,
        and extracts bookmarks.

        Args:
            pdf_path (str): The full path to the PDF file.
            output_dir (str): The base directory where page-wise text files will be saved.
                              It is assumed that this directory exists.
            images_dir (str): Directory where images will be temporarily stored.
            scan_config (dict): Metadata associated with the PDF file.
        """
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        log_handle.verbose(f"pdf_name: {pdf_name} output_dir: {output_dir}")
        if not os.path.exists(output_dir):
            log_handle.critical(f"output_dir {output_dir} does not exist. Exiting.")
            return None

        doc = fitz.open(pdf_path)
        num_pages = doc.page_count
        pages_list = self._get_page_list(scan_config)
        language = scan_config.get("language", "hi")

        # Process only if some pages do not exist
        to_process = False
        if os.path.exists(output_dir):
            for i in pages_list:
                fpath = f"{output_dir}/page_{i:04d}.txt"
                if not os.path.exists(fpath):
                    to_process = True
                    break

        if not to_process:
            log_handle.info(
                f"Skipping process for {pdf_path} as it already exists and has all the requisite files.")
            return None

        paragraphs = self._generate_paragraphs(
            pdf_path, pages_list, language)

        paragraphs = self._paragraph_gen.generate_paragraphs(
            paragraphs, scan_config
        )
        self._write_paragraphs(output_dir, paragraphs)
        return None

    @staticmethod
    def _process_single_page(args):
        """
        Worker function to process a single image with preprocessing for better OCR.
        This function must be at the top level of the module for pickling.
        """
        page_num, image, language_code = args
        try:
            # 1. --- Image Preprocessing ---
            # Convert the image to grayscale for better processing.
            processed_image = image.convert('L')

            # Apply a binary threshold to create a clean, high-contrast
            # black and white image. This is often the most critical step.
            # The '180' is a threshold value; you may need to tune it (127 is a common default).
            processed_image = processed_image.point(lambda x: 0 if x < 180 else 255, '1')

            # 2. --- Perform OCR ---
            # Use the preprocessed image and your existing configuration.
            config = f'--psm 3 -l {language_code}'
            text = pytesseract.image_to_string(processed_image, config=config)

            # 3. --- Clean Up Text ---
            # Split text into paragraphs and clean them up.
            raw_paragraphs = re.split(r'\n\s*\n', text)
            paragraphs = [p.strip().replace('\n', ' ') for p in raw_paragraphs if p.strip()]

            return page_num, paragraphs

        except Exception as e:
            # Log the error and return an empty result for this page.
            print(f"An error occurred while processing page {page_num}: {e}")
            traceback.print_exc()
            return page_num, []

    def _get_page_list(self, scan_config):
        all_pages = set()

        # Add pages from the list of ranges
        pages_list = scan_config.get("page_list", [])
        for i, page in enumerate(pages_list):
            start = page.get("start")
            end = page.get("end")

            # Add pages if both start and end exist
            if start is not None and end is not None:
                all_pages.update(range(start, end + 1))

        # Add pages from the top-level range
        start_page = scan_config.get("start_page")
        end_page = scan_config.get("end_page")

        if start_page is not None and end_page is not None:
            all_pages.update(range(start_page, end_page + 1))

        # 3. Return the final sorted list of unique pages
        return sorted(list(all_pages))
