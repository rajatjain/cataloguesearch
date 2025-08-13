import logging
import os
import shutil
from os.path import basename

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
        "start_page": 14,
        "end_page": 651,
        "header_prefix": [
            "^पंचास्तिकाय\\s*संग्रह\\s*प्रवचन\\,? \\[?\\(?भाग\\s?-\\s?[०-९]+\\s?\\]?\\)?",
            "^.{0,5}\\s*गाथा-?[०-९]+\\s+[०-९]+",
            "^प्रवचन.*-[०-९][०-९][०-९][०-९]",
            "^[०-९]+(?!\\. )",
        ],
        "header_regex": [
            "^.{0,5}$",
            "^.{0,5}पंचास्तिकाय\\s?संग्रह\\s*प्रवचन,?\\s*भाग-?[०-९]+",
            "^.{0,5}गाथा.{0,30}$",
            "^.{0,5}कलश.{0,30}$",
            "^.{0,5}श्लोक.{0,30}$",
            "^.{0,30}प्रवचन\\s+नं\\.?.*$",
            "^[०-९\\s]*$",
            "^.*पर\\s+प्रवचन.*$",
            "^.*श्लोक.*प्रवचन.*$",
            "^\\*\\s+",
            "^[०-९]+",
            "^.{0,5}गाथा.{0,30}$",
            "^.{0,5}कलश.{0,30}$",
            "^.{0,5}श्लोक.{0,30}$",
            "^प्रवचन\\s+नं\\.?.*$",
            "^[०-९\\s]*$",
            "^[०-९]\\.\\s+",
            "^वी\\.?\\s+सं\\.?"
        ]
    }
    home = os.getenv("HOME")
    pdf_file = "%s/cataloguesearch/Panchastikaya/PanchastikaySangrah_Pravachan_Part-03_H.pdf" % home
    basename = os.path.basename(pdf_file)
    fname = os.path.splitext(basename)[0]
    output_dir = "%s/cataloguesearch/%s" % (home, fname)
    shutil.rmtree(output_dir, ignore_errors=True)
    os.makedirs(output_dir, exist_ok=True)
    _pdf_processor.process_pdf(pdf_file, output_dir, meta)

def main():
    prod_setup(console_only=True)
    parse_pdf()


if __name__ == '__main__':
    main()
