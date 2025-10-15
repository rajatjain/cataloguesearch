import logging
import os
import shutil
import traceback
import uuid
from concurrent.futures import ProcessPoolExecutor

import fitz
import pytesseract
from PIL import Image
from tqdm import tqdm

from backend.config import Config

# Disable tokenizers parallelism to avoid fork conflicts
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Setup logging for this module
log_handle = logging.getLogger(__name__)


class PDFProcessor:
    """
    Handles PDF processing, including OCR, text extraction, bookmark extraction.
    """
    def __init__(self, config: Config):
        if shutil.which("pdftoppm") is None:
            raise RuntimeError(
                "Poppler is not installed or not in PATH. "
                "Please configure it for this module to work."
            )
        self._pytesseract_language_map = {
            "hi": "hin",
            "gu": "guj"
        }
        self._config = config
        self._base_ocr_folder = config.BASE_OCR_PATH
        self._base_pdf_folder = config.BASE_PDF_PATH

    def process_pdf(
            self, pdf_file: str, scan_config: dict,
            pages_list: list[int]):
        if not os.path.exists(pdf_file):
            raise FileNotFoundError(f"Error: File {pdf_file} not found.")

        log_handle.info(f"base_pdf_folder: {self._base_pdf_folder}")
        log_handle.info(f"pdf_file: {pdf_file}")
        relative_pdf_path = os.path.relpath(pdf_file, self._base_pdf_folder)
        output_ocr_dir = f"{self._base_ocr_folder}/{os.path.splitext(relative_pdf_path)[0]}"
        log_handle.info(f"Output OCR directory: {output_ocr_dir}")

        # Check if output directory exists and has all required pages
        if os.path.exists(output_ocr_dir):
            existing_files = set()
            for filename in os.listdir(output_ocr_dir):
                if filename.startswith("page_") and filename.endswith(".txt"):
                    # Extract page number from filename (page_0001.txt -> 1)
                    try:
                        page_num = int(filename[5:9])  # Extract 4-digit number
                        existing_files.add(page_num)
                    except ValueError:
                        continue
            
            # If all required pages exist, return early
            if set(pages_list).issubset(existing_files):
                log_handle.info(f"All required pages already processed in {output_ocr_dir}")
                return True
            
            # Otherwise, remove existing directory to reprocess
            shutil.rmtree(output_ocr_dir)

        os.makedirs(output_ocr_dir, exist_ok=True)
        language = scan_config.get("language", "hi")
        paragraphs = self._generate_paragraphs(
            pdf_file, pages_list, scan_config, language)

        # Write to the OCR directory
        self._write_output_to_file(output_ocr_dir, paragraphs)

        log_handle.info(f"Generated OCR text files for {pdf_file} in dir {output_ocr_dir}")
        return True

    def _write_output_to_file(self, output_ocr_dir: str, paragraphs: list[tuple[int, list[str]]]):
        """
        Writes the extracted paragraphs to files in the output directory.

        Args:
            output_ocr_dir: Directory where output files should be written
            paragraphs: List of tuples (page_num, list of paragraph strings)
        """
        for page_num, page_paragraphs in paragraphs:
            fname = f"{output_ocr_dir}/page_{page_num:04d}.txt"
            content = "\n----\n".join(page_paragraphs)
            try:
                with open(fname, 'w', encoding='utf-8') as fh:
                    fh.write(content)
            except IOError as e:
                traceback.print_exc()
                log_handle.error(f"Failed to write OCR file {fname}: {e}")


    def _generate_paragraphs(
            self, pdf_file: str, page_list: list[int], scan_config: dict,
            language: str) -> list[tuple[int, list[str]]]:
        """
        Extracts paragraphs from a specified list of pages in a PDF file.

        This function converts each page of the PDF into an image and then
        uses OCR to extract text.

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

        images, page_numbers_for_images = self._get_image(
            pdf_file, page_list, scan_config
        )

        pyt_lang = self._pytesseract_language_map.get(language)
        log_handle.info(f"Scanning total pages: {len(page_list)}")

        # Extract PSM from scan_config if present
        psm = scan_config.get("psm")

        # Build tasks tuple - include PSM only if specified
        if psm is not None:
            tasks = [(page_num, image, pyt_lang, psm)
                     for page_num, image in zip(page_numbers_for_images, images)]
        else:
            tasks = [(page_num, image, pyt_lang)
                     for page_num, image in zip(page_numbers_for_images, images)]

        if not tasks:
            return []

        extracted_data = []
        with ProcessPoolExecutor(max_workers=8) as executor:
            results = list(tqdm(
                executor.map(self.__class__._process_single_page, tasks),
                total=len(tasks), desc="Processing Pages"))
            extracted_data = results

        # Sort results by page number to guarantee order
        extracted_data.sort(key=lambda x: x[0])

        return extracted_data

    def _get_image(self, pdf_file, page_list, scan_config):
        images = []
        page_numbers_for_images = []
        # Check for cropping configuration once at the beginning
        crop_config = None
        if "crop" in scan_config:
            crop_config = scan_config["crop"]
            top_percent = crop_config.get("top", 0)
            bottom_percent = crop_config.get("bottom", 0)
            if top_percent > 0 or bottom_percent > 0:
                log_handle.info(
                    f"Cropping enabled: {top_percent}% from top, "
                    f"{bottom_percent}% from bottom")
            else:
                crop_config = None  # No actual cropping needed

        try:
            doc = fitz.open(pdf_file)
            total_pages = len(doc)

            for page_num in page_list:
                # Validate page number (1-based) against total pages
                if not 1 <= page_num <= total_pages:
                    log_handle.warning(
                        f"Page number {page_num} is out of bounds for PDF {pdf_file} "
                        f"which has {total_pages} pages. Skipping."
                    )
                    continue

                # PyMuPDF uses 0-based indexing for pages, so we subtract 1
                page = doc.load_page(page_num - 1)

                pix = page.get_pixmap(dpi=350)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                # Apply cropping if enabled
                if crop_config:
                    width, height = img.size
                    top_crop = int(height * top_percent / 100)
                    bottom_crop = int(height * bottom_percent / 100)

                    # Crop the image (left, top, right, bottom)
                    img = img.crop((0, top_crop, width, height - bottom_crop))
                images.append(img)
                page_numbers_for_images.append(page_num)

            doc.close()
            return images, page_numbers_for_images

        except Exception as pdf_error:
            log_handle.error(
                f"Error during PDF to image conversion with PyMuPDF: {pdf_error}")
            traceback.print_exc()
            return [], []

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

    @staticmethod
    def _process_single_page(args):
        """
        Worker function to process a single image with preprocessing for better OCR.
        This function must be at the top level of the module for pickling.
        """
        # Backward compatible: support both 3-element and 4-element tuples
        if len(args) == 3:
            page_num, image, language_code = args
            psm = 6  # Default PSM (current behavior)
        else:
            page_num, image, language_code, psm = args
        try:
            # 1. --- Image Preprocessing ---
            # Convert the image to RGB for better processing
            if image.mode != 'RGB':
                processed_image = image.convert('RGB')
            else:
                processed_image = image

            # 2. --- Perform OCR ---
            # Use the preprocessed image and your existing configuration.
            config = f'--psm {psm} -l {language_code}'
            text = pytesseract.image_to_string(processed_image, config=config)

            # 3. --- Clean Up Text ---
            # Split text into paragraphs and clean them up
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

            return page_num, paragraphs

        except Exception as page_error:
            # Log the error and return an empty result for this page.
            log_handle.error(f"An error occurred while processing page {page_num}: {page_error}")
            traceback.print_exc()
            return page_num, []
