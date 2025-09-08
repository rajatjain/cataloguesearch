import pytesseract
from PIL import Image
import os
import io
import logging
from abc import ABC, abstractmethod
from google.cloud import vision

log_handle = logging.getLogger(__name__)


def _validate_and_process_image(image_path):
    if not os.path.exists(image_path):
        log_handle.error(f"Image file not found at '{image_path}'")
        return None, []

    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            clean_img = Image.open(buffer)
            return clean_img, None
    except Exception as e:
        log_handle.error(f"An error occurred during image processing: {e}")
        return None, []


def _process_text_to_paragraphs(full_text):
    if not full_text.strip():
        log_handle.warning("No text was detected in the image.")
        return []

    paragraphs = [p.strip() for p in full_text.split('\n\n') if p.strip()]
    log_handle.info(f"Extracted {len(paragraphs)} paragraphs from image")
    return paragraphs


class OCR(ABC):
    @abstractmethod
    def extract_text(self, image_path, lang=''):
        pass


class TesseractOCR(OCR):
    def extract_text(self, image_path, lang='hin'):
        clean_img, error_result = _validate_and_process_image(image_path)
        if clean_img is None:
            return error_result

        try:
            full_text = pytesseract.image_to_string(clean_img, lang=lang, config='--psm 6')
            return _process_text_to_paragraphs(full_text)
        except Exception as e:
            log_handle.error(f"An error occurred during text extraction: {e}")
            return []


class GoogleOCR(OCR):
    """OCR implementation using Google Cloud Vision API."""
    def __init__(self):
        self.client = vision.ImageAnnotatorClient()

    def extract_text(self, image_path, lang='hin'):
        """
        Extracts paragraphs from an image using Google Vision's document text detection.
        This method leverages the API's ability to understand document structure.
        """
        if not os.path.exists(image_path):
            log_handle.error(f"Image file not found at '{image_path}'")
            return []

        try:
            with io.open(image_path, 'rb') as image_file:
                content = image_file.read()

            image = vision.Image(content=content)

            # Provide language hints for better OCR accuracy, as seen in the PDF.
            image_context = vision.ImageContext(language_hints=[lang])

            # Use document_text_detection for structured text recognition.
            response = self.client.document_text_detection(
                image=image,
                image_context=image_context
            )

            if response.error.message:
                raise Exception(
                    '{}\nFor more info on error messages, check: '
                    'https://cloud.google.com/apis/design/errors'.format(
                        response.error.message))

            paragraphs_text = []
            # The response provides a hierarchical structure: pages -> blocks -> paragraphs.
            # We iterate through this structure to accurately identify paragraphs.
            if response.full_text_annotation:
                for page in response.full_text_annotation.pages:
                    for block in page.blocks:
                        for paragraph in block.paragraphs:
                            # Reconstruct the paragraph by joining the detected words.
                            para_words = []
                            for word in paragraph.words:
                                word_text = ''.join([
                                    symbol.text for symbol in word.symbols
                                ])
                                para_words.append(word_text)
                            paragraphs_text.append(' '.join(para_words))

            if not paragraphs_text:
                log_handle.warning("No paragraphs were detected in the image.")
                return []

            log_handle.info(f"Extracted {len(paragraphs_text)} paragraphs from image using Google OCR.")
            return paragraphs_text

        except Exception as e:
            log_handle.error(f"An error occurred during Google OCR text extraction: {e}")
            return []