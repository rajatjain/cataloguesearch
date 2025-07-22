# backend/utils/language_detector.py
import logging

# You might need to install 'langdetect': pip install langdetect
from langdetect import detect, DetectorFactory, LangDetectException

log_handle = logging.getLogger(__name__)

# Ensure consistent language detection results
DetectorFactory.seed = 0

class LanguageDetector:
    """
    A utility class for detecting the language of a given text.
    """

    @staticmethod
    def detect_language(text: str) -> str:
        """
        Detects the language of the input text.
        Prioritizes Hindi, Gujarati, and English.

        Args:
            text (str): The text to detect the language for.

        Returns:
            str: The detected language ('hindi', 'gujarati', 'english'),
                 or 'english' as a fallback if detection fails or is uncertain.
        """
        if not text:
            log_handle.warning(
                "Empty text provided for language detection. Defaulting to 'english'.")
            return 'english'

        try:
            # Attempt to detect language
            lang_code = detect(text)
            log_handle.debug(f"langdetect detected: {lang_code} for text: '{text[:50]}...'")

            # Map detected language codes to our internal representation
            if lang_code == 'hi':
                return 'hindi'
            elif lang_code == 'gu':
                return 'gujarati'
            elif lang_code == 'en':
                return 'english'
            else:
                log_handle.warning(
                    f"Detected unsupported language '{lang_code}'. Defaulting to 'english'.")
                return 'english'
        except LangDetectException as e:
            log_handle.error(f"Language detection failed for text: '{text[:50]}...'. Error: {e}. Defaulting to 'english'.")
            return 'english'
        except Exception as e:
            log_handle.exception(f"An unexpected error occurred during language detection: {e}. Defaulting to 'english'.")
            return 'english'
