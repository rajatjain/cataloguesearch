import logging
import os

from backend.crawler.markdown_parser import parse_markdown_file
from scratch.prod_setup import prod_setup

log_handle = logging.getLogger(__name__)

prod_setup(console_only=True)


base_pdf_dir = "%s/github/rajatjain/cataloguesearch-configs" % os.getenv("HOME")
fname = "%s/Granth/hindi/Dravyanuyog/Ishtopadesh/Ishtopadesh_Draft1.md" % base_pdf_dir

granth = parse_markdown_file(fname, base_pdf_dir)

for verse in granth._verses:
    log_handle.info(f"Verse: {verse}")


