import fitz  # PyMuPDF
import pytesseract
import os
import io
import logging
import subprocess
from google.cloud import vision

from tests.backend.test_config import log_handle

# Setup logging for this module
logger = logging.getLogger(__name__)


def _convert_pdf_to_images(
        pdf_file_path: str,
        images_folder: str):
    page_prefix = images_folder + "/page_%04d.jpg"
    cmd = [ "magick", "-density", "200", "-scene", "1",
            pdf_file_path, page_prefix ]
    log_handle.verbose("Calling cmd: %s ..." % (' '.join(cmd)))
    log_handle.verbose("This may take some time...")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.communicate()
    log_handle.verbose("Converted original PDF file to images.")


def _fetch_bookmarks(pdf_file: str) -> dict[int, str]:
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
            current_title = bookmarks[bookmark_index][1]
            bookmark_index += 1
        page_to_bookmark[page_num] = current_title

    return page_to_bookmark


class PDFProcessor:
    """
    Handles PDF processing, including OCR, text extraction, and bookmark extraction.
    """

    def __init__(self):
        """
        Initializes the PDFProcessor.
        """
        self._vision_client = vision.ImageAnnotatorClient()

    def _convert_images_to_text(
            self, images_folder, text_folder):
        """
        Converts images in the specified folder to text files using OCR.
        Args:
            images_folder: Path to the folder containing images.
            text_folder: Path to the folder where text files will be saved.
        """
        file_paths = []
        if not os.path.exists(text_folder):
            os.makedirs(text_folder, exist_ok=True)
            logger.info(f"Created text folder: {text_folder}")

        for f in os.listdir(images_folder):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')):
                image_path = os.path.join(images_folder, f)
                logger.info(f"Processing image: {image_path}")
                txt_file_name = os.path.splitext(f)[0] + ".txt"
                txt_file_path = "%s/%s" % (text_folder, txt_file_name)
                self._detect_text(image_path, txt_file_path)
                file_paths.append(txt_file_path)
                os.remove(image_path)
            else:
                logger.warning(f"Skipping non-image file: {f}")
        return file_paths


    def _detect_text(self, image_file_path: str, txt_file_path: str):
        file_name = os.path.abspath(image_file_path)
        with io.open(file_name, 'rb') as image_file:
            content = image_file.read()

        image = vision.Image(content=content)
        success = False
        text_detection_response = None
        for i in [0, 10]:
            try:
                text_detection_response = self._vision_client.text_detection(image=image)
                success = True
                break
            except Exception as e:
                log_handle.error("Attempt %d failed for file %s. Retrying..." % ((i + 1), image_file_path))
        if success:
            annotations = text_detection_response.text_annotations
            if len(annotations) > 0:
                text = annotations[0].description
            else:
                text = ''
        else:
            text = ''
            print("Unable to convert filename %s. Please check offline." % (image_file_path))

        fh = open(txt_file_path, 'w')
        fh.write(text)
        fh.close()
        log_handle.verbose("Text detection done for file %s" % image_file_path)


    def process_pdf(
            self, pdf_path: str, output_dir: str,
            images_dir: str,
            ) -> tuple[list[str], dict[int: str]]:
        """
        Processes a PDF file, extracts text page by page, saves them,
        and extracts bookmarks.

        Args:
            pdf_path (str): The full path to the PDF file.
            output_dir (str): The base directory where page-wise text files will be saved.
                              It is assumed that this directory exists.
            images_dir (str): Directory where images will be temporarily stored.
        Returns:
            tuple[list[str], list[dict]]: A tuple containing:
                - A list of paths to the saved text files (one per page).
                - A list of dictionaries, where each dictionary represents a bookmark.
        """
        saved_text_file_paths = []
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        if not os.path.exists(output_dir):
            log_handle.critical(f"output_dir {output_dir} does not exist. Exiting.")
            return [], {}

        image_dir = os.path.join(images_dir, pdf_name)
        if not os.path.exists(image_dir):
            logger.info(f"Creating image directory: {image_dir}")
            os.makedirs(image_dir, exist_ok=True)

        logger.info(f"Processing PDF: {pdf_path}")

        try:
            _convert_pdf_to_images(
                pdf_file_path=pdf_path,
                images_folder=image_dir)

            saved_text_file_paths = self._convert_images_to_text(
                images_folder=image_dir,
                text_folder=output_dir,
            )

            # Extract bookmarks
            bookmarks = _fetch_bookmarks(pdf_path)
            logger.info(f"Extracted {len(bookmarks)} bookmarks from {pdf_path}.")

            """# Extract text page by page
            doc = fitz.open(pdf_path)
            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                text_content = self._extract_text_from_page(page, use_ocr, ocr_lang)

                output_file_name = f"page_{page_num + 1:04d}.txt"
                output_file_path = os.path.join(output_dir, output_file_name)

                with open(output_file_path, 'w', encoding='utf-8') as f:
                    f.write(text_content)
                saved_text_file_paths.append(output_file_path)
                logger.debug(f"Saved page {page_num + 1} text to {output_file_path}")

            logger.info(f"Successfully processed {doc.page_count} pages from {pdf_path}.")
            doc.close()
            """
            return saved_text_file_paths, bookmarks

        except fitz.FileNotFoundError:
            logger.error(f"PDF file not found: {pdf_path}")
            return [], {}
        except Exception as e:
            logger.exception(f"An error occurred while processing PDF {pdf_path}: {e}")
            return [], {}