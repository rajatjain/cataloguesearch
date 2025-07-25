import logging
import os

from backend.config import Config
from backend.index.text_splitter.default import DefaultChunksSplitter
from backend.utils import json_dumps
from scratch.prod_setup import prod_setup

log_handle = logging.getLogger(__name__)

def default_chunks():
    prod_setup()

    config = Config()

    base_path = Config._get_project_root()
    # get all the text directors inside `dir`
    text_dir = "%s/tests/data/text/bangalore_hindi" % base_path

    # get all .txt files in the text_dir
    text_files = [os.path.join(text_dir, f) for f in os.listdir(text_dir) if f.endswith('.txt')]

    text_splitter = DefaultChunksSplitter(config)
    chunks = text_splitter.get_chunks("test_doc", text_files)
    log_handle.info(f"Generated {json_dumps(chunks, truncate_fields=['vector_embedding'])}")

if __name__ == "__main__":
    default_chunks()