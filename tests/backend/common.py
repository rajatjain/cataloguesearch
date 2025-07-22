import logging
import os
import shutil
import tempfile
import uuid

from backend.config import Config
from backend.utils import json_dump, json_dumps

log_handle = logging.getLogger(__name__)

def write_config_file(file_name, config_data):
    """
    Write the given config data to a JSON file.
    """
    with open(file_name, 'w') as f:
        json_dump(config_data, f)
    log_handle.info(f"Config file written: {file_name}")

def get_doc_id(base_dir, file_path):
    relative_path = os.path.relpath(file_path, base_dir)
    doc_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, relative_path))
    return doc_id

def setup():
    base_dir = tempfile.mkdtemp(prefix="test_")
    pdf_dir = "%s/data/pdfs" % base_dir
    Config().settings()["crawler"]["base_pdf_path"] = pdf_dir
    Config().settings()["crawler"]["base_text_path"] = "%s/data/texts" % base_dir
    Config().settings()["crawler"]["tmp_images_path"] = "%s/data/tmp_images" % base_dir
    Config().settings()["crawler"]["sqlite_db_path"] = "%s/crawl_state.db" % base_dir

    os.makedirs("%s/a/b/c" % pdf_dir, exist_ok=True)
    os.makedirs("%s/a/b/d" % pdf_dir, exist_ok=True)
    os.makedirs("%s/x/y/z" % pdf_dir, exist_ok=True)

    TEST_BASE_DIR = os.getenv("TEST_BASE_DIR")

    # copy files
    data_pdf_path = os.path.join(TEST_BASE_DIR, "data", "pdfs")
    bangalore_hindi = os.path.join(data_pdf_path, "bangalore_hindi.pdf")
    bangalore_gujarati = os.path.join(data_pdf_path, "bangalore_gujarati.pdf")
    bangalore_english = os.path.join(data_pdf_path, "bangalore_english.pdf")
    multi_language_document = os.path.join(data_pdf_path, "multi_language_document.pdf")

    abcbh = "%s/a/b/c/bangalore_hindi.pdf" % pdf_dir
    abcbg = "%s/a/b/c/bangalore_gujarati.pdf" % pdf_dir
    abbeng = "%s/a/b/bangalore_english.pdf" % pdf_dir
    xyzmld = "%s/x/y/z/multi_language_document.pdf" % pdf_dir
    abdmld = "%s/a/b/d/multi_language_document.pdf" % pdf_dir
    abh = "%s/a/bangalore_hindi.pdf" % pdf_dir
    xbg = "%s/x/bangalore_gujarati.pdf" % pdf_dir

    doc_ids = {
        "abcbh": [abcbh, get_doc_id(pdf_dir, abcbh)],
        "abcbg": [abcbg, get_doc_id(pdf_dir, abcbg)],
        "abbeng": [abbeng, get_doc_id(pdf_dir, abbeng)],
        "xyzmld": [xyzmld, get_doc_id(pdf_dir, xyzmld)],
        "abdmld": [abdmld, get_doc_id(pdf_dir, abdmld)],
        "abh": [abh, get_doc_id(pdf_dir, abh)],
        "xbg": [xbg, get_doc_id(pdf_dir, xbg)]
    }

    shutil.copy(bangalore_hindi, abcbh)
    shutil.copy(bangalore_gujarati, abcbg)
    shutil.copy(bangalore_english, abbeng)
    shutil.copy(multi_language_document, xyzmld)
    shutil.copy(multi_language_document, abdmld)
    shutil.copy(bangalore_hindi, abh)
    shutil.copy(bangalore_gujarati, xbg)

    # create config files
    a = { "category": "a", "type": "t" }
    b = { "category": "b", "type": "t1" }
    # dir c is empty
    bhc = { "type": "t2", "new": "c3" }

    # dir d is empty

    x = { "category": "x", "type": "tx" }
    z = { "category": "z", "type": "tz" }
    bgx = { "type": "t3", "new": "c4" }

    write_config_file("%s/a/config.json" % pdf_dir, a)
    write_config_file("%s/a/b/config.json" % pdf_dir, b)
    write_config_file("%s/a/b/c/bangalore_hindi_config.json" % pdf_dir, bhc)

    write_config_file("%s/x/config.json" % pdf_dir, x)
    write_config_file("%s/x/y/z/config.json" % pdf_dir, z)
    write_config_file("%s/x/bangalore_gujarati_config.json" % pdf_dir, bgx)

    return doc_ids
