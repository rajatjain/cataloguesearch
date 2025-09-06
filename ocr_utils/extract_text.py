import pytesseract
from PIL import Image
import os
import io
import logging

log_handle = logging.getLogger(__name__)

def extract_and_split_paragraphs(image_path, lang='hin'):
    """
    Extracts text from an image using Tesseract OCR and splits it into paragraphs.

    Args:
        image_path (str): The path to the image file.
        lang (str): The language code for Tesseract to use (e.g., 'hin', 'guj', 'eng').

    Returns:
        list: A list of strings, where each string is a paragraph.
              Returns an empty list if the image cannot be opened or no text is found.
    """
    if not os.path.exists(image_path):
        log_handle.error(f"Image file not found at '{image_path}'")
        return []

    try:
        # Open the image file
        with Image.open(image_path) as img:
            # Convert to RGB to ensure compatibility
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Create a clean copy by saving to memory buffer and reloading
            # This fixes issues with corrupted JPEG data that Tesseract can't handle
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            clean_img = Image.open(buffer)
            
            # Use Tesseract to do OCR on the clean image
            # The 'lang' parameter specifies the language of the text.
            full_text = pytesseract.image_to_string(clean_img, lang=lang, config='--psm 6')

            if not full_text.strip():
                log_handle.warning("No text was detected in the image.")
                return []

            # Paragraphs are often separated by one or more blank lines.
            # We split the text by double newlines and filter out any empty strings
            # that might result from the split.
            paragraphs = [p.strip() for p in full_text.split('\n\n') if p.strip()]

            log_handle.info(f"Extracted {len(paragraphs)} paragraphs from image")
            return paragraphs

    except Exception as e:
        log_handle.error(f"An error occurred during text extraction: {e}")
        return []