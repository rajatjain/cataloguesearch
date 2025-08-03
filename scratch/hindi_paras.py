import logging
import os

from backend.crawler.pdf_processor import PDFProcessor
from backend.config import Config
from scratch.prod_setup import prod_setup

log_handle = logging.getLogger(__name__)

_pdf_processor = None

def parse_pdf():
    global _pdf_processor
    if _pdf_processor is None:
        _pdf_processor = PDFProcessor(Config())

    # TODO(rajatjain): Errors in pages 29, 52-53
    meta = {
        "language": "hi",
        "start_page": 17,
        "end_page": 60,
        "header_regex": [
            "^.{0,5}गाथा.{0,30}$",
            "^.{0,5}कलश.{0,30}$",
            "^प्रवचन\s+नं\.?.*$",
            "^प्रवच्चन\s+नं\.?.*$",
            "^[०-९\s]*$",
        ],
        "header_prefix": [
            "^[०-९]+\\s+कारण\\s+.?\\s+कार्य\\s+.?\\s+नियम\\s+\\(?भाग\\s+[०-९]+\\s+\\)?",
            "श्लोक.?\\s+.?[०-९]+\\s+"
        ]
    }
    pdf_file = "/Users/r0j08wt/cataloguesearch/Karan_Karya_Niyam_Part_1_H.pdf"
    output_dir = "/Users/r0j08wt/cataloguesearch/Karan_Karya_Niyam_Part_1_H"
    os.makedirs(output_dir, exist_ok=True)
    _pdf_processor.process_pdf(pdf_file, output_dir, meta)

def main():
    prod_setup(console_only=True)
    parse_pdf()


if __name__ == '__main__':
    main()