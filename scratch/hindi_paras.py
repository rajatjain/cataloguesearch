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
    meta = {
        "language": "hi",
        "start_page": 52,
        "end_page": 60,
        "header_regex": [
            "^.*समयसार\s+सिद्धि,?.*भाग.*",
            "^.{0,5}गाथा.{0,30}$",
            "^.{0,5}कलश.{0,30}$",
            "^प्रवचन\s+नं\.?.*$",
            "^प्रवच्चन\s+नं\.?.*$",
            "^[०-९\s]*$",
            "^.{0,5}प्रवचन\s+सुधा.*भाग.*$",
            # "^.{0,5}प्रवच्चन\s+सुधा.*भाग.*$"
        ],
        "header_prefix": [

        ]
    }
    pdf_file = "/Users/r0j08wt/cataloguesearch/Pravachan_Sudha_Part-5_H.pdf"
    output_dir = "/Users/r0j08wt/cataloguesearch/Pravachan_Sudha_Part-5_H"
    os.makedirs(output_dir, exist_ok=True)
    _pdf_processor.process_pdf(pdf_file, output_dir, meta)

def main():
    prod_setup(console_only=True)
    parse_pdf()


if __name__ == '__main__':
    main()