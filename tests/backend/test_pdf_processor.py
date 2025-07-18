import logging

import pytest
import os
import tempfile
from PIL import Image, ImageDraw, ImageFont # For creating dummy images for OCR
import pytesseract # To check if Tesseract is available
from backend.processor.pdf_processor import PDFProcessor
from tests.backend.base import *
from tests.backend.test_config import config

# Setup logging once for all tests
log_handle = logging.getLogger(__name__)

@pytest.mark.skip("Run this test only when you want to test the PDFProcessor directly. "
                  "This requires google vision images to be called, and the process is time consuming.")
def test_process_pdf_direct_text_extraction(initialise, config):
    """
    Tests direct text extraction from a PDF with embeddable text.
    """
    processor = PDFProcessor(config)

    pdf_dir = "%s/data/pdfs" % get_test_base_dir()
    texts_dir = "%s/data/text" % get_test_base_dir()
    images_dir_tmp = tempfile.mkdtemp()
    images_dir = os.path.abspath(images_dir_tmp)
    shutil.rmtree(texts_dir, ignore_errors=True)
    os.makedirs(texts_dir, exist_ok=True)
    files = [ ("bangalore_hindi.pdf", "hi"),
              ("bangalore_gujarati.pdf", "gu"),
               ("document.pdf", "hi+gu")
              ]
    all_bookmarks = []
    for file, lang in files:
        dummy_pdf_path = "%s/%s" % (pdf_dir, file)
        output_text_path = "%s/%s" % (texts_dir, os.path.splitext(file)[0])
        os.makedirs(output_text_path, exist_ok=True)
        text_files, bookmarks = processor.process_pdf(
            dummy_pdf_path, output_text_path, images_dir)
        log_handle.info(f"bookmarks for file: {file} - {bookmarks}")
        all_bookmarks.append(bookmarks)

    # check for bookmarks
    assert len(all_bookmarks) == 3
    assert all_bookmarks[0][1] == "Title"
    assert all_bookmarks[0][2] == "Title / Mid"
    assert all_bookmarks[0][3] == "Conclusion"

    assert all_bookmarks[1][1] is None
    assert all_bookmarks[1][2] is None
    assert all_bookmarks[1][3] is None

    assert all_bookmarks[2][1] == "Some Title"
    assert all_bookmarks[2][2] == "Some Title"

    test_data = {
        "bangalore_hindi": {
            "page_0001.txt": "किले का निर्माण किया, जिसे आज बेंगलुरु शहर की नींव",
            "page_0002.txt": "विकास के साथ चुनौतियां भी आई हैं।",
            "page_0003.txt": "लागत, विशेष रूप से किराए और दैनिक खर्च,",
        },
        "bangalore_gujarati": {
            "page_0001.txt": "ઇતિહાસ ખૂબ જ સમૃદ્ધ અને જૂનો છે.",
            "page_0002.txt": "આધુનિકતા અને પરંપરાનું એક અનન્ય મિશ્રણ છે.",
            "page_0003.txt": "નંદી હિલ્સ (Nandi Hills) એક લોકપ્રિય સપ્તાહાંત સ્થળ છે,",
        },
        "document": {
            "page_0001.txt": "भारत एक विशाल देश है। यहाँ पर अलग अलग जाति",
            "page_0002.txt": "એના પછી ભારત દેશ સ્વતંત્ર હતા.",
        }
    }

    for pdf_name, expected_texts in test_data.items():
        for page_name, expected_text in expected_texts.items():
            text_file_path = os.path.join(texts_dir, pdf_name, page_name)
            assert os.path.exists(text_file_path), f"Text file {text_file_path} does not exist."
            with open(text_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                assert expected_text in content, f"Expected text '{expected_text}' not found in {text_file_path}"


    shutil.rmtree(texts_dir, ignore_errors=True)