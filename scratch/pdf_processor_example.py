import logging
import shutil
import os
from utils.logger import VERBOSE_LEVEL_NUM, setup_logging
from backend.processor.pdf_processor import PDFProcessor

setup_logging(console_level=True, console_only=True)

log_handle = logging.getLogger(__name__)

if __name__ == "__main__":

    processor = PDFProcessor() # Pass tesseract_cmd_path if needed

    base_dir = "/Users/r0j08wt/github/rajatjain/cataloguesearch"
    pdf_dir = "%s/tests/data/pdfs" % base_dir
    texts_dir = "%s/tests/data/text" % base_dir
    shutil.rmtree(texts_dir, ignore_errors=True)
    os.makedirs(texts_dir, exist_ok=True)
    files = [ "bangalore_hindi.pdf", "bangalore_gujarati.pdf", "document.pdf"]
    for file in files:
        dummy_pdf_path = "%s/%s" % (pdf_dir, file)
        output_text_path = "%s/%s" % (texts_dir, os.path.splitext(file)[0])
        os.makedirs(output_text_path, exist_ok=True)
        text_files, bookmarks = processor.process_pdf(
            dummy_pdf_path, output_text_path, use_ocr=True, ocr_lang='eng+hin+guj')
        log_handle.info(f"bookmarks for file: {file} - {bookmarks}")
