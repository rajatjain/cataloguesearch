import logging
import os

from backend.config import Config
from backend.index.text_splitter.dynamic_chunks import DynamicChunksSplitter
from backend.index.text_splitter.paragraph_splitter import ParagraphChunksSplitter
from backend.utils import json_dumps
from scratch.prod_setup import prod_setup

log_handle = logging.getLogger(__name__)

def get_file_text(base_path, page_num):
    page = "page_%04d.txt" % page_num
    page_path = os.path.join(base_path, page)
    return open(page_path, "r", encoding="utf-8").read()

def dynamic_chunks():
    prod_setup()

    splitter = DynamicChunksSplitter(Config())
    base_path = "/Users/r0j08wt/cataloguesearch/text/Pravachans/hindi/Dravyanuyog/Samaysaar/19th_time/01 G001-012/"

    # get all the text directors inside `dir`
    dir = "/Users/r0j08wt/tmp/text_folder"
    text_files = [os.path.join(dir, f) for f in os.listdir(dir) if f.endswith('.txt')]

    chunks = splitter.get_chunks(
        "document_id", text_files)
    log_handle.info(f"Total chunks generated: {len(chunks)}")
    log_handle.info(f"Generated {json_dumps(chunks, truncate_fields=['vector_embedding'])}")

def embedding_text():
    prod_setup()
    splitter = DynamicChunksSplitter(Config())

    text = "\"तब पुद्गल कर्म के प्रदेशों में स्थित होने से... युगपद पर को एकत्वपूर्वक\nजानता, आहाहाहा ! यहाँ जानता तो लिया... परंतु मोह को राग द्वेष को एकत्वरूप\nसे जानता और परिणमता वहाँ (ज्ञानी) भिन्न रूप जानता और परिणमता। आहाहा ।"
    sentences = text.split('\n')
    log_handle.info(sentences)
    # log_handle.info(splitter._create_embedding_text(sentences))


def para_chunks():
    prod_setup()
    splitter = ParagraphChunksSplitter(Config())

    path = "/Users/r0j08wt/tmp/text_folder"

    text_files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith('.txt')]
    text_files = sorted(text_files)
    chunks = splitter.get_chunks("test_doc", text_files)
    log_handle.info(f"{json_dumps(chunks)}")

para_chunks()