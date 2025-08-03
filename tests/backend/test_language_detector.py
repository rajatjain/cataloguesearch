from backend.common.language_detector import LanguageDetector
from backend.common.opensearch import get_opensearch_client
from backend.crawler.index_generator import IndexGenerator
from tests.backend.base import *
import logging

log_handle = logging.getLogger(__name__)

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

def test_language_detection_test_data_files():
    bangalore_hindi_path = Config().BASE_TEXT_PATH + "/bangalore_hindi"
    bangalore_gujarati_path = Config().BASE_TEXT_PATH + "/bangalore_gujarati"

    bangalore_hindi_files = []
    for root, dirs, files in os.walk(bangalore_hindi_path):
        for file in files:
            if file.endswith(".txt"):
                bangalore_hindi_files.append(os.path.join(root, file))

    bangalore_gujarati_files = []
    for root, dirs, files in os.walk(bangalore_gujarati_path):
        for file in files:
            if file.endswith(".txt"):
                bangalore_gujarati_files.append(os.path.join(root, file))

    assert len(bangalore_hindi_files) > 0
    assert len(bangalore_gujarati_files) > 0

    indexing_module = IndexGenerator(Config(), get_opensearch_client(Config()))
    mp = {"hi": bangalore_hindi_files, "gu": bangalore_gujarati_files}
    for lang in mp.keys():
        files = mp[lang]
        for file in files:
            chunks = indexing_module._text_splitter.get_chunks(
                "doc_%s" % lang, files)
            assert len(chunks) > 0
            for chunk in chunks:
                chunk_test = chunk["text_content"]
                language = LanguageDetector.detect_language(chunk_test)
                log_handle.info(f"detected language: {language} for chunk: {chunk_test[:50]}...")
                assert language == lang, f"Detected language {language} for chunk: {chunk_test[:50]}..."
