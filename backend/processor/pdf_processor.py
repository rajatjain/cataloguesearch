import fitz  # PyMuPDF
import pytesseract
import os
import io
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor
from google.cloud import vision
from PIL import Image

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
        self._vision_client = vision.ImageAnnotatorClient()
        self._output_text_folder = config.BASE_TEXT_PATH
        self._images_folder = config.TMP_IMAGES_PATH

    def _convert_images_to_text(
            self, images_folder, text_folder, file_metadata: dict = None):
        """
        Converts images in the specified folder to text files using OCR.
        Args:
            images_folder: Path to the folder containing images.
            text_folder: Path to the folder where text files will be saved.
        """
        file_paths = []
        if not os.path.exists(text_folder):
            os.makedirs(text_folder, exist_ok=True)
            log_handle.info(f"Created text folder: {text_folder}")

        def process_image(f):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')):
                image_path = os.path.join(images_folder, f)
                log_handle.info(f"Processing image: {image_path}")
                txt_file_name = os.path.splitext(f)[0] + ".txt"
                txt_file_path = "%s/%s" % (text_folder, txt_file_name)
                self._detect_text(image_path, txt_file_path, file_metadata)
                os.remove(image_path)
                return txt_file_path
            else:
                log_handle.warning(f"Skipping non-image file: {f}")
                return None

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(process_image, os.listdir(images_folder)))
            file_paths = [path for path in results if path is not None]

        return sorted(file_paths)

    def _detect_text(self, image_file_path: str, txt_file_path: str, file_metadata):
        if file_metadata is not None and file_metadata.get("scanned"):
            # Use google vision API for scanned images
            return self._detect_text_google(image_file_path, txt_file_path)
        else:
            # Use pytesseract for regular images
            return self._detect_text_pytesseract(
                image_file_path, txt_file_path, lang=file_metadata.get("lang", "hi"))

    def _detect_text_google(self, image_file_path: str, txt_file_path: str):
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
            log_handle.error("Unable to convert filename %s. Please check offline." % (image_file_path))

        fh = open(txt_file_path, 'w')
        fh.write(text)
        fh.close()
        log_handle.verbose("Text detection done for file %s" % image_file_path)

    def _detect_text_pytesseract(
            self, image_file_path: str, txt_file_path: str, lang: str = 'hi'):
        """
        Uses pytesseract to extract text from an image file and saves it to a text file.
        Args:
            image_file_path: Path to the image file.
            txt_file_path: Path where the extracted text will be saved.
        """
        # Map language codes to Tesseract language codes
        lang_dict = {
            'hi': 'hin',
            'hindi': 'hin',
            'gu': 'guj',
            'gujarati': 'guj',
        }
        try:
            img = Image.open(image_file_path)
            extracted_text = pytesseract.image_to_string(img, lang=lang_dict.get(lang, 'hin'))
            with open(txt_file_path, 'w', encoding='utf-8') as f:
                f.write(extracted_text)
            log_handle.verbose(f"Text extracted and saved to {txt_file_path}")
        except Exception as e:
            log_handle.error(f"Error extracting text from {image_file_path}: {e}")

    def _convert_pdf_to_images(
            self,
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
                current_title = bookmarks[bookmark_index][1]
                bookmark_index += 1
            page_to_bookmark[page_num] = current_title

        return page_to_bookmark

    def process_pdf(
            self, pdf_path: str, output_dir: str,
            images_dir: str, file_metadata: dict
            ) -> tuple[list[str], dict[int: str]]:
        """
        Processes a PDF file, extracts text page by page, saves them,
        and extracts bookmarks.

        Args:
            pdf_path (str): The full path to the PDF file.
            output_dir (str): The base directory where page-wise text files will be saved.
                              It is assumed that this directory exists.
            images_dir (str): Directory where images will be temporarily stored.
            file_metadata (dict): Metadata associated with the PDF file.
        Returns:
            tuple[list[str], list[dict]]: A tuple containing:
                - A list of paths to the saved text files (one per page).
                - A list of dictionaries, where each dictionary represents a bookmark.
        """
        saved_text_file_paths = []
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        log_handle.verbose(f"pdf_name: {pdf_name} output_dir: {output_dir} images_dir: {images_dir}")
        if not os.path.exists(output_dir):
            log_handle.critical(f"output_dir {output_dir} does not exist. Exiting.")
            return [], {}

        bookmarks = self.fetch_bookmarks(pdf_path)

        # if output_dir exists and has same number of files as the PDF pages, skip processing
        if os.path.exists(output_dir):
            # count the number of text files in the output_dir
            text_files = [f for f in os.listdir(output_dir) if f.endswith('.txt')]
            # sort text files to ensure consistent order
            text_files.sort()
            # count the number of pages in the PDF
            doc = fitz.open(pdf_path)
            num_pages = doc.page_count
            if len(text_files) == num_pages:
                log_handle.info(f"Skipping processing for {pdf_path} as it already has {len(text_files)} text files.")
                return [os.path.join(output_dir, f) for f in text_files], bookmarks

        image_dir = os.path.join(images_dir, pdf_name)
        if not os.path.exists(image_dir):
            log_handle.info(f"Creating image directory: {image_dir}")
            os.makedirs(image_dir, exist_ok=True)

        log_handle.info(f"Converting PDF: {pdf_path}")

        try:
            self._convert_pdf_to_images(
                pdf_file_path=pdf_path,
                images_folder=image_dir)

            saved_text_file_paths = self._convert_images_to_text(
                images_folder=image_dir,
                text_folder=output_dir,
                file_metadata=file_metadata
            )

            return saved_text_file_paths, bookmarks

        except fitz.FileNotFoundError:
            log_handle.error(f"PDF file not found: {pdf_path}")
            return [], {}
        except Exception as e:
            log_handle.exception(f"An error occurred while processing PDF {pdf_path}: {e}")
            return [], {}
