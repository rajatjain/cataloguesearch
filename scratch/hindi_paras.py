import logging
import os
import shutil

from backend.crawler.pdf_processor import PDFProcessor
from backend.config import Config
from scratch.prod_setup import prod_setup

log_handle = logging.getLogger(__name__)

_pdf_processor = None

"""
Current issues:
Pravachan Sudha Part 1 - Page 31

"""

def parse_pdf():
    global _pdf_processor
    if _pdf_processor is None:
        _pdf_processor = PDFProcessor(Config())

    meta = {
        "language": "hi",
        "start_page": 40,
        "end_page": 50,
        "header_regex": [
            "^.{0,5}गाथा.{0,30}$",
            "^.{0,5}कलश.{0,30}$",
            "^प्रवचन\s+नं\.?.*$",
            "^प्रवच्चन\s+नं\.?.*$",
            "^[०-९\s]*$",
            "^प्रवचन-[०-९]+,?\s*(?:(?:श्लोक|गाथा)-[०-९]+(?:(?:\s+से)?\s+[०-९]+)*,?\s*)?.*?दिनांक\s+[०-९]+(?:-[०-९]+){2}\s*",
            "^प्रवचन-[०-९]+",

            # footer regex
            "^\\*\\s+",
            "^[०-९]\\.\\s+",
        ],
        "header_prefix": [
            "^.{0,5}कारण\\s*.?\\s*कार्य\\s*.?\\s*नियम(?:\\s+\\(?भाग\\s*-?\\s*[०-९]+\\s*\\)?)?(?:\\s+[०-९]+)*\\s*",
            "^.{0,5}\\s*श्लोक-\\s*[०-९]+(?:(?:\\s+से)?\\s+[०-९]+)*\\s*",
            "^.{0,5}\\s*गाथा-\\s*[०-९]+(?:(?:\\s+से)?\\s+[०-९]+)*\\s*",
        ]
    }
    pdf_file = "/Users/r0j08wt/cataloguesearch/Karan_Karya_Niyam_Part_2_H.pdf"
    output_dir = "/Users/r0j08wt/cataloguesearch/Karan_Karya_Niyam_Part_2_H"
    shutil.rmtree(output_dir, ignore_errors=True)
    os.makedirs(output_dir, exist_ok=True)
    _pdf_processor.process_pdf(pdf_file, output_dir, meta)

def main():
    prod_setup(console_only=True)
    parse_pdf()


if __name__ == '__main__':
    main()