from backend.common.language_detector import LanguageDetector

def test_language_detector_hindi():
    text = "यह एक हिंदी वाक्य है।"
    detected_language = LanguageDetector.detect_language(text)
    assert detected_language == 'hi'

def test_language_detector_gujarati():
    text = "આ એક ગુજરાતી વાક્ય છે."
    detected_language = LanguageDetector.detect_language(text)
    assert detected_language == 'gu'

def test_language_detector_mixed():
    text = "This is an English sentence mixed with हिंदी."
    detected_language = LanguageDetector.detect_language(text)
    assert detected_language == 'en'

def test_language_detector_hindi_gujarati():
    text = "यह एक हिंदी वाक्य है। આ એક ગુજરાતી વાક્ય છે."
    detected_language = LanguageDetector.detect_language(text)
    assert detected_language in ["hi", "gu"]

