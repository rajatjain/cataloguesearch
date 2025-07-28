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
    lang_map= {
        'hi': 'hi',      # Hindi
        'ne': 'hi',      # Nepali (similar script, treat as Hindi)
        'mr': 'hi',      # Marathi (similar script, treat as Hindi)
        'sa': 'hi',      # Sanskrit (similar script, treat as Hindi)
        'gu': 'gu',   # Gujarati
        'en': 'en',    # English
    }

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
            return 'en'

        try:
            # Attempt to detect language
            lang_code = detect(text)
            log_handle.debug(f"langdetect detected: {lang_code} for text: '{text[:50]}...'")
            if lang_code in LanguageDetector.lang_map:
                log_handle.verbose(
                    "Changing detected language code '%s' to '%s'." % (
                        lang_code, LanguageDetector.lang_map[lang_code]
                    )
                )
                return LanguageDetector.lang_map[lang_code]
            else:
                log_handle.debug(f"Detected language code '{lang_code}' is not in the map. Defaulting to 'hi'.")
                return 'hi'
        except LangDetectException as e:
            log_handle.error(f"Language detection failed for text: '{text[:50]}...'. Error: {e}. Defaulting to 'english'.")
            return 'hi'
        except Exception as e:
            log_handle.exception(f"An unexpected error occurred during language detection: {e}. Defaulting to 'english'.")
            return 'hi'
