import pytest

from backend.search.language_detector import LanguageDetector

def test_language_detector_hindi():
    text = "यह एक हिंदी वाक्य है।"
    detected_language = LanguageDetector.detect_language(text)
    assert detected_language == 'hindi'

def test_language_detector_gujarati():
    text = "આ એક ગુજરાતી વાક્ય છે."
    detected_language = LanguageDetector.detect_language(text)
    assert detected_language == 'gujarati'

def test_language_detector_mixed():
    text = "This is an English sentence mixed with हिंदी."
    detected_language = LanguageDetector.detect_language(text)
    assert detected_language == 'english'

def test_language_detector_hindi_gujarati():
    text = "यह एक हिंदी वाक्य है। આ એક ગુજરાતી વાક્ય છે."
    detected_language = LanguageDetector.detect_language(text)
    assert detected_language in ["hindi", "gujarati"]

