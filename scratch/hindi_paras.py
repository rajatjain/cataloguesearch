import datetime
import logging
import os
import shutil
import tempfile

import fitz

from backend.crawler.discovery import SingleFileProcessor
from backend.crawler.index_generator import IndexGenerator
from backend.crawler.index_state import IndexState
from backend.crawler.pdf_processor import PDFProcessor
from backend.config import Config
from scratch.prod_setup import prod_setup
import json

log_handle = logging.getLogger(__name__)

_pdf_processor = None

class MySingleFileProcessor(SingleFileProcessor):
    def __init(self, config: Config, file_path: str,
               indexing_mod: IndexGenerator,
               index_state: IndexState,
               pdf_processor: PDFProcessor,
               scan_time: str):
        super().__init__(
            config, file_path, indexing_mod, index_state, pdf_processor, scan_time)

def parse_single_pdf(filename):
    index_state_path = tempfile.mktemp()
    index_state = IndexState(index_state_path)
    config = Config()
    pdf_processor = PDFProcessor(config)
    scan_time = datetime.datetime.now().isoformat()
    file_proc = MySingleFileProcessor(
        config, filename, None, index_state, pdf_processor, scan_time
    )
    file_proc.process()

def parse_pdf():
    config = Config()

    home = os.getenv("HOME")
    dir = "%s/github/rajatjain/cataloguesearch-configs/Pravachans/hindi/Dravyanuyog/Panchastikaya/1970_Series" % home

    # scan all the pdf files in this directories
    for fname in os.listdir(dir):
        if not fname.endswith(".pdf"):
            continue
        full_path = os.path.join(dir, fname)
        parse_single_pdf(full_path)


def main():
    prod_setup(logs_dir="%s/tmp/cataloguesearch_files/logs" % os.getenv("HOME"),
               console_only=False)
    parse_pdf()


if __name__ == '__main__':
    main()
